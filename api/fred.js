// Vercel function: FRED data for the Fundamentals page. Adds the site's own FRED key (the FRED_API_KEY environment variable,
// set in Vercel → Settings → Environment Variables) when the browser doesn't send one, so the key never sits in the code or the page.
// Only the series the page uses are allowed. Mirrors /proxy/fred in server.py.
const SERIES = new Set(["DFEDTARU", "ECBDFR", "IRSTCI01GBM156N", "IRSTCI01JPM156N", "IRSTCI01AUM156N", "IRSTCI01CAM156N", "IRSTCI01CHM156N", "IRSTCI01NZM156N",
  "CPIAUCSL", "UNRATE", "T10YIE", "BAMLH0A0HYM2", "VIXCLS"]);
module.exports = async (req, res) => {
  res.setHeader("Cache-Control", "no-store");
  const send = (code, obj) => { res.statusCode = code; res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify(obj)); };
  if (req.method !== "GET") return send(405, { error_message: "GET only" });
  const q = req.query || {}, id = String(q.series_id || "");
  if (!SERIES.has(id)) return send(400, { error_message: "series not allowed" });
  const key = String(q.api_key || process.env.FRED_API_KEY || "").trim();
  if (!/^[a-z0-9]{20,40}$/i.test(key)) return send(400, { error_message: "no api_key: add FRED_API_KEY in Vercel or paste a key in the app" });
  const p = new URLSearchParams({ series_id: id, api_key: key, file_type: "json", sort_order: "desc", limit: String(Math.min(1000, +q.limit || 420)) });
  try {
    const r = await fetch("https://api.stlouisfed.org/fred/series/observations?" + p, { headers: { Accept: "application/json" } });
    res.statusCode = r.status; res.setHeader("Content-Type", "application/json"); res.end(await r.text());
  } catch (e) { send(502, { error_message: "couldn't reach FRED" }); }
};
