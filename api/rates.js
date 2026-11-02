// Vercel function: interest rates outside the US for the Fundamentals page, no keys needed. Mirrors /proxy/rates in server.py.
//   bis      central-bank policy rates, daily (BIS): BoE, BoJ, RBA, BoC, SNB, RBNZ
//   ecb      euro-area 2Y and 10Y government yields, daily (ECB AAA curve, close to German Bunds)
//   jgb      Japan government bond yields, this month (Ministry of Finance); jgb-all is the full history (large, fetched once)
const SRC = {
  bis: "https://stats.bis.org/api/v1/data/WS_CBPOL/D.GB+JP+AU+CA+CH+NZ/all",
  ecb: "https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y+SR_10Y",
  jgb: "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv",
  "jgb-all": "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv",
};
module.exports = async (req, res) => {
  const send = (code, txt) => { res.statusCode = code; res.setHeader("Content-Type", "text/csv; charset=utf-8"); res.setHeader("Cache-Control", code === 200 ? "public, s-maxage=3600" : "no-store"); res.end(txt); };
  if (req.method !== "GET") return send(405, "GET only");
  const q = req.query || {}, base = SRC[String(q.src || "")];
  if (!base) return send(400, "unknown source");
  const p = new URLSearchParams();
  if (q.src === "bis" || q.src === "ecb") {
    const since = String(q.startPeriod || "");
    if (since && !/^\d{4}-\d{2}-\d{2}$/.test(since)) return send(400, "startPeriod must be YYYY-MM-DD");
    if (since) p.set("startPeriod", since);
    if (q.src === "bis") { p.set("detail", "dataonly"); p.set("format", "csv"); } else p.set("format", "csvdata");
  }
  try {
    const r = await fetch(base + (p.toString() ? "?" + p : ""), { headers: { Accept: "text/csv, application/vnd.sdmx.data+csv;version=1.0.0, */*", "User-Agent": "Mozilla/5.0 (The Finder)" } });
    send(r.status, await r.text());
  } catch (e) { send(502, "couldn't reach the source"); }
};
