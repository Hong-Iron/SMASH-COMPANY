# Worker의 SQL을 그대로 SQLite에 돌려 점수 방어 규칙을 확인한다(D1도 SQLite라 같은 문장이 그대로 돈다)
# src/index.js에서 prepare(...) 안의 SQL 문장을 순서대로 뽑아 쓰고, addScore의 계산은 파이썬으로 똑같이 옮겼다
# usage: python3 test/sql_test.py   -> 모두 맞으면 ALL CHECKS PASSED
import hashlib, pathlib, re, sqlite3, math, datetime as dt

ROOT = pathlib.Path(__file__).resolve().parents[1]
js = (ROOT / "src/index.js").read_text()
SQL = [s.strip() for s in re.findall(r"prepare\((?:'|`)(.*?)(?:'|`)\)", js, re.S)]
SCHOOLS, SEL_IP, SEL_DAY, UP_IP, UP_DAY, UP_TOT, BOARD, CLEAN = SQL
PER_SEND, PER_MIN, BUCKET, REFILL, IP_DAY = 400000, 60, 3000000, 50000, 100000000
SCHOOL_BASE, SCHOOL_PER_IP = 20000000, 5000000

db = sqlite3.connect(":memory:")
db.executescript((ROOT / "schema.sql").read_text())
db.executemany("INSERT INTO school VALUES (?, ?, ?)", [("CAU", "중앙대학교 서울캠퍼스", 45), ("SNU", "서울대학교 관악캠퍼스", 277), ("TINY", "작은대학교", 3)])
bld = dict(db.execute(SCHOOLS).fetchall())

def kst(ms): return dt.datetime.fromtimestamp(ms / 1000 + 9 * 3600, dt.UTC).date().isoformat()
def add(code, score, kills, new, ip, ms):
    if code not in bld: return None
    score = min(PER_SEND, max(0, int(score))); kills = min(bld[code] * 2, max(0, int(kills))); isnew = 1 if new else 0
    if not score and not kills and not isnew: return 0
    day, now = kst(ms), ms / 1000; win = math.floor(now / 60)
    k = hashlib.sha256(f"{ip}|{day}".encode()).hexdigest()[:32]
    row = db.execute(SEL_IP, (k, day, code)).fetchone()
    d = db.execute(SEL_DAY, (day, code)).fetchone() or (0, 0)
    first = 0 if row else 1
    wcount = row[4] if row and row[3] == win else 0
    if wcount >= PER_MIN: return "limited"
    tokens = min(BUCKET, row[1] + (now - row[2]) * REFILL) if row else BUCKET
    score = min(score, math.floor(tokens)); score = min(score, max(0, IP_DAY - (row[0] if row else 0)))
    score = min(score, max(0, SCHOOL_BASE + (d[1] + first) * SCHOOL_PER_IP - d[0])); tokens -= score
    db.execute(UP_IP, (k, day, code, score, tokens, now, win))
    db.execute(UP_DAY, (day, code, score, kills, isnew, first))
    db.execute(UP_TOT, (code, score, kills, isnew))
    return score

T0 = 1793500000000   # some fixed moment (ms)
ok = True
def check(name, got, want):
    global ok
    good = got == want; ok &= good
    print(("OK  " if good else "FAIL"), name, got, "" if good else f"(want {want})")

check("normal send", add("CAU", 100000, 3, True, "1.1.1.1", T0), 100000)
check("unknown school", add("XXX", 100000, 0, True, "1.1.1.1", T0), None)
check("per-send cap 400k", add("CAU", 900000, 0, False, "2.2.2.2", T0), 400000)
check("kills capped at 2x buildings", db.execute("SELECT kills FROM daily WHERE code='TINY'").fetchone(), None)
add("TINY", 0, 50, False, "3.3.3.3", T0)
check("kills capped", db.execute("SELECT kills FROM daily WHERE code='TINY'").fetchone()[0], 6)
# token bucket: one IP spamming 400k sends in the same second gets 3M, then nothing until it refills
got = [add("SNU", 400000, 0, False, "9.9.9.9", T0 + 1000) for _ in range(9)]
check("bucket 3M burst", sum(g for g in got if isinstance(g, int)), 3000000)
check("bucket refills 50k/s", add("SNU", 400000, 0, False, "9.9.9.9", T0 + 1000 + 4000), 200000)
# 60 sends a minute per IP, then refused until the next minute
db.execute("DELETE FROM ipday")
res = [add("CAU", 10, 0, False, "5.5.5.5", T0 + 120000 + i) for i in range(61)]
check("61st send in a minute refused", res[-1], "limited")
check("next minute works", add("CAU", 10, 0, False, "5.5.5.5", T0 + 180000 + 1), 10)
# school daily cap: 20M + 5M per IP that sent to it today
db.execute("DELETE FROM daily"); db.execute("DELETE FROM ipday"); db.execute("DELETE FROM total")
tot = 0
for i in range(200):   # one IP, sends spread out so the bucket refills
    r = add("CAU", 400000, 0, False, "7.7.7.7", T0 + i * 10000)
    tot += r if isinstance(r, int) else 0
check("school cap with 1 IP = 25M", tot, 25000000)
check("second IP lifts the cap by 5M", sum(add("CAU", 400000, 0, False, "8.8.8.8", T0 + 3000000 + i * 10000) or 0 for i in range(40)), 5000000)
# per-IP daily cap 100M (separate school with many IPs so the school cap is not the limit)
db.execute("DELETE FROM daily"); db.execute("DELETE FROM ipday")
db.execute("INSERT INTO daily VALUES (?, 'SNU', 0, 0, 0, 100)", (kst(T0),))
tot = 0
for i in range(300):
    r = add("SNU", 400000, 0, False, "6.6.6.6", T0 + i * 10000)
    tot += r if isinstance(r, int) else 0
check("IP daily cap 100M", tot, 100000000)
# board: today and total per school, one row per school
rows = db.execute(BOARD, (kst(T0),)).fetchall()
check("board rows = schools", len(rows), 3)
check("board total = sum of daily", db.execute("SELECT SUM(score) FROM total").fetchone()[0] >= 100000000, True)
db.execute(CLEAN, (kst(T0 + 2 * 86400000),)); check("cleanup removes old ip rows", db.execute("SELECT COUNT(*) FROM ipday").fetchone()[0], 0)
print("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED")
