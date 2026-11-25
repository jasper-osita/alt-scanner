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
        # ---- review fixes: each check below must hold
        F = []
        def check(name, ok, detail=""):
            print(("   ok " if ok else "   FAIL ") + name + (" · " + str(detail) if detail else ""))
            if not ok: F.append(name)
        C, ec = await device(b, st, {"finder-ctrader": json.dumps({"clientId": "cid", "clientSecret": "sec", "accessToken": "tok", "refreshToken": "ref", "expAt": 4102444800000, "scope": "trading"})})
        await wait(C, "() => CT.state === 'ready'")
        # 1) Share while a connect is under way must not bring the refresh token back
        await C.evaluate("() => { ctClose(); CT.state = 'closed'; window.__p = ctConnect().catch(() => {}); }")
        await C.evaluate("async () => { await ctKeeperSeed('correct horse 42', 'http://localhost:8765'); await window.__p; await new Promise(r => setTimeout(r, 500)); }")
        cfg = await C.evaluate("() => ctCfg()")
        check("share during connect keeps borrowing", cfg.get("keeper") is True and cfg.get("refreshToken") == "", {"keeper": cfg.get("keeper"), "refresh": cfg.get("refreshToken")})
        # 6) a 2147 reports the token that socket used, not whatever another window saved since
        await wait(C, "() => CT.state === 'ready'")
        used = await C.evaluate("() => CT.tok || null"); await C.evaluate("() => { const c = ctCfg(); c.accessToken = 'saved-by-another-window'; ctSaveCfg(c); CT.ws.onmessage({ data: JSON.stringify({ payloadType: 2147, payload: {} }) }); }")
        await asyncio.sleep(1.5)
        check("2147 reports the socket's own token", used is not None and st["bads"] and st["bads"][-1] == used[-8:], {"used": used, "bads": st["bads"][-2:]})
        await wait(C, "() => CT.state === 'ready'")
        # 2) a fresh sign-in on a borrowing device stops borrowing and offers Share
        await C.evaluate("() => openCTSettings()"); await asyncio.sleep(0.2)
        await C.evaluate("() => { document.querySelector('.ctmanual').open = true; }"); await C.fill("#ctToken", "tok"); await C.fill("#ctRefresh", "ref"); await C.click("#ctSave")
        await wait(C, "() => CT.state === 'ready' && !ctCfg().keeper"); await asyncio.sleep(1)
        cfg = await C.evaluate("() => ctCfg()"); await C.evaluate("() => openCTSettings()"); await asyncio.sleep(0.2)
        check("fresh sign-in stops borrowing", not cfg.get("keeper") and cfg.get("refreshToken") == "ref", {"keeper": cfg.get("keeper"), "refresh": cfg.get("refreshToken")})
        check("…and offers Share", await C.evaluate("() => !!document.getElementById('kpShare')"))
        check("sign-in helper clears borrowing", await C.evaluate("() => { const x = ctFreshLogin({ keeper: true, refreshToken: '' }, { accessToken: 'a', refreshToken: 'r', expAt: 1 }); return x.keeper === false && x.refreshToken === 'r'; }"))
        await C.evaluate("() => $('dlg').close()")
        # 4) the passphrase changed on Vercel: drop the stored one, no retry loop
        await C.evaluate("() => ctKeeperJoin('correct horse 42', 'http://localhost:8765')")
        st["pass"] = "a new passphrase 99"; g0 = st["gets"]
        await C.evaluate("() => { ctClose(); CT.state = 'closed'; const c = ctCfg(); c.accessToken = 'dead-token'; ctSaveCfg(c); ctScheduleReconnect(true); }"); await asyncio.sleep(4)
        g1 = st["gets"]; await asyncio.sleep(3)
        check("changed passphrase is forgotten", await C.evaluate("() => KP().pass === ''"), await C.evaluate("() => CT.err"))
        check("…and not retried", st["gets"] == g1 and g1 - g0 <= 1, {"gets after": g1 - g0, "later": st["gets"] - g1})
        check("…with a clear message", await C.evaluate("() => /passphrase changed/i.test(CT.err || '')"), await C.evaluate("() => CT.err"))
        st["pass"] = "correct horse 42"
        # 10) an address that answers 200 with something else must not wipe the login
        await C.evaluate("() => kpSave({ pass: 'correct horse 42', url: 'http://localhost:8765' })"); st["junk"] = True
        before = await C.evaluate("() => ctCfg().accessToken"); err = await C.evaluate("async () => { try { await ctKeeperPull(); return 'no error'; } catch (e) { return e.message; } }")
        check("junk answer leaves the login alone", await C.evaluate("() => ctCfg().accessToken") == before and err != "no error", err)
        st["junk"] = False
        check("address without https:// gets it", await C.evaluate("() => kpUrl({ url: 'alt-scanner-three.vercel.app' }) === 'https://alt-scanner-three.vercel.app/api/ct-keeper' && kpUrl({ url: 'localhost:8787' }) === 'http://localhost:8787/api/ct-keeper'"))
        # 11) keeper error text is shown as text, never run
        st["err403"] = "<img src=x onerror=window.__x=1>Nope"
        await C.evaluate("() => { kpSave(null); const c = ctCfg(); c.keeper = false; ctSaveCfg(c); openCTSettings(); }"); await asyncio.sleep(0.2)
        await C.fill("#kpUrl", "http://localhost:8765"); await C.fill("#kpPass", "wrong passphrase!"); await C.click("#kpJoin"); await asyncio.sleep(0.8)
        check("keeper error is escaped", await C.evaluate("() => window.__x === undefined && document.getElementById('ctMsg').innerText.includes('<img')"), await C.evaluate("() => document.getElementById('ctMsg').innerText"))
        st["err403"] = None
        # 13) Disconnect and forget also forgets the passphrase
        await C.evaluate("() => { kpSave({ pass: 'correct horse 42', url: 'http://localhost:8765' }); openCTSettings(); }"); await asyncio.sleep(0.2); await C.click("#ctForget"); await asyncio.sleep(0.3)
        check("forget clears the passphrase", await C.evaluate("() => localStorage.getItem('finder-keeper') === null"))
        print("errors:", F + (ea + eb + ec)[:4] or "none")
        await b.close()
asyncio.run(main())
