// Vercel function: cTrader sign-in for the deployed site. Swaps cTrader's one-minute sign-in code (or a refresh token)
// for tokens. The browser can't call cTrader's token service directly (no CORS), so this does it server-side.
// Nothing is logged or stored; only same-site POSTs are accepted. Mirrors POST /api/ct-token in server.py.
module.exports = async (req, res) => {
  res.setHeader("Cache-Control", "no-store");
  if (req.method !== "POST") { res.statusCode = 405; return res.end(); }
  const origin = req.headers.origin || "", host = req.headers.host || "";
  if (origin && origin.replace(/^https?:\/\//, "") !== host) { res.statusCode = 403; return res.end(); }
  let p = req.body;
  if (typeof p === "string") { try { p = JSON.parse(p); } catch (e) { p = null; } }
  const send = (code, obj) => { res.statusCode = code; res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify(obj)); };
  if (!p || !["authorization_code", "refresh_token"].includes(p.grant_type)) return send(400, { errorCode: "BAD_REQUEST", description: "the sign-in request was incomplete" });
  const q = new URLSearchParams();
  ["grant_type", "code", "redirect_uri", "client_id", "client_secret", "refresh_token"].forEach(k => { if (p[k]) q.set(k, String(p[k]).slice(0, 2048)); });
  try {
    const r = await fetch("https://openapi.ctrader.com/apps/token?" + q, { headers: { Accept: "application/json" } });
    const body = await r.text();
    res.statusCode = r.status; res.setHeader("Content-Type", "application/json"); res.end(body);
  } catch (e) { send(502, { errorCode: "UNREACHABLE", description: "couldn't reach cTrader's sign-in service" }); }
};
