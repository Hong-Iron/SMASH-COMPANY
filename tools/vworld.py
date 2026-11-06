# Building data and aerial photos from 국토교통부 브이월드 (공공누리 제1유형, 출처 표시).
# usage: ~/.venvs/vault-plots/bin/python tools/vworld.py <area_id> [--refresh]      (key VWORLD_KEY in .env, never committed)
#   1. 건물통합정보 (LT_C_BLDGINFO) + 도로명주소 건물 (LT_C_SPBD) in the box → raw/<id>/vworld_bld.json (height, floors, use,
#      names, complex block numbers); prep_area.py merges it
#   2. 영상지도 Satellite WMTS tiles → raw/<id>/aerial.jpg, a 4096 px square covering the box in local metres (north up)
import io, json, math, os, pathlib, subprocess, sys, urllib.parse
import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
AID = sys.argv[1]
REFRESH = "--refresh" in sys.argv
AREA = json.loads((ROOT / "areas.json").read_text(encoding="utf-8"))[AID]
RAW = ROOT / "raw" / AID
CACHE = RAW / "vworld"; CACHE.mkdir(parents=True, exist_ok=True)
DOMAIN = "https://hong-iron.github.io"          # the key is registered for this domain
LAT0, LON0, SIZE = AREA["lat"], AREA["lon"], AREA["size"]
HALF = SIZE / 2
phi = math.radians(LAT0)
MLAT = 111132.92 - 559.82 * math.cos(2 * phi) + 1.175 * math.cos(4 * phi)
MLON = 111412.84 * math.cos(phi) - 93.5 * math.cos(3 * phi)
Z, TEX = 19, 4096


def key():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("VWORLD_KEY="): return line.split("=", 1)[1].strip()
    if os.environ.get("VWORLD_KEY"): return os.environ["VWORLD_KEY"]
    sys.exit("VWORLD_KEY is missing: put it in .env (git-ignored)")


def get(url):
    # python.org builds on macOS ship without CA certificates, so curl does the transfer
    return subprocess.run(["curl", "-s", "--max-time", "60", "--retry", "3", url], capture_output=True, check=True).stdout


def box(margin=0.0):
    dlat = (HALF + margin) / MLAT; dlon = (HALF + margin) / MLON
    return LON0 - dlon, LAT0 - dlat, LON0 + dlon, LAT0 + dlat


def features(layer):
    f = CACHE / f"{layer}.json"
    if f.exists() and not REFRESH: return json.loads(f.read_text(encoding="utf-8"))
    out, page, k = [], 1, key()
    while True:
        q = dict(service="data", request="GetFeature", data=layer, key=k, domain=DOMAIN, format="json", crs="EPSG:4326",
                 geometry="true", attribute="true", size=1000, page=page, geomFilter="BOX(%.6f,%.6f,%.6f,%.6f)" % box(60))
        r = json.loads(get("https://api.vworld.kr/req/data?" + urllib.parse.urlencode(q)))["response"]
        if r["status"] == "NOT_FOUND": break
        if r["status"] != "OK": sys.exit(f"{layer}: {r.get('error')}")
        out += r["result"]["featureCollection"]["features"]
        if page >= int(r["page"]["total"]): break
        page += 1
    f.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


# ---------- 1. buildings ----------
bld = []
for f in features("LT_C_BLDGINFO"):
    p = f["properties"]
    g = f["geometry"]
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    for poly in polys:
        ring = [[round((lon - LON0) * MLON, 2), round((lat - LAT0) * MLAT, 2)] for lon, lat in poly[0]]
        bld.append({"ring": ring, "floors": int(float(p.get("grnd_flr") or 0)), "h": float(p.get("height") or 0),
                    "use": (p.get("usability") or "").strip(), "name": (p.get("bld_nm") or "").strip(),
                    "dong": (p.get("dong_nm") or "").strip()})
# 도로명주소 건물 (LT_C_SPBD): building names and complex block numbers ("102" in an apartment complex) for buildings whose
# 건물통합정보 entry has neither a name nor a use code (e.g. all of Daegu). Matched by the address polygon's centre.
def inside(p, ring):
    x, y, c = p[0], p[1], False
    for i in range(len(ring)):
        (x1, y1), (x2, y2) = ring[i - 1], ring[i]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1): c = not c
    return c


addr = []
for f in features("LT_C_SPBD"):
    p, g = f["properties"], f["geometry"]
    poly = (g["coordinates"][0] if g["type"] == "MultiPolygon" else g["coordinates"])[0]
    xy = [((lon - LON0) * MLON, (lat - LAT0) * MLAT) for lon, lat in poly]
    addr.append(((sum(q[0] for q in xy) / len(xy), sum(q[1] for q in xy) / len(xy)),
                 (p.get("buld_nm") or "").strip(), (p.get("buld_nm_dc") or "").strip()))
for b in bld:
    xs = [q[0] for q in b["ring"]]; ys = [q[1] for q in b["ring"]]
    for c, nm, dc in addr:
        if min(xs) <= c[0] <= max(xs) and min(ys) <= c[1] <= max(ys) and inside(c, b["ring"]):
            b["addr"], b["dc"] = nm, dc
            break
(RAW / "vworld_bld.json").write_text(json.dumps(bld, ensure_ascii=False), encoding="utf-8")
uses = {}
for b in bld: uses[b["use"]] = uses.get(b["use"], 0) + 1
print(f"buildings: {len(bld)}, with height {sum(1 for b in bld if b['h'] > 0)}, address names {sum(1 for b in bld if b.get('addr'))}, "
      f"uses {sorted(uses.items(), key=lambda kv: -kv[1])[:10]}")

# ---------- 2. aerial mosaic ----------
def merc(lat, lon):
    n = 2 ** Z
    return (lon + 180) / 360 * n * 256, (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n * 256

w, s, e, n = box(0)
px0, py0 = merc(n, w); px1, py1 = merc(s, e)
tx0, ty0, tx1, ty1 = int(px0 // 256), int(py0 // 256), int(px1 // 256), int(py1 // 256)
tdir = CACHE / f"sat{Z}"; tdir.mkdir(exist_ok=True)
k = key()
mos = Image.new("RGB", ((tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256), (128, 128, 128))
missing = 0
for ty in range(ty0, ty1 + 1):
    for tx in range(tx0, tx1 + 1):
        f = tdir / f"{ty}_{tx}.jpeg"
        if not f.exists() or REFRESH:
            f.write_bytes(get(f"https://api.vworld.kr/req/wmts/1.0.0/{k}/Satellite/{Z}/{ty}/{tx}.jpeg"))
        try:
            mos.paste(Image.open(io.BytesIO(f.read_bytes())).convert("RGB"), ((tx - tx0) * 256, (ty - ty0) * 256))
        except Exception:
            missing += 1
# crop the box (Mercator is near-linear over 1.2 km) and resample to the square texture
crop = mos.crop((px0 - tx0 * 256, py0 - ty0 * 256, px1 - tx0 * 256, py1 - ty0 * 256)).resize((TEX, TEX), Image.LANCZOS)
crop.save(RAW / "aerial.jpg", quality=90)
print(f"aerial: {(tx1 - tx0 + 1) * (ty1 - ty0 + 1)} tiles z{Z} ({missing} missing) → {TEX}px, "
      f"{SIZE / TEX:.2f} m/px")
