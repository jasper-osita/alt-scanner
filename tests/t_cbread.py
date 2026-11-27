import asyncio, sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPECT = {k: v for k, v in json.load(open(os.path.join(ROOT, "tests/cb/expect.json"))).items() if not k.startswith("_")}
# Central bank reads: the relay's allowlist, the statement reader, verdict and lean, the watcher, the Fundamentals panel and the brief.

def check(ok, msg):                               # the runner flags a Traceback
    if not ok: raise AssertionError(msg)

def relay_check():                                 # server.py and the Vercel function only ever fetch the six banks' own sites
    sys.path.insert(0, ROOT); import server, subprocess
    from urllib.parse import urlencode
    seen = []; server.cached_get = lambda key, url, ttl, headers, *a, **k: (seen.append(url), (200, b"ok"))[1]
    bad = [("fed", "@evil.com/x"), ("fed", "../x"), ("fed", "/evil.com/x"), ("fed", "a%2Fb"), ("fed", "a:b"), ("xyz", "feeds/a.xml"), ("fed", ""), ("fed", "a?b=1"), ("fed", "a b"), ("fed", "a//b")]
    codes = [server.relay_fund("/proxy/cbpage", urlencode({"bank": b, "p": x}))[0] for b, x in bad]
    old = server.relay_fund("/proxy/cbpage/fed/feeds/press_monetary.xml", "")[0]
    print("0) relay: abusive ->", codes, "| old path form ->", old, "| fetched:", seen)
    check(all(c == 400 for c in codes) and old in (400, 404) and not seen, "relay let a bad path through")
    ok = [server.relay_fund("/proxy/cbpage", urlencode({"bank": "fed", "p": "feeds/press_monetary.xml"}))[0], server.relay_fund("/proxy/cbpage", urlencode({"bank": "ecb", "p": "press/pr/date/2026/html/ecb.mp261029~9a493adf17.en.html"}))[0]]
    print("   valid ->", ok, seen)
    check(seen == ["https://www.federalreserve.gov/feeds/press_monetary.xml", "https://www.ecb.europa.eu/press/pr/date/2026/html/ecb.mp261029~9a493adf17.en.html"], "relay built the wrong URL")
    # the Mac relay follows a redirect only on the bank's own site (as the Vercel function does)
    import urllib.request
    rh = server.SameHostRedirect(); rq = urllib.request.Request("https://www.federalreserve.gov/a")
    off = rh.redirect_request(rq, None, 301, "Moved", {}, "https://evil.example/x"); same = rh.redirect_request(rq, None, 301, "Moved", {}, "https://www.federalreserve.gov/b")
    print("   Mac relay redirect: off-site ->", off, "| same site ->", same and same.full_url)
    check(off is None and same is not None and same.full_url == "https://www.federalreserve.gov/b", "Mac relay follows redirects off the bank's site")
    # the Vercel function (api/cb.js): same allowlist, redirects must stay on the bank's site, served as plain text in a sandbox
    NODE = r"""
const h = require(process.argv[1]); const seen = []; let plan = [];
const mk = (status, body, loc) => ({ status, headers: { get: k => k.toLowerCase() === "location" ? loc || null : null }, text: async () => body });
global.fetch = async (url, o) => { seen.push([url, o && o.redirect]); return plan.shift() || mk(200, "ok"); };
const run = async (query, p0 = []) => { plan = p0; const H = {}; let code = 0, body = "";
  await h({ method: "GET", query }, { setHeader: (k, v) => { H[k.toLowerCase()] = v; }, set statusCode(c) { code = c; }, get statusCode() { return code; }, end: b => { body = String(b || ""); } });
  return { code, ct: H["content-type"], csp: H["content-security-policy"], nos: H["x-content-type-options"] }; };
(async () => { const o = { bad: [] };
  for (const [b, p] of [["fed", "@evil.com/x"], ["fed", "../x"], ["fed", "/evil.com/x"], ["fed", "a%2Fb"], ["fed", "a:b"], ["xyz", "feeds/a.xml"], ["fed", ""], ["fed", "a//b"]]) o.bad.push((await run({ bank: b, p })).code);
  o.fetchedForBad = seen.length;
  let n = seen.length; o.ok = await run({ bank: "ecb", p: "press/pr/date/2026/html/ecb.mp261029~9a493adf17.en.html" }); o.okUrls = seen.slice(n);
  o.off = await run({ bank: "fed", p: "x.htm" }, [mk(301, "", "https://evil.example/x")]);
  n = seen.length; o.same = await run({ bank: "boc", p: "2026/10/fad-press-release-2026-10-28/" }, [mk(301, "", "/2026/10/fad-press-release-2026-10-28/index.html"), mk(200, "page")]); o.sameUrls = seen.slice(n).map(x => x[0]);
  console.log(JSON.stringify(o)); })().catch(e => console.log(JSON.stringify({ error: String(e) })));
"""
    r = subprocess.run(["node", "-e", NODE, os.path.join(ROOT, "api/cb.js")], capture_output=True, text=True)
    o = json.loads((r.stdout or "{}").strip().splitlines()[-1] if r.stdout.strip() else json.dumps({"error": r.stderr[-300:]}))
    print("   Vercel function:", o)
    check(not o.get("error") and all(c == 400 for c in o["bad"]) and o["fetchedForBad"] == 0, "Vercel function let a bad path through")
    check(o["ok"]["code"] == 200 and o["ok"]["ct"].startswith("text/plain") and "sandbox" in o["ok"]["csp"] and o["ok"]["nos"] == "nosniff"
          and o["okUrls"] == [["https://www.ecb.europa.eu/press/pr/date/2026/html/ecb.mp261029~9a493adf17.en.html", "manual"]], "Vercel function fetch / headers")
    check(o["off"]["code"] == 502 and o["same"]["code"] == 200 and o["sameUrls"] == ["https://www.bankofcanada.ca/2026/10/fad-press-release-2026-10-28/", "https://www.bankofcanada.ca/2026/10/fad-press-release-2026-10-28/index.html"], "Vercel function redirects")
    v = json.load(open(os.path.join(ROOT, "vercel.json")))
    rw = [x for x in v["rewrites"] if "cbpage" in x["source"]]
    print("   vercel.json cbpage rewrites:", rw)
    check(rw == [{"source": "/proxy/cbpage", "destination": "/api/cb"}], "vercel.json should send /proxy/cbpage to the function only (cleanUrls would mangle .html paths)")

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
        await q("() => { window.cbU = k => '/proxy/cbpage?bank=' + k.slice(0, k.indexOf('/')) + '&p=' + encodeURIComponent(k.slice(k.indexOf('/') + 1)); }")
        async def wait(js, secs=30):
            for _ in range(secs * 4):
                if await q(js): return True
                await asyncio.sleep(0.25)
            return False
        print("   mock serves a sample:", await q("async () => { const r = await fetch(cbU('fed/feeds/press_monetary.xml')); return [r.status, (await r.text()).includes('FOMC statement')]; }"))
        # 1) the reader: each bank's decision list, then each saved statement against what was read by hand (tests/cb/expect.json)
        LISTS = {"USD": ["fed/feeds/press_monetary.xml", "newsevents/pressreleases/monetary20261028a.htm", 4], "EUR": ["ecb/press/govcdec/mopo/2026/html/index_include.en.html", "press/pr/date/2026/html/ecb.mp261029~9a493adf17.en.html", 5],
                 "GBP": ["boe/rss/news", "monetary-policy-summary-and-minutes/2026/november-2026", 3], "JPY": ["boj/en/rss/whatsnew.xml", "en/mopo/mpmdeci/mpr_2026/k261030a.pdf", 1],
                 "AUD": ["rba/media-releases/2026/", "media-releases/2026/mr-26-30.html", 6], "CAD": ["boc/content_type/press-releases/feed/", "2026/10/fad-press-release-2026-10-28/", 3]}
        items = await q("""async L => { const o = {}; for (const [c, [f]] of Object.entries(L)) { const it = cbItems(c, await (await fetch(cbU(f))).text()); o[c] = [it.length, it[0] && it[0].path, it[0] && it[0].title, it.every((x, i) => !i || x.t <= it[i - 1].t && x.t > 0)]; } return o; }""", LISTS)
        for c, (n, path, title, ordered) in items.items():
            print(f"1) {c} list: {n} decisions, newest {path} ({title}), newest first: {ordered}")
            check(n >= LISTS[c][2] and path == LISTS[c][1] and ordered, f"{c} decision list read wrong")
        got = await q("""async E => { const o = []; for (const [k, e] of Object.entries(E)) { const p = cbParse(e.ccy, await (await fetch(cbU(k))).text());
            o.push([k, p.ok, p.move, p.rate, p.hawk, p.dove, p.sentences.length, p.sentences.slice(0, 2)]); } return o; }""", EXPECT)
        for k, ok, move, rate, hawk, dove, ns, first in got:
            e = EXPECT[k]; good = ok and move == e["move"] and rate == e["rate"] and hawk == e["hawk"] and dove == e["dove"] and ns >= e["minSentences"]
            print(f"   {'ok ' if good else 'BAD'} {k.split('/')[0]} {k.split('/')[-1] or k.split('/')[-2]}: {move} {rate} hawk {hawk} dove {dove}, {ns} sentences | {first[0][:70] if first else ''}")
            check(good, f"{k}: read {move} {rate} {hawk}/{dove} {ns}, expected {e}")
        mixed = """<div id="article"><p>The Federal Open Market Committee approved the following statement for release by a 9 – 3 vote:</p>
<p>The Committee decided to lower the target range for the federal funds rate by 1/4 percentage point to 3-1/2 to 3-3/4 percent.</p><p>Economic activity has been expanding at a moderate pace.</p>
<p>Job gains have slowed this year, and the unemployment rate has edged up.</p><p>Inflation has moved up since earlier in the year and remains somewhat elevated.</p>
<p>Voting against this action were Stephen I. Miran, who preferred to lower the target range for the federal funds rate by 1/2 percentage point at this meeting; and Austan D. Goolsbee and Jeffrey R. Schmid, who preferred no change to the target range for the federal funds rate at this meeting.</p>For media inquiries</div>"""
        mx = await q("h => { const p = cbParse('USD', h); return [p.move, p.rate, p.hawk, p.dove]; }", mixed)
        print("   Fed dissents both ways (cut; 1 wanted a bigger cut, 2 no change):", mx); check(mx == ["cut", 3.75, 2, 1], "mixed Fed dissents")
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
        check(V["noFc"]["label"] == "No clear lean" and any("no forecast to compare" in w.lower() for w in V["noFc"]["why"]), "no forecast: don't claim it was expected")
        nf = await q("() => [cbVerdict({move: 'hike', rate: 4, hawk: 2, dove: 0}, {added: [], dropped: []}, null).label, cbLean('USD', 'No clear lean').length]")
        print("   no forecast, 2 hawkish votes:", nf[0], "| lean when unclear:", nf[1]); check(nf == ["Hawkish", 0], "no forecast with votes")
        check(V["dates"] == {"added": [], "dropped": []}, f"month and number changes aren't wording changes: {V['dates']}")
        print("   lean USD hawkish:", V["usd"], "| JPY hawkish:", V["jpy"], "| EUR dovish:", V["eurDove"], "| as expected:", V["none"])
        check(all(x in V["usd"] for x in ["Gold short", "Nasdaq 100 short", "US dollar long", "EUR/USD short", "USD/JPY long"]), "USD lean")
        check(all(x in V["jpy"] for x in ["USD/JPY short", "Nikkei 225 short"]), "JPY lean")
        check("EUR/USD short" in V["eurDove"] and "EUR/GBP short" in V["eurDove"] and V["none"] == [], "EUR dovish lean / none when as expected")
        for prev, cur, na, nd in json.load(open(os.path.join(ROOT, "tests/cb/expect.json")))["_diffs"]:
            d = await q("""async ([a, b]) => { const p = cbParse('USD', await (await fetch(cbU(a))).text()), c = cbParse('USD', await (await fetch(cbU(b))).text()); return cbDiff(p.sentences, c.sentences); }""", [prev, cur])
            print(f"   {cur.split('/')[-1]} vs {prev.split('/')[-1]}: +{len(d['added'])} -{len(d['dropped'])} | + {[x[:60] for x in d['added']]}")
            check(len(d["added"]) == na and len(d["dropped"]) == nd, f"diff {prev} -> {cur}")
        # 3) the watcher: a Fed decision is due; the list still shows the old one, then the new statement appears
        import email.utils, re as _re
        FEED = "fed/feeds/press_monetary.xml"; real = open(os.path.join(ROOT, "tests/cb/fed/feeds/press_monetary.xml"), encoding="utf-8").read()
        OCT = _re.search(r"<item>(?:(?!</item>)[\s\S])*?monetary20261028a\.htm[\s\S]*?</item>", real).group(0)
        def fed_feed(age_s=None):                     # without the Oct 28 statement, or with it dated age_s seconds ago
            if age_s is None: return real.replace(OCT, "")
            return real.replace(OCT, _re.sub(r"<pubDate>[\s\S]*?</pubDate>", f"<pubDate>{email.utils.formatdate(time.time() - age_s, usegmt=True)}</pubDate>", OCT))
        await wait("() => CBW.rounds > 0", 30)
        reset = """() => { CBR = {}; lsSet('finder-cbreads', {}); CBW.poll = {}; CBW.caught = {}; NC = NC.filter(n => n.icon !== '🏦'); ncSave(); }"""
        bank_alerts = "() => NC.filter(n => n.icon === '🏦').map(n => [n.title, n.detail, n.kind, n.noTg, n.action, n.mk])"
        CB_SRV["swap"][FEED] = fed_feed(None); await q(reset); await q("() => cbCatchUp()")
        print("3) before: Fed newest stored:", await q("() => CBR.USD && CBR.USD[0].path"), "| alerts:", await q(bank_alerts))
        at = await q("""() => { const at = Date.now() + 60e3; CAL.items = CAL.items.filter(x => x.id !== 'test-fomc').concat([{ id: 'test-fomc', at, ccy: 'USD', title: 'Federal Funds Rate', impact: 'High', type: 'Central Bank', forecast: '4.00%', previous: '4.00%' }]); return at; }""")
        print("   due:", await q("t => cbDue(t)", at + 60e3))
        await q("t => cbTick(t)", at + 60e3)
        old = await q("() => [CBR.USD.length, CBR.USD[0].path, NC.filter(n => n.icon === '🏦').length]")
        print("   still old:", old); check(old[1].endswith("20260916a.htm") and old[2] == 0, "re-read or alerted the old statement")
        CB_SRV["swap"][FEED] = fed_feed(30); await q("t => cbTick(t)", at + 120e3)
        r = await q("() => { const r = CBR.USD[0]; return [r.path, r.ok, r.p.move, r.p.rate, r.forecast, r.v.label, r.v.why, r.diff.added.length, r.diff.dropped.length, CBR.USD[1] && CBR.USD[1].path]; }")
        al = await q(bank_alerts); print("   new read:", r); print("   alerts:", al)
        check(r[0].endswith("20261028a.htm") and r[1] and r[5] == "Hawkish" and r[7] == 3 and r[8] == 3 and r[9].endswith("20260916a.htm"), "new statement read wrong")
        check(len(al) == 1 and al[0][0] == "Fed held at 4.00%: hawkish" and al[0][1].startswith("Gold short · Nasdaq 100 short · US dollar long") and al[0][2] == "News" and al[0][3] is True and al[0][4] == "brief", "one in-app alert")
        await q("t => cbTick(t)", at + 240e3)
        await pg.reload(); await ready(pg); await wait("() => CBW.rounds > 0", 30)
        print("   after reload alerts:", len(await q(bank_alerts))); check(len(await q(bank_alerts)) == 1, "alerted again")
        await q("""at => { CAL.items = CAL.items.filter(x => x.id !== 'test-fomc').concat([{ id: 'test-fomc', at, ccy: 'USD', title: 'Federal Funds Rate', impact: 'High', type: 'Central Bank', forecast: '4.00%', previous: '4.00%' }]); }""", at)
        CB_SRV["swap"][FEED] = fed_feed(None); await q("t => cbTick(t)", at + 300e3)          # a stale copy of the list (older decision on top), then the fresh one again
        CB_SRV["swap"][FEED] = fed_feed(30); await q("t => cbTick(t)", at + 360e3)
        st = await q("() => [CBR.USD.map(r => r.path.split('/').pop()), NC.filter(n => n.icon === '🏦').length]")
        print("   stale list, then fresh:", st); check(st == [["monetary20261028a.htm", "monetary20260916a.htm"], 1], "a stale list re-read the old statement or alerted twice")
        # 4) catch-up on open: a decision 2 days old alerts once; 10 days old is read but doesn't alert; no stored read: the previous comes from the list
        for age, want in [(2 * 86400, 1), (10 * 86400, 0)]:
            CB_SRV["swap"][FEED] = fed_feed(age); await q(reset); await q("() => cbCatchUp()")
            c = await q("() => [CBR.USD[0].path, CBR.USD[0].ok, CBR.USD[1] && CBR.USD[1].path, CBR.USD[0].diff && CBR.USD[0].diff.added.length, NC.filter(n => n.icon === '🏦').map(n => n.title)]")
            print(f"4) {age // 86400} days old:", c); check(c[0].endswith("20261028a.htm") and c[2].endswith("20260916a.htm") and c[3] == 3 and len(c[4]) == want, "catch-up")
        # 5) the statement page fails: the read keeps the error, retries at most 3 times, and says so
        PAGE = "fed/newsevents/pressreleases/monetary20261028a.htm"; CB_SRV["status"][PAGE] = 500
        CB_SRV["swap"][FEED] = fed_feed(3600); await q(reset); await q("() => cbCatchUp()")
        await q("""at => { CAL.items = CAL.items.filter(x => x.id !== 'test-fomc').concat([{ id: 'test-fomc', at, ccy: 'USD', title: 'Federal Funds Rate', impact: 'High', type: 'Central Bank', forecast: '4.00%', previous: '4.00%' }]); }""", at)
        for k in range(5): await q("t => cbTick(t)", at + 60e3 * (k + 1))
        f = await q("() => [CBR.USD[0].ok, CBR.USD[0].err, CBR.USD[0].tries, NC.filter(n => n.icon === '🏦').map(n => n.title + ' | ' + n.detail)]")
        print("5) failing page:", f); check(f[0] is False and "500" in f[1] and f[2] == 3 and len(f[3]) == 1, "failure handling")
        del CB_SRV["status"][PAGE]                    # the site recovers: 30+ minutes after the last try the app tries again and sends the real read once
        await q("t => cbTick(t)", at + 35 * 60e3); await q("t => cbTick(t)", at + 36 * 60e3)
        f2 = await q("() => [CBR.USD[0].ok, CBR.USD[0].v && CBR.USD[0].v.label, NC.filter(n => n.icon === '🏦').map(n => n.title)]")
        print("   site back 35 min later:", f2); check(f2[0] is True and f2[2] == ["Fed held at 4.00%: hawkish", "Fed statement is out"], "a read that failed at release should be retried later and sent once")
        # 6) Telegram set up with News on: the bank alert stays in the app, other alerts still go out
        t = await q("""() => { lsSet(TG_KEY, { token: '1:x', chat: '1', kinds: { News: true } }); let n = 0; const keep = tgSend; tgSend = () => { n++; return Promise.resolve({ ok: true }); };
          cbAlert('USD', CBR.USD[0]); const bank = n; ncAdd({ kind: 'News', icon: '📰', title: 'control' }); const other = n - bank; tgSend = keep; lsSet(TG_KEY, null); return [bank, other]; }""")
        print("6) Telegram sends: bank alert", t[0], "| other alert", t[1]); check(t == [0, 1], "bank alert went to Telegram")
        # 7) Fundamentals: the panel, a card per bank, a lean chip opens the brief, today's read, phone width
        CB_SRV["swap"][FEED] = fed_feed(3600); await q(reset); await q("() => cbCatchUp()")
        await q("() => goPage('fund')"); await wait("() => document.querySelector('#fundBody .fcbr')", 20); await q("() => fundRender()")
        P = await q("""() => { const p = document.querySelector('#fundBody .fcbr'); if (!p) return null; const cards = [...p.querySelectorAll('.cbc')];
          const fed = p.querySelector('.cbc[data-cb="USD"]'), a = fed && fed.querySelector('a.cblink');
          return { head: p.querySelector('.fph').textContent, order: cards.map(c => c.dataset.cb), want: Object.keys(CBR).filter(c => CBR[c][0]).sort((x, y) => CBR[y][0].at - CBR[x][0].at),
            fed: fed && fed.innerText.replace(/\\s+/g, ' '), plus: fed ? fed.querySelectorAll('.cbw li.add').length : -1, minus: fed ? fed.querySelectorAll('.cbw li.drop').length : -1,
            link: a && [a.href, a.target, a.rel], next: phtDay(fbMeet('USD')).slice(4), boj: (p.querySelector('.cbc[data-cb="JPY"]') || {}).innerText }; }""")
        print("7) panel:", P and P["head"], "| cards:", P and P["order"]); print("   Fed card:", P and P["fed"][:600]); print("   +", P and P["plus"], "−", P and P["minus"], "| link:", P and P["link"], "| BoJ:", P and (P["boj"] or "")[:120].replace("\n", " "))
        check(P and "Central bank reads" in P["head"] and P["order"] == P["want"] and P["order"][0] == "USD", "panel and card order")
        check(all(x in P["fed"] for x in ["Held at 4.00%", "Hawkish", "Gold short", "What changed", "Until the next meeting", P["next"]]) and 0 < P["plus"] <= 3 and 0 < P["minus"] <= 3, "Fed card content")
        chips = await q("() => [...document.querySelectorAll('#fundBody .cbc[data-cb=\"USD\"] .cbl [data-fmk]')].map(x => x.textContent)")
        print("   Fed lean chips:", chips); check(chips == ["Gold short", "Nasdaq 100 short", "US dollar long", "EUR/USD short", "GBP/USD short", "USD/JPY long"], "lean chips: yours, the dollar, then pairs, 6 at most")
        check(P["link"][0].startswith("https://www.federalreserve.gov/") and P["link"][1] == "_blank" and "noopener" in P["link"][2], "statement link")
        check("PDF" in (P["boj"] or "") and "can't read" in (P["boj"] or ""), "a PDF statement says so")
        boc = await q("() => document.querySelector('#fundBody .cbc[data-cb=\"CAD\"]').innerText")
        print("   BoC (no forecast):", boc.replace("\n", " | ")[:200]); check("No clear lean" in boc and "As expected" not in boc and "no forecast" in boc.lower(), "no-forecast card copy")
        D = await q("() => [...document.querySelectorAll('#fundBody .cbc')].map(c => [c.dataset.cb, !!c.querySelector('details.cbmore[open]'), (c.querySelector('.cbout') || {}).textContent || ''])")
        print("   details open:", [(c, o) for c, o, _ in D], "| outlook lines:", sum(1 for *_, t in D if "next meeting" in t.lower()))
        check(D[0][0] == "USD" and D[0][1] and not any(o for c, o, _ in D[1:]) and all("next meeting" in t.lower() for *_, t in D), "only the newest read is open; every card shows the outlook")
        W2 = await q("() => [...new Set((CBR.AUD[0].v.why.find(w => w.startsWith('Wording')) || '').split(', '))].length === (CBR.AUD[0].v.why.find(w => w.startsWith('Wording')) || '').split(', ').length")
        check(W2, "wording reasons repeat")
        await q("() => document.querySelector('#fundBody .fcbr .cbc[data-cb=\"USD\"] [data-fmk=\"Gold\"]').click()"); await asyncio.sleep(0.4)
        B = await q("() => [FB.k, document.getElementById('fbDlg').open, document.getElementById('fbBody').textContent.includes('Last central bank read'), (document.getElementById('fbBody').textContent.match(/Last central bank read[\\s\\S]{0,160}/) || [''])[0].replace(/\\s+/g, ' ')]")
        print("   chip → brief:", B); check(B[0] == "Gold" and B[1] and B[2], "lean chip opens the brief with the read")
        await q("() => document.getElementById('fbDlg').close()")
        await pg.focus('#fundBody .fcbr .cbc[data-cb="USD"] [data-fmk="Nasdaq 100"]'); await pg.keyboard.press("Enter"); await asyncio.sleep(0.4)
        K = await q("() => [FB.k, document.getElementById('fbDlg').open]"); print("   chip by keyboard (Enter):", K); check(K == ["Nasdaq 100", True], "lean chips don't open with the keyboard")
        await q("() => document.getElementById('fbDlg').close()")
        T = await q("() => (document.querySelector('#fundRead [data-fmk=\"Gold\"]') || {}).innerText || ''")
        print("   today's read, Gold:", T.replace("\n", " | ")[:220]); check("Fed statement hawkish" in T, "today's read line")
        await pg.set_viewport_size({"width": 390, "height": 900}); await asyncio.sleep(0.4)
        W = await q("() => [document.documentElement.scrollWidth, document.querySelector('#fundBody .fcbr').getBoundingClientRect().width]")
        print("   phone width:", W); check(W[0] <= 390, "page scrolls sideways on a phone")
        await pg.set_viewport_size({"width": 1500, "height": 1000})
        E = await q("() => { const keep = CBR; CBR = {}; fundRender(); const t = document.querySelector('#fundBody .fcbr').innerText; CBR = keep; fundRender(); return t; }")
        print("   empty:", E.replace("\n", " | ")[:160]); check("No decisions read yet" in E, "empty state")
        # review leftovers: the ECB's time follows summer/winter time, last year's list when this year's isn't up, only decisions open the watch window
        ecb = await q("""() => { const h = '<dt isoDate="2026-12-17"><div class="date">x</div></dt><dd><div class="title"><a href="/a.en.html">Monetary policy decisions</a></div></dd><dt isoDate="2026-07-23"><div class="date">x</div></dt><dd><div class="title"><a href="/b.en.html">Monetary policy decisions</a></div></dd>';
          return cbItems('EUR', h).map(x => new Date(x.t).toISOString().slice(11, 16)); }""")
        print("8) ECB decision times (UTC), December and July:", ecb); check(ecb == ["13:15", "12:15"], "ECB time ignores summer/winter time")
        jan = await q("t => cbList('EUR', t).then(L => L.length, e => 'threw: ' + e.message)", 1799020800000)      # 2027-01-04: no 2027 list on the bank's site yet
        print("   January 2027, no list for the year yet:", jan, "decisions from 2026"); check(isinstance(jan, int) and jan > 0, "a missing list for the new year hides last year's")
        due = await q("""() => { const now = Date.now(), keep = calAll; calAll = () => [{ ccy: 'USD', impact: 'High', type: 'Central Bank', title: 'FOMC Meeting Minutes', at: now }, { ccy: 'GBP', impact: 'High', type: 'Central Bank', title: 'BOE Gov Bailey Speaks', at: now },
          { ccy: 'EUR', impact: 'High', type: 'Central Bank', title: 'Main Refinancing Rate', at: now }, { ccy: 'CAD', impact: 'High', type: 'Central Bank', title: 'BOC Rate Statement', at: now }]; const r = cbDue(now); calAll = keep; return r.sort(); }""")
        print("   watch window opens for:", due); check(due == ["CAD", "EUR"], "minutes or speeches start the watch window")
        CB_SRV["swap"].clear(); await q(reset); await q("() => cbCatchUp()")
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
