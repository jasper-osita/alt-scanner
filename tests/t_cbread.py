import asyncio, sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPECT = {k: v for k, v in json.load(open(os.path.join(ROOT, "tests/cb/expect.json"))).items() if not k.startswith("_")}
# Central bank reads: the relay's allowlist, the statement reader, verdict and lean, the watcher, the Fundamentals panel and the brief.

def check(ok, msg):                               # the runner flags a Traceback
    if not ok: raise AssertionError(msg)

def relay_check():                                 # server.py only ever fetches the six banks' own sites
    sys.path.insert(0, ROOT); import server
    seen = []; server.cached_get = lambda key, url, ttl, headers: (seen.append(url), (200, b"ok"))[1]
    bad = ["/proxy/cbpage/fed/@evil.com/x", "/proxy/cbpage/fed/../x", "/proxy/cbpage/fed//evil.com/x", "/proxy/cbpage/fed/a%2Fb",
           "/proxy/cbpage/fed/a:b", "/proxy/cbpage/xyz/feeds/a.xml", "/proxy/cbpage/fed/", "/proxy/cbpage/fed/a?b=1"]
    codes = [server.relay_fund(p, "")[0] for p in bad]
    print("0) relay: abusive paths ->", codes, "| fetched:", seen)
    check(all(c == 400 for c in codes) and not seen, "relay let a bad path through")
    ok = server.relay_fund("/proxy/cbpage/fed/feeds/press_monetary.xml", "")[0], server.relay_fund("/proxy/cbpage/ecb/press/pr/date/2026/html/ecb.mp261029~9a493adf17.en.html", "")[0]
    print("   valid paths ->", ok, seen)
    check(seen == ["https://www.federalreserve.gov/feeds/press_monetary.xml", "https://www.ecb.europa.eu/press/pr/date/2026/html/ecb.mp261029~9a493adf17.en.html"], "relay built the wrong URL")

async def main():
    relay_check()
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1500, "height": 1000}, color_scheme="dark")
        await setup(ctx); await setup_extra(ctx); await setup_fund(ctx); await setup_cb(ctx)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        q = lambda js, arg=None: pg.evaluate(js, arg)
        print("   mock serves a sample:", await q("async () => { const r = await fetch('/proxy/cbpage/fed/feeds/press_monetary.xml'); return [r.status, (await r.text()).includes('FOMC statement')]; }"))
        # 1) the reader: each bank's decision list, then each saved statement against what was read by hand (tests/cb/expect.json)
        LISTS = {"USD": ["fed/feeds/press_monetary.xml", "newsevents/pressreleases/monetary20261028a.htm", 4], "EUR": ["ecb/press/govcdec/mopo/2026/html/index_include.en.html", "press/pr/date/2026/html/ecb.mp261029~9a493adf17.en.html", 5],
                 "GBP": ["boe/rss/news", "monetary-policy-summary-and-minutes/2026/november-2026", 3], "JPY": ["boj/en/rss/whatsnew.xml", "en/mopo/mpmdeci/mpr_2026/k261030a.pdf", 1],
                 "AUD": ["rba/media-releases/2026/", "media-releases/2026/mr-26-30.html", 6], "CAD": ["boc/content_type/press-releases/feed/", "2026/10/fad-press-release-2026-10-28/", 3]}
        items = await q("""async L => { const o = {}; for (const [c, [f]] of Object.entries(L)) { const it = cbItems(c, await (await fetch('/proxy/cbpage/' + f)).text()); o[c] = [it.length, it[0] && it[0].path, it[0] && it[0].title, it.every((x, i) => !i || x.t <= it[i - 1].t && x.t > 0)]; } return o; }""", LISTS)
        for c, (n, path, title, ordered) in items.items():
            print(f"1) {c} list: {n} decisions, newest {path} ({title}), newest first: {ordered}")
            check(n >= LISTS[c][2] and path == LISTS[c][1] and ordered, f"{c} decision list read wrong")
        got = await q("""async E => { const o = []; for (const [k, e] of Object.entries(E)) { const p = cbParse(e.ccy, await (await fetch('/proxy/cbpage/' + k)).text());
            o.push([k, p.ok, p.move, p.rate, p.hawk, p.dove, p.sentences.length, p.sentences.slice(0, 2)]); } return o; }""", EXPECT)
        for k, ok, move, rate, hawk, dove, ns, first in got:
            e = EXPECT[k]; good = ok and move == e["move"] and rate == e["rate"] and hawk == e["hawk"] and dove == e["dove"] and ns >= e["minSentences"]
            print(f"   {'ok ' if good else 'BAD'} {k.split('/')[0]} {k.split('/')[-1] or k.split('/')[-2]}: {move} {rate} hawk {hawk} dove {dove}, {ns} sentences | {first[0][:70] if first else ''}")
            check(good, f"{k}: read {move} {rate} {hawk}/{dove} {ns}, expected {e}")
        print("   BoJ PDF:", await q("() => cbParse('JPY', '', 'Statement on Monetary Policy', 'en/mopo/mpmdeci/mpr_2026/k261030a.pdf')"))
        # 2) wording changes, verdict, lean
        V = await q("""() => { const E = {added: [], dropped: []}, r = {};
          r.surprise = cbVerdict({move: "hike", rate: 4.25, hawk: 0, dove: 0}, E, 4.0); r.asExp = cbVerdict({move: "hike", rate: 4.0, hawk: 0, dove: 0}, E, 4.0);
          r.doves = cbVerdict({move: "hold", rate: 4, hawk: 0, dove: 2}, E, 4); r.words = cbVerdict({move: "hold", rate: 4, hawk: 0, dove: 0}, {added: ["Upside risks to inflation have increased."], dropped: ["The Committee will consider further adjustments to the target range."]}, 4);
          r.noFc = cbVerdict({move: "hike", rate: 4, hawk: 0, dove: 0}, E, null);
          r.dates = cbDiff(["In September, inflation rose to 3.1 percent."], ["In October, inflation rose to 2.9 percent."]);
          const L = (c, l) => cbLean(c, l).map(x => x.k + " " + x.dir); r.usd = L("USD", "Hawkish"); r.jpy = L("JPY", "Hawkish"); r.eurDove = L("EUR", "Dovish"); r.none = L("USD", "As expected"); return r; }""")
        print("2) surprise:", V["surprise"]["label"], V["surprise"]["score"], V["surprise"]["why"][0], "| as expected:", V["asExp"]["label"], "| 2 doves:", V["doves"]["label"], "| wording:", V["words"]["score"], V["words"]["label"], "| no forecast:", V["noFc"]["label"], V["noFc"]["why"])
        check(V["surprise"]["label"] == "Hawkish" and "4.25%" in V["surprise"]["why"][0] and "4.00%" in V["surprise"]["why"][0], "a surprise hike should read hawkish")
        check(V["asExp"]["label"] == "As expected" and V["doves"]["label"] == "Dovish" and V["words"]["score"] == 2 and V["words"]["label"] == "Hawkish", "verdict scoring")
        check(V["noFc"]["label"] == "As expected" and any("no forecast to compare" in w.lower() for w in V["noFc"]["why"]), "no forecast")
        check(V["dates"] == {"added": [], "dropped": []}, f"month and number changes aren't wording changes: {V['dates']}")
        print("   lean USD hawkish:", V["usd"], "| JPY hawkish:", V["jpy"], "| EUR dovish:", V["eurDove"], "| as expected:", V["none"])
        check(all(x in V["usd"] for x in ["Gold short", "Nasdaq 100 short", "US dollar long", "EUR/USD short", "USD/JPY long"]), "USD lean")
        check(all(x in V["jpy"] for x in ["USD/JPY short", "Nikkei 225 short"]), "JPY lean")
        check("EUR/USD short" in V["eurDove"] and "EUR/GBP short" in V["eurDove"] and V["none"] == [], "EUR dovish lean / none when as expected")
        for prev, cur, na, nd in json.load(open(os.path.join(ROOT, "tests/cb/expect.json")))["_diffs"]:
            d = await q("""async ([a, b]) => { const p = cbParse('USD', await (await fetch('/proxy/cbpage/' + a)).text()), c = cbParse('USD', await (await fetch('/proxy/cbpage/' + b)).text()); return cbDiff(p.sentences, c.sentences); }""", [prev, cur])
            print(f"   {cur.split('/')[-1]} vs {prev.split('/')[-1]}: +{len(d['added'])} -{len(d['dropped'])} | + {[x[:60] for x in d['added']]}")
            check(len(d["added"]) == na and len(d["dropped"]) == nd, f"diff {prev} -> {cur}")
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
