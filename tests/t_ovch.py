import asyncio, sys, re
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OPTS = {"secret": "sec", "token": "tok", "live": True}
OUT = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "out")
# The overview pages borrow the Charts engine: Bitcoin as the main chart on the crypto overview, the dollar and Nasdaq 100 side by side
# on the forex one. The Charts page must get its own symbol, layout and timeframes back untouched.
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1500, "height": 1000}, color_scheme="dark"); await setup(ctx); await setup_mexc(ctx)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.route_web_socket("wss://contract.mexc.com/edge", mx_ws_handler)
        await pg.route_web_socket(re.compile(r"wss://(live|demo)\.ctraderapi\.com:5036.*"), ct_handler(OPTS))
        await pg.goto("http://localhost:8765/")
        await pg.evaluate("() => { localStorage.clear(); localStorage.setItem('finder-ctrader', JSON.stringify({ clientId: 'cid', clientSecret: 'sec', accessToken: 'tok' })); localStorage.setItem('finder-charts', JSON.stringify({ sym: 'SOLUSDT', layout: '4g', tfs: ['4h', '1h', '15m', '5m'] })); }")
        await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        async def wait(js, secs=60):
            for _ in range(secs * 2):
                if await q(js): return True
                await asyncio.sleep(0.5)
            return False
        state = "() => ({ on: OVC.on, sym: CH.sym, act: OVC.act, panes: chVis().map(P => [P.psym || '-', P.sym, P.tf, P.t.length > 50, P.pane.classList.contains('act')]), host: !!document.querySelector('.ovchost .chpage'), box: (() => { const r = document.getElementById('chGrid').getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; })() })"

        # --- crypto overview: Bitcoin in the real chart
        await q("() => goPage('overview')")
        print("crypto hosted:", await wait("() => OVC.on === 'c' && CHP[0].t.length > 50"))
        print("crypto:", await q(state))
        print("toolbar:", await q("() => ['chSymBtn', 'chIndBtn', 'chTools', 'chLayBtn', 'chWL', 'chFocus'].map(id => id + (document.getElementById(id).offsetParent ? ' shown' : ' hidden')).join(', ')"))
        await wait("() => !CCH.busy && ['c_eth', 'c_ethbtc'].every(k => XCH.charts[k])")
        print("btc status:", await q("() => document.getElementById('ovBtcSt').innerText.replace(/\\s+/g, ' ')"))
        # a timeframe change on the main chart sticks to the overview only
        await q("() => { const s = CHP[0].pane.querySelector('.chtf'); s.value = '15m'; s.onchange(); }")
        await wait("() => CHP[0].tf === '15m' && CHP[0].t.length > 50")
        # draw a line on Bitcoin
        await q("() => { const L = chList(); L.push({ id: 'ovt1', type: 'hline', pts: [{ t: CHP[0].t.at(-5), p: CHP[0].c.at(-1) }] }); chSaveDraw(); chDirty = true; }")
        el = await pg.query_selector(".cchsec"); await el.screenshot(path=f"{OUT}/ovch_crypto.png")
        # clicking the Ethereum card shows it in the main chart instead of opening the coin window
        await q("() => document.querySelector('.xch[data-ck=\"eth\"] .xchc').click()")
        print("eth swap:", await wait("() => CH.sym === 'ETHUSDT' && CHP[0].sym === 'ETHUSDT'", 20), "| dialog open:", await q("() => document.getElementById('dlg').open"))
        print("saved overview:", await q("() => JSON.stringify(lsGet('finder-ovch'))"), "| saved charts:", await q("() => { const c = lsGet('finder-charts'); return [c.sym, c.layout, c.tfs.join(',')]; }"))

        # --- the Charts page gets everything back
        await q("() => goPage('charts')")
        await wait("() => chVis().length === 4 && chVis().every(P => P.sym === 'SOLUSDT')", 30)
        print("charts page:", await q("() => [OVC.on, CH.sym, CH.layout, CH.tfs.join(','), chVis().length, document.querySelector('.ovchost .chpage') ? 'still on overview' : 'home']"))
        print("btc line kept:", await q("() => (CHD.BTCUSDT || []).some(d => d.id === 'ovt1')"))

        # --- back to the overview: Ethereum and 15m are remembered
        await q("() => goPage('overview')")
        await wait("() => OVC.on === 'c' && CHP[0].t.length > 50", 30)
        print("crypto again:", await q("() => [CH.sym, CHP[0].tf, CH.layout]"))
        # the coin window borrows the chart and hands it back
        await q("() => openDetail(data.all.find(r => !r.macro).symbol)"); await wait("() => CHDLG.on && CHP[0].t.length > 50", 30)
        print("dialog:", await q("() => [CHDLG.on, OVC.on, CH.sym, !!document.querySelector('#dlg .chpage')]"))
        await q("() => document.getElementById('dlg').close()"); await asyncio.sleep(0.5)
        print("after dialog:", await wait("() => OVC.on === 'c' && !!document.querySelector('#ovChartC .chpage')", 20), await q("() => [CH.sym, CHP[0].tf]"))

        # --- forex overview: dollar (EUR/USD here: the mock broker lists no dollar index) and Nasdaq 100 side by side
        await q("() => { document.getElementById('exF').value = 'mexc'; goPage('macroov'); macroScan(true); }")
        print("macro loaded:", await wait("() => !MACRO.running && MACRO.rows.some(r => r.ct)", 200))
        print("macro hosted:", await wait("() => OVC.on === 'x' && CHP[0].t.length > 50 && CHP[1].t.length > 50", 60))
        await asyncio.sleep(1)
        print("macro:", await q(state))
        # click the Nasdaq chart: it becomes the active one
        await q("() => CHP[1].cv.scrollIntoView({ block: 'center' })"); await asyncio.sleep(0.3)
        bx = await q("() => { const r = CHP[1].cv.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }")
        await pg.mouse.click(bx[0], bx[1]); await asyncio.sleep(0.3)
        print("activate right:", await q("() => [OVC.act, CH.sym, document.getElementById('chSymName').textContent]"))
        # picking a symbol changes only the active chart
        await q("() => chSetSym(xFind(xRows(), 'S&P 500').symbol)")
        await wait("() => CHP[1].sym === CHP[1].psym && CHP[1].t.length > 50", 30)
        print("pick S&P:", await q("() => [chName(CHP[0].psym), chName(CHP[1].psym), chName(CH.sym)]"))
        # a gold card click goes to the active chart too
        await wait("() => !XCH.busy && XCH.charts.gold", 30)
        await q("() => document.querySelector('.xch[data-xk=\"gold\"] .xchc').click()")
        await wait("() => CHP[1].sym === CHP[1].psym && /XAU/.test(CHP[1].sym) && CHP[1].t.length > 50", 30)
        print("gold card:", await q("() => [chName(CHP[0].psym), chName(CHP[1].psym), document.getElementById('dlg').open]"))
        # drawings land on the active chart's symbol only
        await q("() => { chPush(); chList().push({ id: 'ovt2', type: 'hline', pts: [{ t: CHP[1].t.at(-5), p: CHP[1].c.at(-1) }] }); chSaveDraw(); chDirty = true; }")
        await asyncio.sleep(0.5)
        print("drawn on:", await q("() => [chList(CHP[0].psym).some(d => d.id === 'ovt2'), chList(CHP[1].psym).some(d => d.id === 'ovt2')]"))
        el = await pg.query_selector(".xchsec:not(.cchsec)"); await el.screenshot(path=f"{OUT}/ovch_macro.png")
        # crypto overview and back: each page keeps its own charts
        await q("() => goPage('overview')"); await wait("() => OVC.on === 'c' && CHP[0].t.length > 50", 30)
        print("crypto from macro:", await q("() => [OVC.on, CH.sym, CH.layout, chVis().length]"))
        await q("() => goPage('macroov')"); await wait("() => OVC.on === 'x' && CHP[1].t.length > 50", 30)
        print("macro again:", await q("() => [OVC.act, chName(CHP[0].psym), chName(CHP[1].psym)]"))
        # session timeframes: pretend it's London, so Gold goes to 5m; your own pick inside the window stands; after London it's back to yours
        tfs = "() => [CHP[0].tf, CHP[1].tf, CHP[0].manTf, CHP[1].manTf]"
        await q("() => { window._sessReal = ovcSessTf; ovcSessTf = sym => /^Gold/.test(chName(sym)) ? '5m' : null; ovcSessApply(true); }")
        await wait("() => CHP[1].tf === '5m' && CHP[1].t.length > 50", 20)
        print("london:", await q(tfs))
        await q("() => { const s = CHP[1].pane.querySelector('.chtf'); s.value = '15m'; s.onchange(); }"); await asyncio.sleep(0.5)
        await q("() => ovcSessApply(true)")
        print("own pick in london:", await q(tfs))
        await q("() => { ovcSessTf = () => null; ovcSessApply(true); }"); await asyncio.sleep(0.5)
        print("after london:", await q(tfs), "| saved:", await q("() => JSON.stringify(lsGet('finder-ovch').x.tfs)"))
        # session timeframes off: nothing switches
        await q("() => document.getElementById('ovcAuto').click()")
        await q("() => { ovcSessTf = sym => /^Gold/.test(chName(sym)) ? '5m' : null; CHP.forEach(P => P.sessKey = null); ovcSessApply(true); }"); await asyncio.sleep(0.3)
        print("auto off:", await q(tfs), await q("() => [document.getElementById('ovcAuto').getAttribute('aria-pressed'), lsGet('finder-ovch').x.auto]"))
        await q("() => { document.getElementById('ovcAuto').click(); ovcSessTf = window._sessReal; CHP.forEach(P => P.sessKey = null); ovcSessApply(true); }")
        # same timeframe: change one, the other follows
        await q("() => document.getElementById('ovcLink').click()"); await asyncio.sleep(0.3)
        await q("() => { const s = CHP[0].pane.querySelector('.chtf'); s.value = '4h'; s.onchange(); }")
        await wait("() => CHP[0].tf === '4h' && CHP[1].tf === '4h' && CHP[1].t.length > 50", 20)
        print("linked:", await q(tfs), await q("() => document.getElementById('ovcLink').getAttribute('aria-pressed')"))
        await q("() => document.getElementById('ovcLink').click()")
        await q("() => goPage('charts')"); await wait("() => chVis().length === 4 && chVis().every(P => P.sym === 'SOLUSDT')", 30)
        print("charts page end:", await q("() => [OVC.on, CH.sym, CH.layout, CH.tfs.join(','), chVis().map(P => P.psym || '-').join(',')]"))
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
