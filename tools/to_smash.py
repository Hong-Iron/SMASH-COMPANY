# Converts one prepared sub-area into the SMASH 대학교 engine's data format (data/<area>.json), so buildings are built,
# chunked and destroyed by the same engine. Unbreakable buildings (homes, schools, care, worship, public safety) go to
# "locked": the page draws them as plain grey blocks that weapons never target.
# usage: ~/.venvs/vault-plots/bin/python tools/to_smash.py <area_id>      (numpy, matplotlib)
# SMASH axes: x east, z south (metres from the centre); terrain heights in decimetres, rows along z.
import json, math, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
AID = sys.argv[1]
AREA = json.loads((ROOT / "areas.json").read_text(encoding="utf-8"))[AID]
RAW = ROOT / "raw" / AID
prep = json.loads((RAW / "prep.json").read_text(encoding="utf-8"))
osm = json.loads((RAW / "osm.json").read_text(encoding="utf-8"))
FAC = {v["i"]: v for v in json.loads((ROOT / "site" / "tex" / "facades.json").read_text(encoding="utf-8"))["variants"]}
LAT0, LON0, SIZE = prep["lat"], prep["lon"], prep["size"]
HALF = SIZE / 2
phi = math.radians(LAT0)
MLAT = 111132.92 - 559.82 * math.cos(2 * phi) + 1.175 * math.cos(4 * phi)
MLON = 111412.84 * math.cos(phi) - 93.5 * math.cos(3 * phi)
xz = lambda lon, lat: (round((lon - LON0) * MLON, 1), round((LAT0 - lat) * MLAT, 1))
inbox = lambda x, z: abs(x) <= HALF and abs(z) <= HALF

# terrain: prep rows run south→north (y up); SMASH rows run north→south (z down)
nx, G, T = prep["nx"], prep["grid"], prep["terrain"]
dm = []
for iz in range(nx):
    j = nx - 1 - iz
    dm += [int(round(T[j * nx + i] * 10)) for i in range(nx)]
terrain = {"x0": -HALF, "z0": -HALF, "step": G, "nx": nx, "nz": nx, "dm": dm}


def ground(x, z):
    fx = min(max((x + HALF) / G, 0), nx - 1.001); fz = min(max((z + HALF) / G, 0), nx - 1.001)
    i, k = int(fx), int(fz); tx, tz = fx - i, fz - k
    r = lambda iz, ix: dm[iz * nx + ix] / 10
    return (r(k, i) * (1 - tx) + r(k, i + 1) * tx) * (1 - tz) + (r(k + 1, i) * (1 - tx) + r(k + 1, i + 1) * tx) * tz


def hexc(rgb): return "#%02x%02x%02x" % tuple(max(0, min(255, int(c))) for c in rgb)


# per-building look in the engine's own style vocabulary, picked from our facade choice and the roof photo
STYLE_FOR = {"curtain": "glass", "grid": "concrete", "ribbon": "ribbon", "punched": "tan"}
buildings, locked, look = [], [], {}
for b in prep["buildings"]:
    ring = [[round(x, 1), round(-y, 1)] for x, y in b["ring"]]
    samples = [ground(x, z) for x, z in ring]
    g, lo = round(sum(samples) / len(samples), 1), round(min(samples), 1)
    if not b["smash"]:
        locked.append({"o": ring, "h": b["h"], "lo": lo, "minh": b["minh"], "canopy": b["kind"] == "canopy"})
        continue
    bid = f"b/{b['id']}"
    lv = int(b["levels"]) if b.get("levels") else max(1, round(b["h"] / 3.6))
    rec = {"id": bid, "n": b["name"] or "", "lv": lv, "h": b["h"], "campus": True, "kind": b["type"] or "yes",
           "g": g, "lo": lo, "o": ring, "ho": []}
    if b.get("roof"): rec["rc"] = hexc(b["roof"])
    buildings.append(rec)
    v = FAC.get(b.get("fac"))
    if v:
        t = b.get("tint", [1, 1, 1])
        mean = [m * k for m, k in zip(v["mean"], t)]
        st = STYLE_FOR[v["kind"]]
        lk = {"style": st}
        if st == "glass": lk["glass"] = hexc(mean); lk["wall"] = hexc([c * 1.25 + 20 for c in mean])
        else: lk["wall"] = hexc([c * 1.15 for c in mean])
        look[bid] = lk

# ---------- overlaps: two prisms in the same place flicker (coplanar walls and roofs), so only one may stay ----------
# rule: when the shared area is over 15% of the smaller footprint (5% for footprints under 300 m²), an unbreakable building wins over a breakable one
# (homes must never become smashable), otherwise the larger footprint wins.
import numpy as np
from matplotlib.path import Path


def fp_area(r): return abs(sum(r[i - 1][0] * r[i][1] - r[i][0] * r[i - 1][1] for i in range(len(r)))) / 2


def shared(a, b, n=14):
    xs = [p[0] for p in a]; zs = [p[1] for p in a]
    g = np.mgrid[min(xs):max(xs):complex(n), min(zs):max(zs):complex(n)].reshape(2, -1).T
    ina = Path(a).contains_points(g)
    return 0.0 if not ina.any() else float((ina & Path(b).contains_points(g)).sum() / ina.sum())


allb = [("S", r) for r in buildings] + [("L", r) for r in locked]
box = [(min(p[0] for p in r["o"]), max(p[0] for p in r["o"]), min(p[1] for p in r["o"]), max(p[1] for p in r["o"])) for _, r in allb]
gone = set()
for i in range(len(allb)):
    for j in range(i + 1, len(allb)):
        if i in gone or j in gone: continue
        a, b = box[i], box[j]
        if a[1] < b[0] or b[1] < a[0] or a[3] < b[2] or b[3] < a[2]: continue
        ai, aj = fp_area(allb[i][1]["o"]), fp_area(allb[j][1]["o"])
        small, big = (i, j) if ai <= aj else (j, i)
        if shared(allb[small][1]["o"], allb[big][1]["o"]) <= (0.05 if min(ai, aj) < 300 else 0.15): continue
        if allb[i][0] != allb[j][0]:
            lk, sm = (i, j) if allb[i][0] == "L" else (j, i)
            gone.add(sm if fp_area(allb[lk][1]["o"]) >= 0.5 * fp_area(allb[sm][1]["o"]) else lk)
        else:
            gone.add(small)
dropped = len(gone)
buildings = [r for k, (t, r) in enumerate(allb) if t == "S" and k not in gone]
locked = [r for k, (t, r) in enumerate(allb) if t == "L" and k not in gone]
look = {k: v for k, v in look.items() if any(b["id"] == k for b in buildings)}

roads = []
for e in osm["elements"]:
    t = e.get("tags", {})
    if e["type"] != "way" or "geometry" not in e or not t.get("highway"): continue
    p = [list(xz(q["lon"], q["lat"])) for q in e["geometry"]]
    if not any(inbox(x, z) for x, z in p): continue
    roads.append({"k": t["highway"], "n": t.get("name", ""), "p": p})
lands = []
LANDK = {"park": "park", "grass": "grass", "forest": "forest", "meadow": "grass", "recreation_ground": "park"}
for e in osm["elements"]:
    t = e.get("tags", {})
    k = LANDK.get(t.get("leisure")) or LANDK.get(t.get("landuse")) or ("water" if t.get("natural") == "water" else None)
    if not k or e["type"] != "way" or "geometry" not in e: continue
    r = [list(xz(q["lon"], q["lat"])) for q in e["geometry"]]
    if any(inbox(x, z) for x, z in r): lands.append({"k": k, "r": [r]})
trees = [[x, -y, 0.8] for x, y in prep["trees"]]

data = {"terrain": terrain, "campus": [[[-HALF, -HALF], [HALF, -HALF], [HALF, HALF], [-HALF, HALF]]],
        "buildings": buildings, "roads": roads, "lands": lands, "trees": trees,
        "meta": {"lat": LAT0, "lon": LON0, "area": AID, "size": SIZE}, "locked": locked}
out = ROOT / "data"; out.mkdir(exist_ok=True)
(out / f"{AID}.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
(out / f"{AID}.look.json").write_text(json.dumps(look, ensure_ascii=False, indent=0), encoding="utf-8")
print(f"{AID}: {len(buildings)} smashable, {len(locked)} locked, {len(roads)} roads, {len(lands)} lands, "
      f"{len(trees)} trees, look for {len(look)}, dropped {dropped} overlapping")
