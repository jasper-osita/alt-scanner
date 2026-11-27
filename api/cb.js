// Vercel function: one page from a central bank's own site for the Fundamentals "Central bank reads" (mirrors /proxy/cbpage in server.py).
// Only the six banks' sites; the path, and any redirect, must stay on that bank's site. Sent back as plain text in a sandbox,
// so a bank page can never run as a page of this site. Called as /proxy/cbpage?bank=<key>&p=<path> (vercel.json rewrite).
const HOSTS = { fed: "https://www.federalreserve.gov", ecb: "https://www.ecb.europa.eu", boe: "https://www.bankofengland.co.uk",
  boj: "https://www.boj.or.jp", rba: "https://www.rba.gov.au", boc: "https://www.bankofcanada.ca" };
const UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36";
module.exports = async (req, res) => {
  res.setHeader("Cache-Control", "no-store"); res.setHeader("X-Content-Type-Options", "nosniff"); res.setHeader("Content-Security-Policy", "sandbox; default-src 'none'");
  const send = (code, text) => { res.statusCode = code; res.setHeader("Content-Type", "text/plain; charset=utf-8"); res.end(text); };
  if (req.method !== "GET") return send(405, "GET only");
  const q = req.query || {}, bank = String(q.bank || ""), p = String(q.p || "");
  if (!HOSTS[bank] || !/^[A-Za-z0-9_.~-][A-Za-z0-9/_.~-]*$/.test(p) || p.includes("..") || p.includes("//")) return send(400, '{"error":"not allowed"}');
  let url = HOSTS[bank] + "/" + p;
  try {
    for (let hop = 0; hop < 4; hop++) {
      const r = await fetch(url, { redirect: "manual", headers: { "User-Agent": UA, Accept: "text/html,application/xhtml+xml,application/xml,*/*" } });
      const loc = r.status >= 300 && r.status < 400 ? r.headers.get("location") : null;
      if (!loc) return send(r.status, await r.text());
      const next = new URL(loc, url); if (next.origin !== HOSTS[bank]) return send(502, "the bank's site redirected elsewhere");
      url = next.href;
    }
    return send(502, "too many redirects");
  } catch (e) { return send(502, "couldn't reach the bank's site"); }
};
