// Vercel function: EIA weekly oil and gas stocks for the Fundamentals page. Adds the site's own EIA key (the EIA_API_KEY environment variable,
// set in Vercel → Settings → Environment Variables; free at eia.gov/opendata) when the browser doesn't send one. Mirrors /proxy/eia in server.py.
const SERIES = new Set(["PET.WCESTUS1.W", "PET.WGTSTUS1.W", "PET.WDISTUS1.W", "PET.W_EPC0_SAX_YCUOK_MBBL.W", "NG.NW2_EPG0_SWO_R48_BCF.W"]);
module.exports = async (req, res) => {
  res.setHeader("Cache-Control", "no-store");
  const send = (code, obj) => { res.statusCode = code; res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify(obj)); };
  if (req.method !== "GET") return send(405, { error: "GET only" });
  const q = req.query || {}, id = String(q.series || "");
  if (!SERIES.has(id)) return send(400, { error: "series not allowed" });
  const key = String(q.api_key || process.env.EIA_API_KEY || "").trim();
  if (!/^[A-Za-z0-9]{20,64}$/.test(key)) return send(400, { error: "no api_key: add EIA_API_KEY in Vercel or paste a key in the app" });
  try {
    const r = await fetch(`https://api.eia.gov/v2/seriesid/${id}?` + new URLSearchParams({ api_key: key, length: "400" }), { headers: { Accept: "application/json" } });
    res.statusCode = r.status; res.setHeader("Content-Type", "application/json"); res.end(await r.text());
  } catch (e) { send(502, { error: "couldn't reach the EIA" }); }
};
