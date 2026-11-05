# Paints the shared facade textures (one tile = 8 bays x 8 storeys = 24 m x 28 m, so windows line up with 3 m bays
# and 3.5 m storeys when walls are UV-mapped in world metres).
# usage: ~/.venvs/vault-plots/bin/python tools/make_textures.py      → site/tex/*.webp (+ PNG copies in raw/tex for Blender)
import pathlib
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "tex"; OUT.mkdir(parents=True, exist_ok=True)
RAWT = ROOT / "raw" / "tex"; RAWT.mkdir(parents=True, exist_ok=True)
W = 1024
TW, TH = 24.0, 28.0                       # metres covered by one tile
SX, SY = W / TW, W / TH                    # pixels per metre
rng = np.random.default_rng(11)


def noise(img, amount=6, blur=1.2):
    a = np.asarray(img, dtype=np.int16)
    n = rng.normal(0, amount, a.shape[:2])
    n = np.asarray(Image.fromarray(np.uint8(np.clip(n + 128, 0, 255)), "L").filter(ImageFilter.GaussianBlur(blur)), dtype=np.int16) - 128
    return Image.fromarray(np.uint8(np.clip(a + n[..., None], 0, 255)))


def rect(d, x0, y0, x1, y1, col):   # metres → pixels; y measured from the top of the tile
    d.rectangle([x0 * SX, y0 * SY, x1 * SX - 1, y1 * SY - 1], fill=col)


def save(img, name):
    img.save(OUT / f"{name}.webp", quality=88, method=6)
    img.save(RAWT / f"{name}.png")


def glass():
    img = Image.new("RGB", (W, W), (70, 88, 104))
    d = ImageDraw.Draw(img)
    for f in range(8):
        y0 = f * 3.5
        for p in range(16):                                   # panes 1.5 m wide
            x0 = p * 1.5
            t = rng.uniform(-1, 1)
            base = np.array([84, 104, 122]) + t * np.array([10, 12, 14])
            if rng.random() < 0.12: base = np.array([150, 158, 160])   # blinds down
            for k in range(int(3.0 * SY)):                    # vertical sky gradient inside each pane
                c = base + (1 - k / (3.0 * SY)) * np.array([36, 40, 42])
                d.line([(x0 * SX + 2, y0 * SY + k), ((x0 + 1.5) * SX - 3, y0 * SY + k)], fill=tuple(int(v) for v in c))
        rect(d, 0, y0 + 3.0, TW, y0 + 3.5, (46, 56, 66))      # spandrel at the slab
    for p in range(17):                                       # mullions
        d.rectangle([p * 1.5 * SX - 2, 0, p * 1.5 * SX + 1, W], fill=(150, 160, 168))
    for f in range(9):
        d.rectangle([0, f * 3.5 * SY - 2, W, f * 3.5 * SY + 1], fill=(132, 142, 150))
    # a soft diagonal sky reflection across the whole tile
    a = np.asarray(img, dtype=np.float32)
    yy, xx = np.mgrid[0:W, 0:W]
    band = np.exp(-((xx * 0.6 + yy - 700) / 260.0) ** 2)[..., None] * 34
    return Image.fromarray(np.uint8(np.clip(a + band, 0, 255)))


def concrete():
    img = Image.new("RGB", (W, W), (186, 182, 174))
    d = ImageDraw.Draw(img)
    for f in range(8):
        y0 = f * 3.5
        rect(d, 0, y0 + 1.1, TW, y0 + 3.3, (58, 70, 80))      # ribbon window
        for p in range(17):
            d.rectangle([p * 1.5 * SX - 2, (y0 + 1.1) * SY, p * 1.5 * SX + 1, (y0 + 3.3) * SY], fill=(120, 124, 126))
        for p in range(16):
            if rng.random() < 0.18: rect(d, p * 1.5 + 0.08, y0 + 1.15, p * 1.5 + 1.42, y0 + 3.25, (168, 170, 166))
            else:
                t = rng.uniform(-8, 8)
                rect(d, p * 1.5 + 0.08, y0 + 1.15, p * 1.5 + 1.42, y0 + 1.6, (int(92 + t), int(106 + t), int(118 + t)))
        rect(d, 0, y0 + 3.3, TW, y0 + 3.42, (150, 146, 140))  # sill shadow
    for x in (0, 12):                                         # vertical fins every 12 m
        rect(d, x, 0, x + 0.6, TH, (200, 196, 188))
    return noise(img, 5)


def plaster():
    img = Image.new("RGB", (W, W), (204, 188, 160))
    d = ImageDraw.Draw(img)
    for f in range(8):
        y0 = f * 3.5
        for b in range(8):
            x0 = b * 3 + 0.7
            lit = rng.random()
            col = (66, 74, 82) if lit > 0.2 else (140, 132, 116)
            rect(d, x0, y0 + 1.0, x0 + 1.6, y0 + 2.6, col)
            rect(d, x0 + 0.78, y0 + 1.0, x0 + 0.84, y0 + 2.6, (190, 184, 170))
            rect(d, x0 - 0.1, y0 + 2.6, x0 + 1.7, y0 + 2.75, (226, 214, 190))   # sill
        rect(d, 0, y0 + 3.4, TW, y0 + 3.5, (180, 164, 138))
    return noise(img, 7, 1.6)


def shop():
    # 24 m x 6 m band for the ground floor of offices and shops, stretched to a 1024 x 256 image
    img = Image.new("RGB", (W, 256), (40, 44, 48))
    d = ImageDraw.Draw(img)
    sx, sy = W / 24.0, 256 / 6.0
    signs = [(200, 70, 60), (60, 120, 190), (230, 190, 70), (70, 150, 100), (220, 220, 220), (160, 90, 170)]
    x = 0.0
    while x < 24:
        w = rng.choice([4.0, 6.0, 8.0])
        c = signs[rng.integers(len(signs))]
        d.rectangle([x * sx + 3, 0.2 * sy, (x + w) * sx - 3, 1.1 * sy], fill=c)                 # sign band
        d.rectangle([x * sx + 6, 1.4 * sy, (x + w) * sx - 6, 5.6 * sy], fill=(96, 120, 132))     # shop glass
        for k in range(int(w / 1.5) + 1):
            d.rectangle([x * sx + k * 1.5 * sx - 2, 1.4 * sy, x * sx + k * 1.5 * sx + 2, 5.6 * sy], fill=(30, 32, 36))
        d.rectangle([x * sx + 6, 1.4 * sy, (x + w) * sx - 6, 2.0 * sy], fill=(150, 176, 186))     # reflection strip
        x += w
    d.rectangle([0, 5.6 * sy, W, 256], fill=(120, 116, 110))
    return noise(img, 4)


def offlimits():
    img = Image.new("RGB", (512, 512), (176, 176, 172))
    d = ImageDraw.Draw(img)
    for k in range(-512, 1024, 36):
        d.line([(k, 0), (k + 512, 512)], fill=(158, 158, 154), width=5)
    return img


def core():
    img = Image.new("RGB", (512, 512), (92, 90, 86))
    d = ImageDraw.Draw(img)
    for k in range(0, 512, 64): d.rectangle([0, k, 512, k + 6], fill=(70, 68, 64))
    return noise(img, 8)


def roofkit():
    img = Image.new("RGB", (256, 256), (146, 150, 152))
    d = ImageDraw.Draw(img)
    for k in range(0, 256, 16): d.line([(0, k), (256, k)], fill=(120, 124, 126), width=3)
    return img


for name, fn in [("glass", glass), ("concrete", concrete), ("plaster", plaster), ("shop", shop),
                 ("off", offlimits), ("core", core), ("roofkit", roofkit)]:
    save(fn(), name)
    print("wrote", name)


# ---------- per-building facade variants: a 2048 px atlas of 8 x 8 tiles (256 px = 24 m x 28 m each) ----------
# The game picks one tile per building (vertex attribute _FAC) and tints it (_TINT); walls wrap inside their tile.
AT, TS = 2048, 256
PX, PY = TS / TW, TS / TH


def tile_rect(d, ox, oy, x0, y0, x1, y1, col):
    d.rectangle([ox + x0 * PX, oy + y0 * PY, ox + x1 * PX - 1, oy + y1 * PY - 1], fill=tuple(int(c) for c in col))


def v_curtain(d, ox, oy, r, p):
    tint, mull, mcol, band, fin = p
    for f in range(8):
        y0 = f * 3.5
        x = 0.0
        while x < TW - 1e-6:
            t = r.uniform(-1, 1)
            base = np.array(tint) + t * 8
            if r.random() < 0.1: base = np.array(tint) * 0.6 + 70
            for k in range(int(3.5 * PY)):
                g = base + (1 - k / (3.5 * PY)) * 30
                d.line([(ox + x * PX + 1, oy + y0 * PY + k), (ox + (x + mull) * PX - 2, oy + y0 * PY + k)], fill=tuple(int(v) for v in g))
            x += mull
        if band: tile_rect(d, ox, oy, 0, y0 + 2.9, TW, y0 + 3.5, np.array(tint) * 0.55)
    x = 0.0
    while x <= TW + 1e-6:
        d.line([(ox + x * PX, oy), (ox + x * PX, oy + TS - 1)], fill=mcol, width=2 if fin else 1)
        x += mull * (2 if fin else 1)
    for f in range(9): d.line([(ox, oy + f * 3.5 * PY), (ox + TS - 1, oy + f * 3.5 * PY)], fill=mcol, width=1)


def v_ribbon(d, ox, oy, r, p):
    clad, ratio, glass, fins = p
    d.rectangle([ox, oy, ox + TS - 1, oy + TS - 1], fill=clad)
    for f in range(8):
        y0 = f * 3.5
        wy0, wy1 = y0 + 3.5 * (1 - ratio) * 0.6, y0 + 3.5 * (1 - (1 - ratio) * 0.4)
        tile_rect(d, ox, oy, 0, wy0, TW, wy1, glass)
        for b in range(17): d.line([(ox + b * 1.5 * PX, oy + wy0 * PY), (ox + b * 1.5 * PX, oy + wy1 * PY)], fill=tuple(int(c * 0.8) for c in clad))
        for b in range(16):
            if r.random() < 0.15: tile_rect(d, ox, oy, b * 1.5 + 0.1, wy0 + 0.1, b * 1.5 + 1.4, wy1 - 0.1, np.array(glass) * 0.5 + 90)
        tile_rect(d, ox, oy, 0, wy1, TW, wy1 + 0.12, np.array(clad) * 0.75)
    if fins:
        for b in range(0, 8, 2): tile_rect(d, ox, oy, b * 3, 0, b * 3 + 0.5, TH, np.array(clad) * 1.06)


def v_grid(d, ox, oy, r, p):
    frame, glass, bay = p
    d.rectangle([ox, oy, ox + TS - 1, oy + TS - 1], fill=frame)
    for f in range(8):
        for b in range(int(TW / bay)):
            t = r.uniform(-6, 6)
            tile_rect(d, ox, oy, b * bay + 0.35, f * 3.5 + 0.45, (b + 1) * bay - 0.35, f * 3.5 + 3.1, np.array(glass) + t)
            tile_rect(d, ox, oy, b * bay + 0.35, f * 3.5 + 0.45, (b + 1) * bay - 0.35, f * 3.5 + 0.9, np.array(glass) + 35)


def v_punched(d, ox, oy, r, p):
    wall, ww, glass = p
    d.rectangle([ox, oy, ox + TS - 1, oy + TS - 1], fill=wall)
    for f in range(8):
        for b in range(8):
            x0 = b * 3 + (3 - ww) / 2
            col = glass if r.random() > 0.15 else np.array(wall) * 0.7
            tile_rect(d, ox, oy, x0, f * 3.5 + 1.0, x0 + ww, f * 3.5 + 2.6, col)
            tile_rect(d, ox, oy, x0 - 0.1, f * 3.5 + 2.6, x0 + ww + 0.1, f * 3.5 + 2.75, np.array(wall) * 1.08)


def facade_atlas():
    r = np.random.default_rng(23)
    TINTS = [(70, 92, 112), (62, 96, 98), (86, 96, 104), (112, 98, 80), (122, 132, 138), (44, 54, 64), (76, 104, 92), (92, 110, 130)]
    CLADS = [(226, 226, 222), (192, 190, 184), (206, 196, 176), (122, 124, 128), (162, 112, 88), (172, 178, 184), (150, 140, 128), (96, 98, 104)]
    GLASS = [(52, 64, 76), (60, 78, 92), (48, 70, 70), (70, 76, 84)]
    WALLS = [(214, 198, 170), (172, 98, 78), (200, 200, 194), (236, 232, 224), (152, 150, 146), (190, 170, 140)]
    variants = []
    for i in range(24): variants.append(("curtain", (TINTS[i % 8], [1.5, 1.2, 3.0][i // 8], [(40, 44, 50), (150, 158, 164), (110, 116, 122)][(i + i // 8) % 3], i % 2 == 0, i % 3 == 0)))
    for i in range(16): variants.append(("ribbon", (CLADS[i % 8], [0.5, 0.65][i // 8], GLASS[i % 4], i % 3 == 0)))
    for i in range(12): variants.append(("grid", (CLADS[(i * 3) % 8], GLASS[i % 4], [3.0, 1.5][i % 2])))
    for i in range(12): variants.append(("punched", (WALLS[i % 6], [1.4, 2.0][i // 6], GLASS[i % 4])))
    img = Image.new("RGB", (AT, AT), (0, 0, 0)); d = ImageDraw.Draw(img)
    info = []
    for k, (kind, p) in enumerate(variants):
        ox, oy = (k % 8) * TS, (k // 8) * TS
        {"curtain": v_curtain, "ribbon": v_ribbon, "grid": v_grid, "punched": v_punched}[kind](d, ox, oy, r, p)
        mean = np.asarray(img.crop((ox, oy, ox + TS, oy + TS)), dtype=np.float32).reshape(-1, 3).mean(0)
        info.append({"i": k, "kind": kind, "mean": [int(v) for v in mean]})
    img = noise(img, 3, 0.8)
    img.save(OUT / "facades.webp", quality=90, method=6)
    img.save(RAWT / "facades.png")
    (OUT / "facades.json").write_text(json.dumps({"tiles": 8, "tile_m": [TW, TH], "variants": info}), encoding="utf-8")
    print("wrote facades atlas:", len(info), "variants")


import json
facade_atlas()
