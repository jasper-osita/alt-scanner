// Tests for api/ct-keeper.js with a fake Upstash Redis (REST) and a fake cTrader token service. Prints "ok <name>" or "FAIL <name>: why".
import { createRequire } from "module";
import path from "path";
import { fileURLToPath } from "url";
const require = createRequire(import.meta.url), here = path.dirname(fileURLToPath(import.meta.url)), modPath = path.join(here, "..", "api", "ct-keeper.js");
const load = () => { delete require.cache[require.resolve(modPath)]; return require(modPath); };   // a fresh copy = another function instance

let DB = new Map(), TOK = { calls: 0, fail: false, n: 0, hang: false, during: null }, RFAIL = { login: 0 };
const REDIS = "https://fake-redis.example";
globalThis.fetch = async (url, opts = {}) => {
  const json = (status, body) => ({ ok: status < 400, status, json: async () => body, text: async () => JSON.stringify(body) });
  if (url.startsWith(REDIS)) {
    if ((opts.headers || {}).Authorization !== "Bearer redis-token") return json(401, { error: "unauthorized" });
    const [cmd, k, v, ...rest] = JSON.parse(opts.body), now = Date.now();
    const live = key => { const e = DB.get(key); if (e && e.exp && e.exp < now) { DB.delete(key); return null; } return e || null; };
    if (cmd === "GET") { const e = live(k); return json(200, { result: e ? e.v : null }); }
    if (cmd === "SET" && k === "ct:login" && RFAIL.login > 0) { RFAIL.login--; return json(500, { error: "flaky" }); }
    if (cmd === "SET") { const nx = rest.includes("NX"), ex = rest.indexOf("EX"); if (nx && live(k)) return json(200, { result: null });
      DB.set(k, { v, exp: ex >= 0 ? now + +rest[ex + 1] * 1000 : 0 }); return json(200, { result: "OK" }); }
    if (cmd === "DEL") { DB.delete(k); return json(200, { result: 1 }); }
    if (cmd === "INCR") { const e = live(k), n = (e ? +e.v : 0) + 1; DB.set(k, { v: String(n), exp: e ? e.exp : 0 }); return json(200, { result: n }); }
    if (cmd === "DECR") { const e = live(k), n = (e ? +e.v : 0) - 1; DB.set(k, { v: String(n), exp: e ? e.exp : 0 }); return json(200, { result: n }); }
    if (cmd === "EVAL") { const [, , key, id] = JSON.parse(opts.body).slice(1); const e = live(key); if (e && e.v === id) { DB.delete(key); return json(200, { result: 1 }); } return json(200, { result: 0 }); }
    if (cmd === "EXPIRE") { const e = live(k); if (e) e.exp = now + +v * 1000; return json(200, { result: e ? 1 : 0 }); }
    return json(400, { error: "unknown command " + cmd });
  }
  if (url.startsWith("https://openapi.ctrader.com/apps/token")) {
    TOK.calls++; const q = new URL(url).searchParams; if (TOK.during) TOK.during();
    await new Promise((r, j) => { const t = setTimeout(r, TOK.hang ? 3000 : 150); if (opts.signal) opts.signal.addEventListener("abort", () => { clearTimeout(t); j(new Error("aborted")); }); });
    if (TOK.fail || q.get("grant_type") !== "refresh_token" || q.get("client_secret") !== "sec") return json(400, { errorCode: "ACCESS_DENIED", description: "bad" });
    TOK.n++; return json(200, { accessToken: "tok-new-" + TOK.n, refreshToken: "ref-new-" + TOK.n, expiresIn: 2628000, tokenType: "bearer" });
  }
  return json(404, {});
};
// fake @vercel/blob: create-only by default, ifMatch → only if the ETag still matches, like the real service
let BL = new Map(), etagN = 0;
const tick = () => new Promise(r => setTimeout(r, Math.random() * 3));
const fakeBlob = {
  async get(path) { await tick(); const e = BL.get(path); return e ? { statusCode: 200, stream: new Blob([e.v]).stream(), blob: { etag: e.etag } } : null; },
  async put(path, body, o) {
    await tick(); if (path === "keeper/login.json" && RFAIL.login > 0) { RFAIL.login--; throw Object.assign(new Error("unavailable"), { name: "BlobServiceNotAvailable" }); }
    const e = BL.get(path);
    if (o.ifMatch) { if (!e || e.etag !== o.ifMatch) throw Object.assign(new Error("precondition failed"), { name: "BlobPreconditionFailedError" }); }
    else if (!o.allowOverwrite && e) throw Object.assign(new Error("This blob already exists"), { name: "BlobError" });
    BL.set(path, { v: body, etag: '"e' + (++etagN) + '"' }); return { pathname: path };
  },
};
let BACKEND = "redis";
const stored = () => BACKEND === "redis" ? JSON.parse(DB.get("ct:login").v) : JSON.parse(BL.get("keeper/login.json").v);
const takeLock = () => BACKEND === "redis" ? DB.set("ct:lock", { v: "someone-else", exp: Date.now() + 30000 }) : BL.set("keeper/lock.json", { v: JSON.stringify({ id: "someone-else", until: Date.now() + 30000 }), etag: '"e' + (++etagN) + '"' });
const lockOwner = () => { if (BACKEND === "redis") { const l = DB.get("ct:lock"); return l && l.v; } const l = BL.get("keeper/lock.json"); return l && JSON.parse(l.v).id; };
const failExpiry = ip => { if (BACKEND === "redis") { const e = [...DB.entries()].find(([k]) => k.includes(ip)); return e && e[1].exp; } const e = [...BL.entries()].find(([k]) => k.includes(ip.replace(/[^a-z0-9.]/gi, "_"))); return e && JSON.parse(e[1].v).until; };
async function call(mod, body, { method = "POST", origin = "", ip = "1.1.1.1" } = {}) {
  const req = { method, headers: { host: "alt-scanner-three.vercel.app", ...(origin ? { origin } : {}), "x-forwarded-for": ip }, body };
  const res = { statusCode: 200, headers: {}, setHeader(k, v) { this.headers[k.toLowerCase()] = v; }, end(b) { this.body = b; } };
  await mod(req, res); let j = null; try { j = JSON.parse(res.body || "null"); } catch (e) {}
  return { status: res.statusCode, body: j, raw: res.body || "", headers: res.headers };
}
const PASS = "correct horse 42", seed = (extra = {}) => ({ action: "seed", pass: PASS, clientId: "cid", clientSecret: "sec", accessToken: "tok-1", refreshToken: "ref-1", expAt: Date.now() + 20 * 864e5, scope: "trading", ...extra });
const env = (o) => { ["KV_REST_API_URL", "KV_REST_API_TOKEN", "UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN", "BLOB_STORE_ID", "BLOB_READ_WRITE_TOKEN", "FINDER_PASS"].forEach(k => delete process.env[k]); Object.assign(process.env, o); };
const full = () => BACKEND === "redis" ? env({ KV_REST_API_URL: REDIS, KV_REST_API_TOKEN: "redis-token", FINDER_PASS: PASS }) : env({ BLOB_STORE_ID: "store_test", FINDER_PASS: PASS });
const reset = () => { BL = new Map(); DB = new Map(); TOK = { calls: 0, fail: false, n: 0, hang: false, during: null }; RFAIL = { login: 0 }; delete process.env.KEEPER_FETCH_MS; };
const cases = [];
const t = (name, fn) => cases.push([name, fn]);
const expect = (c, why) => { if (!c) throw new Error(why); };

t("unconfigured", async () => {
  env({ FINDER_PASS: PASS }); let r = await call(load(), { action: "get", pass: PASS });
  expect(r.status === 503 && /Upstash/.test(r.body.error) && /FINDER_PASS/.test(r.body.error), `no redis → ${r.status} ${r.raw}`);
  full(); process.env.FINDER_PASS = "short123"; r = await call(load(), { action: "get", pass: "short123" });
  expect(r.status === 503 && /12/.test(r.body.error), `short pass → ${r.status} ${r.raw}`);
});
t("upstash names", async () => {
  if (BACKEND !== "redis") return;
  env({ UPSTASH_REDIS_REST_URL: REDIS, UPSTASH_REDIS_REST_TOKEN: "redis-token", FINDER_PASS: PASS }); const m = load();
  const r = await call(m, seed()); expect(r.status === 200 && r.body.ok, `seed via UPSTASH_ names → ${r.status} ${r.raw}`);
});
t("wrong pass", async () => {
  full(); const m = load(); await call(m, seed()); const r = await call(m, { action: "get", pass: "nope nope nope" });
  expect(r.status === 403 && !/tok-1|sec/.test(r.raw), `→ ${r.status} ${r.raw}`);
});
t("lockout", async () => {
  full(); const m = load(); await call(m, seed(), { ip: "9.9.9.9" });
  for (let i = 0; i < 10; i++) { const r = await call(m, { action: "get", pass: "wrong wrong " + i }, { ip: "6.6.6.6" }); expect(r.status === 403, `try ${i + 1} → ${r.status}`); }
  let r = await call(m, { action: "get", pass: PASS }, { ip: "6.6.6.6" }); expect(r.status === 429 && !/tok-1/.test(r.raw), `11th → ${r.status} ${r.raw}`);
  r = await call(m, { action: "get", pass: PASS }, { ip: "7.7.7.7" }); expect(r.status === 200 && r.body.accessToken === "tok-1", `other ip → ${r.status}`);
});
t("seed then get", async () => {
  full(); const m = load(); let r = await call(m, seed()); expect(r.status === 200 && r.body.ok === true, `seed → ${r.status} ${r.raw}`);
  r = await call(m, { action: "get", pass: PASS });
  expect(r.status === 200 && r.body.accessToken === "tok-1" && r.body.clientSecret === "sec" && r.body.clientId === "cid" && r.body.scope === "trading" && !("refreshToken" in r.body) && TOK.calls === 0, `get → ${r.raw} calls ${TOK.calls}`);
});
t("seed needs fields", async () => {
  full(); const r = await call(load(), seed({ refreshToken: "" })); expect(r.status === 400, `→ ${r.status}`);
});
t("nothing shared", async () => {
  full(); const r = await call(load(), { action: "get", pass: PASS }); expect(r.status === 404 && r.body.error, `→ ${r.status} ${r.raw}`);
});
t("renew near expiry", async () => {
  full(); const m = load(); await call(m, seed({ expAt: Date.now() + 2 * 864e5 }));
  const r = await call(m, { action: "get", pass: PASS }), st = stored();
  expect(r.body.accessToken === "tok-new-1" && st.refreshToken === "ref-new-1" && st.expAt > Date.now() + 25 * 864e5 && TOK.calls === 1, `→ ${r.raw} stored ${st.refreshToken} calls ${TOK.calls}`);
});
t("concurrent renew", async () => {
  full(); await call(load(), seed({ expAt: Date.now() + 864e5 }));
  const a = load(), b = load(); const [x, y] = await Promise.all([call(a, { action: "get", pass: PASS }), call(b, { action: "get", pass: PASS })]);
  expect(TOK.calls === 1 && x.body.accessToken === "tok-new-1" && y.body.accessToken === "tok-new-1", `calls ${TOK.calls} · ${x.raw} · ${y.raw}`);
});
t("bad token", async () => {
  full(); const m = load(); await call(m, seed());
  let r = await call(m, { action: "get", pass: PASS, bad: "tok-0-old".slice(-8) }); expect(TOK.calls === 0 && r.body.accessToken === "tok-1", `old bad renewed (${TOK.calls})`);
  r = await call(m, { action: "get", pass: PASS, bad: "tok-1".slice(-8) }); expect(TOK.calls === 1 && r.body.accessToken === "tok-new-1", `current bad → ${r.raw} calls ${TOK.calls}`);
});
t("renew failed", async () => {
  full(); const m = load(); await call(m, seed({ expAt: Date.now() + 864e5 })); TOK.fail = true;
  const r = await call(m, { action: "get", pass: PASS, bad: "tok-1" }), st = stored();
  expect(r.status === 502 && st.refreshToken === "ref-1" && st.accessToken === "tok-1", `→ ${r.status} ${r.raw} stored ${st.refreshToken}`);
});
t("cors", async () => {
  full(); const m = load(); let r = await call(m, {}, { method: "OPTIONS", origin: "http://localhost:8787" });
  expect(r.status === 204 && r.headers["access-control-allow-origin"] === "http://localhost:8787", `preflight → ${r.status} ${JSON.stringify(r.headers)}`);
  r = await call(m, { action: "get", pass: PASS }, { origin: "https://evil.example" });
  expect(r.headers["access-control-allow-origin"] !== "https://evil.example" && r.status === 403, `evil origin → ${r.status} ${JSON.stringify(r.headers)}`);
  r = await call(m, seed(), { origin: "https://alt-scanner-three.vercel.app" }); expect(r.status === 200, `same site → ${r.status}`);
});
t("forget", async () => {
  full(); const m = load(); await call(m, seed()); let r = await call(m, { action: "forget", pass: PASS }); expect(r.status === 200, `forget → ${r.status}`);
  r = await call(m, { action: "get", pass: PASS }); expect(r.status === 404, `after forget → ${r.status}`);
});
t("parallel wrong guesses", async () => {
  full(); const m = load(); await call(m, seed());
  const rs = await Promise.all(Array.from({ length: 40 }, (_, i) => call(m, { action: "get", pass: "wrong guess " + i }, { ip: "5.5.5.5" })));
  const n403 = rs.filter(r => r.status === 403).length; expect(n403 <= 10 && rs.every(r => r.status === 403 || r.status === 429), `403s ${n403} of 40`);
});
t("ipv6 /64 shares a bucket", async () => {
  full(); const m = load(); await call(m, seed());
  for (let i = 1; i <= 10; i++) await call(m, { action: "get", pass: "nope nope nope" }, { ip: `2001:db8:1:2:${i.toString(16)}::1` });
  const r = await call(m, { action: "get", pass: PASS }, { ip: "2001:db8:1:2:ff::9" }); expect(r.status === 429, `11th in the /64 → ${r.status}`);
});
t("global ceiling", async () => {
  full(); const m = load(); await call(m, seed());
  for (let i = 0; i < 100; i++) await call(m, { action: "get", pass: "nope nope nope" }, { ip: `10.0.${i >> 8}.${i & 255}` });
  const r = await call(m, { action: "get", pass: "nope nope nope" }, { ip: "10.9.9.9" }); expect(r.status === 429, `after 100 wrong from many → ${r.status}`);
});
t("counter always expires", async () => {
  full(); const m = load(); await call(m, seed()); await call(m, { action: "get", pass: "nope nope nope" }, { ip: "8.8.4.4" });
  const x = failExpiry("8.8.4.4"); expect(x > Date.now() && x <= Date.now() + 3600e3, `fail counter expiry ${x}`);
});
t("right passphrase not counted", async () => {
  full(); const m = load(); await call(m, seed());
  for (let i = 0; i < 15; i++) { const r = await call(m, { action: "get", pass: PASS }, { ip: "4.4.4.4" }); expect(r.status === 200, `right #${i + 1} → ${r.status}`); }
});
t("fetch timeout", async () => {
  full(); process.env.KEEPER_FETCH_MS = "300"; const m = load(); await call(m, seed()); TOK.hang = true; const t0 = Date.now();
  const r = await call(m, { action: "get", pass: PASS, bad: "tok-1" }); expect(r.status === 502 && Date.now() - t0 < 2000, `→ ${r.status} in ${Date.now() - t0} ms`);
});
t("lock is only released by its owner", async () => {
  full(); const m = load(); await call(m, seed({ expAt: Date.now() + 864e5 }));
  TOK.during = takeLock;
  await call(m, { action: "get", pass: PASS }); const l = lockOwner(); expect(l === "someone-else", `lock after renew: ${l}`);
});
t("new pair saved despite a flaky store", async () => {
  full(); const m = load(); await call(m, seed({ expAt: Date.now() + 864e5 })); RFAIL.login = 1;
  const r = await call(m, { action: "get", pass: PASS }), st = stored();
  expect(r.body.accessToken === "tok-new-1" && st.accessToken === "tok-new-1", `→ ${r.raw} stored ${st.accessToken}`);
});
t("bad right after a renewal is ignored", async () => {
  full(); const m = load(); await call(m, seed());
  await call(m, { action: "get", pass: PASS, bad: "tok-1" }); const r = await call(m, { action: "get", pass: PASS, bad: "tok-new-1".slice(-8) });
  expect(TOK.calls === 1 && r.body.accessToken === "tok-new-1", `calls ${TOK.calls}`);
});
t("proactive renewal failing keeps serving a valid login", async () => {
  full(); const m = load(); await call(m, seed({ expAt: Date.now() + 2 * 864e5 })); TOK.fail = true;
  const r = await call(m, { action: "get", pass: PASS }); expect(r.status === 200 && r.body.accessToken === "tok-1", `→ ${r.status} ${r.raw}`);
});
t("127.0.0.1 Mac app allowed", async () => {
  full(); const r = await call(load(), {}, { method: "OPTIONS", origin: "http://127.0.0.1:8787" }); expect(r.status === 204, `→ ${r.status}`);
});
t("method", async () => { full(); const r = await call(load(), null, { method: "GET" }); expect(r.status === 405, `GET → ${r.status}`); });
t("set-up check says nothing secret", async () => {
  full(); const m = load(); await call(m, seed()); const req = { method: "GET", url: "/api/ct-keeper?check=1", headers: { host: "x" } };
  const res = { statusCode: 200, headers: {}, setHeader(k, v) { this.headers[k] = v; }, end(b) { this.body = b; } }; await m(req, res); const j = JSON.parse(res.body);
  expect(res.statusCode === 200 && j.store === BACKEND && j.passphrase === true && j.shared === true && !/tok-1|sec|ref-1|correct horse/.test(res.body), res.body);
});

globalThis.__KEEPER_BLOB__ = fakeBlob;
for (const be of ["redis", "blob"]) { BACKEND = be;
  for (const [name, fn] of cases) { reset(); try { await fn(); console.log(`ok ${be}: ${name}`); } catch (e) { console.log(`FAIL ${be}: ${name}: ${e.message}`); } } }
