# Builds site/<area>/index.html from src/app.html (the SMASH 대학교 engine), data/<area>.json, data/<area>.look.json
# and config.json + areas.json. One page per sub-area, like one page per campus in SMASH 대학교.
# usage: python3 tools/assemble.py <area_id> [<area_id> …]      (no ids: every area that has data)
import html, json, pathlib, shutil, sys

root = pathlib.Path(__file__).resolve().parent.parent
base = json.loads((root / "config.json").read_text(encoding="utf-8"))
areas = json.loads((root / "areas.json").read_text(encoding="utf-8"))
tpl = (root / "src" / "app.html").read_text(encoding="utf-8")
assert all(k in tpl for k in ("__CAU_DATA__", "__TITLE__", "__PAGE_TITLE__", "__INTRO__"))
ids = sys.argv[1:] or [p.stem for p in (root / "data").glob("*.json") if not p.stem.endswith(".look")]
e = lambda v: html.escape(v, quote=True)

for aid in ids:
    a = areas[aid]
    data = json.loads((root / "data" / f"{aid}.json").read_text(encoding="utf-8"))
    lookf = root / "data" / f"{aid}.look.json"
    cfg = dict(base)
    cfg.update({"code": aid.upper(), "school": a["district"], "fullName": f"{a['district']} {a['name']}",
                "campusName": f"{a['district']} {a['name']}", "url": f"{base['url']}{aid}/",
                "tagline": f"{a['district']} {a['name']}를 부셔 (월요병 해소)",
                "description": f"{a['district']} {a['name']}의 실제 회사 건물을 3D로 부수는 스트레스 해소 게임",
                "ogAlt": f"무너지는 {a['district']} {a['name']} 3D 화면과 SMASH 회사 제목",
                "look": json.loads(lookf.read_text(encoding="utf-8")) if lookf.exists() else {}})
    data["config"] = cfg
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    place = cfg["fullName"]
    page_title = f"{place} 부수기 게임 | 회사 건물 3D | {cfg['title']}"
    desc = (cfg["description"] + "입니다. 폭탄, 야구 배트, 레이저, 운석, 지진, 핵폭탄으로 건물을 무너뜨리고, "
            "설치 없이 휴대폰과 PC 브라우저에서 무료로 할 수 있습니다.")
    page = (tpl.replace("__CAU_DATA__", blob).replace("__PAGE_TITLE__", html.escape(page_title))
            .replace("__TITLE__", html.escape(cfg["title"])).replace("__INTRO__", html.escape(desc)))
    head, rest = page.split('<div id="app">', 1)
    url = cfg["url"]
    gc = f'<script data-goatcounter="{e(cfg["goatcounter"])}" async src="https://gc.zgo.at/count.js"></script>\n' if cfg.get("goatcounter") else ""
    doc = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(url)}">
<meta property="og:title" content="{e(cfg['title'] + ' — ' + place + ' 부수기 게임')}">
<meta property="og:site_name" content="SMASH 회사">
<meta property="og:locale" content="ko_KR">
<meta property="og:description" content="{e(cfg['tagline'])}">
<meta property="og:type" content="website">
<meta property="og:url" content="{e(url)}">
<meta property="og:image" content="{e(url)}og.png">
<meta property="og:image:alt" content="{e(cfg['ogAlt'])}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="../icon-32.png" sizes="32x32">
<link rel="icon" href="../icon-512.png" sizes="512x512">
<link rel="apple-touch-icon" href="../icon-180.png">
{gc}{head.strip()}
</head>
<body>
<div id="app">{rest.rstrip()}
</body>
</html>
"""
    out = root / "site" / aid
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(doc, encoding="utf-8")
    shutil.copy(root / "site" / "pp-stub.js", out / "pp-stub.js")   # the engine's import map points at ./pp-stub.js
    for g in ("ground.webp", "ground_m.webp"):                          # aerial photo made by tools/prep_area.py
        src = root / "site" / "areas" / aid / g
        if src.exists(): shutil.copy(src, out / g)
    print(f"site/{aid}/index.html", len(doc.encode()) // 1024, "KB")
