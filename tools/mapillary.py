# Lists Mapillary street photos (CC BY-SA 4.0) in a sub-area box with their computed camera poses.
# usage: python3 tools/mapillary.py <area_id> [--refresh]       (MAPILLARY_TOKEN in .env, never committed)
# Output: raw/<id>/mly/images.json — one record per photo: id, lon, lat, alt, compass, rotation, camera type and
# parameters, size, capture time, sequence, 2048 px thumbnail URL.
import json, math, os, pathlib, subprocess, sys, time, urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
AID = sys.argv[1]
REFRESH = "--refresh" in sys.argv
AREA = json.loads((ROOT / "areas.json").read_text(encoding="utf-8"))[AID]
OUT = ROOT / "raw" / AID / "mly"; OUT.mkdir(parents=True, exist_ok=True)
FIELDS = ("id,computed_geometry,computed_altitude,computed_compass_angle,computed_rotation,camera_type,"
          "camera_parameters,width,height,captured_at,sequence,is_pano,thumb_2048_url,creator")


def token():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("MAPILLARY_TOKEN="): return line.split("=", 1)[1].strip()
    if os.environ.get("MAPILLARY_TOKEN"): return os.environ["MAPILLARY_TOKEN"]
    sys.exit("MAPILLARY_TOKEN is missing: put it in .env (git-ignored)")


def get(url):
    r = subprocess.run(["curl", "-s", "--max-time", "90", "--retry", "3", url], capture_output=True, check=True)
    return json.loads(r.stdout)


def main():
    dst = OUT / "images.json"
    if dst.exists() and not REFRESH:
        imgs = json.loads(dst.read_text())
    else:
        lat0, lon0, half = AREA["lat"], AREA["lon"], AREA["size"] / 2 + 80
        dlat, dlon = half / 111132.0, half / (111320.0 * math.cos(math.radians(lat0)))
        k, seen, imgs = token(), set(), []
        n = 4   # the images endpoint caps results per call, so ask in a 4 x 4 grid of small boxes
        for i in range(n):
            for j in range(n):
                w = lon0 - dlon + 2 * dlon * i / n; e = w + 2 * dlon / n
                s = lat0 - dlat + 2 * dlat * j / n; nn = s + 2 * dlat / n
                url = "https://graph.mapillary.com/images?" + urllib.parse.urlencode(
                    {"access_token": k, "fields": FIELDS, "bbox": f"{w:.6f},{s:.6f},{e:.6f},{nn:.6f}", "limit": 2000})
                d = get(url)
                if "error" in d: sys.exit(f"Mapillary: {d['error'].get('message')}")
                for im in d.get("data", []):
                    if im["id"] in seen or "computed_geometry" not in im: continue
                    seen.add(im["id"])
                    lon, lat = im["computed_geometry"]["coordinates"]
                    imgs.append({"id": im["id"], "lon": lon, "lat": lat, "alt": im.get("computed_altitude"),
                                 "compass": im.get("computed_compass_angle"), "rot": im.get("computed_rotation"),
                                 "cam": im.get("camera_type"), "par": im.get("camera_parameters"),
                                 "w": im.get("width"), "h": im.get("height"), "t": im.get("captured_at"),
                                 "seq": im.get("sequence"), "pano": im.get("is_pano"), "url": im.get("thumb_2048_url"),
                                 "by": (im.get("creator") or {}).get("username")})
                time.sleep(0.2)
        dst.write_text(json.dumps(imgs, ensure_ascii=False), encoding="utf-8")
    cams, years, seqs = {}, {}, set()
    for im in imgs:
        cams[im["cam"]] = cams.get(im["cam"], 0) + 1
        y = time.gmtime((im["t"] or 0) / 1000).tm_year
        years[y] = years.get(y, 0) + 1
        seqs.add(im["seq"])
    print(f"{AID}: {len(imgs)} photos with poses, {len(seqs)} sequences, cameras {cams}, "
          f"years {dict(sorted(years.items()))}, with rotation {sum(1 for i in imgs if i['rot'])}")


if __name__ == "__main__":
    main()
