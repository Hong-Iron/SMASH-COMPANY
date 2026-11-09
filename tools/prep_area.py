# Turns raw OSM + terrarium tiles into local-metre data for the Blender build, and paints the ground texture.
# usage: ~/.venvs/vault-plots/bin/python tools/prep_area.py <area_id>     (numpy, Pillow)
# Coordinates: x east, y north, metres from the area centre; z up (Blender convention).
# Output: raw/<id>/prep.json (buildings, trees, terrain grid), raw/<id>/ground.png (placeholder until the aerial mosaic)
import json, math, pathlib, re, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parent.parent
AID = sys.argv[1]
AREA = json.loads((ROOT / "areas.json").read_text(encoding="utf-8"))[AID]
RAW = ROOT / "raw" / AID
LAT0, LON0, SIZE = AREA["lat"], AREA["lon"], AREA["size"]
HALF = SIZE / 2
phi = math.radians(LAT0)
MLAT = 111132.92 - 559.82 * math.cos(2 * phi) + 1.175 * math.cos(4 * phi)
MLON = 111412.84 * math.cos(phi) - 93.5 * math.cos(3 * phi)
STOREY = 3.5
DEM_Z = 15
GRID = 8.0      # terrain grid spacing in metres
TEX = 4096      # ground texture size

# building types and names that are never smashable (homes, schools, care, worship, public safety, government)
OFF_TYPES = {"apartments", "residential", "house", "detached", "semidetached_house", "terrace", "dormitory",
             "school", "kindergarten", "university", "college", "hospital", "clinic", "church", "temple",
             "chapel", "mosque", "shrine", "government", "public", "civic", "fire_station", "police",
             "military", "embassy", "train_station", "transportation"}
OFF_NAME = re.compile(r"아파트|빌라|주택|오피스텔|초등학교|중학교|고등학교|학교|유치원|어린이집|교회|성당|사찰|절$|병원|의원|"
                      r"보건|주민센터|행정복지센터|구청|시청|소방|경찰|파출소|지구대|군부대|대사관|영사관|도서관|청사|정부|[가-힣]{2,}청(\s|$)|"
                      r"법원|검찰|세무서|등기소|우체국|의회|국회|선거관리|병무|119|안전센터|복지관|커뮤니티센터|요양|노인|\d{3,4}동$|^\d{3,4}$|"
                      r"역$|비즈텔|"         # 역$: railway stations; 비즈텔: officetel brand that the WORK_NAME exemption would let through
                      r"(?<![호모])텔$|고시원|기숙사|다세대|저택|邸宅|메종|레지던스|큐브스테이트|여고$|여중$|학과|"   # officetels (○○텔, not 호텔·모텔), dorms, schools
                      r"복지센터|치안센터|우편|세관|기념관|측정소|공원관리|역사$|정거장$|문화역서울|선교|심인당|진리회|행복의집|야생동물|계사$|축사$|"
                      r"불교|조계|템플스테이|원불교|교당$|조계사|불광사|금수사|향림사|"
                      r"단독|연립|마을회관|동사무소|발전소|장애인|유소년센터|합숙소|"
                      r"마을$|택지개발지구|지식정보타운\s*(단\d?|\d)|"
                      r"문화원$|주한|시민회관|구민회관|세종문화회관|고덕문화회관|"
                      r"대통령|관저|청와대|장례|주상복합|구립|시립|국립|도립|기술교육원|(도로|차량|등록|시설|승무|수도|하수|녹지|공원)사업소|민원|아동교육|"
                      r"타워팰리스|엠프리스|르웨스트|미르웰|드미라벨|아카데미스위트|[Pp]ost ?[Vv]ille|VIEW$|자원화시설|겸재정선미술관|식물문화센터|역\(\d호선\)")   # 11-09: 한남 대통령 관저, 대치 타워팰리스, 마곡 시니어 주거·오피스텔   # public culture halls (city/district-run), foreign cultural centres   # apartment complexes named ○○마을 (판교 봇들마을·백현마을), 과천 lot names   # 11-09: 과천 단독주택 lots, row houses, public halls, power plants    # temples the 사찰/절$ rule misses (11-08)


# homes without a use code (e.g. all of Daegu in 건물통합정보): apartment brands, and complex blocks numbered "101동"
APT_NAME = re.compile(r"맨션|빌라|위브|메르디앙|아너스|캐슬|예가|푸르지오|파크드림|리젠시|라온프라이빗|데시앙|하이빌|그린빌|나우빌|"
                      r"포레스트|유쉘|하늘채|래미안|힐스테이트|아이파크|더샵|e편한세상|이편한세상|자이(\s|$|\d)|스위첸|수자인|"
                      r"꿈에그린|해링턴|스타힐스|더휴|SK ?뷰|에스케이뷰|아크로|휴먼시아|리첸시아|센트레빌|어울림|코아루|노르웨이숲|"
                      r"빌리지|타운$|\d단지|맨숀|하이츠|하임$|하우스$|빌(\s|$)|팰리스|브라운스톤|KAN$|아파트|"
                      r"펜테리움|디엠시티|로얄듀크|아데나루체|아스테리움|인텔리지|하이엘|"
                      r"빌\s?[A-Z\dⅠ-Ⅹ]+차?$|\d+차$|[Hh]ouse$|파크뷰|지웰|베네리치|크로시티|드림팔레스|또레로사|로즈빌|아펠리체|"
                      r"엘리시아|부띠크시티|코보스카운티|소미골드|케렌시아|성운힐스|트랭퀼|가원재|"
                      r"(?i:house)|(?i:villa)|홈$|힐$|S-?클래스|아르테온|그라시움|리버파크|아르누보|리체$|펠리체|스위트뷰")   # 11-08: villas "위너빌A", "○○ 4차" phases, residential brands
APT_DC = re.compile(r"\d{3,4}동?")
WORK_NAME = re.compile(r"센터|타워|밸리|벨리|호텔|테크|지식|비즈|빌딩|오피스$|산업|사옥|프라자|플라자|스퀘어|몰")


def ko_name(t):
    """OSM name, or name:ko when the name has no Hangul (e.g. name=Shinsegae, name:ko=신세계)."""
    n = t.get("name") or ""
    return n if re.search("[가-힣]", n) else (t.get("name:ko") or n)


# label only (the lock rules above see the raw name): VWorld names like "고잔동 632-7 판매시설 (홍길동)" carry the owner's
# name, so the address and use go and only a company in the brackets is kept; unit numbers like "(제7호)" or "823-2" go
COMPANY = re.compile(r"\(주\)|㈜|주식회사|\(유\)|유한|회사|산업|공업|교역|전자|테크|화학|빌딩|센터|주차장|교육|엔터|[A-Za-z]{2,}")


def label(n):
    n = n.strip()
    if re.search(r"허가|^no\.?\s*\d", n, re.I): return ""          # "건축허가번호(93-311호)", "NO. 160": permit numbers, not names
    m = re.match(r"^\S*[동가리로길]\s+\d+(?:-\d+)?(?:번지)?(?:외\s*\d+\s*필지)?(?:\s+(.*))?$", n)   # "상대원동 1318-1외1필지 (owner)", "삼정동 308-5"; not "○○벨리 2차"
    if m:
        rest = m.group(1) or ""
        b = re.match(r".*\s\((.+)\)\s*$", " " + rest)
        n = b.group(1) if b and COMPANY.search(b.group(1)) else ""
    m = re.match(r"^\S*[동리읍면]\s+\S*시설\s*\((.+)\)$", n)        # "도원동  제2종근린생활시설 (김창배)": no lot number
    if m: n = m.group(1) if COMPANY.search(m.group(1)) else ""
    # owner names after a company: "그랜드건설(주)대표;임도영", "HB한남동빌딩 ((주)에이치비콥 문성준)"; a 3-syllable word
    # ending like 공장·지점·본관·연구소 is a place, not a person
    person = r"[가-힣]{2}[가-힣](?<![장점관소사터딩워동실층호])"
    n = re.sub(r"\s*대표[;:]?\s*" + person + r"(\)?)$", r"\1", n)
    n = re.sub(r"((?:\(주\)|㈜|주식회사)[^()\s]*)\s+" + person + r"(\)?)$", r"\1\2", n)
    return n if len(re.sub(r"[\W\d_제호층내]", "", n)) >= 2 else ""


def ll2xy(lat, lon):
    return (lon - LON0) * MLON, (lat - LAT0) * MLAT


def ring_xy(geom):
    return [ll2xy(p["lat"], p["lon"]) for p in geom]


def area_of(r):
    a = 0.0
    for (x0, y0), (x1, y1) in zip(r, r[1:] + r[:1]):
        a += x0 * y1 - x1 * y0
    return a / 2


def centroid(r):
    xs, ys = zip(*r)
    return sum(xs) / len(xs), sum(ys) / len(ys)


def inside(pt, r):
    x, y = pt; c = False
    for (x0, y0), (x1, y1) in zip(r, r[1:] + r[:1]):
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0 + 1e-12) + x0: c = not c
    return c


def num(v):
    m = re.match(r"\s*([\d.]+)", str(v or ""))
    return float(m.group(1)) if m else None


# ---------- terrain from terrarium tiles ----------
def load_dem():
    tiles = {}
    for f in (RAW / "dem").glob(f"{DEM_Z}_*.png"):
        _, x, y = f.stem.split("_")
        a = np.asarray(Image.open(f).convert("RGB"), dtype=np.float64)
        tiles[(int(x), int(y))] = a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768
    n = 2 ** DEM_Z

    def h(lat, lon):
        fx = (lon + 180) / 360 * n
        fy = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
        tx, ty = int(fx), int(fy)
        px, py = (fx - tx) * 256, (fy - ty) * 256
        t = tiles.get((tx, ty))
        if t is None: return None
        i, j = min(int(py), 255), min(int(px), 255)
        return float(t[i, j])
    return h


demh = load_dem()
nx = int(SIZE / GRID) + 1
xs = np.linspace(-HALF, HALF, nx)
zgrid = np.zeros((nx, nx))
for j, y in enumerate(xs):
    for i, x in enumerate(xs):
        lat, lon = LAT0 + y / MLAT, LON0 + x / MLON
        zgrid[j, i] = demh(lat, lon) or 0.0
# smooth 1 cell (terrarium at z15 is ~4 m/px but noisy around buildings) and make heights relative to the lowest point
k = np.ones((3, 3)) / 9
pad = np.pad(zgrid, 1, mode="edge")
zgrid = sum(pad[a:a + nx, b:b + nx] * k[a, b] for a in range(3) for b in range(3))
ZBASE = float(zgrid.min())
zgrid -= ZBASE


def ground_z(x, y):
    fx = (x + HALF) / GRID; fy = (y + HALF) / GRID
    i = min(max(int(fx), 0), nx - 2); j = min(max(int(fy), 0), nx - 2)
    tx, ty = fx - i, fy - j
    z00, z10, z01, z11 = zgrid[j, i], zgrid[j, i + 1], zgrid[j + 1, i], zgrid[j + 1, i + 1]
    return float((z00 * (1 - tx) + z10 * tx) * (1 - ty) + (z01 * (1 - tx) + z11 * tx) * ty)


# ---------- buildings ----------
osm = json.loads((RAW / "osm.json").read_text(encoding="utf-8"))
items = []
for e in osm["elements"]:
    t = e.get("tags", {})
    if "building" not in t and "building:part" not in t: continue
    if t.get("location") == "underground" or t.get("tunnel") == "yes" or t.get("building") == "underground": continue
    if e["type"] == "way" and "geometry" in e:
        ring = ring_xy(e["geometry"])
    elif e["type"] == "relation":
        outers = [m for m in e.get("members", []) if m.get("role") == "outer" and "geometry" in m]
        if not outers: continue
        ring = max((ring_xy(m["geometry"]) for m in outers), key=lambda r: abs(area_of(r)))
    else:
        continue
    if len(ring) > 2 and ring[0] == ring[-1]: ring = ring[:-1]
    if len(ring) < 3: continue
    a = area_of(ring)
    if abs(a) < 12: continue
    if a < 0: ring = ring[::-1]                      # counter-clockwise
    cx, cy = centroid(ring)
    if abs(cx) > HALF or abs(cy) > HALF: continue   # keep buildings whose centre is in the box
    items.append({"osm": f"{e['type'][0]}{e['id']}", "ring": ring, "tags": t, "part": "building:part" in t,
                  "area": abs(a), "c": (cx, cy)})

parts = [b for b in items if b["part"]]
outlines = [b for b in items if not b["part"]]
for b in outlines:
    kids = [p for p in parts if abs(p["c"][0] - b["c"][0]) < 200 and abs(p["c"][1] - b["c"][1]) < 200 and inside(p["c"], b["ring"])]
    if kids:
        # Simple 3D Buildings: the parts carry the real massing (podium, towers, raised bridges), so the outline is skipped
        b["skip"] = True
        for p in kids: p.setdefault("parent", b)


# ---------- VWorld building data (heights, floors, use codes, names) when tools/vworld.py has run ----------
# 건축물 용도 코드: 01000 단독주택, 02000 공동주택, 06000 종교, 09000 의료, 11000 노유자, 23000 교정·군사 → never smashable
VW_OFF = {"01000", "02000", "06000", "09000", "11000", "23000"}
VW_USE = {"14000": "office", "03000": "commercial", "04000": "commercial", "07000": "retail", "10000": "research",
          "17000": "industrial", "18000": "warehouse", "20000": "garage"}
vw = json.loads((RAW / "vworld_bld.json").read_text(encoding="utf-8")) if (RAW / "vworld_bld.json").exists() else []
for vi, v in enumerate(vw):
    v["idx"] = vi
    if len(v["ring"]) > 1 and v["ring"][0] == v["ring"][-1]: v["ring"] = v["ring"][:-1]
    v["area"] = abs(area_of([tuple(p) for p in v["ring"]])) if len(v["ring"]) > 2 else 0
    v["c"] = centroid(v["ring"]) if v["ring"] else (1e9, 1e9)


def overlap(a, b, n=14):
    # share of polygon a's area that lies inside polygon b, by grid sampling
    xs_ = [p[0] for p in a]; ys_ = [p[1] for p in a]
    hit = tot = 0
    for i in range(n):
        for j in range(n):
            p = (min(xs_) + (i + 0.5) * (max(xs_) - min(xs_)) / n, min(ys_) + (j + 0.5) * (max(ys_) - min(ys_)) / n)
            if inside(p, a):
                tot += 1
                if inside(p, b): hit += 1
    return hit / tot if tot else 0.0


def vw_match(b):
    best, bo = None, 0.0
    for v in vw:
        if v["area"] < 10 or abs(v["c"][0] - b["c"][0]) > 120 or abs(v["c"][1] - b["c"][1]) > 120: continue
        o = overlap(b["ring"], v["ring"]) * b["area"]
        if o > bo: best, bo = v, o
    if best and bo >= 0.4 * min(b["area"], best["area"]):
        best["used"] = True
        return best
    return None


for b in items:
    b["vw"] = vw_match(b) if not b.get("skip") else None
# VWorld buildings that OSM lacks become buildings too
for v in vw:
    if v.get("used") or v["area"] < 60 or abs(v["c"][0]) > HALF or abs(v["c"][1]) > HALF: continue
    if any(overlap(v["ring"], b["ring"]) > 0.25 for b in items if abs(b["c"][0] - v["c"][0]) < 120 and abs(b["c"][1] - v["c"][1]) < 120):
        continue
    r = [tuple(p) for p in v["ring"]]
    if area_of(r) < 0: r = r[::-1]
    items.append({"osm": "vw", "ring": r, "tags": {"building": "yes"}, "part": False, "area": v["area"], "c": v["c"], "vw": v})


# OSM residential land: a low building that nothing else identifies is locked only when it stands on it
RESID = []
for e in osm["elements"]:
    if e.get("tags", {}).get("landuse") != "residential": continue
    if e["type"] == "way" and "geometry" in e: RESID.append(ring_xy(e["geometry"]))
    elif e["type"] == "relation":
        RESID += [ring_xy(m["geometry"]) for m in e.get("members", []) if m.get("role") == "outer" and "geometry" in m]
RESID = [(r, min(p[0] for p in r), max(p[0] for p in r), min(p[1] for p in r), max(p[1] for p in r)) for r in RESID if len(r) > 2]


# where 건물통합정보 has no use codes at all (e.g. Daegu), every unidentified low building may be a house
NO_USE = bool(vw) and sum(1 for v in vw if not v["use"]) > 0.8 * len(vw)


def on_resid(c, rings=RESID):
    return any(x0 <= c[0] <= x1 and y0 <= c[1] <= y1 and inside(c, r) for r, x0, x1, y0, y1 in rings)


# ... but not on OSM industrial land, where an unnamed low building is a factory (e.g. 동탄 테크노밸리 has no use codes)
INDUS = []
for e in osm["elements"]:
    if e.get("tags", {}).get("landuse") != "industrial": continue
    if e["type"] == "way" and "geometry" in e: INDUS.append(ring_xy(e["geometry"]))
    elif e["type"] == "relation":
        INDUS += [ring_xy(m["geometry"]) for m in e.get("members", []) if m.get("role") == "outer" and "geometry" in m]
INDUS = [(r, min(p[0] for p in r), max(p[0] for p in r), min(p[1] for p in r), max(p[1] for p in r)) for r in INDUS if len(r) > 2]


OVR = json.loads((ROOT / "overrides.json").read_text(encoding="utf-8")).get(AID, {}) if (ROOT / "overrides.json").exists() else {}


def height_of(b):
    t = b["tags"]
    o = OVR.get(b["osm"])
    if o and "h" in o:
        return max(o["h"], 3.0), o.get("minh", num(t.get("min_height")) or 0.0)
    v = b.get("vw")
    osm_says = num(t.get("height")) is not None or num(t.get("building:levels")) is not None
    if v and not b["part"] and not osm_says and (v["h"] > 0 or v["floors"] > 0):
        h = v["h"] if v["h"] >= max(v["floors"], 1) * 2.4 else v["floors"] * 3.8 + 1.0
        return max(h, 3.0), 0.0
    h = num(t.get("height"))
    lv = num(t.get("building:levels"))
    if h is None and lv is not None: h = lv * STOREY + 1.0
    if h is None:
        kind = t.get("building", "yes")
        h = {"office": 30, "commercial": 15, "retail": 10, "apartments": 45, "house": 7, "roof": 5,
             "industrial": 12, "warehouse": 10}.get(kind)
        if h is None: h = 8 if b["area"] < 250 else 14 if b["area"] < 1200 else 24
    mh = num(t.get("min_height"))
    if mh is None and t.get("building:min_level") is not None: mh = num(t["building:min_level"]) * STOREY
    return max(h, 3.0), (mh or 0.0)


out = []
n_resid = 0
for b in items:
    if b.get("skip"): continue
    t = b["tags"]
    parent = b.get("parent")
    pt = parent["tags"] if parent else {}
    h, mh = height_of(b)
    btype = t.get("building") if t.get("building") not in (None, "yes", "part") else pt.get("building", t.get("building", "yes"))
    v = b.get("vw") or (parent or {}).get("vw")
    name = ko_name(t) or ko_name(pt) or (v and (v["name"] or v.get("addr") or v["dong"])) or ""
    addr = (v and v.get("addr")) or ""
    if v and btype in ("yes", None) and v["use"] in VW_USE: btype = VW_USE[v["use"]]
    off = (btype in OFF_TYPES) or any(OFF_NAME.search(x) for x in (name, addr)) \
        or bool(any(APT_NAME.search(x) for x in (name, addr)) and not WORK_NAME.search(name + " " + addr)) \
        or t.get("amenity") in ("school", "hospital", "place_of_worship") or bool(v and v["use"] in VW_OFF) \
        or bool(v and APT_DC.fullmatch(v.get("dc") or "") and not WORK_NAME.search(name + " " + addr))
    # nothing says what a low building on residential land (or anywhere, when NO_USE) is (no name, no use code, no OSM
    # type or shop): it may be a house, so it stays
    unknown = btype in ("yes", None, "part") and not name and not (v and v["use"]) and not (t.get("shop") or t.get("amenity"))
    if not off and unknown and h < 4 * 3.8 + 1.5 and ((NO_USE and not on_resid(b["c"], INDUS)) or on_resid(b["c"])):
        off = True; n_resid += 1
    # areas.json lockLow: a district mixed with lots of named single houses (과천 지식정보타운): every low building
    # without a work name stays, named or not
    if not off and AREA.get("lockLow") and h < 4 * 3.8 + 1.5 and not WORK_NAME.search(name):
        off = True; n_resid += 1
    if btype == "roof": kind = "canopy"
    elif off: kind = "off"
    elif h >= 60 or (btype == "office" and h >= 36): kind = "glass"
    elif h >= 15: kind = "concrete"
    else: kind = "plaster"
    gz = min(ground_z(x, y) for x, y in b["ring"])
    # one building = its OSM parent, or every OSM way that overlaps the same VWorld building (e.g. towers + sky bridge)
    grp = parent["osm"] if parent else (f"vw{b['vw']['idx']}" if b.get("vw") else b["osm"])
    out.append({"id": len(out), "osm": b["osm"], "group": grp, "name": label(name),
                "type": btype, "kind": kind, "smash": not off and kind != "canopy",
                "h": round(h, 1), "minh": round(mh, 1), "base": round(gz, 2),
                "levels": num(t.get("building:levels")),
                "ring": [[round(x, 2), round(y, 2)] for x, y in b["ring"]]})

# ---------- per-building facade: variant from the shared atlas + tint from the building's own roof photo ----------
FAC = json.loads((ROOT / "tools" / "facades.json").read_text(encoding="utf-8"))["variants"]
BYKIND = {}
for v_ in FAC: BYKIND.setdefault(v_["kind"], []).append(v_)
MIX = {"glass": [("curtain", 0.7), ("grid", 0.3)], "concrete": [("ribbon", 0.6), ("grid", 0.4)],
       "plaster": [("punched", 0.7), ("ribbon", 0.3)]}
aerial = None
if (RAW / "aerial.jpg").exists():
    aerial = Image.open(RAW / "aerial.jpg").convert("RGB")
    AS = aerial.width / SIZE
    web = ROOT / "site" / "areas" / AID; web.mkdir(parents=True, exist_ok=True)
    aerial.save(web / "ground.webp", quality=78, method=6)                       # desktop
    aerial.resize((2048, 2048), Image.LANCZOS).save(web / "ground_m.webp", quality=80, method=6)   # phones


def roof_colour(ring):
    xs_ = [(x + HALF) * AS for x, _ in ring]; ys_ = [(HALF - y) * AS for _, y in ring]
    x0, y0, x1, y1 = int(min(xs_)), int(min(ys_)), int(max(xs_)) + 1, int(max(ys_)) + 1
    if x1 - x0 < 3 or y1 - y0 < 3: return None
    crop = np.asarray(aerial.crop((x0, y0, x1, y1)), dtype=np.float32)
    m = Image.new("L", (x1 - x0, y1 - y0), 0)
    ImageDraw.Draw(m).polygon([(x - x0, y - y0) for x, y in zip(xs_, ys_)], fill=255)
    m = np.asarray(m.filter(ImageFilter.MinFilter(5))) > 0          # shrink so street pixels at the edge don't count
    if m.sum() < 9: return None
    return np.median(crop[m], axis=0)


for b in out:
    if not b["smash"]: continue
    h_ = (int.from_bytes(b["osm"].encode()[-6:].rjust(6, b"0"), "big") + b["id"] * 7919) * 2654435761 % 2**32   # stable per building
    rc = roof_colour(b["ring"]) if aerial is not None else None
    roll = (h_ % 1000) / 1000
    cat = MIX[b["kind"]][0][0] if roll < MIX[b["kind"]][0][1] else MIX[b["kind"]][1][0]
    cand = BYKIND[cat]
    if rc is not None:
        # light roofs lean to light facades and dark roofs to dark ones; the hash keeps neighbours apart
        lum = float(rc.mean())
        cand = sorted(cand, key=lambda v_: abs(sum(v_["mean"]) / 3 - lum) + ((h_ >> 8) % 7) * 9)
        tint = np.clip((rc / max(rc.mean(), 1)) ** 0.35, 0.86, 1.14)
    else:
        tint = np.ones(3)
    b["fac"] = cand[(h_ >> 4) % min(3, len(cand))]["i"]
    b["tint"] = [round(float(t), 3) for t in tint]
    b["uoff"] = round((h_ >> 12) % 240 / 10, 1)
    b["roof"] = [int(c) for c in rc] if rc is not None else None

# ---------- parts of one building stand on one ground level (the lowest under any of them) ----------
gb = {}
for b in out: gb[b["group"]] = min(gb.get(b["group"], 1e9), b["base"])
for b in out:
    if sum(1 for o in out if o["group"] == b["group"]) > 1: b["base"] = gb[b["group"]]; b["gbase"] = True

# ---------- trees ----------
trees = []
for e in osm["elements"]:
    t = e.get("tags", {})
    if e["type"] == "node" and t.get("natural") == "tree":
        x, y = ll2xy(e["lat"], e["lon"])
        if abs(x) < HALF and abs(y) < HALF: trees.append([round(x, 1), round(y, 1)])
    elif e["type"] == "way" and t.get("natural") == "tree_row" and "geometry" in e:
        r = ring_xy(e["geometry"])
        for (x0, y0), (x1, y1) in zip(r, r[1:]):
            n = max(1, int(math.hypot(x1 - x0, y1 - y0) / 9))
            for k2 in range(n):
                x, y = x0 + (x1 - x0) * k2 / n, y0 + (y1 - y0) * k2 / n
                if abs(x) < HALF and abs(y) < HALF: trees.append([round(x, 1), round(y, 1)])

# ---------- placeholder ground texture (OSM painted), replaced by the VWorld aerial mosaic when available ----------
S = TEX / SIZE
def px(x, y): return ((x + HALF) * S, (HALF - y) * S)

img = Image.new("RGB", (TEX, TEX), (172, 168, 158))
d = ImageDraw.Draw(img)
rng = np.random.default_rng(7)
LAND = {"grass": (128, 150, 100), "park": (118, 146, 92), "forest": (88, 118, 72), "meadow": (140, 156, 104),
        "recreation_ground": (130, 152, 98), "construction": (170, 150, 120), "residential": (176, 172, 162),
        "commercial": (180, 176, 168), "retail": (182, 176, 166)}
for e in osm["elements"]:
    t = e.get("tags", {})
    col = None
    if t.get("leisure") == "park": col = LAND["park"]
    elif t.get("landuse") in LAND: col = LAND[t["landuse"]]
    elif t.get("natural") == "water" or t.get("waterway") in ("riverbank",): col = (92, 122, 138)
    if col and e["type"] == "way" and "geometry" in e:
        d.polygon([px(*p) for p in ring_xy(e["geometry"])], fill=col)
WIDTH = {"motorway": 22, "trunk": 20, "primary": 18, "secondary": 14, "tertiary": 11, "unclassified": 8,
         "residential": 7, "living_street": 6, "service": 5, "motorway_link": 8, "trunk_link": 8, "primary_link": 8,
         "secondary_link": 7}
roads = []
for e in osm["elements"]:
    t = e.get("tags", {})
    hw = t.get("highway")
    if not hw or e["type"] != "way" or "geometry" not in e: continue
    pts = [px(*p) for p in ring_xy(e["geometry"])]
    if hw in WIDTH:
        roads.append((WIDTH[hw], pts, hw))
    elif hw in ("footway", "pedestrian", "path", "cycleway", "steps"):
        d.line(pts, fill=(196, 190, 178), width=max(2, int(3 * S)), joint="curve")
for w, pts, hw in sorted(roads, key=lambda r: r[0]):           # sidewalk band, then asphalt
    d.line(pts, fill=(190, 186, 176), width=int((w + 5) * S), joint="curve")
for w, pts, hw in sorted(roads, key=lambda r: r[0]):
    d.line(pts, fill=(64, 66, 70), width=int(w * S), joint="curve")
for w, pts, hw in roads:
    if w >= 11:                                                   # dashed centre line on big roads
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            L = math.hypot(x1 - x0, y1 - y0); n = int(L / (12 * S))
            for k2 in range(0, n, 2):
                a, c = k2 / max(n, 1), min((k2 + 1) / max(n, 1), 1)
                d.line([(x0 + (x1 - x0) * a, y0 + (y1 - y0) * a), (x0 + (x1 - x0) * c, y0 + (y1 - y0) * c)],
                       fill=(222, 214, 170), width=max(1, int(0.35 * S)))
# contact shadow under buildings, then roofs painted in (roofs are UV-projected onto this same texture)
sh = Image.new("L", (TEX, TEX), 0)
ds = ImageDraw.Draw(sh)
for b in out:
    ds.polygon([px(*p) for p in b["ring"]], fill=150)
sh = sh.filter(ImageFilter.GaussianBlur(3 * S))
img = Image.composite(Image.new("RGB", (TEX, TEX), (40, 40, 44)), img, sh.point(lambda v: int(v * 0.55)))
d = ImageDraw.Draw(img)
ROOF = {"glass": (150, 156, 160), "concrete": (168, 166, 160), "plaster": (176, 160, 140), "off": (160, 160, 160),
        "canopy": (120, 140, 150)}
for b in sorted(out, key=lambda b: b["h"]):
    base = np.array(ROOF[b["kind"]]) + rng.integers(-14, 14, 3)
    d.polygon([px(*p) for p in b["ring"]], fill=tuple(int(v) for v in base), outline=(120, 120, 118))
img = img.filter(ImageFilter.GaussianBlur(0.6))
img.save(RAW / "ground.png")

prep = {"id": AID, "lat": LAT0, "lon": LON0, "size": SIZE, "zbase": round(ZBASE, 2), "grid": GRID, "nx": nx,
        "terrain": [round(float(v), 2) for v in zgrid.ravel()], "buildings": out, "trees": trees}
(RAW / "prep.json").write_text(json.dumps(prep, ensure_ascii=False), encoding="utf-8")
kinds = {}
for b in out: kinds[b["kind"]] = kinds.get(b["kind"], 0) + 1
print(f"{AID}: {len(out)} buildings {kinds}, {n_resid} unknown low homes locked, trees {len(trees)}, terrain {nx}x{nx} relief {zgrid.max():.1f} m, "
      f"tallest {max(b['h'] for b in out):.0f} m")
