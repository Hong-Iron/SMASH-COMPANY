# Renders each area's share image and hub thumbnail the way SMASH 대학교 does (tools/roll_thumb_slow.py + make_card.py):
# headless Chrome opens the game page, a "SMASH 회사" title is laid over it, the camera frames the biggest named office
# block, three bombs land on it and the frame is frozen mid-blast.
#   site/<area>/og.jpg    1200 x 630 (share preview; JPEG instead of SMASH's 1 MB PNG)
#   site/<area>/card.webp 600 x 315, quality 72 (hub card, about 30 KB)
# Ranking requests are blocked while it runs, so the test blasts never reach the leaderboard.
# usage: ~/.venvs/vault-plots/bin/python tools/thumbs.py [area …]      (needs the local server on :8790 — preview "smash-company")
import base64, io, json, math, os, pathlib, random, re, shutil, socket, struct, subprocess, sys, tempfile, time, urllib.request
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
BASE = "http://localhost:8790"
SKIP = ("주차", "화장실", "주유소", "관리사무", "사무소", "경비", "공영", "문화회관", "극장", "미술관", "박물관", "지하")


class WS:   # minimal CDP websocket client (standard library only), as in SMASH's cdp_shot.py
    def __init__(self, url):
        host, rest = url[len("ws://"):].split("/", 1); h, p = host.split(":")
        self.s = socket.create_connection((h, int(p)), timeout=180)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall((f"GET /{rest} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                        f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        buf = b""
        while b"\r\n\r\n" not in buf: buf += self.s.recv(4096)
        self.rest = buf.split(b"\r\n\r\n", 1)[1]; self.n = 0

    def _read(self, k):
        while len(self.rest) < k:
            c = self.s.recv(1 << 20)
            if not c: raise ConnectionError("closed")
            self.rest += c
        out, self.rest = self.rest[:k], self.rest[k:]; return out

    def recv(self):
        data = b""
        while True:
            b1, b2 = self._read(2); ln = b2 & 0x7F
            if ln == 126: ln = struct.unpack(">H", self._read(2))[0]
            elif ln == 127: ln = struct.unpack(">Q", self._read(8))[0]
            data += self._read(ln)
            if b1 & 0x80: return data

    def call(self, method, **params):
        self.n += 1; mid = self.n
        payload = json.dumps({"id": mid, "method": method, "params": params}).encode()
        mask = os.urandom(4); ln = len(payload)
        hdr = bytes([0x81]) + (bytes([0x80 | ln]) if ln < 126 else bytes([0x80 | 126]) + struct.pack(">H", ln) if ln < 65536
                               else bytes([0x80 | 127]) + struct.pack(">Q", ln))
        self.s.sendall(hdr + mask + bytes(c ^ mask[i % 4] for i, c in enumerate(payload)))
        while True:
            m = json.loads(self.recv())
            if m.get("id") == mid:
                if "error" in m: raise RuntimeError(m["error"])
                return m.get("result", {})


BLOCK = re.compile(r"[A-Za-z0-9가-힣]{1,2}동")                  # names that are only a block number ("1동", "A동")


def inside(p, ring):
    x, y, c = p[0], p[1], False
    for i in range(len(ring)):
        (x1, y1), (x2, y2) = ring[i - 1], ring[i]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1): c = not c
    return c


FOCUS = {"yangjae": "현대자동차그룹 본사", "daechi-dogok": "린스퀘어", "hannam": "제일기획",
         "cheonan-4": "신세계푸드 천안공장", "magok": "LG사이언스파크"}   # the landmark the area is named after or the issue asked for, when the biggest building is something else


def plan(aid):
    d = json.loads((ROOT / "data" / f"{aid}.json").read_text(encoding="utf-8"))
    bs = []
    for b in d["buildings"]:
        xs = [p[0] for p in b["o"]]; zs = [p[1] for p in b["o"]]
        a = abs(sum(b["o"][i][0] * b["o"][i - 1][1] - b["o"][i - 1][0] * b["o"][i][1] for i in range(len(b["o"])))) / 2
        bs.append(dict(n=b.get("n"), cx=sum(xs) / len(xs), cz=sum(zs) / len(zs), g=b["g"], h=b["h"], a=a,
                       w=max(max(xs) - min(xs), max(zs) - min(zs))))
    named = [b for b in bs if b["n"] and not any(s in b["n"] for s in SKIP) and not BLOCK.fullmatch(b["n"])
             and abs(b["cx"]) < 400 and abs(b["cz"]) < 400]
    f = next((b for b in bs if b["n"] == FOCUS.get(aid)), None) or max(named or bs, key=lambda b: b["a"] * (1 + b["h"] / 40))
    near = sorted((b for b in (named or bs) if b is not f and b["n"] != f["n"]), key=lambda b: math.hypot(b["cx"] - f["cx"], b["cz"] - f["cz"]))
    near = [b for b in near if math.hypot(b["cx"] - f["cx"], b["cz"] - f["cz"]) < 170][:2]
    dist = min(520, max(200, 2.4 * f["w"] + 1.6 * f["h"]))
    k = math.sqrt(0.22 ** 2 + 0.45 ** 2 + 0.87 ** 2)
    ty = f["g"] + 0.35 * f["h"]
    # every footprint the camera could look through (smashable and locked), with its top height
    walls = [(b["o"], b["g"] + b["h"]) for b in d["buildings"] if b.get("n") != f["n"]] + \
            [(b["o"], b["lo"] + b["h"]) for b in d.get("locked", [])]
    walls = [(o, top, min(p[0] for p in o), max(p[0] for p in o), min(p[1] for p in o), max(p[1] for p in o)) for o, top in walls]

    def hits(cam):                                          # samples of the sight line that pass through a building
        n = 0
        for i in range(1, 20):
            t = i / 20; x, y, z = (cam[j] + (cam[j + 3] - cam[j]) * t for j in range(3))
            n += any(x0 <= x <= x1 and z0 <= z <= z1 and top > y and inside((x, z), o) for o, top, x0, x1, z0, z1 in walls)
        return n

    cams = []
    for turn in range(4):                                   # the usual south-east view first, then the other three sides
        c, sn = math.cos(turn * math.pi / 2), math.sin(turn * math.pi / 2)
        ox, oz = 0.22 * c - 0.87 * sn, 0.22 * sn + 0.87 * c
        cams.append([f["cx"] + dist * ox / k, ty + dist * 0.45 / k, f["cz"] + dist * oz / k, f["cx"], ty, f["cz"]])
    cam = min(cams, key=hits)
    strikes = [x["n"] or [round(x["cx"], 1), round(x["cz"], 1)] for x in [f] + near]
    return cam, strikes, f["n"]


def js(cam, strikes, place):
    css = ("#app>*:not(#stage):not(#labels):not(#hud):not(#pops){display:none!important} #lb{display:none!important}"
           " #og{position:fixed;left:44px;bottom:30px;z-index:99;pointer-events:none;max-width:760px}"
           " #og h2{margin:0;font:400 104px/0.9 Bungee,Impact,sans-serif;color:#fff;-webkit-text-stroke:3px #111;"
           "text-shadow:0 6px 0 #111,0 0 24px rgba(0,0,0,.45);transform:skewX(-8deg);transform-origin:left bottom;letter-spacing:-.02em;white-space:nowrap}"
           " #og h2 span{font-family:'IBM Plex Sans KR',sans-serif;font-weight:600;font-size:.82em;-webkit-text-stroke:2px #111}"
           " #og p{display:inline-block;margin:22px 0 0;padding:10px 18px;border-radius:10px;background:rgba(20,22,26,.86);"
           "font:600 29px 'IBM Plex Sans KR',sans-serif;color:#fff} #og p b{color:#ffb24a;font-weight:600}")
    c = place[-1]
    josa = "을" if "가" <= c <= "힣" and (ord(c) - 0xAC00) % 28 else "를"
    html = f"<h2>SMASH <span>회사</span></h2><p><b>{place}{josa} 부셔</b> · 월요병 해소</p>"
    return ("(async()=>{const _f=window.fetch;window.fetch=(u,...a)=>String(u).includes('rank')?Promise.resolve(new Response('[]')):_f(u,...a);"
            "navigator.sendBeacon=()=>true;"
            f"const st=document.createElement('style');st.textContent={json.dumps(css)};document.head.appendChild(st);"
            f"const d=document.createElement('div');d.id='og';d.innerHTML={json.dumps(html)};document.body.appendChild(d);"
            "await document.fonts.ready;"
            f"__cau.look(...{json.dumps(cam)});await new Promise(r=>setTimeout(r,3000));__cau.look(...{json.dumps(cam)});"
            "await new Promise(r=>setTimeout(r,1500));"
            f"const hit={json.dumps(strikes, ensure_ascii=False)}.map(n=>typeof n==='string'?__cau.strikeAt(n,'bomb'):(__cau.strikeGround(n[0],n[1],'bomb'),true));"
            "for(let i=0;i<25&&__cau.deep().score<=0;i++)__cau.tick(0.2);__cau.tick(0.7);__cau.freeze(true);"
            "await new Promise(r=>setTimeout(r,800));return JSON.stringify({hit,score:__cau.deep().score})})()")


def shoot(aid, w=1200, h=630):
    cam, strikes, focus = plan(aid)
    areas = json.loads((ROOT / "areas.json").read_text(encoding="utf-8"))
    place = f"{areas[aid]['district']} {areas[aid]['name']}"
    port = random.randint(20000, 40000); ud = tempfile.mkdtemp(prefix="smash-company-cdp-")
    proc = subprocess.Popen([CHROME, "--headless=new", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--hide-scrollbars",
                             f"--remote-debugging-port={port}", f"--user-data-dir={ud}", f"--window-size={w},{h}", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try: urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2); break
            except Exception: time.sleep(0.5)
        tgt = json.load(urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/json/new?about:blank", method="PUT"), timeout=10))
        ws = WS(tgt["webSocketDebuggerUrl"])
        ws.call("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=False)
        ws.call("Page.enable"); ws.call("Page.navigate", url=f"{BASE}/{aid}/?thumb=1")
        for _ in range(240):                                    # wait for the engine's test handle
            r = ws.call("Runtime.evaluate", expression="!!(window.__cau && window.__cau.deep)", returnByValue=True)
            if r.get("result", {}).get("value"): break
            time.sleep(1)
        time.sleep(4)                                           # aerial photo and fonts
        r = ws.call("Runtime.evaluate", expression=js(cam, strikes, place), awaitPromise=True, returnByValue=True, timeout=170000)
        res = r.get("result", {}).get("value")
        if not res or json.loads(res).get("score", 0) <= 0: raise RuntimeError(f"no blast in the frame: {res}")
        time.sleep(1.0)
        png = base64.b64decode(ws.call("Page.captureScreenshot", format="png")["data"])
    finally:
        proc.kill(); proc.wait(); shutil.rmtree(ud, ignore_errors=True)
    im = Image.open(io.BytesIO(png)).convert("RGB")
    out = ROOT / "site" / aid
    im.save(out / "og.jpg", quality=84, optimize=True, progressive=True)
    im.resize((600, 315), Image.LANCZOS).save(out / "card.webp", "WEBP", quality=72, method=6)
    return focus, res, (out / "og.jpg").stat().st_size // 1024, (out / "card.webp").stat().st_size // 1024


if __name__ == "__main__":
    ids = sys.argv[1:] or [p.name for p in sorted((ROOT / "site").iterdir()) if (p / "index.html").exists() and (ROOT / "data" / f"{p.name}.json").exists()]
    for aid in ids:
        for attempt in (1, 2):                                  # headless Chrome sometimes drops under load: one retry
            try:
                focus, res, og, card = shoot(aid)
                print(f"{aid}: focus {focus} {res} og.jpg {og} KB card.webp {card} KB", flush=True)
                break
            except Exception as e:
                print(f"{aid}: {'retrying after' if attempt == 1 else 'FAILED'} {type(e).__name__} {e}", flush=True)
