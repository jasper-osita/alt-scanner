"""Devices borrow the shared cTrader login: share from one browser, use it in another, recover from a rejected token, no device renews."""
import asyncio, sys, os, re, functools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
print = functools.partial(print, flush=True)
OPTS = {"secret": "sec", "token": "tok", "live": True, "scope": "SCOPE_TRADE", "demo2": True}
async def device(b, st, storage):
    ctx = await b.new_context(viewport={"width": 1400, "height": 900}); await setup(ctx); await route_keeper(ctx, st)
    pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
    await pg.route_web_socket(re.compile(r"wss://(live|demo)\.ctraderapi\.com:5036.*"), ct_handler(OPTS))
    await pg.goto("http://localhost:8765/#macro"); await pg.evaluate("(s) => { localStorage.clear(); Object.entries(s).forEach(([k, v]) => localStorage.setItem(k, v)); }", storage)
    await pg.reload(); await asyncio.sleep(1.5)
    return pg, errs
async def wait(pg, js, secs=20):
    for _ in range(secs * 4):
        if await pg.evaluate(js): return True
        await asyncio.sleep(0.25)
    return False
async def main():
    serve(); st = keeper_state()
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        A, ea = await device(b, st, {"finder-ctrader": json.dumps({"clientId": "cid", "clientSecret": "sec", "accessToken": "tok", "refreshToken": "ref", "expAt": 4102444800000, "scope": "trading"})})
        await wait(A, "() => CT.state === 'ready'")
        await A.evaluate("() => openCTSettings()"); await asyncio.sleep(0.3)
        print("   Mac-style address box:", await A.evaluate("() => document.getElementById('kpUrl').value"))
        await A.fill("#kpUrl", "http://localhost:8765"); await A.fill("#kpPass", "correct horse 42"); await A.click("#kpShare"); await asyncio.sleep(1)
        print("1) A shared:", "seeds", st["seeds"], "| login refresh kept by keeper:", (st["login"] or {}).get("refreshToken"),
              "| A cfg:", await A.evaluate("() => { const c = ctCfg(); return 'keeper ' + c.keeper + ' refresh ' + JSON.stringify(c.refreshToken) + ' state ' + CT.state; }"),
              "| msg:", await A.evaluate("() => document.getElementById('ctMsg').innerText.slice(0, 120)"))
        print("   A dialog now:", await A.evaluate("() => { openCTSettings(); return document.querySelector('.ctshare').innerText.replace(/\\s+/g, ' ').slice(0, 160); }"))
        await A.evaluate("() => $('dlg').close()")
        B, eb = await device(b, st, {})
        await B.evaluate("() => openCTSettings()"); await asyncio.sleep(0.3)
        await B.fill("#kpUrl", "http://localhost:8765/"); await B.fill("#kpPass", "wrong passphrase!"); await B.click("#kpJoin"); await asyncio.sleep(0.6)
        print("6) wrong passphrase:", await B.evaluate("() => document.getElementById('ctMsg').innerText"), "| saved:", await B.evaluate("() => localStorage.getItem('finder-keeper')"))
        await B.fill("#kpPass", "correct horse 42"); await B.click("#kpJoin")
        ok = await wait(B, "() => CT.state === 'ready'")
        print("2) B joined:", ok, "| token", await B.evaluate("() => ctCfg().accessToken"), "| keeper", await B.evaluate("() => ctCfg().keeper"), "| refresh", await B.evaluate("() => JSON.stringify(ctCfg().refreshToken)"))
        print("3) renewals sent to cTrader by devices:", CT_LOG.count(2173))
        # the keeper hands out a stale token: B recovers by itself
        st["serve_stale"] = True
        await B.evaluate("() => { ctClose(); CT.state = 'closed'; const c = ctCfg(); c.expAt = Date.now() + 3600e3; ctSaveCfg(c); }")
        await B.evaluate("() => ctConnect().catch(e => window.__e = e.message)")
        ok = await wait(B, "() => CT.state === 'ready'")
        print("4) stale token recovered:", ok, "| bad sent:", st["bads"], "| token now", await B.evaluate("() => ctCfg().accessToken"), "| error shown:", await B.evaluate("() => window.__e || ''"),
              "| 'Paste a fresh' anywhere:", await B.evaluate("() => document.body.innerText.includes('Paste a fresh')"))
        # Trade socket uses the borrowed login
        print("7) trade socket:", await B.evaluate("async () => { try { await cttConnect(); return 'ok ' + CTT.state; } catch (e) { return 'ERR ' + e.message; } }"))
        # keeper not set up: the dialog says so, A keeps its connection
        st["fail503"] = True
        await A.evaluate("() => openCTSettings()"); await asyncio.sleep(0.2)
        await A.evaluate("() => ctKeeperPull().catch(e => { document.getElementById('ctMsg').textContent = e.message; })"); await asyncio.sleep(0.5)
        print("5) keeper down:", await A.evaluate("() => document.getElementById('ctMsg').innerText.slice(0, 140)"), "| A still", await A.evaluate("() => CT.state"))
        st["fail503"] = False
        await B.evaluate("() => openCTSettings()"); await asyncio.sleep(0.2); await B.click("#kpLeave"); await asyncio.sleep(0.3)
        print("8) B stops borrowing:", await B.evaluate("() => JSON.stringify({ kp: localStorage.getItem('finder-keeper'), tok: (ctCfg() || {}).accessToken || null, keeper: !!(ctCfg() || {}).keeper })"))
        print("errors:", (ea + eb)[:4] or "none")
        await b.close()
asyncio.run(main())
