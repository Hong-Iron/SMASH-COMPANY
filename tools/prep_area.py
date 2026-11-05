# Turns raw OSM + terrarium tiles into local-metre data for the Blender build, and paints the ground texture.
# usage: ~/.venvs/vault-plots/bin/python tools/prep_area.py <area_id>     (numpy, Pillow)
# Coordinates: x east, y north, metres from the area centre; z up (Blender convention).
# Output: raw/<id>/prep.json (buildings, trees, terrain grid), raw/<id>/ground.png (placeholder until the aerial mosaic)
import json, math, pathlib, re, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parent.parent
AID = sys.argv[1]
AREA = json.loads((ROOT / "areas.json").read_text(encoding="utf-8"))[AID]
RAW = ROOT / "raw" / AID
LAT0, LON0, SIZE = AREA["lat"], AREA["lon"], AREA["size"]
HALF = SIZE / 2
phi = math.radians(LAT0)
MLAT = 111132.92 - 559.82 * math.cos(2 * phi) + 1.175 * math.cos(4 * phi)
MLON = 111412.84 * math.cos(phi) - 93.5 * math.cos(3 * phi)
STOREY = 3.5
DEM_Z = 15
GRID = 8.0      # terrain grid spacing in metres
TEX = 4096      # ground texture size

# building types and names that are never smashable (homes, schools, care, worship, public safety, government)
OFF_TYPES = {"apartments", "residential", "house", "detached", "semidetached_house", "terrace", "dormitory",
             "school", "kindergarten", "university", "college", "hospital", "clinic", "church", "temple",
             "chapel", "mosque", "shrine", "government", "public", "civic", "fire_station", "police",
             "military", "embassy", "train_station", "transportation"}
OFF_NAME = re.compile(r"아파트|빌라|주택|오피스텔|초등학교|중학교|고등학교|학교|유치원|어린이집|교회|성당|사찰|절$|병원|의원|"
                      r"보건|주민센터|행정복지센터|구청|시청|소방|경찰|파출소|지구대|군부대|대사관|도서관|\d{3,4}동$|^\d{3,4}$")


def ll2xy(lat, lon):
    return (lon - LON0) * MLON, (lat - LAT0) * MLAT


def ring_xy(geom):
    return [ll2xy(p["lat"], p["lon"]) for p in geom]


def area_of(r):
    a = 0.0
    for (x0, y0), (x1, y1) in zip(r, r[1:] + r[:1]):
        a += x0 * y1 - x1 * y0
    return a / 2


def centroid(r):
    xs, ys = zip(*r)
    return sum(xs) / len(xs), sum(ys) / len(ys)


def inside(pt, r):
    x, y = pt; c = False
    for (x0, y0), (x1, y1) in zip(r, r[1:] + r[:1]):
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0 + 1e-12) + x0: c = not c
    return c


def num(v):
    m = re.match(r"\s*([\d.]+)", str(v or ""))
    return float(m.group(1)) if m else None


# ---------- terrain from terrarium tiles ----------
def load_dem():
    tiles = {}
    for f in (RAW / "dem").glob(f"{DEM_Z}_*.png"):
        _, x, y = f.stem.split("_")
        a = np.asarray(Image.open(f).convert("RGB"), dtype=np.float64)
        tiles[(int(x), int(y))] = a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768
    n = 2 ** DEM_Z

    def h(lat, lon):
        fx = (lon + 180) / 360 * n
        fy = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
        tx, ty = int(fx), int(fy)
        px, py = (fx - tx) * 256, (fy - ty) * 256
        t = tiles.get((tx, ty))
        if t is None: return None
        i, j = min(int(py), 255), min(int(px), 255)
        return float(t[i, j])
    return h


demh = load_dem()
nx = int(SIZE / GRID) + 1
xs = np.linspace(-HALF, HALF, nx)
zgrid = np.zeros((nx, nx))
for j, y in enumerate(xs):
    for i, x in enumerate(xs):
        lat, lon = LAT0 + y / MLAT, LON0 + x / MLON
        zgrid[j, i] = demh(lat, lon) or 0.0
# smooth 1 cell (terrarium at z15 is ~4 m/px but noisy around buildings) and make heights relative to the lowest point
k = np.ones((3, 3)) / 9
pad = np.pad(zgrid, 1, mode="edge")
zgrid = sum(pad[a:a + nx, b:b + nx] * k[a, b] for a in range(3) for b in range(3))
ZBASE = float(zgrid.min())
zgrid -= ZBASE


def ground_z(x, y):
    fx = (x + HALF) / GRID; fy = (y + HALF) / GRID
    i = min(max(int(fx), 0), nx - 2); j = min(max(int(fy), 0), nx - 2)
    tx, ty = fx - i, fy - j
    z00, z10, z01, z11 = zgrid[j, i], zgrid[j, i + 1], zgrid[j + 1, i], zgrid[j + 1, i + 1]
    return float((z00 * (1 - tx) + z10 * tx) * (1 - ty) + (z01 * (1 - tx) + z11 * tx) * ty)


# ---------- buildings ----------
osm = json.loads((RAW / "osm.json").read_text(encoding="utf-8"))
items = []
for e in osm["elements"]:
    t = e.get("tags", {})
    if "building" not in t and "building:part" not in t: continue
    if e["type"] == "way" and "geometry" in e:
        ring = ring_xy(e["geometry"])
    elif e["type"] == "relation":
        outers = [m for m in e.get("members", []) if m.get("role") == "outer" and "geometry" in m]
        if not outers: continue
        ring = max((ring_xy(m["geometry"]) for m in outers), key=lambda r: abs(area_of(r)))
    else:
        continue
    if len(ring) > 2 and ring[0] == ring[-1]: ring = ring[:-1]
    if len(ring) < 3: continue
    a = area_of(ring)
    if abs(a) < 12: continue
    if a < 0: ring = ring[::-1]                      # counter-clockwise
    cx, cy = centroid(ring)
    if abs(cx) > HALF or abs(cy) > HALF: continue   # keep buildings whose centre is in the box
    items.append({"osm": f"{e['type'][0]}{e['id']}", "ring": ring, "tags": t, "part": "building:part" in t,
                  "area": abs(a), "c": (cx, cy)})

parts = [b for b in items if b["part"]]
outlines = [b for b in items if not b["part"]]
for b in outlines:
    # Simple 3D Buildings: an outline that contains parts is drawn by its parts instead
    b["skip"] = any(inside(p["c"], b["ring"]) for p in parts if abs(p["c"][0] - b["c"][0]) < 200 and abs(p["c"][1] - b["c"][1]) < 200)
    if b["skip"]:
        for p in parts:
            if inside(p["c"], b["ring"]): p.setdefault("parent", b)


def height_of(b):
    t = b["tags"]
    h = num(t.get("height"))
    lv = num(t.get("building:levels"))
    if h is None and lv is not None: h = lv * STOREY + 1.0
    if h is None:
        kind = t.get("building", "yes")
        h = {"office": 30, "commercial": 15, "retail": 10, "apartments": 45, "house": 7, "roof": 5,
             "industrial": 12, "warehouse": 10}.get(kind)
        if h is None: h = 8 if b["area"] < 250 else 14 if b["area"] < 1200 else 24
    mh = num(t.get("min_height"))
    if mh is None and t.get("building:min_level") is not None: mh = num(t["building:min_level"]) * STOREY
    return max(h, 3.0), (mh or 0.0)


out = []
for b in items:
    if b.get("skip"): continue
    t = b["tags"]
    parent = b.get("parent")
    pt = parent["tags"] if parent else {}
    h, mh = height_of(b)
    btype = t.get("building") if t.get("building") not in (None, "yes", "part") else pt.get("building", t.get("building", "yes"))
    name = t.get("name") or pt.get("name") or ""
    off = (btype in OFF_TYPES) or bool(OFF_NAME.search(name)) or t.get("amenity") in ("school", "hospital", "place_of_worship")
    if btype == "roof": kind = "canopy"
    elif off: kind = "off"
    elif h >= 60 or (btype == "office" and h >= 36): kind = "glass"
    elif h >= 15: kind = "concrete"
    else: kind = "plaster"
    gz = min(ground_z(x, y) for x, y in b["ring"])
    out.append({"id": len(out), "osm": b["osm"], "group": parent["osm"] if parent else b["osm"], "name": name,
                "type": btype, "kind": kind, "smash": not off and kind != "canopy",
                "h": round(h, 1), "minh": round(mh, 1), "base": round(gz, 2),
                "levels": num(t.get("building:levels")),
                "ring": [[round(x, 2), round(y, 2)] for x, y in b["ring"]]})

# ---------- trees ----------
trees = []
for e in osm["elements"]:
    t = e.get("tags", {})
    if e["type"] == "node" and t.get("natural") == "tree":
        x, y = ll2xy(e["lat"], e["lon"])
        if abs(x) < HALF and abs(y) < HALF: trees.append([round(x, 1), round(y, 1)])
    elif e["type"] == "way" and t.get("natural") == "tree_row" and "geometry" in e:
        r = ring_xy(e["geometry"])
        for (x0, y0), (x1, y1) in zip(r, r[1:]):
            n = max(1, int(math.hypot(x1 - x0, y1 - y0) / 9))
            for k2 in range(n):
                x, y = x0 + (x1 - x0) * k2 / n, y0 + (y1 - y0) * k2 / n
                if abs(x) < HALF and abs(y) < HALF: trees.append([round(x, 1), round(y, 1)])

# ---------- placeholder ground texture (OSM painted), replaced by the VWorld aerial mosaic when available ----------
S = TEX / SIZE
def px(x, y): return ((x + HALF) * S, (HALF - y) * S)

img = Image.new("RGB", (TEX, TEX), (172, 168, 158))
d = ImageDraw.Draw(img)
rng = np.random.default_rng(7)
LAND = {"grass": (128, 150, 100), "park": (118, 146, 92), "forest": (88, 118, 72), "meadow": (140, 156, 104),
        "recreation_ground": (130, 152, 98), "construction": (170, 150, 120), "residential": (176, 172, 162),
        "commercial": (180, 176, 168), "retail": (182, 176, 166)}
for e in osm["elements"]:
    t = e.get("tags", {})
    col = None
    if t.get("leisure") == "park": col = LAND["park"]
    elif t.get("landuse") in LAND: col = LAND[t["landuse"]]
    elif t.get("natural") == "water" or t.get("waterway") in ("riverbank",): col = (92, 122, 138)
    if col and e["type"] == "way" and "geometry" in e:
        d.polygon([px(*p) for p in ring_xy(e["geometry"])], fill=col)
WIDTH = {"motorway": 22, "trunk": 20, "primary": 18, "secondary": 14, "tertiary": 11, "unclassified": 8,
         "residential": 7, "living_street": 6, "service": 5, "motorway_link": 8, "trunk_link": 8, "primary_link": 8,
         "secondary_link": 7}
roads = []
for e in osm["elements"]:
    t = e.get("tags", {})
    hw = t.get("highway")
    if not hw or e["type"] != "way" or "geometry" not in e: continue
    pts = [px(*p) for p in ring_xy(e["geometry"])]
    if hw in WIDTH:
        roads.append((WIDTH[hw], pts, hw))
    elif hw in ("footway", "pedestrian", "path", "cycleway", "steps"):
        d.line(pts, fill=(196, 190, 178), width=max(2, int(3 * S)), joint="curve")
for w, pts, hw in sorted(roads, key=lambda r: r[0]):           # sidewalk band, then asphalt
    d.line(pts, fill=(190, 186, 176), width=int((w + 5) * S), joint="curve")
for w, pts, hw in sorted(roads, key=lambda r: r[0]):
    d.line(pts, fill=(64, 66, 70), width=int(w * S), joint="curve")
for w, pts, hw in roads:
    if w >= 11:                                                   # dashed centre line on big roads
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            L = math.hypot(x1 - x0, y1 - y0); n = int(L / (12 * S))
            for k2 in range(0, n, 2):
                a, c = k2 / max(n, 1), min((k2 + 1) / max(n, 1), 1)
                d.line([(x0 + (x1 - x0) * a, y0 + (y1 - y0) * a), (x0 + (x1 - x0) * c, y0 + (y1 - y0) * c)],
                       fill=(222, 214, 170), width=max(1, int(0.35 * S)))
# contact shadow under buildings, then roofs painted in (roofs are UV-projected onto this same texture)
sh = Image.new("L", (TEX, TEX), 0)
ds = ImageDraw.Draw(sh)
for b in out:
    ds.polygon([px(*p) for p in b["ring"]], fill=150)
sh = sh.filter(ImageFilter.GaussianBlur(3 * S))
img = Image.composite(Image.new("RGB", (TEX, TEX), (40, 40, 44)), img, sh.point(lambda v: int(v * 0.55)))
d = ImageDraw.Draw(img)
ROOF = {"glass": (150, 156, 160), "concrete": (168, 166, 160), "plaster": (176, 160, 140), "off": (160, 160, 160),
        "canopy": (120, 140, 150)}
for b in sorted(out, key=lambda b: b["h"]):
    base = np.array(ROOF[b["kind"]]) + rng.integers(-14, 14, 3)
    d.polygon([px(*p) for p in b["ring"]], fill=tuple(int(v) for v in base), outline=(120, 120, 118))
img = img.filter(ImageFilter.GaussianBlur(0.6))
img.save(RAW / "ground.png")

prep = {"id": AID, "lat": LAT0, "lon": LON0, "size": SIZE, "zbase": round(ZBASE, 2), "grid": GRID, "nx": nx,
        "terrain": [round(float(v), 2) for v in zgrid.ravel()], "buildings": out, "trees": trees}
(RAW / "prep.json").write_text(json.dumps(prep, ensure_ascii=False), encoding="utf-8")
kinds = {}
for b in out: kinds[b["kind"]] = kinds.get(b["kind"], 0) + 1
print(f"{AID}: {len(out)} buildings {kinds}, trees {len(trees)}, terrain {nx}x{nx} relief {zgrid.max():.1f} m, "
      f"tallest {max(b['h'] for b in out):.0f} m")
