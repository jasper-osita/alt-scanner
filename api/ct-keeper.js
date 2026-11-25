// Vercel function: the shared cTrader login ("keeper"). cTrader's refresh token works once and rotates, so every device that
// renewed on its own knocked the others out. Here one place holds the login, renews it alone, and lends the current access to
// your devices when they show the passphrase (env FINDER_PASS). The login lives in Upstash Redis (REST, no packages);
// nothing is logged. Actions (POST JSON): seed (store a fresh login), get (borrow it; renews when under 3 days are left or
// when a device says cTrader rejected it), forget.
const crypto = require("crypto");
const RENEW_MS = 3 * 864e5, LOCK_S = 45, TRIES = 10, ALL_TRIES = 100, BAD_COOLDOWN = 120e3, LOCAL = ["http://localhost:8787", "http://127.0.0.1:8787"];
const FETCH_MS = () => +process.env.KEEPER_FETCH_MS || 10000;          // cTrader's token service gets 10 s; the lock outlives it

const conf = () => ({ url: process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL || "",
  token: process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN || "", pass: process.env.FINDER_PASS || "" });
async function redis(c, ...cmd) {
  const r = await fetch(c.url, { method: "POST", headers: { Authorization: "Bearer " + c.token, "Content-Type": "application/json" }, body: JSON.stringify(cmd.map(String)) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok || j.error) throw new Error("store");
  return j.result;
}
const readLogin = async c => { try { return JSON.parse((await redis(c, "GET", "ct:login")) || "null"); } catch (e) { if (e.message === "store") throw e; return null; } };
const digest = s => crypto.createHash("sha256").update(String(s)).digest();
const samePass = (a, b) => crypto.timingSafeEqual(digest(a), digest(b));
const sleep = ms => new Promise(r => setTimeout(r, ms));
const fail = (code, msg) => Object.assign(new Error(msg), { code });

const UNLOCK = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end";
let inflight = null;                                         // one renewal at a time in this instance; the Redis lock covers the others
function renew(c, seen) {
  if (inflight) return inflight;
  inflight = (async () => {
    const id = crypto.randomBytes(12).toString("hex");
    if ((await redis(c, "SET", "ct:lock", id, "NX", "EX", LOCK_S)) !== "OK") {      // someone else is renewing: wait for their result
      for (let i = 0; i < 30; i++) {
        await sleep(500); const cur = await readLogin(c);
        if (cur && cur.accessToken !== seen.accessToken) return cur;
        if (!(await redis(c, "GET", "ct:lock"))) break;
      }
      const cur = await readLogin(c); if (cur && cur.accessToken !== seen.accessToken) return cur;
      throw fail(502, (await redis(c, "GET", "ct:renewerr").catch(() => null)) || "Renewing the shared cTrader login is taking too long. Try again in a minute.");
    }
    try {
      const cur = await readLogin(c);
      if (cur && cur.accessToken !== seen.accessToken) return cur;                     // renewed between our read and the lock
      const st = cur || seen, q = new URLSearchParams({ grant_type: "refresh_token", refresh_token: st.refreshToken, client_id: st.clientId, client_secret: st.clientSecret });
      let r, j = {};
      try { r = await fetch("https://openapi.ctrader.com/apps/token?" + q, { headers: { Accept: "application/json" }, signal: AbortSignal.timeout(FETCH_MS()) }); j = await r.json().catch(() => ({})); }
      catch (e) { throw fail(502, "Couldn't reach cTrader to renew the shared login. Try again in a minute."); }
      if (!r.ok || !j.accessToken) {
        const msg = "cTrader didn't renew the shared login. Sign in to cTrader again on one device and share it.";
        await redis(c, "SET", "ct:renewerr", msg, "EX", 60).catch(() => {}); throw fail(502, msg);
      }
      const next = { ...st, accessToken: j.accessToken, refreshToken: j.refreshToken || st.refreshToken, expAt: Date.now() + (+j.expiresIn || 30 * 86400) * 1000, renewedAt: Date.now() };
      for (let k = 0; ; k++) {                                   // the old pair is spent now: losing the new one would end the shared login
        try { await redis(c, "SET", "ct:login", JSON.stringify(next)); break; } catch (e) { if (k >= 3) throw e; await sleep(300 * (k + 1)); }
      }
      return next;
    } finally { await redis(c, "EVAL", UNLOCK, 1, "ct:lock", id).catch(() => {}); }
  })();
  return inflight.finally(() => { inflight = null; });
}

module.exports = async (req, res) => {
  res.setHeader("Cache-Control", "no-store");
  const origin = req.headers.origin || "", host = req.headers.host || "";
  const okOrigin = !origin || origin.replace(/^https?:\/\//, "") === host || LOCAL.includes(origin);
  if (origin && okOrigin) {
    res.setHeader("Access-Control-Allow-Origin", origin); res.setHeader("Vary", "Origin");
    res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS"); res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  }
  if (req.method === "OPTIONS") { res.statusCode = okOrigin ? 204 : 403; return res.end(); }
  if (req.method !== "POST") { res.statusCode = 405; return res.end(); }
  const send = (code, obj) => { res.statusCode = code; res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify(obj)); };
  if (!okOrigin) return send(403, { error: "This page isn't allowed to use the shared login." });
  const c = conf();
  if (!c.url || !c.token) return send(503, { error: "The shared login isn't set up yet: add the Upstash Redis store to this Vercel project and set FINDER_PASS." });
  if (c.pass.length < 12) return send(503, { error: "Set FINDER_PASS in Vercel to a passphrase of 12 or more characters." });
  let p = req.body; if (typeof p === "string") { try { p = JSON.parse(p); } catch (e) { p = null; } }
  if (!p || typeof p !== "object") return send(400, { error: "The request was incomplete." });
  let ip = String(req.headers["x-forwarded-for"] || "").split(",")[0].trim() || (req.socket && req.socket.remoteAddress) || "?";
  if (ip.includes(":") && !ip.includes(".")) ip = ip.split(":").slice(0, 4).join(":") + "::/64";      // IPv6: one bucket per /64, not per address
  const failKey = "ct:fail:" + ip, allKey = "ct:fail:*";
  try {
    // every attempt is counted first (atomic INCR, with the hour's expiry set before), and given back when the passphrase is right
    await redis(c, "SET", failKey, "0", "EX", 3600, "NX"); await redis(c, "SET", allKey, "0", "EX", 3600, "NX");
    const n = await redis(c, "INCR", failKey), all = await redis(c, "INCR", allKey);
    if (n > TRIES || all > ALL_TRIES) return send(429, { error: "Too many wrong passphrases. Try again in an hour." });
    if (!samePass(p.pass || "", c.pass)) return send(403, { error: "That passphrase didn't work." });
    await redis(c, "DECR", failKey); await redis(c, "DECR", allKey);
    if (p.action === "seed") {
      const str = k => typeof p[k] === "string" && p[k].length > 0 && p[k].length <= 4096;
      if (!["clientId", "clientSecret", "accessToken", "refreshToken"].every(str)) return send(400, { error: "Sign in to cTrader on this device first, then share it." });
      const login = { clientId: p.clientId, clientSecret: p.clientSecret, accessToken: p.accessToken, refreshToken: p.refreshToken,
        expAt: +p.expAt > Date.now() ? +p.expAt : Date.now() + 30 * 864e5, scope: String(p.scope || "").slice(0, 40), seededAt: Date.now() };
      await redis(c, "SET", "ct:login", JSON.stringify(login));
      return send(200, { ok: true });
    }
    if (p.action === "get") {
      let st = await readLogin(c);
      if (!st) return send(404, { error: "Nothing is shared yet. Sign in to cTrader on one device and press “Share this login”." });
      const bad = String(p.bad || ""), rejected = bad.length >= 4 && st.accessToken.slice(-8) === bad && !(Date.now() - (st.renewedAt || 0) < BAD_COOLDOWN);
      if (rejected || st.expAt - Date.now() < RENEW_MS) {
        try { st = await renew(c, st); }
        catch (e) { if (rejected || !(st.expAt - Date.now() > 60e3)) throw e; }      // a renewal ahead of time failed: the current login still works, lend it
      }
      return send(200, { clientId: st.clientId, clientSecret: st.clientSecret, accessToken: st.accessToken, expAt: st.expAt, scope: st.scope });
    }
    if (p.action === "forget") { await redis(c, "DEL", "ct:login"); return send(200, { ok: true }); }
    return send(400, { error: "Unknown action." });
  } catch (e) {
    if (e.code === 502) return send(502, { error: e.message });
    return send(503, { error: "The shared login store didn't answer. Try again in a minute." });
  }
};
