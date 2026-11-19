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
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
