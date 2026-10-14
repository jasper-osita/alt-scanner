import asyncio, sys, re, json
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OPTS = {"secret": "sec", "token": "tok", "live": True}
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1400, "height": 900}); await setup(ctx); await setup_mexc(ctx)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.route_web_socket("wss://contract.mexc.com/edge", mx_ws_handler)
        await pg.route_web_socket(re.compile(r"wss://(live|demo)\.ctraderapi\.com:5036.*"), ct_handler(OPTS))
        # an expired access token plus a refresh token: the app should renew by itself
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => { localStorage.clear(); localStorage.setItem('finder-ctrader', JSON.stringify({ clientId: 'cid', clientSecret: 'sec', accessToken: 'expired', refreshToken: 'ref' })); }"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        async def wait(js, secs=30):
            for _ in range(secs * 4):
                if await q(js): return True
                await asyncio.sleep(0.25)
            return False
        await q("() => ctConnect().catch(e => window.__e = e.message)")
        print("1) renewed on connect:", await wait("() => CT.state === 'ready'"), await q("() => { const c = ctCfg(); return [c.accessToken, c.refreshToken, Math.round((c.expAt - Date.now()) / 864e5) + 'd', window.__e || 'ok']; }"))
        CT_LOG.clear()
        await q("() => { CT.subRows = [{ symbolId: 1 }, { symbolId: 2 }]; CT.ws.close(); }"); await wait("() => CT.state !== 'ready'", 5)
        ok2 = await wait("() => CT.state === 'ready'", 15); await asyncio.sleep(1)
        print("2) socket dropped → back:", ok2, "| resubscribed:", 2127 in CT_LOG, "| bar:", await q("() => document.getElementById('ctBar') ? document.getElementById('ctBar').innerText.slice(0, 60) : '-'"))
        CT_LOG.clear()
        await q("() => CT.ws.onmessage({ data: JSON.stringify({ payloadType: 2148, payload: {} }) })"); await wait("() => CT.state !== 'ready'", 5)
        print("3) server disconnect event → back:", await wait("() => CT.state === 'ready'", 15), CT_LOG[:4])
        CT_LOG.clear()
        await q("() => { const c = ctCfg(); c.expAt = Date.now() + 864e5; ctSaveCfg(c); CT.ws.close(); }"); await wait("() => CT.state !== 'ready'", 5)
        print("4) near expiry renews on reconnect:", await wait("() => CT.state === 'ready'", 15), 2173 in CT_LOG)
        # a bad refresh token stops retrying and asks for new tokens
        await q("() => { ctSaveCfg({ clientId: 'cid', clientSecret: 'sec', accessToken: 'expired', refreshToken: 'bad' }); ctClose(); CT.state = 'closed'; ctConnect().catch(e => window.__e2 = e.message); }")
        await wait("() => CT.state === 'error'", 10); await asyncio.sleep(4)
        print("5) bad refresh:", await q("() => [CT.state, window.__e2, !CT.retryT]"))
        print("6) dialog field:", await q("() => { openCTSettings(); return !!document.getElementById('ctRefresh'); }") if await q("() => typeof openCTSettings === 'function'") else "skip")
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
