// Vercel function: the shared cTrader login ("keeper"). cTrader's refresh token works once and rotates, so every device that
// renewed on its own knocked the others out. Here one place holds the login, renews it alone, and lends the current access to
// your devices when they show the passphrase (env FINDER_PASS). The login lives in the project's private Vercel Blob store
// (or Upstash Redis if that is connected instead); nothing is logged. Actions (POST JSON): seed (store a fresh login),
// get (borrow it; renews when under 3 days are left or when a device says cTrader rejected it), forget.
// GET ?check=1 says whether it is set up, without anything secret.
const crypto = require("crypto");
const RENEW_MS = 3 * 864e5, LOCK_S = 45, TRIES = 10, ALL_TRIES = 100, BAD_COOLDOWN = 120e3, HOUR = 3600e3, LOCAL = ["http://localhost:8787", "http://127.0.0.1:8787"];
const FETCH_MS = () => +process.env.KEEPER_FETCH_MS || 10000;          // cTrader's token service gets 10 s; the lock outlives it
const digest = s => crypto.createHash("sha256").update(String(s)).digest();
const samePass = (a, b) => crypto.timingSafeEqual(digest(a), digest(b));
const sleep = ms => new Promise(r => setTimeout(r, ms));
const fail = (code, msg) => Object.assign(new Error(msg), { code });
const storeErr = () => new Error("store");

/* ---- storage: count (atomic, expiring), the login, a lock only its owner releases, a short-lived error note ---- */
function redisStore(url, token) {
  const R = async (...cmd) => {
    const r = await fetch(url, { method: "POST", headers: { Authorization: "Bearer " + token, "Content-Type": "application/json" }, body: JSON.stringify(cmd.map(String)) });
    const j = await r.json().catch(() => ({})); if (!r.ok || j.error) throw storeErr(); return j.result;
  };
  const UNLOCK = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end";
  return { kind: "redis",
    count: async k => { await R("SET", "ct:fail:" + k, "0", "EX", HOUR / 1000, "NX"); return R("INCR", "ct:fail:" + k); },
    uncount: k => R("DECR", "ct:fail:" + k),
    getLogin: async () => { const v = await R("GET", "ct:login"); try { return JSON.parse(v || "null"); } catch (e) { return null; } },
    setLogin: v => R("SET", "ct:login", JSON.stringify(v)),
    delLogin: () => R("DEL", "ct:login"),
    lock: async id => (await R("SET", "ct:lock", id, "NX", "EX", LOCK_S)) === "OK",
    locked: async () => !!(await R("GET", "ct:lock")),
    unlock: id => R("EVAL", UNLOCK, 1, "ct:lock", id),
    setNote: m => R("SET", "ct:renewerr", m, "EX", 60),
    getNote: () => R("GET", "ct:renewerr") };
}
function blobStore() {                                       // private Vercel Blob: create-only writes and ETag conditional writes stand in for Redis' atomic commands
  const B = globalThis.__KEEPER_BLOB__ || require("@vercel/blob"), P = "keeper/";
  const read = async path => {
    let r; try { r = await B.get(P + path, { access: "private", useCache: false }); } catch (e) { if (e && e.name === "BlobNotFoundError") return { v: null, etag: null }; throw storeErr(); }
    if (!r || r.statusCode !== 200) return { v: null, etag: null };
    let v = null; try { v = JSON.parse(await new Response(r.stream).text()); } catch (e) {}
    return { v, etag: r.blob.etag };
  };
  const write = async (path, v, etag) => {                  // etag: only if unchanged; "new": only if absent; undefined: always. → false on a conflict
    const o = { access: "private", contentType: "application/json", addRandomSuffix: false, cacheControlMaxAge: 60 };
    if (etag === undefined) o.allowOverwrite = true; else if (etag !== "new") o.ifMatch = etag;
    try { await B.put(P + path, JSON.stringify(v), o); return true; }
    catch (e) { if (e && (e.name === "BlobPreconditionFailedError" || /exist/i.test(e.message || ""))) return false; throw storeErr(); }
  };
  const change = async (path, fn) => {                       // read-modify-write until nobody else wrote in between
    for (let i = 0; i < 12; i++) {
      const cur = await read(path), next = fn(cur.v);
      if (await write(path, next, cur.etag || "new")) return next;
      await sleep(20 + Math.random() * 60 * (i + 1));
    }
    return null;
  };
  const fpath = k => "fail/" + k.replace(/[^a-z0-9.]/gi, "_") + ".json";
  return { kind: "blob",
    count: async k => { const n = await change(fpath(k), v => v && v.until > Date.now() ? { n: v.n + 1, until: v.until } : { n: 1, until: Date.now() + HOUR }); return n ? n.n : Infinity; },   // too busy to count: treat as over the limit
    uncount: k => change(fpath(k), v => v && v.until > Date.now() ? { n: Math.max(0, v.n - 1), until: v.until } : { n: 0, until: Date.now() + HOUR }),
    getLogin: async () => (await read("login.json")).v,
    setLogin: async v => { if (!(await write("login.json", v))) throw storeErr(); },
    delLogin: async () => { await write("login.json", null); },
    lock: async id => { const cur = await read("lock.json"); if (cur.v && cur.v.until > Date.now()) return false;
      return write("lock.json", { id, until: Date.now() + LOCK_S * 1000 }, cur.etag || "new"); },
    locked: async () => { const cur = await read("lock.json"); return !!(cur.v && cur.v.until > Date.now()); },
    unlock: async id => { const cur = await read("lock.json"); if (cur.v && cur.v.id === id) await write("lock.json", { id: null, until: 0 }, cur.etag); },
    setNote: m => write("renewerr.json", { m, until: Date.now() + 60e3 }),
    getNote: async () => { const v = (await read("renewerr.json")).v; return v && v.until > Date.now() ? v.m : null; } };
}
function storeFor() {
  const url = process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL, token = process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN;
  if (url && token) return redisStore(url, token);
  if (process.env.BLOB_STORE_ID || process.env.BLOB_READ_WRITE_TOKEN) return blobStore();
  return null;
}

let inflight = null;                                         // one renewal at a time in this instance; the store's lock covers the others
function renew(S, seen) {
  if (inflight) return inflight;
  inflight = (async () => {
    const id = crypto.randomBytes(12).toString("hex");
    if (!(await S.lock(id))) {                               // someone else is renewing: wait for their result
      for (let i = 0; i < 30; i++) {
        await sleep(500); const cur = await S.getLogin();
        if (cur && cur.accessToken !== seen.accessToken) return cur;
        if (!(await S.locked())) break;
      }
      const cur = await S.getLogin(); if (cur && cur.accessToken !== seen.accessToken) return cur;
      throw fail(502, (await S.getNote().catch(() => null)) || "Renewing the shared cTrader login is taking too long. Try again in a minute.");
    }
    try {
      const cur = await S.getLogin();
      if (cur && cur.accessToken !== seen.accessToken) return cur;                     // renewed between our read and the lock
      const st = cur || seen, q = new URLSearchParams({ grant_type: "refresh_token", refresh_token: st.refreshToken, client_id: st.clientId, client_secret: st.clientSecret });
      let r, j = {};
      try { r = await fetch("https://openapi.ctrader.com/apps/token?" + q, { headers: { Accept: "application/json" }, signal: AbortSignal.timeout(FETCH_MS()) }); j = await r.json().catch(() => ({})); }
      catch (e) { throw fail(502, "Couldn't reach cTrader to renew the shared login. Try again in a minute."); }
      if (!r.ok || !j.accessToken) {
        const msg = "cTrader didn't renew the shared login. Sign in to cTrader again on one device and share it.";
        await S.setNote(msg).catch(() => {}); throw fail(502, msg);
      }
      const next = { ...st, accessToken: j.accessToken, refreshToken: j.refreshToken || st.refreshToken, expAt: Date.now() + (+j.expiresIn || 30 * 86400) * 1000, renewedAt: Date.now() };
      for (let k = 0; ; k++) {                                   // the old pair is spent now: losing the new one would end the shared login
        try { await S.setLogin(next); break; } catch (e) { if (k >= 3) throw e; await sleep(300 * (k + 1)); }
      }
      return next;
    } finally { await S.unlock(id).catch(() => {}); }
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
  const send = (code, obj) => { res.statusCode = code; res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify(obj)); };
  const S = storeFor(), pass = process.env.FINDER_PASS || "";
  if (req.method === "GET" && /[?&]check=1\b/.test(req.url || "")) {     // set-up check: nothing secret in it
    let login = null; try { login = S ? !!(await S.getLogin()) : null; } catch (e) { login = "store didn't answer"; }
    return send(200, { store: S ? S.kind : null, passphrase: pass.length >= 12, shared: login });
  }
  if (req.method === "OPTIONS") { res.statusCode = okOrigin ? 204 : 403; return res.end(); }
  if (req.method !== "POST") { res.statusCode = 405; return res.end(); }
  if (!okOrigin) return send(403, { error: "This page isn't allowed to use the shared login." });
  if (!S) return send(503, { error: "The shared login isn't set up yet: connect a Blob store (or the Upstash Redis store) to this Vercel project and set FINDER_PASS." });
  if (pass.length < 12) return send(503, { error: "Set FINDER_PASS in Vercel to a passphrase of 12 or more characters." });
  let p = null; try { p = req.body; if (typeof p === "string") p = JSON.parse(p); } catch (e) { p = null; }
  if (!p || typeof p !== "object") return send(400, { error: "The request was incomplete." });
  let ip = String(req.headers["x-forwarded-for"] || "").split(",")[0].trim() || (req.socket && req.socket.remoteAddress) || "?";
  if (ip.includes(":") && !ip.includes(".")) ip = ip.split(":").slice(0, 4).join(":") + "::/64";      // IPv6: one bucket per /64, not per address
  try {
    // every attempt is counted first (atomically, expiring after an hour) and given back when the passphrase is right
    const n = await S.count(ip), all = await S.count("*");
    if (n > TRIES || all > ALL_TRIES) return send(429, { error: "Too many wrong passphrases. Try again in an hour." });
    if (!samePass(p.pass || "", pass)) return send(403, { error: "That passphrase didn't work." });
    await S.uncount(ip); await S.uncount("*");
    if (p.action === "seed") {
      const str = k => typeof p[k] === "string" && p[k].length > 0 && p[k].length <= 4096;
      if (!["clientId", "clientSecret", "accessToken", "refreshToken"].every(str)) return send(400, { error: "Sign in to cTrader on this device first, then share it." });
      const login = { clientId: p.clientId, clientSecret: p.clientSecret, accessToken: p.accessToken, refreshToken: p.refreshToken,
        expAt: +p.expAt > Date.now() ? +p.expAt : Date.now() + 30 * 864e5, scope: String(p.scope || "").slice(0, 40), seededAt: Date.now() };
      await S.setLogin(login);
      return send(200, { ok: true });
    }
    if (p.action === "get") {
      let st = await S.getLogin();
      if (!st) return send(404, { error: "Nothing is shared yet. Sign in to cTrader on one device and press “Share this login”." });
      const bad = String(p.bad || ""), rejected = bad.length >= 4 && st.accessToken.slice(-8) === bad && !(Date.now() - (st.renewedAt || 0) < BAD_COOLDOWN);
      if (rejected || st.expAt - Date.now() < RENEW_MS) {
        try { st = await renew(S, st); }
        catch (e) { if (rejected || !(st.expAt - Date.now() > 60e3)) throw e; }      // a renewal ahead of time failed: the current login still works, lend it
      }
      return send(200, { clientId: st.clientId, clientSecret: st.clientSecret, accessToken: st.accessToken, expAt: st.expAt, scope: st.scope });
    }
    if (p.action === "forget") { await S.delLogin(); return send(200, { ok: true }); }
    return send(400, { error: "Unknown action." });
  } catch (e) {
    if (e.code === 502) return send(502, { error: e.message });
    return send(503, { error: "The shared login store didn't answer. Try again in a minute." });
  }
};
