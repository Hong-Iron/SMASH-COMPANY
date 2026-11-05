# Builds site/index.html (the SMASH 회사 hub) from hub/index.html, areas.json, data/<area>.json and hub/config.json.
# Area cards are also written into the HTML so search crawlers see every game link. Each card image is a crop of the
# area's aerial photo (site/<area>/card.webp). Forked from the SMASH 대학교 hub (Hong-Iron/SMASH tools/build.py).
# usage: ~/.venvs/vault-plots/bin/python hub/build.py      (Pillow)
import html, json, pathlib
from PIL import Image
here = pathlib.Path(__file__).resolve().parent
root = here.parent
tpl = (here / "index.html").read_text(encoding="utf-8")
cfg = json.loads((here / "config.json").read_text(encoding="utf-8"))
areas = json.loads((root / "areas.json").read_text(encoding="utf-8"))
nf = here / "notices.json"
notices = json.loads(nf.read_text(encoding="utf-8")) if nf.exists() else []
schools = []      # the template calls them schools; here each one is an 업무지구 page
for aid, a in areas.items():
    page = root / "site" / aid / "index.html"
    dataf = root / "data" / f"{aid}.json"
    if not page.exists() or not dataf.exists(): continue
    d = json.loads(dataf.read_text(encoding="utf-8"))
    names = sorted({b["n"] for b in d["buildings"] if b.get("n")})
    card = root / "site" / aid / "card.webp"
    g = root / "site" / aid / "ground_m.webp"
    if g.exists() and (not card.exists() or card.stat().st_mtime < g.stat().st_mtime):
        im = Image.open(g).convert("RGB"); w, h = im.size
        im.crop((0, int(h * 0.24), w, int(h * 0.24) + int(w * 315 / 600))).resize((600, 315), Image.LANCZOS).save(card, quality=82)
    schools.append({"code": aid.upper(), "name": a["district"], "campus": f"{a['district']} {a['name']}", "url": f"{aid}/",
                    "buildings": len(d["buildings"]), "nameEn": a.get("nameEn", ""), "region": a.get("region", ""),
                    "added": a.get("added", "2026-11-06"), "lat": a["lat"], "lon": a["lon"], "names": " ".join(names)})
for k in ("__NOTICES__", "__SCHOOLS__", "__HUB_CONFIG__", "<!--GOATCOUNTER-->", "<!--JSONLD-->", "__CARDS__", "__COUNT__", "__MAP__"):
    assert k in tpl, k
e = lambda v: html.escape(str(v), quote=True)
blob = lambda v: json.dumps(v, ensure_ascii=False).replace("</", "<\\/")
gc = f'<script data-goatcounter="{e(cfg["goatcounter"])}" async src="https://gc.zgo.at/count.js"></script>' if cfg.get("goatcounter") else ""
pub = {k: cfg[k] for k in ("supabaseUrl", "supabaseKey", "rankingPaused") if cfg.get(k)}
by_name = sorted(schools, key=lambda s: s["name"])  # same order as the page's default "이름순"; the script re-sorts with Korean collation
cards = "".join(
    f'<a class="card" href="{e(s["url"])}"><img src="{e(s["url"])}card.webp" alt="{e(s["campus"])}가 부서지는 게임 화면" loading="lazy" width="600" height="315" onerror="this.onerror=null;this.src=this.src.replace(\'card.webp\',\'og.png\')">'
    f'<div class="body"><span class="code">SMASH {e(s["name"])}</span><span class="name">{e(s["campus"])}</span>'
    f'<span class="region">{e(s.get("region", ""))}</span><span class="meta"></span><span class="go">부수러 가기 →</span></div></a>'
    for s in by_name)
def notice(n):
    m, d = (int(x) for x in n["date"].split("-")[1:])
    return (f'<a class="notice" href="{e(n["url"])}" data-id="{e(n["id"])}" data-until="{e(n.get("until", ""))}">'
            f'<img src="{e(n["image"])}" alt="{e(n["title"])} 화면" width="1200" height="630"{' class="px"' if n.get("pixel") else ''}>'
            f'<div class="body"><span class="tag">{e(n.get("tag", "공지"))} · <time datetime="{e(n["date"])}">{m}월 {d}일</time></span>'
            f'<strong>{e(n["title"])}</strong><span class="go">{e(n.get("cta", "보러 가기"))} →</span></div></a>')
notice_html = (f'<section class="notices" aria-labelledby="notice-title"><h2 class="sec-title" id="notice-title">공지</h2>'
               f'{"".join(notice(n) for n in notices)}</section>') if notices else ""
ld = {
    "@context": "https://schema.org",
    "@graph": [
        {"@type": "WebSite", "name": "SMASH 회사", "alternateName": "우리 회사 부수기 게임", "url": cfg["url"], "inLanguage": "ko"},
        {"@type": "ItemList", "name": "SMASH 회사 업무지구 목록", "numberOfItems": len(schools),
         "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": cfg["url"] + s["url"], "name": f'{s["campus"]} 부수기 게임'} for i, s in enumerate(by_name)]},
        # breadcrumb: Google shows "Hong-Iron › SMASH 대학교" in place of the bare address
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Hong-Iron", "item": "https://hong-iron.github.io/"},
            {"@type": "ListItem", "position": 2, "name": "SMASH 회사", "item": cfg["url"]}]},
    ],
}
# 지도: 남한 시도 경계(KOSTAT 2013, 자유 이용 — github.com/southkorea/southkorea-maps)를 8개 구역으로 묶어 SVG로 그린다.
# 학교는 같은 투영의 좌표(mx, my)와 속한 구역(sec)을 갖는다
import math
LON0, LAT1, K = 124.5, 38.75, 100.0
KX = K * math.cos(math.radians(36.2))
INSET_DX, INSET_DY = -1.3, 0.95   # 울릉도·독도(동경 130.5° 동쪽)는 지도 오른쪽 위 바다의 상자 안으로 옮겨 그린다
proj = lambda lon, lat: (round((lon - LON0) * KX, 1), round((LAT1 - lat) * K, 1))
SECTIONS = [("seoul", "서울", {"11"}), ("gyeonggi", "경기·인천", {"23", "31"})]   # SMASH 회사: the capital area only
prov = json.loads((here / "korea_provinces.json").read_text(encoding="utf-8"))
def rings_of(f):
    g = f["geometry"]; polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    return [r for poly in polys for r in poly[:1]]          # 바깥 테두리만 (시도 경계에는 구멍이 없다)
def moved(ring):
    shift = min(lon for lon, _ in ring) > 130.5
    return [proj(lon + (INSET_DX if shift else 0), lat + (INSET_DY if shift else 0)) for lon, lat in ring]
def ring_d(pts):
    out, last = [], None
    for q in pts:
        if q != last: out.append(q); last = q
    return "M" + "L".join(f"{x:g},{y:g}" for x, y in out) + "Z" if len(out) > 2 else ""
def inside(x, y, ring):
    c = False
    for i in range(len(ring)):
        (x1, y1), (x2, y2) = ring[i], ring[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c
sec_rings = {k: [] for k, _, _ in SECTIONS}; sec_of_code = {c: k for k, _, cs in SECTIONS for c in cs}
for f in prov["features"]:
    if f["properties"]["code"] in sec_of_code: sec_rings[sec_of_code[f["properties"]["code"]]] += [moved(r) for r in rings_of(f)]
def label_point(rings):
    # 구역 안에서 경계에서 가장 먼 점(이름표 자리): 큰 섬들만 보고 격자로 찾는다
    big = sorted(rings, key=lambda r: -abs(sum(r[i][0] * r[i - 1][1] - r[i - 1][0] * r[i][1] for i in range(len(r)))))[:3]
    xs = [p[0] for r in big for p in r]; ys = [p[1] for r in big for p in r]
    edge = [p for r in big for p in r[::2]]
    best, bd = None, -1
    for i in range(36):
        for j in range(36):
            x = min(xs) + (max(xs) - min(xs)) * (i + .5) / 36; y = min(ys) + (max(ys) - min(ys)) * (j + .5) / 36
            if not any(inside(x, y, r) for r in big): continue
            d = min((x - ex) ** 2 + (y - ey) ** 2 for ex, ey in edge)
            if d > bd: bd, best = d, (round(x, 1), round(y, 1))
    return best
# 학교가 어느 구역인지: 위치가 들어 있는 시도로, 해안선 밖(매립지·섬)이면 가장 가까운 구역 경계점으로
for s in schools:
    s["mx"], s["my"] = proj(s["lon"], s["lat"])
    hit = [k for k, rs in sec_rings.items() if any(inside(s["mx"], s["my"], r) for r in rs)]
    s["sec"] = hit[0] if hit else min(sec_rings, key=lambda k: min((s["mx"] - x) ** 2 + (s["my"] - y) ** 2 for r in sec_rings[k] for x, y in r))
secs = []
groups = []
for k, name, _ in SECTIONS:
    rs = sec_rings[k]; xs = [p[0] for r in rs for p in r]; ys = [p[1] for r in rs for p in r]
    lx, ly = proj(127.42, 37.12) if k == "gyeonggi" else label_point(rs)   # 경기 이름표는 서울과 겹치지 않게 남동쪽(이천·안성 부근)에
    n = sum(1 for s in schools if s["sec"] == k)
    secs.append({"k": k, "name": name, "bbox": [min(xs), min(ys), max(xs), max(ys)], "lx": lx, "ly": ly, "n": n})
    groups.append(f'<g class="sec" data-sec="{k}"><path d="{"".join(ring_d(r) for r in rs)}"/></g>')
dx, dy = proj(131.8667 + INSET_DX, 37.2417 + INSET_DY); ux, uy = proj(130.87 + INSET_DX, 37.5 + INSET_DY)
ix0, iy0 = proj(130.65 + INSET_DX, 37.7 + INSET_DY); ix1, iy1 = proj(132.0 + INSET_DX, 37.12 + INSET_DY)
extra = ""
_unused = (f'<g class="inset"><rect x="{ix0}" y="{iy0}" width="{round(ix1 - ix0, 1)}" height="{round(iy1 - iy0, 1)}" rx="3"/>'
         f'<circle cx="{dx}" cy="{dy}" r="1.6"/><circle cx="{dx + 2.4}" cy="{dy + 0.6}" r="1.2"/>'
         f'<text class="isl" x="{dx + 1}" y="{dy - 6}" text-anchor="middle">독도</text><text class="isl" x="{ux}" y="{uy - 9}" text-anchor="middle">울릉도</text></g>')
W, Hh = proj(130.78, 33.0)   # (the page frames the visible sections itself)
map_svg = (f'<svg class="kmap" id="kmap" viewBox="0 0 {W} {Hh}" data-w="{W}" data-h="{Hh}" role="img" aria-label="수도권 지도: 구역을 누르면 그 지역 업무지구가 핀으로 나온다">'
           f'<rect class="sea" x="-2000" y="-2000" width="5000" height="5000"/><g id="kmap-land">{"".join(groups)}{extra}</g>'
           f'<g id="kmap-labels"></g><g id="kmap-pins"></g></svg>'
           f'<script type="application/json" id="map-sections">{blob(secs)}</script>')
out = (tpl.replace("__SCHOOLS__", blob(schools)).replace("__HUB_CONFIG__", blob(pub)).replace("<!--GOATCOUNTER-->", gc)
       .replace("<!--JSONLD-->", '<script type="application/ld+json">' + blob(ld) + "</script>")
       .replace("__NOTICES__", notice_html).replace("__MAP__", map_svg).replace("__CARDS__", cards).replace("__COUNT__", str(len(schools)))
       # 랭킹을 멈춘 동안(config rankingPaused)은 안내 카드를 처음부터 보이고, 랭킹 서버는 부르지 않는다
       .replace("__RANK_DOWN_HIDDEN__", "" if cfg.get("rankingPaused") else " hidden"))
(root / "site" / "index.html").write_text(out, encoding="utf-8")
print("site/index.html", len(out.encode()) // 1024, "KB,", len(schools), "areas")
