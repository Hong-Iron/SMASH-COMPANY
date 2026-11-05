// SMASH 회사 지구별 랭킹 서버 (Cloudflare Worker + D1) — SMASH 대학교 smash-rank와 같은 코드. 표 이름 school은 여기서 "업무지구(구역)"를 뜻한다
// 예전 Supabase 주소 모양을 그대로 받는다: 게임과 허브는 config.json의 supabaseUrl만 이 Worker 주소로 바꾸면 된다
//   POST /rest/v1/rpc/smash_add   {p_code, p_score, p_kills, p_new}
//   GET  /rest/v1/rpc/smash_board -> [{code, name, today_score, today_kills, today_players, total_score, total_kills, total_players}]
// 점수 방어(예전 guard4와 같은 규칙):
//   한 번에 40만 점까지 / IP 하나는 1분에 60번까지 / IP 하나는 한 번에 300만 점, 그 뒤 초당 5만 점씩 (토큰 버킷)
//   IP 하나가 한 학교에 하루 1억 점까지 / 학교 하루 점수는 2000만 + 그날 점수를 보낸 IP 수 × 500만까지
//   진짜 IP는 cf-connecting-ip(Cloudflare가 붙이고 브라우저가 꾸밀 수 없다)만 쓴다
// 순위표는 Cloudflare 캐시에 60초 동안 두어, 화면이 아무리 많아도 데이터베이스는 1분에 한 번만 읽는다

const PER_SEND = 400000, PER_MIN = 60, BUCKET = 3000000, REFILL = 50000, IP_DAY = 100000000;
const SCHOOL_BASE = 20000000, SCHOOL_PER_IP = 5000000, BOARD_TTL = 60;
const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'apikey, authorization, content-type, x-client-info',
  'Access-Control-Max-Age': '86400',
};

const kstDay = (ms = Date.now()) => new Date(ms + 9 * 3600 * 1000).toISOString().slice(0, 10);
const int = (v) => (Number.isFinite(Number(v)) ? Math.trunc(Number(v)) : 0);
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const reply = (body, status = 200, extra = {}) =>
  new Response(body === null ? null : JSON.stringify(body), { status, headers: { ...CORS, 'Content-Type': 'application/json', ...extra } });

async function hash(text) {
  const d = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return [...new Uint8Array(d)].slice(0, 16).map((b) => b.toString(16).padStart(2, '0')).join('');
}

// school list kept in memory for 10 minutes (it only changes when new campuses are added)
let schools = null, schoolsAt = 0;
async function schoolMap(env) {
  if (!schools || Date.now() - schoolsAt > 600000) {
    const { results } = await env.DB.prepare('SELECT code, buildings FROM school').all();
    schools = new Map(results.map((r) => [r.code, r.buildings])); schoolsAt = Date.now();
  }
  return schools;
}

export async function addScore(env, body, ip, nowMs = Date.now()) {
  const code = String(body?.p_code || '');
  const bld = (await schoolMap(env)).get(code);
  if (!bld) return { ok: false, why: 'unknown school' };
  let score = clamp(int(body.p_score), 0, PER_SEND);
  const kills = clamp(int(body.p_kills), 0, bld * 2);
  const isNew = body.p_new === true ? 1 : 0;
  if (!score && !kills && !isNew) return { ok: true, added: 0 };
  if (!ip) return { ok: false, why: 'no ip' };

  const day = kstDay(nowMs), now = nowMs / 1000, win = Math.floor(now / 60);
  const k = await hash(`${ip}|${day}`);
  const [ipRes, dayRes] = await env.DB.batch([
    env.DB.prepare('SELECT score, tokens, at, win, wcount FROM ipday WHERE k = ?1 AND day = ?2 AND code = ?3').bind(k, day, code),
    env.DB.prepare('SELECT score, ips FROM daily WHERE day = ?1 AND code = ?2').bind(day, code),
  ]);
  const row = ipRes.results[0], firstFromIp = row ? 0 : 1;
  const wcount = row && row.win === win ? row.wcount : 0;
  if (wcount >= PER_MIN) return { ok: false, why: 'too often' };

  let tokens = row ? Math.min(BUCKET, row.tokens + (now - row.at) * REFILL) : BUCKET;
  score = Math.min(score, Math.floor(tokens));
  score = Math.min(score, Math.max(0, IP_DAY - (row ? row.score : 0)));
  const d = dayRes.results[0] || { score: 0, ips: 0 };
  score = Math.min(score, Math.max(0, SCHOOL_BASE + (d.ips + firstFromIp) * SCHOOL_PER_IP - d.score));
  tokens -= score;

  await env.DB.batch([
    env.DB.prepare(`INSERT INTO ipday (k, day, code, score, tokens, at, win, wcount) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, 1)
      ON CONFLICT (k, day, code) DO UPDATE SET score = score + ?4, tokens = ?5, at = ?6, win = ?7,
        wcount = CASE WHEN win = ?7 THEN wcount + 1 ELSE 1 END`).bind(k, day, code, score, tokens, now, win),
    env.DB.prepare(`INSERT INTO daily (day, code, score, kills, players, ips) VALUES (?1, ?2, ?3, ?4, ?5, ?6)
      ON CONFLICT (day, code) DO UPDATE SET score = score + ?3, kills = kills + ?4, players = players + ?5, ips = ips + ?6`)
      .bind(day, code, score, kills, isNew, firstFromIp),
    env.DB.prepare(`INSERT INTO total (code, score, kills, players) VALUES (?1, ?2, ?3, ?4)
      ON CONFLICT (code) DO UPDATE SET score = score + ?2, kills = kills + ?3, players = players + ?4`).bind(code, score, kills, isNew),
  ]);
  return { ok: true, added: score };
}

// the board also stays in this Worker copy's memory for a minute, in case the Cloudflare cache is not used for this address
let boardText = null, boardAt = 0;
export async function board(env, nowMs = Date.now()) {
  const { results } = await env.DB.prepare(`SELECT s.code AS code, s.name AS name,
      COALESCE(d.score, 0) AS today_score, COALESCE(d.kills, 0) AS today_kills, COALESCE(d.players, 0) AS today_players,
      COALESCE(t.score, 0) AS total_score, COALESCE(t.kills, 0) AS total_kills, COALESCE(t.players, 0) AS total_players
    FROM school s LEFT JOIN daily d ON d.code = s.code AND d.day = ?1 LEFT JOIN total t ON t.code = s.code`).bind(kstDay(nowMs)).all();
  return results;
}

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: CORS });
    if (url.pathname.endsWith('/rpc/smash_add') && req.method === 'POST') {
      let body = null;
      try { body = await req.json(); } catch { return reply({ error: 'bad json' }, 400); }
      await addScore(env, body, req.headers.get('cf-connecting-ip'));
      return reply(null, 204);                       // same as the old server: the game only checks that the call worked
    }
    if (url.pathname.endsWith('/rpc/smash_board') && (req.method === 'GET' || req.method === 'POST')) {
      const headers = { 'Cache-Control': `public, max-age=${BOARD_TTL}` };
      if (boardText && Date.now() - boardAt < BOARD_TTL * 1000)   // this Worker copy already read it within the last minute
        return new Response(boardText, { headers: { ...CORS, 'Content-Type': 'application/json', ...headers } });
      const cache = caches.default, key = new Request(`${url.origin}/rest/v1/rpc/smash_board`, { method: 'GET' });
      let res = await cache.match(key);
      if (!res) {
        res = reply(await board(env), 200, headers);
        ctx.waitUntil(cache.put(key, res.clone()));
      }
      boardText = await res.clone().text(); boardAt = Date.now();
      return res;
    }
    if (url.pathname === '/' || url.pathname === '/health') return reply({ ok: true, day: kstDay() });
    return reply({ error: 'not found' }, 404);
  },
  // every day at 04:00 KST: forget per-IP rows older than yesterday
  async scheduled(event, env) {
    await env.DB.prepare('DELETE FROM ipday WHERE day < ?1').bind(kstDay(Date.now() - 86400000)).run();
  },
};
