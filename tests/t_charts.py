import asyncio, sys, time
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OUT = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "out", "finder")
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1600, "height": 950}, color_scheme="dark"); await setup(ctx)
        pg = await ctx.new_page(); errs, csp = [], []
        pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: ("Content Security Policy" in m.text and csp.append(m.text[:140])) or (m.type == "error" and errs.append("console: " + m.text[:160])))
        fails = []; pg.on("requestfailed", lambda r: fails.append(r.url[:110]))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        await pg.click('#side [data-go="charts"]')
        for _ in range(60):
            if await q("() => CHP.length === 4 && CHP.every(P => P.t.length > 0)"): break
            await asyncio.sleep(0.25)
        print("1) page:", await q("() => ({ hash: location.hash, pills: getComputedStyle(document.querySelector('.pills')).display, tfs: CHP.map(P => P.tf + ':' + P.t.length).join(' '), grid: document.getElementById('chGrid').className, sym: document.getElementById('chSymName').textContent, legend: document.getElementById('chLeg1').innerText.slice(0, 70) })"))
        print("   watchlist:", await q("() => [...document.querySelectorAll('#chWL .chwg')].map(g => g.textContent).join(' / ') + ' | ' + [...document.querySelectorAll('#chWL .chwr .n')].map(n => n.textContent).join(', ')"))
        await pg.screenshot(path=f"{OUT}/charts_4.png")
        # crosshair sync
        await q("() => { window.__x = []; CHP.forEach(P => { const f = P.chart.setCrosshairPosition.bind(P.chart); P.chart.setCrosshairPosition = (p, t, s) => { __x.push(P.i + ':' + t); return f(p, t, s); }; }); }")
        box = await pg.locator("#chCv1").bounding_box()
        await pg.mouse.move(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.35); await asyncio.sleep(0.3)
        print("2) crosshair sync calls:", await q("() => [...new Set(__x.map(x => x.split(':')[0]))].join(',')"), "| legends:", await q("() => CHP.map(P => document.getElementById('chLeg' + P.i).innerText.split(' C ')[1] || '').join(' | ').slice(0, 160)"))
        # trend line on the 1H pane by two clicks
        await pg.evaluate("() => chPickTool(\'trend\')")
        x1, y1, x2, y2 = box["x"] + box["width"] * 0.35, box["y"] + box["height"] * 0.45, box["x"] + box["width"] * 0.7, box["y"] + box["height"] * 0.25
        await pg.mouse.click(x1, y1); await pg.mouse.move(x2, y2, steps=5); await pg.mouse.click(x2, y2); await asyncio.sleep(0.3)
        print("3) trend:", await q("() => { const d = CHD[CH.sym]; return d.length + ' drawing(s) ' + d.map(x => x.type + ' ' + x.pts.length + 'pts').join(', ') + ' | tool now ' + chTool + ' | selected ' + !!chSel; }"))
        print("   drawn on every timeframe (x of both ends per pane):", await q("() => { const d = CHD[CH.sym][0]; return CHP.map(P => CH_TFL[P.tf] + ' ' + d.pts.map(p => Math.round(chX(P, p.t))).join('→')).join(' | '); }"))
        print("   pixels on the 4H overlay near the line:", await q("() => { const d = CHD[CH.sym][0], P = CHP[0], x = (chX(P, d.pts[0].t) + chX(P, d.pts[1].t)) / 2, y = (chY(P, d.pts[0].p) + chY(P, d.pts[1].p)) / 2, dpr = devicePixelRatio, g = P.ov.getContext('2d'); let a = 0; for (let dx = -3; dx <= 3; dx++) for (let dy = -3; dy <= 3; dy++) a = Math.max(a, g.getImageData(Math.round((x + dx) * dpr), Math.round((y + dy) * dpr), 1, 1).data[3]); return a; }"))
        # select + drag the trend line, then delete and undo
        await pg.keyboard.press("Escape")
        mid = await q("() => { const d = CHD[CH.sym][0], P = CHP[1], r = P.cv.getBoundingClientRect(); return { x: r.left + (chX(P, d.pts[0].t) + chX(P, d.pts[1].t)) / 2, y: r.top + (chY(P, d.pts[0].p) + chY(P, d.pts[1].p)) / 2, p0: d.pts[0].p }; }")
        await pg.mouse.move(mid["x"], mid["y"]); await pg.mouse.down(); await pg.mouse.move(mid["x"] + 30, mid["y"] - 25, steps=6); await pg.mouse.up(); await asyncio.sleep(0.2)
        print("5) drag moved line:", await q(f"() => CHD[CH.sym][0].pts[0].p !== {mid['p0']}"), "| selected:", await q("() => chSel === CHD[CH.sym][0].id"), "| sel bar:", await q("() => !document.getElementById('chFloat').hidden"))
        await pg.click('#chFloat [data-fl="c"]'); await pg.click('#chColPop [data-pc="#f23645"]'); await pg.evaluate("() => chColorClose()"); n0 = await q("() => CHD[CH.sym].length")
        await pg.keyboard.press("Delete"); n1 = await q("() => CHD[CH.sym].length")
        await pg.keyboard.press("Control+z"); n2 = await q("() => CHD[CH.sym].length")
        print("   colour:", await q("() => CHD[CH.sym].map(d => d.s && d.s.c)[0]"), "| delete:", n0, "→", n1, "| undo →", n2)
        # more tools on the 15m pane
        b2 = await pg.locator("#chCv2").bounding_box(); X = lambda f: b2["x"] + b2["width"] * f; Y = lambda f: b2["y"] + b2["height"] * f
        await pg.evaluate("() => chPickTool(\'hline\')"); await pg.mouse.click(X(0.5), Y(0.3)); await asyncio.sleep(0.1)
        await pg.evaluate("() => chPickTool(\'rect\')"); await pg.mouse.move(X(0.2), Y(0.2)); await pg.mouse.down(); await pg.mouse.move(X(0.35), Y(0.4), steps=6); await pg.mouse.up(); await asyncio.sleep(0.1)
        await pg.evaluate("() => chPickTool(\'fib\')"); await pg.mouse.click(X(0.4), Y(0.6)); await pg.mouse.move(X(0.6), Y(0.2), steps=4); await pg.mouse.click(X(0.6), Y(0.2)); await asyncio.sleep(0.1)
        await pg.evaluate("() => chPickTool(\'long\')"); await pg.mouse.click(X(0.6), Y(0.45)); await pg.mouse.move(X(0.75), Y(0.55), steps=3); await pg.mouse.click(X(0.75), Y(0.55)); await asyncio.sleep(0.1)
        await pg.evaluate("() => chPickTool(\'path\')"); await pg.mouse.click(X(0.1), Y(0.6)); await pg.mouse.move(X(0.2), Y(0.5), steps=3); await pg.mouse.click(X(0.2), Y(0.5)); await pg.mouse.move(X(0.3), Y(0.55), steps=3); await pg.mouse.click(X(0.3), Y(0.55)); await asyncio.sleep(0.05); await pg.mouse.click(X(0.3), Y(0.55)); await asyncio.sleep(0.1)
        await pg.evaluate("() => chPickTool(\'brush\')"); await pg.mouse.move(X(0.1), Y(0.3)); await pg.mouse.down()
        for k in range(12): await pg.mouse.move(X(0.1 + k * 0.01), Y(0.3 + (k % 3) * 0.02))
        await pg.mouse.up(); await asyncio.sleep(0.1)
        await pg.evaluate("() => chPickTool(\'arrow\')"); await pg.mouse.click(X(0.45), Y(0.7)); await pg.mouse.move(X(0.55), Y(0.62), steps=3); await pg.mouse.click(X(0.55), Y(0.62)); await asyncio.sleep(0.1)
        await pg.evaluate("() => chPickTool(\'text\')"); await pg.mouse.click(X(0.4), Y(0.6)); await asyncio.sleep(0.2); await pg.keyboard.type("OB retest"); await pg.keyboard.press("Enter"); await asyncio.sleep(0.2)
        await pg.click('#chTools [data-tool="measure"]'); await pg.mouse.click(X(0.3), Y(0.5)); await pg.mouse.move(X(0.45), Y(0.35), steps=3); await pg.mouse.click(X(0.45), Y(0.35)); await asyncio.sleep(0.2)
        print("4) tools:", await q("() => CHD[CH.sym].map(d => d.type + (d.type === 'path' ? '(' + d.pts.length + ')' : d.type === 'brush' ? '(' + d.pts.length + ')' : '') + (d.s && d.s.txt ? '\"' + d.s.txt + '\"' : '')).join(', ')"), "| measure shown:", await q("() => !!chMeasure"))
        print("   long position:", await q("() => { const d = CHD[CH.sym].find(x => x.type === 'long'); const [e, s, t] = d.pts.map(p => p.p); return `entry ${e.toFixed(3)} stop ${s.toFixed(3)} target ${t.toFixed(3)} R ${((t - e) / (e - s)).toFixed(2)}`; }"))
        await pg.screenshot(path=f"{OUT}/charts_draw.png")
        # timeframe change, layout, symbol from watchlist
        await pg.select_option('.chtf[data-i="3"]', "30m"); await asyncio.sleep(1.2)
        print("6) tf change:", await q("() => CHP[3].tf + ' ' + CHP[3].t.length + ' bars, step ' + (CHP[3].t[1] - CHP[3].t[0]) / 60000 + 'm'"))
        await pg.click("#chLayBtn"); await pg.click('#chLayPop [data-lay="2c"]'); await asyncio.sleep(0.4)
        print("   layout 2:", await q("() => CH.layout + ' visible panes ' + document.querySelectorAll('#chGrid .chpane').length"))
        await pg.click("#chLayBtn"); await pg.click('#chLayPop [data-lay="4g"]'); await asyncio.sleep(0.4)
        await pg.click('#chWL .chwr[data-s="XAUUSDT"]')
        for _ in range(40):
            if await q("() => CH.sym === 'XAUUSDT' && CHP.every(P => P.sym === 'XAUUSDT')"): break
            await asyncio.sleep(0.25)
        print("7) gold:", await q("() => document.getElementById('chSymName').textContent + ' | panes ' + CHP.map(P => P.sym).join(',') + ' | drawings ' + (CHD.XAUUSDT || []).length + ' (BTC keeps ' + CHD.BTCUSDT.length + ')'"))
        # watchlist add
        await pg.click("#chWLAddB"); await pg.fill("#chWLQ", "nasd"); await asyncio.sleep(0.2)
        print("8) search 'nasd':", await q("() => [...document.querySelectorAll('#chWL [data-add]')].map(b => b.innerText.replace(/\\s+/g, ' ')).join(' | ')"))
        await pg.fill("#chWLQ", "doge"); await asyncio.sleep(0.2); await pg.click('#chWL [data-add="DOGEUSDT"]'); await pg.click("#chWLAddB"); await asyncio.sleep(0.2)
        print("   added DOGE:", await q("() => CHW.includes('DOGEUSDT') && !!document.querySelector('#chWL .chwr[data-s=\"DOGEUSDT\"]')"))
        # persistence
        await pg.reload(); await asyncio.sleep(2.5)
        for _ in range(40):
            if await q("() => typeof CHP !== 'undefined' && CHP.length === 4 && CHP.every(P => P.t.length > 0)"): break
            await asyncio.sleep(0.25)
        print("9) after reload:", await q("() => ({ page, sym: CH.sym, tfs: CH.tfs.join(','), btcDrawings: (CHD.BTCUSDT || []).length, wl: CHW.length })"))
        # popup → Charts button
        await q("() => goPage('overview')"); await ready(pg)
        s = await q("() => data.all[2].symbol"); await q(f"() => openDetail({s!r})"); await asyncio.sleep(1)
        await pg.click(f'[data-openchart="{s}"]'); await asyncio.sleep(1.5)
        print("10) popup → Charts:", await q("() => page + ' ' + CH.sym"), "expected", s)
        await pg.set_viewport_size({"width": 390, "height": 844}); await asyncio.sleep(0.6)
        print("11) mobile overflow:", await q("() => document.documentElement.scrollWidth - innerWidth"))
        await pg.screenshot(path=f"{OUT}/charts_mobile.png", full_page=False)
        import collections; print("failed requests:", collections.Counter(f.split("?")[0] for f in fails).most_common(8))
        print("CSP:", csp or "none", "| errors:", [e for e in errs if "Failed to load resource" not in e] or "none")
        await b.close()
asyncio.run(main())
