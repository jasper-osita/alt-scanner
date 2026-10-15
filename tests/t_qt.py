import asyncio, sys, re
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OPTS = {"secret": "sec", "token": "tok", "live": True, "scope": "SCOPE_TRADE", "demo2": True, "names": True}
OUT = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "out")
# Quick trade on the chart: market buy/sell with SL/TP lines you can switch off, a locked reward : risk, and dragging the
# entry off the price turns it into a limit or stop order. Orders go to the mocked cTrader demo account only.
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1500, "height": 1000}, color_scheme="dark"); await setup(ctx); await setup_mexc(ctx)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e) + " @ " + (e.stack or "")[:300]))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.route_web_socket("wss://contract.mexc.com/edge", mx_ws_handler)
        await pg.route_web_socket(re.compile(r"wss://(live|demo)\.ctraderapi\.com:5036.*"), ct_handler(OPTS))
        await pg.goto("http://localhost:8765/")
        await pg.evaluate("() => { localStorage.clear(); localStorage.setItem('finder-ctrader', JSON.stringify({ clientId: 'cid', clientSecret: 'sec', accessToken: 'tok' })); }")
        await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        async def wait(js, secs=60):
            for _ in range(secs * 4):
                if await q(js): return True
                await asyncio.sleep(0.25)
            return False
        sent = lambda: [p for t, p in CT_TRADE["log"] if t == 2106]
        await q("() => { document.getElementById('exF').value = 'mexc'; trSave({ ...trCfg(), acct: '777' }); goPage('macro'); macroScan(true); }")
        print("loaded:", await wait("() => !MACRO.running && MACRO.rows.some(r => r.ct)", 200))
        await q("() => { goPage('charts'); CH.layout = '1'; chApplyLayout(); chSetSym('CT:XAUUSD'); }")
        await wait("() => chVis()[0].sym === 'CT:XAUUSD' && chVis()[0].t.length > 50", 60)
        await q("() => document.getElementById('chQtBtn').click()")
        print("box:", await wait("() => !!document.getElementById('qtBox')", 10), "| account:", await wait("() => CTT.state === 'ready' && String(CTT.acct.ctidTraderAccountId) === '777'", 30))
        await wait("() => { const x = cttSym('CT:XAUUSD'); return x && (CTT.spots[x.symbolId] || {}).bid > 0; }", 20); await asyncio.sleep(1)
        box = "() => document.getElementById('qtBox').innerText.replace(/\\s+/g, ' ').slice(0, 230)"
        lines = "() => { const L = qtLines(CH.sym, chCS()), q = trLivePrice(CH.sym), e = L.find(l => l.role === 'entry'), sl = L.find(l => l.role === 'sl'), tp = L.find(l => l.role === 'tp'); return { keys: L.map(l => l.key).join(','), entryIsAsk: e && Math.abs(e.p - q.ask) < 1e-9, rr: sl && tp ? +(Math.abs(tp.p - e.p) / Math.abs(e.p - sl.p)).toFixed(3) : null, entry: e && e.txt }; }"
        print("1) box:", await q(box))
        print("2) lines:", await q(lines))
        await q("() => document.querySelector('#qtBox [data-qt=\"sl\"]').click()"); await asyncio.sleep(0.6)
        print("3) SL off:", await q(lines), "|", await q("() => document.getElementById('qtWarn').innerText"))
        await q("() => document.querySelector('#qtBox [data-qt=\"sl\"]').click()")
        await q("() => document.querySelector('#qtBox [data-rr=\"3\"]').click()"); await asyncio.sleep(0.3)
        print("4) lock 1:3:", await q(lines))
        # market buy, no confirm on demo
        n = len(sent()); await q("() => document.querySelector('#qtBox [data-qs=\"buy\"]').click()")
        await wait(f"() => true", 1); await asyncio.sleep(2.5)
        s = sent()[n:]; print("5) market buy sent:", len(s), {k: s[-1].get(k) for k in ("orderType", "tradeSide", "volume")} if s else None, "| sl/tp relative:", bool(s and s[-1].get("relativeStopLoss") and s[-1].get("relativeTakeProfit")))
        # drag the entry below the price: buy limit (and the sell side would be a sell stop); SL/TP move with it
        await q("() => { const L = qtLevels(CH.sym, 'buy'); window._slD = L.slD; qtDrop('entry', L.live - 40 * L.tick); }"); await asyncio.sleep(0.6)
        print("6) entry below:", await q("() => [document.getElementById('qtBuyL').innerText, document.getElementById('qtSellL').innerText, document.getElementById('qtPendT').innerText]"))
        n = len(sent()); await q("() => document.querySelector('#qtBox [data-qs=\"buy\"]').click()"); await asyncio.sleep(2.5)
        s = sent()[n:]; lv = await q("() => QT._last || null")
        print("7) buy limit sent:", {k: s[-1].get(k) for k in ("orderType", "tradeSide", "limitPrice", "stopLoss", "takeProfit")} if s else None)
        print("   bracket kept:", await q(f"() => {{ const o = {s[-1] if s else {}}; return o.limitPrice ? [+(o.limitPrice - o.stopLoss).toFixed(2) === +window._slD.toFixed(2), +((o.takeProfit - o.limitPrice) / (o.limitPrice - o.stopLoss)).toFixed(2)] : null; }}"), "| back to market after send:", await q("() => qtLevels(CH.sym, 'buy').type"))
        # entry above the price, placed as a sell: sell limit
        await q("() => { const L = qtLevels(CH.sym, 'sell'); qtDrop('entry', L.live + 40 * L.tick); }"); await asyncio.sleep(0.6)
        print("8) entry above:", await q("() => [document.getElementById('qtBuyL').innerText, document.getElementById('qtSellL').innerText]"))
        n = len(sent()); await q("() => { QT.side = 'sell'; document.querySelector('#qtBox [data-qs=\"sell\"]').click(); }"); await asyncio.sleep(2.5)
        s = sent()[n:]; print("9) sell limit sent:", {k: s[-1].get(k) for k in ("orderType", "tradeSide", "limitPrice", "stopLoss", "takeProfit")} if s else None)
        # within 2 ticks of the price it stays a market order; "Back to market" snaps back
        await q("() => { QT.side = 'buy'; const L = qtLevels(CH.sym, 'buy'); qtDrop('entry', L.live + L.tick); }")
        print("10) 1 tick off:", await q("() => qtLevels(CH.sym, 'buy').type"))
        await q("() => { const L = qtLevels(CH.sym, 'buy'); qtDrop('entry', L.live + 30 * L.tick); }")
        t1 = await q("() => qtLevels(CH.sym, 'buy').type"); await q("() => document.getElementById('qtMkt').click()")
        print("11) above price:", t1, "→ back to market:", await q("() => qtLevels(CH.sym, 'buy').type"))
        # a real mouse drag of the entry line down the chart
        await q("() => { QT.side = 'buy'; chDirty = true; }"); await asyncio.sleep(0.5)
        pt = await q("() => { const P = chVis()[0], b = P.bk.find(b => b.key === 'qt:entry'), r = P.cv.getBoundingClientRect(); return [r.left + b.pr[0] + 30, r.top + b.y]; }")
        await pg.mouse.move(pt[0], pt[1]); await asyncio.sleep(0.2); await pg.mouse.down(); await pg.mouse.move(pt[0], pt[1] + 70, steps=8); await asyncio.sleep(0.2)
        mid = await q("() => qtLines(CH.sym, chCS()).map(l => l.key + (l.show ? '*' : '')).join(',')")
        await pg.mouse.up(); await asyncio.sleep(0.6)
        print("12) mouse drag:", mid, "→", await q("() => [qtLevels(CH.sym, 'buy').type, document.getElementById('qtBuyL').innerText]"))
        await q("() => document.getElementById('qtMkt').click()")
        # ask to confirm on demo: first click arms, second sends
        await q("() => { QT.cfDemo = true; }"); n = len(sent())
        await q("() => document.querySelector('#qtBox [data-qs=\"buy\"]').click()"); await asyncio.sleep(0.4)
        print("13) armed:", await q("() => document.getElementById('qtBuyL').innerText"), "| sent yet:", len(sent()) - n)
        await q("() => document.querySelector('#qtBox [data-qs=\"buy\"]').click()"); await asyncio.sleep(2.5)
        print("    after second click sent:", len(sent()) - n); await q("() => { QT.cfDemo = false; }")
        # size from risk %
        await q("() => { document.getElementById('qtGear').click(); document.querySelector('#qtBox [data-sb=\"risk\"]').click(); }")
        await wait("() => QT.sz && QT.sz.val > 0", 15)
        print("14) risk sizing:", await q("() => [QT.sizeBy, QT.sz && QT.sz.val, document.getElementById('qtSize').value, document.getElementById('qtSzL').innerText]"))
        await q("() => { document.querySelector('#qtBox [data-sb=\"lots\"]').click(); document.getElementById('qtGear').click(); }")
        print("15) saved:", await q("() => JSON.stringify(lsGet('finder-qt'))"))
        el = await pg.query_selector("#chPage .chbody"); await el.screenshot(path=f"{OUT}/qt_chart.png")
        # the Trade panel from a Long position hovers top-left of its chart, beside the quick trade box (3 charts, like Jas's layout)
        await q("() => { CH.layout = '3L'; chApplyLayout(); }"); await wait("() => chVis().length === 3 && chVis().every(P => P.t.length > 20)", 30); await asyncio.sleep(1)
        await q("() => { const P = chVis()[0], n = P.t.length, e = P.c.at(-1); CHD[CH.sym] = [{ id: 'lp', type: 'long', pts: [{ t: P.t[n - 6], p: e * 0.998 }, { t: P.t[n - 1], p: e * 0.988 }, { t: P.t[n - 1], p: e * 1.018 }], s: {} }]; chSelPane = 0; chSaveDraw(); chDirty = true; trFromPos(CHD[CH.sym][0]); }")
        await wait("() => !!document.getElementById('trPosPanel')", 10); await asyncio.sleep(1.5)
        print("15b) order panel:", await q("() => { const a = document.getElementById('trPosPanel').getBoundingClientRect(), p = chVis()[0].cv.getBoundingClientRect(), b = document.getElementById('qtBox').getBoundingClientRect(); return { fromChartLeft: Math.round(a.left - p.left), fromChartTop: Math.round(a.top - p.top), underQuickTrade: a.top >= b.bottom - 1, leftOfPosition: a.right < p.left + chX(chVis()[0], CHD[CH.sym][0].pts[0].t) }; }"))
        el = await pg.query_selector("#chPage"); await el.screenshot(path=f"{OUT}/qt_panels.png")
        await q("() => trPosClose()")
        # close the box: lines gone
        await q("() => document.getElementById('qtX').click()"); await asyncio.sleep(0.6)
        print("16) closed:", await q("() => [!!document.getElementById('qtBox'), qtLines(CH.sym, chCS()).length, document.getElementById('chQtBtn').getAttribute('aria-pressed')]"))
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
