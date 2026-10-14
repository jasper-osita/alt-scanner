import asyncio, sys, re
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OUT = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "out", "finder")
OPTS = {"secret": "sec", "token": "tok", "live": True}
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1440, "height": 900}, color_scheme="dark"); await setup(ctx)
        pg = await ctx.new_page(); errs, csp = [], []
        pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: "Content Security Policy" in m.text and csp.append(m.text[:160]))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.route_web_socket(re.compile(r"wss://(live|demo)\.ctraderapi\.com:5036.*"), ct_handler(OPTS))
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        await pg.evaluate("() => goPage('macro')")
        async def wait_rows(pred, secs=90):
            for _ in range(secs * 2):
                if await pg.evaluate(f"() => !MACRO.running && ({pred})"): return True
                await asyncio.sleep(0.5)
            return False
        await wait_rows("MACRO.rows.length > 0")
        print("1) before connect:", await pg.evaluate("() => document.getElementById('ctBar').innerText"), "| ct rows:", await pg.evaluate("() => MACRO.rows.filter(r => r.ct).length"))
        await pg.click("#ctOpen"); await asyncio.sleep(0.3)
        await pg.fill("#ctId", "cid"); await pg.fill("#ctSecret", "sec"); await pg.evaluate("() => document.querySelector('.ctmanual').open = true"); await pg.fill("#ctToken", "WRONG"); await pg.click("#ctSave"); await asyncio.sleep(1.5)
        print("2) bad token:", await pg.evaluate("() => document.getElementById('ctMsg').innerText"))
        await pg.fill("#ctSecret", "nope"); await pg.fill("#ctToken", "tok"); await pg.click("#ctSave"); await asyncio.sleep(1.5)
        print("   bad secret:", await pg.evaluate("() => document.getElementById('ctMsg').innerText"))
        await pg.fill("#ctSecret", "sec"); await pg.click("#ctSave"); await asyncio.sleep(1.2)
        print("3) good:", await pg.evaluate("() => document.getElementById('ctMsg') ? document.getElementById('ctMsg').innerText : '(dialog closed)'"))
        ok = await wait_rows("MACRO.rows.some(r => r.ct)", 120)
        print("   loaded:", ok, "| host:", await pg.evaluate("() => CT.ws && CT.ws.url"), "| bar:", await pg.evaluate("() => document.getElementById('ctBar').innerText"))
        print("4) forex:", await pg.evaluate("() => MACRO.rows.filter(r => r.group === 'Forex').length"), "| broker:", await pg.evaluate("() => MACRO.rows.filter(r => r.group === 'Broker CFDs').map(r => r.name + '=' + coin(r.symbol)).join(', ')"),
              "| excluded GER40/AAPL:", await pg.evaluate("() => !MACRO.by['CT:GER40'] && !MACRO.by['CT:AAPL.US']"))
        print("   EURUSD:", await pg.evaluate("() => { const r = MACRO.by['CT:EURUSD']; return `${r.name} ${fmtPrice(r.price)} chg ${r.chg24h.toFixed(2)}% ${r.rating} 1H ${r.s1h.state} RSI ${r.rsi.h1} sess ${r.session} tv ${r.tv} play ${coinPlay(r).short}`; }"))
        print("   bars match mock:", await pg.evaluate("async () => { const k = await klines('CT:EURUSD', '1h', 5); return k.t.length + ' bars, last close ' + k.c.at(-1).toFixed(5); }"), "| mock last closed:", f"{candles('EURUSD', '1h')[-2][4]:.5f}")
        print("   strength:", await pg.evaluate("() => (document.querySelector('#macroRead .mchip') || {}).innerText"))
        print("   groups:", await pg.evaluate("() => [...document.querySelectorAll('#macroBody .board-head')].map(h => h.innerText.replace(/\\s+/g, ' ')).join(' | ')"))
        print("5) spot:", await pg.evaluate("() => document.querySelector('[data-mp=\"CT:EURUSD\"]').textContent"), "vs mock bid", f"{candles('EURUSD','1h')[-1][4] * 1.01:.4f}")
        await pg.screenshot(path=f"{OUT}/forex.png")
        await pg.click('#macroBody .row[data-s="CT:EURUSD"]'); await asyncio.sleep(2.5)
        print("6) popup:", await pg.evaluate("() => ({ head: document.querySelector('.dhead h3').innerText.replace(/\\s+/g,' '), meta: document.querySelector('.dhead .meta').innerText.slice(0, 80), canvases: document.querySelectorAll('#dChartHost canvas').length, chart: CHDLG.on && CH.sym, tabs: [...document.querySelectorAll('.dtabs .tab')].map(t => t.innerText).join(',') })"))
        await pg.click('.dtabs [data-pane="why"]'); await asyncio.sleep(0.6)
        print("   why:", await pg.evaluate("() => document.getElementById('drv').innerText.slice(0, 90)"))
        await pg.evaluate("() => { const s = document.querySelector('#dChartHost .chtf'); s.value = '15m'; s.dispatchEvent(new Event('change')); }"); await asyncio.sleep(2)
        print("   15m chart:", await pg.evaluate("() => CH.sym + ' ' + chVis()[0].tf + ' ' + chVis()[0].t.length + ' bars · ' + document.querySelector('#dChartHost .chsrcb').textContent"))
        await pg.screenshot(path=f"{OUT}/forex_popup.png")
        await pg.keyboard.press("Escape")
        print("   export:", await pg.evaluate("() => claudeText().split('\\n').find(l => l.startsWith('Forex, gold')).slice(0, 160)"))
        # reload: stored settings reconnect on their own
        await pg.reload(); await ready(pg)
        ok = await wait_rows("MACRO.rows.some(r => r.ct)", 120)
        print("7) after reload:", ok, "| page:", await pg.evaluate("() => page"), "| ct rows:", await pg.evaluate("() => MACRO.rows.filter(r => r.ct).length"))
        # demo account path
        OPTS["live"] = False
        await pg.evaluate("() => { const c = ctCfg(); delete c.accountId; c.live = true; ctSaveCfg(c); CT.state = 'off'; ctClose(); }")
        await pg.evaluate("() => macroScan(true)"); ok = await wait_rows("CT.state === 'ready'", 60)
        print("8) demo account:", ok, "| host:", await pg.evaluate("() => CT.ws && CT.ws.url"), "| bar:", await pg.evaluate("() => document.getElementById('ctBar').innerText"))
        # forget
        await pg.click("#ctOpen"); await asyncio.sleep(0.3); await pg.click("#ctForget"); await asyncio.sleep(0.5)
        print("9) forgot:", await pg.evaluate("() => ({ cfg: ctCfg(), ct: MACRO.rows.filter(r => r.ct).length, bar: document.getElementById('ctBar').innerText })"))
        print("protocol msgs seen:", sorted(set(CT_LOG)))
        print("CSP:", csp or "none", "| errors:", errs or "none")
        await b.close()
asyncio.run(main())
