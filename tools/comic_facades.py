# Draws a slightly comic facade texture for every smashable building from its look (style, colours, window sizes —
# photo-checked where tools/LOOKS_BRIEF.md found a photo, guessed otherwise) and packs them into one atlas per area.
# Each tile is 4 bays x 4 floors of that building, so windows line up with its real floor height; the alpha channel is the
# window mask, which the engine uses for glass reflections and lit windows at night.
# usage: ~/.venvs/vault-plots/bin/python tools/comic_facades.py <area_id> [--sheet]
# In:  data/<area>.json, data/<area>.look.json        Out: site/<area>/facades.webp, data/<area>.json (+ t, tm per building)
import json, math, pathlib, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parent.parent
AID = sys.argv[1]
DATA = ROOT / "data" / f"{AID}.json"
data = json.loads(DATA.read_text(encoding="utf-8"))
look = json.loads((ROOT / "data" / f"{AID}.look.json").read_text(encoding="utf-8"))
# the engine's own style defaults (src/app.html STYLE), used when a look leaves a value out
STYLE = {
    "stone": dict(wall="#d6d0c2", glass="#2c3843", frame="#e9e7e1", bay=3.4, winW=0.52, winH=0.5),
    "brick": dict(wall="#8a4a38", glass="#28313a", frame="#e6e1d6", bay=3.0, winW=0.48, winH=0.55),
    "glass": dict(wall="#a9b2ba", glass="#3a5266", frame="#2b3036", bay=1.6, winW=0.9, winH=0.84),
    "concrete": dict(wall="#bab8b0", glass="#2b353f", frame="#8f9396", bay=4.0, winW=0.94, winH=0.42),
    "tan": dict(wall="#c7b394", glass="#2e3740", frame="#ece6d8", bay=3.2, winW=0.56, winH=0.5),
    "ribbon": dict(wall="#c9c8c2", glass="#2d3b47", frame="#5d646b", bay=1.5, winW=0.97, winH=0.4),
    "dorm": dict(wall="#dccdb2", glass="#2c343c", frame="#f1ece2", bay=2.4, winW=0.46, winH=0.46),
}
ATLAS, TILE, SS = 2048, 128, 4            # atlas size, tile size, supersampling for clean comic outlines
N = ATLAS // TILE
INK = (34, 30, 38)


def rgb(h): h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def shade(c, k): return tuple(max(0, min(255, int(v * k))) for v in c)


def comic_tile(lk, seed):
    """One tile = 4 bays x 4 floors, drawn big and scaled down. Flat colours, thick ink lines, a glare streak per pane.
    Returns (RGB image, window mask L image)."""
    st = {**STYLE.get(lk.get("style", "concrete"), STYLE["concrete"]), **{k: v for k, v in lk.items() if v is not None}}
    S = TILE * SS
    wall, glass, frame = rgb(st["wall"]), rgb(st["glass"]), rgb(st["frame"])
    def pop(c, k=1.35):                                                    # comic: push colours away from grey
        m = sum(c) / 3
        return tuple(max(0, min(255, int(m + (v - m) * k))) for v in c)
    wall = pop(wall, 1.3)
    glass_c = pop(tuple(min(255, int(v * 1.3 + 22)) for v in glass), 1.5)
    img = Image.new("RGB", (S, S), wall); d = ImageDraw.Draw(img)
    msk = Image.new("L", (S, S), 0); dm = ImageDraw.Draw(msk)
    glare = Image.new("L", (S, S), 0); dg = ImageDraw.Draw(glare)
    r = np.random.default_rng(seed)
    bw, fh = S / 4, S / 4
    line = max(3, int(SS * 3.2))                                      # bold ink that survives distance
    if lk.get("style") == "glass":
        d.rectangle([0, 0, S, S], fill=glass_c); dm.rectangle([0, 0, S, S], fill=255)
        for f in range(4):
            y0 = f * fh
            d.rectangle([0, y0 + fh * 0.86, S, y0 + fh], fill=shade(glass_c, 0.72)); dm.rectangle([0, y0 + fh * 0.86, S, y0 + fh], fill=40)
            for b in range(4):
                if r.random() < 0.12: d.rectangle([b * bw + line, y0 + line, (b + 1) * bw - line, y0 + fh * 0.84], fill=shade(glass_c, 1.3))
        for b in range(5): d.line([(b * bw, 0), (b * bw, S)], fill=INK, width=line)
        for b in range(4): d.line([(b * bw + bw / 2, 0), (b * bw + bw / 2, S)], fill=frame, width=max(1, line // 2))
        for f in range(5): d.line([(0, f * fh), (S, f * fh)], fill=INK, width=line)
        for k in (-0.2, 0.35):
            dg.polygon([(S * k, S), (S * (k + 0.16), S), (S * (k + 0.66), 0), (S * (k + 0.5), 0)], fill=115)
    else:
        ww, wh = st["winW"], st["winH"]
        if lk.get("style") == "brick":
            for y in range(0, S, max(2, int(fh / 7))): d.line([(0, y), (S, y)], fill=shade(wall, 0.82), width=max(1, SS))
        for f in range(4):
            y0 = f * fh
            sill = (1 - wh) * 0.45 * fh
            y1 = y0 + sill + wh * fh
            if lk.get("style") == "ribbon":
                d.rectangle([0, y0 + sill, S, y1], fill=glass_c, outline=INK, width=line); dm.rectangle([0, y0 + sill, S, y1], fill=255)
                for b in range(9): d.line([(b * S / 8, y0 + sill), (b * S / 8, y1)], fill=INK, width=max(1, line // 2))
                for b in range(4): dg.line([(b * bw + bw * 0.1, y1 - wh * fh * 0.2), (b * bw + bw * 0.3, y0 + sill + wh * fh * 0.2)], fill=200, width=line)
            else:
                for b in range(4):
                    x0 = b * bw + (1 - ww) * bw / 2; x1 = x0 + ww * bw
                    fill = shade(glass_c, 1.35) if r.random() < 0.12 else glass_c
                    d.rectangle([x0 - line * 2, y0 + sill - line * 2, x1 + line * 2, y1 + line * 2], fill=frame)       # frame
                    d.rectangle([x0, y0 + sill, x1, y1], fill=fill, outline=INK, width=line)                        # pane
                    dm.rectangle([x0, y0 + sill, x1, y1], fill=255)
                    if (x1 - x0) > 0.35 * bw: d.line([((x0 + x1) / 2, y0 + sill), ((x0 + x1) / 2, y1)], fill=INK, width=max(1, line // 2))
                    gx = x0 + (x1 - x0) * 0.2
                    dg.line([(gx, y1 - (y1 - y0 - sill) * 0.22), (gx + (x1 - x0) * 0.22, y0 + sill + (y1 - y0 - sill) * 0.22)], fill=200, width=line)
                    d.rectangle([x0 - line * 3, y1 + line * 2, x1 + line * 3, y1 + line * 4], fill=shade(wall, 1.12))   # sill
            d.line([(0, y0 + fh - 2), (S, y0 + fh - 2)], fill=shade(wall, 0.76), width=max(2, SS))                   # slab line
    img = Image.composite(Image.new("RGB", (S, S), (255, 255, 255)), img, glare)                                    # glare
    return img.resize((TILE, TILE), Image.LANCZOS), msk.resize((TILE, TILE), Image.LANCZOS)


# group identical looks so similar buildings share a tile; photo-checked named buildings keep their own
tiles, key_of, tile_of = [], {}, {}
for b in data["buildings"]:
    lk = look.get(b["id"], {"style": "concrete"})
    fh = b["h"] / max(b["lv"], 1)
    bay = lk.get("bay") or STYLE.get(lk.get("style", "concrete"), STYLE["concrete"])["bay"]
    key = json.dumps({k: lk.get(k) for k in ("style", "wall", "glass", "frame", "bay", "winW", "winH")}, sort_keys=True)
    if key not in key_of:
        if len(tiles) >= N * N: key = next(iter(key_of))            # atlas full: reuse the first tile
        else:
            key_of[key] = len(tiles); tiles.append(lk)
    b["t"] = key_of[key]
    b["tm"] = [round(4 * bay, 2), round(4 * fh, 2)]                 # metres covered by one tile (4 bays x 4 floors)
atlas = Image.new("RGBA", (ATLAS, ATLAS), (0, 0, 0, 0))
for i, lk in enumerate(tiles):
    c, m = comic_tile(lk, 7 + i)
    c.putalpha(m.point(lambda v: 8 + v * 247 // 255))       # alpha never 0, so WebP keeps the wall colour
    atlas.paste(c, ((i % N) * TILE, (i // N) * TILE))
out = ROOT / "site" / AID; out.mkdir(parents=True, exist_ok=True)
atlas.save(out / "facades.webp", quality=90, method=6, exact=True)
DATA.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(f"{AID}: {len(tiles)} facade tiles for {len(data['buildings'])} buildings → site/{AID}/facades.webp "
      f"{(out / 'facades.webp').stat().st_size // 1024} KB")
if "--sheet" in sys.argv:
    sheet = Image.new("RGB", (8 * 140, ((min(len(tiles), 32) + 7) // 8) * 140), (40, 38, 44))
    for i in range(min(len(tiles), 32)):
        t = atlas.crop(((i % N) * TILE, (i // N) * TILE, (i % N + 1) * TILE, (i // N + 1) * TILE)).convert("RGB")
        sheet.paste(t, ((i % 8) * 140 + 6, (i // 8) * 140 + 6))
    sheet.save(ROOT / "raw" / f"{AID}_facades_sheet.png")
