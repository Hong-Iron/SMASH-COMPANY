// Worker를 Cloudflare와 같은 실행기(workerd, wrangler dev와 같은 방식)에 올려 실제 요청으로 확인한다. 데이터베이스는 매번 임시 폴더에 새로 만든다
// usage: node test/worker_test.mjs   -> 모두 맞으면 ALL CHECKS PASSED
import { unstable_startWorker, getPlatformProxy } from 'wrangler';
import { readFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const root = new URL('..', import.meta.url);
const read = (p) => readFileSync(new URL(p, root), 'utf8');
const statements = (sql) => sql.split(/;\s*\n/).map((s) => s.replace(/--.*$/gm, '').trim()).filter(Boolean);
const config = new URL('wrangler.toml', root).pathname;
const persist = mkdtempSync(join(tmpdir(), 'smash-rank-test-'));   // a fresh local database for every run

// the test reads and writes the local D1 directly through a second handle on the same files
const proxy = await getPlatformProxy({ configPath: config, persist: { path: join(persist, 'v3') } });   // the dev runner keeps its files under v3/
const db = proxy.env.DB;
for (const s of [...statements(read('schema.sql')), ...statements(read('test/fixture_schools.sql'))]) await db.prepare(s).run();
const w = await unstable_startWorker({ config, dev: { persist, server: { port: 0 }, inspector: false, watch: false, logLevel: 'error' } });
await w.ready;
const mf = { dispatchFetch: (u, init) => w.fetch(u, init) };

let ok = true;
const check = (name, got, want) => {
  const good = JSON.stringify(got) === JSON.stringify(want); ok &&= good;
  console.log(good ? 'OK  ' : 'FAIL', name, JSON.stringify(got), good ? '' : `(want ${JSON.stringify(want)})`);
};
const add = (body, ip = '1.1.1.1') => mf.dispatchFetch('http://rank.test/rest/v1/rpc/smash_add', {
  method: 'POST', headers: { 'content-type': 'application/json', apikey: 'x', ...(ip ? { 'cf-connecting-ip': ip } : {}) }, body: JSON.stringify(body),
});
const today = (code) => db.prepare("SELECT score, kills, players, ips FROM daily WHERE code = ?1").bind(code).first();
const total = (code) => db.prepare('SELECT score FROM total WHERE code = ?1').bind(code).first('score');

const opt = await mf.dispatchFetch('http://rank.test/rest/v1/rpc/smash_add', { method: 'OPTIONS' });
check('preflight 204 + CORS', [opt.status, opt.headers.get('access-control-allow-origin'), opt.headers.get('access-control-allow-headers')?.includes('apikey')], [204, '*', true]);

let r = await add({ p_code: 'CAU', p_score: 100000, p_kills: 3, p_new: true });
check('send -> 204, CORS', [r.status, r.headers.get('access-control-allow-origin')], [204, '*']);
check('daily row', await today('CAU'), { score: 100000, kills: 3, players: 1, ips: 1 });
await add({ p_code: 'CAU', p_score: 50000, p_kills: 1, p_new: false });
check('same IP adds, no new IP or player', await today('CAU'), { score: 150000, kills: 4, players: 1, ips: 1 });
await add({ p_code: 'NOPE', p_score: 100000, p_kills: 0, p_new: true });
check('unknown school ignored', await db.prepare("SELECT COUNT(*) AS n FROM daily WHERE code = 'NOPE'").first('n'), 0);
r = await mf.dispatchFetch('http://rank.test/rest/v1/rpc/smash_add', { method: 'POST', body: 'not json' });
check('bad json -> 400', r.status, 400);
// (a request without cf-connecting-ip cannot be tested here: the local runner fills it in, and on Cloudflare it is always set)
await add({ p_code: 'KU', p_score: 9e9, p_kills: 1e6, p_new: true }, '2.2.2.2');
check('per-send 400k, kills 2x buildings (KU 172)', await today('KU'), { score: 400000, kills: 344, players: 1, ips: 1 });
for (let i = 0; i < 9; i++) await add({ p_code: 'SNU', p_score: 400000, p_kills: 0, p_new: false }, '9.9.9.9');
const snu = (await today('SNU')).score;
check('token bucket burst ~3M (refill during the test adds a little)', snu >= 3000000 && snu < 3200000, true);
let last;
for (let i = 0; i < 61; i++) last = await add({ p_code: 'YONSEI', p_score: 1, p_kills: 0, p_new: false }, '5.5.5.5');
const yonsei = (await today('YONSEI')).score;
check('61 sends in a minute -> at most 60 count', yonsei >= 60 && yonsei <= 61 && last.status === 204, true);
check('total follows daily', await total('CAU'), 150000);

const b1 = await mf.dispatchFetch('http://rank.test/rest/v1/rpc/smash_board');
const board = await b1.json();
const cau = board.find((x) => x.code === 'CAU');
check('board: 4 rows, CORS, cache header', [board.length, b1.headers.get('access-control-allow-origin'), b1.headers.get('cache-control')], [4, '*', 'public, max-age=60']);
check('board CAU row', cau, { code: 'CAU', name: '중앙대학교 서울캠퍼스', today_score: 150000, today_kills: 4, today_players: 1, total_score: 150000, total_kills: 4, total_players: 1 });
await add({ p_code: 'CAU', p_score: 1000, p_kills: 0, p_new: false });
const b2 = await (await mf.dispatchFetch('http://rank.test/rest/v1/rpc/smash_board')).json();
check('board cached for a minute (new points not yet shown)', b2.find((x) => x.code === 'CAU').today_score, 150000);
const h = await (await mf.dispatchFetch('http://rank.test/health')).json();
check('health', h.ok, true);

await db.prepare("INSERT INTO ipday (k, day, code) VALUES ('old', '2020-01-01', 'CAU')").run();
const url = await w.url;
await fetch(new URL('/cdn-cgi/handler/scheduled?cron=0+19+*+*+*', url));   // wrangler dev's test path for cron triggers
check('cron removes old IP rows, keeps today', [await db.prepare("SELECT COUNT(*) AS n FROM ipday WHERE k = 'old'").first('n'), (await db.prepare('SELECT COUNT(*) AS n FROM ipday').first('n')) > 0], [0, true]);

await w.dispose(); await proxy.dispose();
console.log(ok ? 'ALL CHECKS PASSED' : 'SOME CHECKS FAILED');
process.exit(ok ? 0 : 1);
