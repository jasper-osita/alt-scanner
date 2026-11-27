import asyncio, sys, re, json
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OPTS = {"secret": "sec", "token": "tok", "live": True}
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1400, "height": 900}); await setup(ctx); await setup_mexc(ctx)
        seen = {"n": 0}; used, hits = set(), []
        async def grant(route):          # cTrader's sign-in page: the person approves and cTrader sends them back with a code
            u = route.request.url; seen["auth"] = u; seen["n"] += 1
            ru = re.search(r"redirect_uri=([^&]+)", u).group(1)
            from urllib.parse import unquote
            await route.fulfill(status=302, headers={"Location": unquote(ru) + f"?code=onetime{seen['n']}"})
        def swap(p, via):                # like cTrader: each sign-in code works once ("Access denied" after that)
            hits.append(via); code = p.get("code", "")
            ok = code.startswith("onetime") and code not in used and p.get("client_secret") == "sec" and p.get("grant_type") == "authorization_code"
            used.add(code)
            return {"accessToken": "tok", "refreshToken": "ref-" + code, "expiresIn": 2628000, "tokenType": "bearer"} if ok else {"errorCode": "ACCESS_DENIED", "description": "Access denied. Make sure the credentials are valid."}
        async def token(route):          # straight to cTrader. The real service sends no CORS header: the browser sends the code, then hides the answer
            from urllib.parse import urlparse, parse_qsl
            body = swap(dict(parse_qsl(urlparse(route.request.url).query)), "direct")
            await route.fulfill(status=200, content_type="application/json", body=json.dumps(body))
        async def relay(route):          # /api/ct-token (server.py on the Mac, api/ct-token.js on Vercel) forwards the same request
            body = swap(json.loads(route.request.post_data or "{}"), "relay")
            await route.fulfill(status=200, content_type="application/json", body=json.dumps(body))
        await ctx.route(re.compile(r"https://id\.ctrader\.com/my/settings/openapi/grantingaccess/.*"), grant)
        await ctx.route(re.compile(r"https://openapi\.ctrader\.com/apps/token.*"), token)
        await ctx.route(re.compile(r"http://localhost:8765/api/ct-token.*"), relay)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.route_web_socket("wss://contract.mexc.com/edge", mx_ws_handler)
        await pg.route_web_socket(re.compile(r"wss://(live|demo)\.ctraderapi\.com:5036.*"), ct_handler(OPTS))
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        await q("() => openCTSettings()"); await asyncio.sleep(0.5)
        print("1) dialog:", await q("() => [!!document.getElementById('ctSignIn'), document.getElementById('ctRedir').textContent, document.querySelector('.ctmanual').open]"))
        await q("() => document.getElementById('ctSignIn').click()"); await asyncio.sleep(0.3)
        print("2) needs id first:", await q("() => document.getElementById('ctMsg').innerText"))
        await pg.fill("#ctId", "cid"); await pg.fill("#ctSecret", "sec")
        await pg.click("#ctSignIn")
        for _ in range(80):
            if await q("() => typeof CT !== 'undefined' && CT.state === 'ready'"): break
            await asyncio.sleep(0.25)
        print("3) auth url:", re.sub(r"client_id=[^&]+", "client_id=…", seen.get("auth", "")[:160]))
        print("4) after return:", await q("() => { const c = ctCfg(); return [CT.state, CT.broker, c.accessToken, c.refreshToken, Math.round((c.expAt - Date.now()) / 864e5) + 'd', location.search, NC[0] && NC[0].title]; }"))
        print("4b) code sent once, through the relay:", hits)
        if hits != ["relay"]: errs.append(f"sign-in code sent {hits}: the page must not call cTrader directly when the relay is there (it spends the one-time code)")
        # a host with no relay (POST answers 501): the page asks cTrader itself
        await ctx.unroute(re.compile(r"http://localhost:8765/api/ct-token.*")); hits.clear()
        await q("() => openCTSettings()"); await asyncio.sleep(0.5); await pg.click("#ctSignIn")
        for _ in range(80):
            if await q("() => typeof CT !== 'undefined' && (ctCfg() || {}).refreshToken === 'ref-onetime2' && CT.state === 'ready'"): break
            await asyncio.sleep(0.25)
        print("4c) no relay, straight to cTrader:", hits, await q("() => [CT.state, (ctCfg() || {}).refreshToken]"))
        if hits != ["direct"]: errs.append(f"no-relay sign-in sent {hits}")
        # a code that isn't ours (no pending sign-in) is ignored and removed from the address bar
        await pg.goto("http://localhost:8765/?code=stray"); await ready(pg); await asyncio.sleep(1)
        print("5) stray code ignored:", await q("() => [location.search, (ctCfg() || {}).accessToken]"))
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
