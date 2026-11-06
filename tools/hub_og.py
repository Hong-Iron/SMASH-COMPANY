# Renders the hub's share image site/og.jpg (1200 x 630) the way SMASH 대학교's hub og.png looks: three phone-sized game
# screens caught mid-blast, tilted side by side, with the "SMASH 회사" title on the left.
# usage: ~/.venvs/vault-plots/bin/python tools/hub_og.py [area area area]      (needs the local server on :8790)
import base64, io, json, pathlib, random, shutil, subprocess, sys, tempfile, time, urllib.request
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from thumbs import CHROME, BASE, ROOT, WS, plan

PICKS = sys.argv[1:] or ["pangyo-tv1", "yeouido", "gangnam-station"]


def chrome(w, h):
    port = random.randint(20000, 40000); ud = tempfile.mkdtemp(prefix="smash-company-og-")
    proc = subprocess.Popen([CHROME, "--headless=new", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--hide-scrollbars",
                             f"--remote-debugging-port={port}", f"--user-data-dir={ud}", f"--window-size={w},{h}", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try: urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2); break
        except Exception: time.sleep(0.5)
    tgt = json.load(urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/json/new?about:blank", method="PUT"), timeout=10))
    ws = WS(tgt["webSocketDebuggerUrl"])
    ws.call("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=False)
    ws.call("Page.enable")
    return ws, proc, ud


def phone(aid, w=390, h=844):
    """One portrait game screen: labels on, buttons and score hidden, frozen just after three bombs land."""
    cam, strikes, _ = plan(aid)
    cam = [cam[3] + (cam[0] - cam[3]) * 0.8, cam[4] + (cam[1] - cam[4]) * 0.8, cam[5] + (cam[2] - cam[5]) * 0.8] + cam[3:]
    ws, proc, ud = chrome(w, h)
    try:
        ws.call("Page.navigate", url=f"{BASE}/{aid}/?thumb=1")
        for _ in range(240):
            r = ws.call("Runtime.evaluate", expression="!!(window.__cau && window.__cau.deep)", returnByValue=True)
            if r.get("result", {}).get("value"): break
            time.sleep(1)
        time.sleep(4)
        css = "#app>*:not(#stage):not(#labels):not(#pops){display:none!important}"
        ws.call("Runtime.evaluate", awaitPromise=True, returnByValue=True, timeout=170000, expression=(
            "(async()=>{const _f=window.fetch;window.fetch=(u,...a)=>String(u).includes('rank')?Promise.resolve(new Response('[]')):_f(u,...a);"
            "navigator.sendBeacon=()=>true;"
            f"const st=document.createElement('style');st.textContent={json.dumps(css)};document.head.appendChild(st);"
            f"__cau.look(...{json.dumps(cam)});await new Promise(r=>setTimeout(r,3000));__cau.look(...{json.dumps(cam)});"
            "await new Promise(r=>setTimeout(r,1500));"
            f"{json.dumps(strikes, ensure_ascii=False)}.forEach(n=>typeof n==='string'?__cau.strikeAt(n,'bomb'):__cau.strikeGround(n[0],n[1],'bomb'));"
            "for(let i=0;i<25&&__cau.deep().score<=0;i++)__cau.tick(0.2);__cau.tick(0.7);__cau.freeze(true);"
            "await new Promise(r=>setTimeout(r,800));return 1})()"))
        time.sleep(1.0)
        return base64.b64decode(ws.call("Page.captureScreenshot", format="png")["data"])
    finally:
        proc.kill(); proc.wait(); shutil.rmtree(ud, ignore_errors=True)


def compose(shots, count):
    def uri(png):
        b = io.BytesIO(); Image.open(io.BytesIO(png)).convert("RGB").save(b, "JPEG", quality=90)
        return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()
    pos = [(420, -70, -3, 0.66), (655, 60, 2, 0.6), (900, -40, -2, 0.66)]       # left, top, tilt in degrees, scale
    phones = "".join(f'<img src="{uri(p)}" style="left:{x}px;top:{y}px;transform:rotate({r}deg) scale({s});z-index:{2 if i == 1 else 1}">'
                     for i, (p, (x, y, r, s)) in enumerate(zip(shots, pos)))
    return f"""<!doctype html><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Bungee&family=IBM+Plex+Sans+KR:wght@600&display=block" rel="stylesheet">
<style>html,body{{margin:0;width:1200px;height:630px;overflow:hidden;background:#0d0e12}}
img{{position:absolute;width:390px;height:844px;transform-origin:top left;border-radius:22px;border:3px solid #1b1d22;
box-shadow:0 18px 50px rgba(0,0,0,.6)}}
#t{{position:absolute;left:62px;top:300px;z-index:5}}
h1{{margin:0;font:400 112px/0.95 Bungee,Impact,sans-serif;color:#fff;-webkit-text-stroke:3px #111;
text-shadow:0 6px 0 #111,0 0 30px rgba(255,170,60,.35);transform:skewX(-8deg);transform-origin:left bottom}}
h2{{margin:0;font:600 104px/1.05 'IBM Plex Sans KR',sans-serif;color:#ffb24a;text-shadow:0 0 22px rgba(255,170,60,.55)}}
p{{margin:24px 0 0;font:600 30px 'IBM Plex Sans KR',sans-serif;color:#fff}} p b{{color:#ffb24a;font-weight:600}}
#fade{{position:absolute;inset:0;z-index:3;background:linear-gradient(90deg,#0d0e12 0,rgba(13,14,18,.92) 30%,rgba(13,14,18,0) 52%)}}
</style>{phones}<div id="fade"></div><div id="t"><h1>SMASH</h1><h2>회사</h2><p><b>우리 회사를 부셔</b> · 전국 {count}개 업무지구</p></div>"""


if __name__ == "__main__":
    shots = [phone(a) for a in PICKS]
    count = sum((ROOT / "site" / a / "index.html").exists() for a in json.loads((ROOT / "areas.json").read_text(encoding="utf-8")))
    page = ROOT / "raw" / "hub_og.html"; page.write_text(compose(shots, count), encoding="utf-8")
    ws, proc, ud = chrome(1200, 630)
    try:
        ws.call("Page.navigate", url=page.as_uri()); time.sleep(4)
        ws.call("Runtime.evaluate", expression="document.fonts.ready.then(()=>1)", awaitPromise=True, returnByValue=True)
        png = base64.b64decode(ws.call("Page.captureScreenshot", format="png")["data"])
    finally:
        proc.kill(); proc.wait(); shutil.rmtree(ud, ignore_errors=True)
    out = ROOT / "site" / "og.jpg"
    Image.open(io.BytesIO(png)).convert("RGB").save(out, quality=84, optimize=True, progressive=True)
    print(f"site/og.jpg {out.stat().st_size // 1024} KB from {', '.join(PICKS)}")
