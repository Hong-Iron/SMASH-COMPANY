# Converts one prepared sub-area into the SMASH 대학교 engine's data format (data/<area>.json), so buildings are built,
# chunked and destroyed by the same engine. Unbreakable buildings (homes, schools, care, worship, public safety) go to
# "locked": the page draws them as plain grey blocks that weapons never target.
# usage: python3 tools/to_smash.py <area_id>
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
      f"{len(trees)} trees, look for {len(look)}")
