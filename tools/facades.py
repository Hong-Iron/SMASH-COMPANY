# Makes a texture for every outside wall of every smashable building from Mapillary street photos (CC BY-SA 4.0):
# each wall is sampled on a metre grid, every texel is projected into the photos that see it (camera pose from Mapillary's
# structure-from-motion: rotation R maps east-north-up into camera axes x right, y down, z forward), and the best view
# wins per texel. Texels no photo sees (upper floors of towers, back walls) are filled one storey at a time from the floor
# below, so towers repeat their own photographed floors upward.
# usage: ~/.venvs/vault-plots/bin/python tools/facades.py <area_id> [--only <building id>] [--sheet]
# Output: raw/<id>/facades/<building>_<edge>.png and raw/<id>/facades/index.json (coverage per wall)
import io, json, math, pathlib, subprocess, sys, time
import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
AID = sys.argv[1]
ONLY = int(sys.argv[sys.argv.index("--only") + 1]) if "--only" in sys.argv else None
RAW = ROOT / "raw" / AID
OUT = RAW / "facades"; OUT.mkdir(exist_ok=True)
PHOTO = RAW / "mly" / "img"; PHOTO.mkdir(exist_ok=True)
prep = json.loads((RAW / "prep.json").read_text(encoding="utf-8"))
imgs = json.loads((RAW / "mly" / "images.json").read_text(encoding="utf-8"))
LAT0, LON0, SIZE = prep["lat"], prep["lon"], prep["size"]
HALF = SIZE / 2
phi = math.radians(LAT0)
MLAT = 111132.92 - 559.82 * math.cos(2 * phi) + 1.175 * math.cos(4 * phi)
MLON = 111412.84 * math.cos(phi) - 93.5 * math.cos(3 * phi)
PPM = 6.0            # texels per metre
STOREY = 3.5
CAM_H = 2.0          # camera height above the street (car roof or hand)
MAX_D, MIN_COS = 140.0, 0.25
nx, G, T = prep["nx"], prep["grid"], np.array(prep["terrain"]).reshape(prep["nx"], prep["nx"])


def ground(x, y):
    fx = min(max((x + HALF) / G, 0), nx - 1.001); fy = min(max((y + HALF) / G, 0), nx - 1.001)
    i, j = int(fx), int(fy); tx, ty = fx - i, fy - j
    return (T[j, i] * (1 - tx) + T[j, i + 1] * tx) * (1 - ty) + (T[j + 1, i] * (1 - tx) + T[j + 1, i + 1] * tx) * ty


def rod(r):
    r = np.array(r, float); th = np.linalg.norm(r)
    if th < 1e-12: return np.eye(3)
    k = r / th; K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + math.sin(th) * K + (1 - math.cos(th)) * K @ K


cams = []
for im in imgs:
    if im["cam"] != "perspective" or not im["rot"] or not im["par"] or not im["url"]: continue
    x, y = (im["lon"] - LON0) * MLON, (im["lat"] - LAT0) * MLAT
    if abs(x) > HALF + 100 or abs(y) > HALF + 100: continue
    yr = time.gmtime((im["t"] or 0) / 1000).tm_year
    cams.append({"id": im["id"], "C": np.array([x, y, ground(x, y) + CAM_H]), "R": rod(im["rot"]), "par": im["par"],
                 "w": im["w"], "h": im["h"], "url": im["url"], "fresh": 1.6 if yr >= 2023 else 1.2 if yr >= 2018 else 1.0})
CXY = np.array([c["C"][:2] for c in cams]) if cams else np.zeros((0, 2))

blds = prep["buildings"]
# every building edge, for occlusion tests (2D segment + roof height)
occ_a, occ_b, occ_h, occ_id = [], [], [], []
for b in blds:
    r = b["ring"]
    for i in range(len(r)):
        occ_a.append(r[i]); occ_b.append(r[(i + 1) % len(r)]); occ_h.append(b["base"] + b["h"]); occ_id.append(b["id"])
occ_a, occ_b, occ_h, occ_id = np.array(occ_a), np.array(occ_b), np.array(occ_h), np.array(occ_id)

_cache = {}
def photo(c):
    if c["id"] in _cache: return _cache[c["id"]]
    f = PHOTO / f"{c['id']}.jpg"
    if not f.exists():
        data = subprocess.run(["curl", "-s", "--max-time", "60", "--retry", "2", c["url"]], capture_output=True).stdout
        if len(data) < 1000: return None
        f.write_bytes(data)
    try: a = np.asarray(Image.open(f).convert("RGB"), dtype=np.float32)
    except Exception: return None
    if len(_cache) > 60: _cache.pop(next(iter(_cache)))
    _cache[c["id"]] = a
    return a


def project(c, P, H, W):
    # P: (..., 3) world points → pixel coords (u, v) in an image of H x W and depth
    Xc = (P - c["C"]) @ c["R"].T
    z = Xc[..., 2]
    zs = np.where(z > 0.1, z, np.nan)
    xn, yn = Xc[..., 0] / zs, Xc[..., 1] / zs
    f, k1, k2 = c["par"][0], c["par"][1], c["par"][2]
    r2 = xn * xn + yn * yn
    d = 1 + k1 * r2 + k2 * r2 * r2
    s = max(W, H)
    return f * d * xn * s + W / 2 - 0.5, f * d * yn * s + H / 2 - 0.5, z


def occluded(C, P, own):
    # P: (n, 3) sample points; True where another building blocks the line of sight
    out = np.zeros(len(P), bool)
    lo = np.minimum(C[:2], P[:, :2].min(0)) - 1; hi = np.maximum(C[:2], P[:, :2].max(0)) + 1
    m = (np.minimum(occ_a, occ_b) <= hi).all(1) & (np.maximum(occ_a, occ_b) >= lo).all(1) & (occ_id != own)
    A, B, Hh = occ_a[m], occ_b[m], occ_h[m]
    if not len(A): return out
    for k, p in enumerate(P):
        d = p[:2] - C[:2]; e = B - A; w = A - C[:2]
        den = d[0] * e[:, 1] - d[1] * e[:, 0]
        ok = np.abs(den) > 1e-9
        t = np.where(ok, (w[:, 0] * e[:, 1] - w[:, 1] * e[:, 0]) / np.where(ok, den, 1), -1)
        u = np.where(ok, (w[:, 0] * d[1] - w[:, 1] * d[0]) / np.where(ok, den, 1), -1)
        hit = ok & (t > 0.0) & (t < 0.995) & (u >= 0) & (u <= 1)
        if hit.any():
            zray = C[2] + (p[2] - C[2]) * t[hit]
            out[k] = bool((Hh[hit] > zray).any())
    return out


def wall_texture(b, i):
    r = b["ring"]
    a, c2 = np.array(r[i]), np.array(r[(i + 1) % len(r)])
    L = float(np.linalg.norm(c2 - a))
    if L < 2.0: return None, 0.0
    dirv = (c2 - a) / L
    nrm = np.array([dirv[1], -dirv[0]])                       # outward for a counter-clockwise ring
    z0, z1 = b["base"] + b["minh"], b["base"] + b["h"]
    Wp, Hp = max(2, int(L * PPM)), max(2, int((z1 - z0) * PPM))
    ss = (np.arange(Wp) + 0.5) / PPM; zz = z1 - (np.arange(Hp) + 0.5) / PPM          # row 0 = top
    P = np.zeros((Hp, Wp, 3))
    P[..., 0] = a[0] + dirv[0] * ss[None, :]; P[..., 1] = a[1] + dirv[1] * ss[None, :]; P[..., 2] = zz[:, None]
    mid = (a + c2) / 2
    best_w = np.zeros((Hp, Wp)); col = np.zeros((Hp, Wp, 3), np.float32)
    if len(CXY):
        dd = np.linalg.norm(CXY - mid, axis=1)
        cand = [k for k in np.argsort(dd) if dd[k] < MAX_D][:40]
    else:
        cand = []
    for k in cand:
        c = cams[k]
        v = c["C"][:2] - mid
        dist = float(np.linalg.norm(v))
        cosv = float(np.dot(v, nrm) / max(dist, 1e-6))
        if cosv < MIN_COS or dist < 4: continue
        img = None
        H, W = (c["h"], c["w"])
        # thumbnails are 2048 px on the long side
        sc = 2048 / max(W, H); H, W = int(round(H * sc)), int(round(W * sc))
        u, vv, z = project(c, P, H, W)
        vis = (z > 2) & (u >= 8) & (u < W - 8) & (vv >= 8) & (vv < H - 8)
        if vis.mean() < 0.02: continue
        # occlusion on a coarse grid, then expand to texels
        gs = max(1, int(3 * PPM))
        sub = P[::gs, ::gs].reshape(-1, 3)
        occ = occluded(c["C"], sub, b["id"]).reshape(P[::gs, ::gs].shape[:2])
        occ_full = np.repeat(np.repeat(occ, gs, 0), gs, 1)[:Hp, :Wp]
        vis &= ~occ_full
        if not vis.any(): continue
        img = photo(c)
        if img is None: continue
        if img.shape[0] != H or img.shape[1] != W:
            H, W = img.shape[:2]
            u, vv, z = project(c, P, H, W)
            vis &= (u >= 8) & (u < W - 8) & (vv >= 8) & (vv < H - 8) & (z > 2)
        # weight: facing, distance, freshness; penalise steep upward views (stretched upper floors)
        elev = np.abs(P[..., 2] - c["C"][2]) / np.maximum(np.hypot(P[..., 0] - c["C"][0], P[..., 1] - c["C"][1]), 1)
        wgt = cosv * (1 / (1 + dist / 40)) * c["fresh"] / (1 + 0.8 * elev)
        take = vis & (wgt > best_w)
        if not take.any(): continue
        ui = np.clip(u[take], 0, W - 1.001); vi = np.clip(vv[take], 0, H - 1.001)
        x0, y0 = ui.astype(int), vi.astype(int); fx, fy = (ui - x0)[:, None], (vi - y0)[:, None]
        px = (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x0 + 1] * fx * (1 - fy) +
              img[y0 + 1, x0] * (1 - fx) * fy + img[y0 + 1, x0 + 1] * fx * fy)
        col[take] = px; best_w[take] = wgt[take]
    filled = best_w > 0
    cov = float(filled.mean())
    if cov > 0:
        # fill unseen rows from the floor below (or above), one storey at a time
        per = max(1, int(round(STOREY * PPM)))
        for _ in range(int(Hp / per) + 2):
            down = np.zeros_like(filled); down[:-per] = filled[per:]
            src = np.zeros_like(col); src[:-per] = col[per:]
            m = ~filled & down
            col[m] = src[m]; filled |= m
            up = np.zeros_like(filled); up[per:] = filled[:-per]
            src2 = np.zeros_like(col); src2[per:] = col[:-per]
            m2 = ~filled & up
            col[m2] = src2[m2]; filled |= m2
    return (Image.fromarray(np.uint8(np.clip(col, 0, 255))) if cov > 0 else None), cov


def main():
    todo = [b for b in blds if b["smash"] and (ONLY is None or b["id"] == ONLY)]
    if ONLY is None and "--sheet" in sys.argv:
        # pick the tall buildings with the most nearby photos for a quick look
        score = lambda b: sum(1 for p in CXY if np.hypot(*(p - np.mean(b["ring"], axis=0))) < 80)
        todo = sorted([b for b in todo if b["h"] > 40], key=score, reverse=True)[:4]
    index = {}
    for b in todo:
        for i in range(len(b["ring"])):
            img, cov = wall_texture(b, i)
            index[f"{b['id']}_{i}"] = round(cov, 3)
            if img is not None: img.save(OUT / f"{b['id']}_{i}.png")
        print(f"building {b['id']} {b['name'] or '(no name)'} h={b['h']} walls {len(b['ring'])}: "
              f"coverage {[index[f'{b['id']}_{i}'] for i in range(len(b['ring']))]}")
    (OUT / "index.json").write_text(json.dumps(index), encoding="utf-8")


if __name__ == "__main__":
    main()
