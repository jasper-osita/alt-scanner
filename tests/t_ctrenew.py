import asyncio, sys, re, json
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OPTS = {"secret": "sec", "token": "tok", "live": True, "rotate": True}
# cTrader keeps one live sign-in per app: each renewal ends the old access and refresh token, and signing in anywhere else ends this one.
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1400, "height": 900}); await setup(ctx); await setup_mexc(ctx)
        auth, mode = [], {"back": False}
        async def grant(route):          # cTrader's sign-in page; in "back" mode the person approves and cTrader returns a code
            auth.append(route.request.url)
            if not mode["back"]: return await route.fulfill(status=200, content_type="text/html", body="<p>cTrader sign-in</p>")
            from urllib.parse import unquote
            await route.fulfill(status=302, headers={"Location": unquote(re.search(r"redirect_uri=([^&]+)", route.request.url).group(1)) + "?code=fresh1"})
        async def relay(route):          # /api/ct-token: a new sign-in replaces the old one
            CT_AUTH.update(access={"tok-new"}, refresh={"ref-new"})
            await route.fulfill(status=200, content_type="application/json", body=json.dumps({"accessToken": "tok-new", "refreshToken": "ref-new", "expiresIn": 2628000}))
        await ctx.route(re.compile(r"https://id\.ctrader\.com/.*"), grant)
        await ctx.route(re.compile(r"http://localhost:8765/api/ct-token.*"), relay)
        errs, pages = [], []
        for _ in range(2):
            pg = await ctx.new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
            await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
            await pg.route_web_socket("wss://contract.mexc.com/edge", mx_ws_handler)
            await pg.route_web_socket(re.compile(r"wss://(live|demo)\.ctraderapi\.com:5036.*"), ct_handler(OPTS))
            await pg.goto("http://localhost:8765/"); pages.append(pg)
        A, B = pages
        await A.evaluate("() => localStorage.clear()"); await A.reload(); await B.reload(); await ready(A); await ready(B)
        async def wait(pg, js, secs=20):
            for _ in range(secs * 4):
                if await pg.evaluate(js): return True
                await asyncio.sleep(0.25)
            return False
        # 1) two windows open, access close to running out: both connect at once, only one renews, both end up on the new tokens
        CT_AUTH.update(access={"tok0"}, refresh={"ref0"}, n=0)
        await A.evaluate("() => localStorage.setItem('finder-ctrader', JSON.stringify({ clientId: 'cid', clientSecret: 'sec', accessToken: 'tok0', refreshToken: 'ref0', expAt: Date.now() + 864e5 }))")
        await asyncio.gather(*[pg.evaluate("() => ctConnect().then(() => 'ok', e => e.message)") for pg in pages])
        st = [await pg.evaluate("() => [CT.state, CT.err, (ctCfg() || {}).refreshToken]") for pg in pages]
        print("1) two windows renew at once:", st, "| renewals:", CT_AUTH["n"])
        if any(x[0] != "ready" for x in st): errs.append(f"a window lost its cTrader sign-in when both renewed: {st}")
        if CT_AUTH["n"] != 1: errs.append(f"renewed {CT_AUTH['n']} times, expected once")
        await B.close()
        # 2) signed in somewhere else (another device, the Mac app or the Sandbox page): cTrader ends this sign-in, the app says so and opens cTrader's sign-in by itself
        CT_AUTH.update(access={"tok-other"}, refresh={"ref-other"})
        outs = lambda: A.evaluate("() => NC.filter(n => n.action === 'ctsignin').length")
        await A.evaluate("() => goPage('fund')")
        await A.evaluate("() => CT.ws.onmessage({ data: JSON.stringify({ payloadType: 2147, payload: {} }) })")
        await wait(A, "() => CT.state === 'error'", 10)
        print("2) signed out elsewhere:", await A.evaluate("() => [CT.state, CT.err, !CT.retryT]"))
        nc = await A.evaluate("() => NC.filter(n => n.action === 'ctsignin').map(n => [n.title, n.action])")
        toast = await A.evaluate("() => [...document.querySelectorAll('.nctoast .go')].map(b => b.textContent)")
        print("   notice:", nc, "Sign in again" in toast)
        if not (await A.evaluate("() => /signed out/.test(CT.err || '')")): errs.append("no plain 'signed out' reason")
        if len(nc) != 1 or "Sign in again" not in toast: errs.append(f"expected one 'sign in again' notice, got {nc} {toast}")
        for _ in range(40):
            if auth: break
            await asyncio.sleep(0.25)
        print("   opened cTrader's sign-in by itself:", bool(auth), A.url[:40])
        if len(auth) != 1: errs.append(f"auto sign-in opened cTrader {len(auth)} times")
        # 3) back without approving (or cancelled): no second notice, no redirect loop
        await A.goto("http://localhost:8765/"); await ready(A); await A.evaluate("() => ctConnect().catch(() => {})"); await asyncio.sleep(4)
        print("3) no repeat after reload:", await outs(), "notice,", len(auth), "trip to cTrader")
        if await outs() != 1 or len(auth) != 1: errs.append("the signed-out notice or the sign-in trip repeated")
        await A.evaluate("() => ncGo(NC.find(n => n.action === 'ctsignin').id)"); await asyncio.sleep(1)
        print("4) Sign in again button → cTrader:", len(auth) == 2)
        if len(auth) != 2: errs.append("Sign in again didn't open cTrader's sign-in page")
        # 5) the whole automatic round trip: cTrader sends a code back, the app swaps it, reconnects and returns to the page you were on
        mode["back"] = True
        await A.goto("http://localhost:8765/"); await ready(A)
        await A.evaluate("() => { localStorage.removeItem('finder-ct-auto'); goPage('fund'); ctConnect().catch(() => {}); }")
        ok5 = False
        for _ in range(80):
            try: ok5 = await A.evaluate("() => typeof CT !== 'undefined' && CT.state === 'ready' && (ctCfg() || {}).refreshToken === 'ref-new'")
            except Exception: ok5 = False
            if ok5: break
            await asyncio.sleep(0.25)
        print("5) automatic sign-in round trip:", ok5, await A.evaluate("() => [page, location.search, NC[0] && NC[0].title]"))
        if not ok5 or await A.evaluate("() => page") != "fund": errs.append("automatic sign-in didn't reconnect and return to the page")
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
