// Tests for api/ct-keeper.js with a fake Upstash Redis (REST) and a fake cTrader token service. Prints "ok <name>" or "FAIL <name>: why".
import { createRequire } from "module";
import path from "path";
import { fileURLToPath } from "url";
const require = createRequire(import.meta.url), here = path.dirname(fileURLToPath(import.meta.url)), modPath = path.join(here, "..", "api", "ct-keeper.js");
const load = () => { delete require.cache[require.resolve(modPath)]; return require(modPath); };   // a fresh copy = another function instance

let DB = new Map(), TOK = { calls: 0, fail: false, n: 0 };
const REDIS = "https://fake-redis.example";
globalThis.fetch = async (url, opts = {}) => {
  const json = (status, body) => ({ ok: status < 400, status, json: async () => body, text: async () => JSON.stringify(body) });
  if (url.startsWith(REDIS)) {
    if ((opts.headers || {}).Authorization !== "Bearer redis-token") return json(401, { error: "unauthorized" });
    const [cmd, k, v, ...rest] = JSON.parse(opts.body), now = Date.now();
    const live = key => { const e = DB.get(key); if (e && e.exp && e.exp < now) { DB.delete(key); return null; } return e || null; };
    if (cmd === "GET") { const e = live(k); return json(200, { result: e ? e.v : null }); }
    if (cmd === "SET") { const nx = rest.includes("NX"), ex = rest.indexOf("EX"); if (nx && live(k)) return json(200, { result: null });
      DB.set(k, { v, exp: ex >= 0 ? now + +rest[ex + 1] * 1000 : 0 }); return json(200, { result: "OK" }); }
    if (cmd === "DEL") { DB.delete(k); return json(200, { result: 1 }); }
    if (cmd === "INCR") { const e = live(k), n = (e ? +e.v : 0) + 1; DB.set(k, { v: String(n), exp: e ? e.exp : 0 }); return json(200, { result: n }); }
    if (cmd === "EXPIRE") { const e = live(k); if (e) e.exp = now + +v * 1000; return json(200, { result: e ? 1 : 0 }); }
    return json(400, { error: "unknown command " + cmd });
  }
  if (url.startsWith("https://openapi.ctrader.com/apps/token")) {
    TOK.calls++; const q = new URL(url).searchParams; await new Promise(r => setTimeout(r, 150));
    if (TOK.fail || q.get("grant_type") !== "refresh_token" || q.get("client_secret") !== "sec") return json(400, { errorCode: "ACCESS_DENIED", description: "bad" });
    TOK.n++; return json(200, { accessToken: "tok-new-" + TOK.n, refreshToken: "ref-new-" + TOK.n, expiresIn: 2628000, tokenType: "bearer" });
  }
  return json(404, {});
};
async function call(mod, body, { method = "POST", origin = "", ip = "1.1.1.1" } = {}) {
  const req = { method, headers: { host: "alt-scanner-three.vercel.app", ...(origin ? { origin } : {}), "x-forwarded-for": ip }, body };
  const res = { statusCode: 200, headers: {}, setHeader(k, v) { this.headers[k.toLowerCase()] = v; }, end(b) { this.body = b; } };
  await mod(req, res); let j = null; try { j = JSON.parse(res.body || "null"); } catch (e) {}
  return { status: res.statusCode, body: j, raw: res.body || "", headers: res.headers };
}
const PASS = "correct horse 42", seed = (extra = {}) => ({ action: "seed", pass: PASS, clientId: "cid", clientSecret: "sec", accessToken: "tok-1", refreshToken: "ref-1", expAt: Date.now() + 20 * 864e5, scope: "trading", ...extra });
const env = (o) => { ["KV_REST_API_URL", "KV_REST_API_TOKEN", "UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN", "FINDER_PASS"].forEach(k => delete process.env[k]); Object.assign(process.env, o); };
const full = () => env({ KV_REST_API_URL: REDIS, KV_REST_API_TOKEN: "redis-token", FINDER_PASS: PASS });
const reset = () => { DB = new Map(); TOK = { calls: 0, fail: false, n: 0 }; };
const cases = [];
const t = (name, fn) => cases.push([name, fn]);
const expect = (c, why) => { if (!c) throw new Error(why); };

t("unconfigured", async () => {
  env({ FINDER_PASS: PASS }); let r = await call(load(), { action: "get", pass: PASS });
  expect(r.status === 503 && /Upstash/.test(r.body.error) && /FINDER_PASS/.test(r.body.error), `no redis → ${r.status} ${r.raw}`);
  env({ KV_REST_API_URL: REDIS, KV_REST_API_TOKEN: "redis-token", FINDER_PASS: "short123" }); r = await call(load(), { action: "get", pass: "short123" });
  expect(r.status === 503 && /12/.test(r.body.error), `short pass → ${r.status} ${r.raw}`);
});
t("upstash names", async () => {
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
  const r = await call(m, { action: "get", pass: PASS }), st = JSON.parse(DB.get("ct:login").v);
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
  const r = await call(m, { action: "get", pass: PASS }), st = JSON.parse(DB.get("ct:login").v);
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
t("method", async () => { full(); const r = await call(load(), null, { method: "GET" }); expect(r.status === 405, `GET → ${r.status}`); });

for (const [name, fn] of cases) { reset(); try { await fn(); console.log("ok " + name); } catch (e) { console.log(`FAIL ${name}: ${e.message}`); } }
