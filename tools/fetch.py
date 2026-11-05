# Downloads OpenStreetMap features and AWS terrarium elevation tiles for one sub-area box.
# usage: python3 tools/fetch.py <area_id>            (box comes from areas.json)
#        python3 tools/fetch.py --find "<name regex>" <s,w,n,e>   (prints matching OSM objects with their centres)
# Output: raw/<area_id>/osm.json, raw/<area_id>/dem/<z>_<x>_<y>.png
import json, math, os, pathlib, subprocess, sys, time, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
MIRRORS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter",
           "https://maps.mail.ru/osm/tools/overpass/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]
UA = {"User-Agent": "SMASH company data build (github.com/Hong-Iron)"}
DEM_Z = 15


def http(url, data=None):
    # urllib first; curl as a fallback (python.org builds on macOS ship without CA certificates)
    try:
        req = urllib.request.Request(url, data=data, headers=UA)
        with urllib.request.urlopen(req, timeout=200) as r:
            return r.read()
    except Exception:
        cmd = ["curl", "-sf", "-m", "200", "-A", UA["User-Agent"], url]
        if data is not None: cmd += ["--data-binary", "@-"]
        return subprocess.run(cmd, input=data, capture_output=True, check=True).stdout


def overpass(q):
    body = urllib.parse.urlencode({"data": q}).encode()
    for _ in range(3):
        for url in MIRRORS:
            try:
                data = http(url, body)
                if data[:1] == b"{": return json.loads(data)
            except Exception as e:
                print("  retry:", url, type(e).__name__)
        time.sleep(5)
    raise SystemExit("Overpass failed")


def box_of(area):
    # a square of side `size` metres centred on (lat, lon), as (south, west, north, east)
    lat, lon, half = area["lat"], area["lon"], area["size"] / 2
    dlat = half / 111132.0
    dlon = half / (111320.0 * math.cos(math.radians(lat)))
    return lat - dlat, lon - dlon, lat + dlat, lon + dlon


def tile(lat, lon, z):
    n = 2 ** z
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


def main():
    if sys.argv[1] == "--find":
        pat, bb = sys.argv[2], sys.argv[3]
        d = overpass(f'[out:json][timeout:60];nwr["name"~"{pat}"]({bb});out center tags;')
        for e in d["elements"]:
            c = e.get("center") or {"lat": e.get("lat"), "lon": e.get("lon")}
            t = e["tags"]
            kind = t.get("landuse") or t.get("railway") or t.get("building") or t.get("place") or ""
            print(e["type"], e["id"], t.get("name"), kind, round(c["lat"], 6), round(c["lon"], 6))
        return
    aid = sys.argv[1]
    area = json.loads((ROOT / "areas.json").read_text(encoding="utf-8"))[aid]
    out = ROOT / "raw" / aid
    (out / "dem").mkdir(parents=True, exist_ok=True)
    s, w, n, e = box_of(area)
    m = 0.004  # fetch a margin around the box so footprints cut by the edge come whole
    bb = f"{s - m:.6f},{w - m:.6f},{n + m:.6f},{e + m:.6f}"
    osm = overpass(f'[out:json][timeout:180];(way["building"]({bb});relation["building"]({bb});'
                   f'way["building:part"]({bb});way["highway"]({bb});way["natural"="water"]({bb});'
                   f'relation["natural"="water"]({bb});way["waterway"]({bb});way["leisure"="park"]({bb});'
                   f'way["landuse"]({bb});node["natural"="tree"]({bb});way["natural"="tree_row"]({bb}););out geom;')
    (out / "osm.json").write_text(json.dumps(osm, ensure_ascii=False), encoding="utf-8")
    x0, y0 = tile(n + m, w - m, DEM_Z)
    x1, y1 = tile(s - m, e + m, DEM_Z)
    got = 0
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            dst = out / "dem" / f"{DEM_Z}_{x}_{y}.png"
            if not dst.exists():
                dst.write_bytes(http(f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{DEM_Z}/{x}/{y}.png"))
            got += 1
    kinds = {}
    for el in osm["elements"]:
        k = "building" if ("building" in el.get("tags", {}) or "building:part" in el.get("tags", {})) else \
            "highway" if "highway" in el.get("tags", {}) else "other"
        kinds[k] = kinds.get(k, 0) + 1
    print(f"{aid}: box {s:.5f},{w:.5f},{n:.5f},{e:.5f}  osm {kinds}  dem tiles {got}")


if __name__ == "__main__":
    main()
