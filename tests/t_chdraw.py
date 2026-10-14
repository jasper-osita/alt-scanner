import asyncio, sys, time, json
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OUT = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "out", "finder")
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1600, "height": 950}, color_scheme="dark"); await setup(ctx)
        pg = await ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        await pg.click('#side [data-go="charts"]')
        for _ in range(60):
            if await q("() => CHP.length === 4 && CHP.every(P => P.t.length > 0)"): break
            await asyncio.sleep(0.25)
        await q("() => { CH.layout = '1'; CH.max = null; chApplyLayout(); }"); await asyncio.sleep(1.2)
        P = await q("() => chVis()[0].i"); box = await pg.locator(f"#chCv{P}").bounding_box()
        X = lambda f: box["x"] + box["width"] * 0.85 * f; Y = lambda f: box["y"] + box["height"] * 0.7 * f
        # every tool: pick it and click its points
        tools = await q("() => Object.values(CH_T).filter(T => T.paint).map(T => [T.id, T.n])")
        made, bad = [], []
        for tid, n in tools:
            before = await q("() => chList().length")
            await q(f"() => chPickTool('{tid}')")
            pts = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7}.get(n, 0)
            base = [(0.15, 0.6), (0.35, 0.3), (0.5, 0.55), (0.62, 0.35), (0.75, 0.6), (0.85, 0.3), (0.95, 0.5)]
            if n == "free":
                await pg.mouse.move(X(0.2), Y(0.5)); await pg.mouse.down()
                for k in range(12): await pg.mouse.move(X(0.2 + k * 0.03), Y(0.5 + (k % 3) * 0.05))
                await pg.mouse.up()
            elif n == "multi":
                for (fx, fy) in base[:4]: await pg.mouse.click(X(fx), Y(fy)); await asyncio.sleep(0.05)
                await pg.keyboard.press("Enter")
            else:
                for (fx, fy) in base[:pts]: await pg.mouse.move(X(fx), Y(fy), steps=3); await pg.mouse.click(X(fx), Y(fy)); await asyncio.sleep(0.05)
            await asyncio.sleep(0.15)
            if await q("() => !!document.querySelector('.chtxt')"): await pg.keyboard.type("Hi " + tid); await pg.keyboard.press("Enter"); await asyncio.sleep(0.1)
            after = await q("() => chList().length")
            (made if after == before + 1 else bad).append(tid)
            await q("() => { chSel = null; chSelBar(); }")
        print("1) created:", len(made), "| failed:", bad, "| errors:", errs[:3] or "none")
        await asyncio.sleep(0.4); await pg.screenshot(path=f"{OUT}/chd_all.png")
        print("   hits per drawing:", await q("() => { const P = chVis()[0]; return P.hits.filter(h => !h.hits.length).map(h => chList().find(d => d.id === h.id).type).join(',') || 'all hittable'; }"))
        # clear and test selection, floating toolbar, settings
        await q("() => { CHD[CH.sym] = []; chCommit(); }")
        await q("() => chPickTool('trend')"); await pg.mouse.click(X(0.3), Y(0.6)); await pg.mouse.move(X(0.6), Y(0.3), steps=4); await pg.mouse.click(X(0.6), Y(0.3)); await asyncio.sleep(0.3)
        print("2) selected:", await q("() => !!chSelD()"), "| float:", await q("() => document.getElementById('chFloat').innerText.replace(/\\s+/g, ' ')"), "| buttons:", await q("() => [...document.querySelectorAll('#chFloat [data-fl]')].map(b => b.dataset.fl).join(',')"))
        await pg.click('#chFloat [data-fl="w"]'); await asyncio.sleep(0.2); await pg.click('#chMenu [data-mk="4"]'); await asyncio.sleep(0.2)
        await pg.click('#chFloat [data-fl="c"]'); await asyncio.sleep(0.2); await pg.click('#chColPop [data-pc="#f23645"]'); await asyncio.sleep(0.1); await q("() => chColorClose()")
        print("   style now:", await q("() => JSON.stringify(chSelD().s)"))
        await pg.click('#chFloat [data-fl="set"]'); await asyncio.sleep(0.3)
        print("3) settings tabs:", await q("() => [...document.querySelectorAll('.chtabs button')].map(b => b.textContent).join('|')"), "| rows:", await q("() => [...document.querySelectorAll('#chDSB .chsr label')].map(l => l.textContent).join(', ')"))
        await pg.select_option('#chDSB [data-k="ext"]', "right"); await pg.check('#chDSB [data-b="stats"]'); await asyncio.sleep(0.2)
        await pg.screenshot(path=f"{OUT}/chd_settings.png")
        await pg.click('.chtabs [data-tab="text"]'); await asyncio.sleep(0.1); await pg.fill("#chDSB textarea", "Breakout line"); await asyncio.sleep(0.1)
        await pg.click('.chtabs [data-tab="coords"]'); await asyncio.sleep(0.1); await pg.screenshot(path=f"{OUT}/chd_coords.png")
        await pg.click("#chDSOk"); await asyncio.sleep(0.3)
        print("   after Ok:", await q("() => JSON.stringify(chSelD().s)"))
        # undo/redo
        await pg.keyboard.press("Meta+z"); await asyncio.sleep(0.1); u = await q("() => JSON.stringify((chList()[0] || {}).s)"); await pg.keyboard.press("Meta+Shift+z"); await asyncio.sleep(0.1)
        print("4) undo→", u, "| redo→", await q("() => JSON.stringify((chList()[0] || {}).s)"))
        # flyout with stars
        await pg.click('#chTools [data-garr="lines"]'); await asyncio.sleep(0.2)
        print("5) lines flyout:", await q("() => [...document.querySelectorAll('#chMenu .chmhd, #chMenu [data-mk] .ml')].map(e => e.textContent).join(' | ')"))
        await pg.screenshot(path=f"{OUT}/chd_flyout.png")
        await pg.click('#chMenu [data-star="vline"]'); await asyncio.sleep(0.1); await pg.click('#chMenu [data-mk="pchan"]'); await asyncio.sleep(0.1)
        print("   tool:", await q("() => chTool"), "| group icon now:", await q("() => document.querySelector('[data-gt=lines]').title"), "| fav has vline:", await q("() => CH.toolFav.includes('vline')"))
        await pg.keyboard.press("Escape")
        # shortcuts
        await pg.keyboard.press("Alt+KeyH"); print("6) Alt+H →", await q("() => chTool"), end=" ")
        await pg.keyboard.press("Alt+KeyF"); print("| Alt+F →", await q("() => chTool"), end=" ")
        await pg.keyboard.press("Alt+Shift+KeyR"); print("| Alt+Shift+R →", await q("() => chTool"))
        await pg.keyboard.press("Escape")
        # drag move + ctrl-drag clone + eraser
        n0 = await q("() => chList().length")
        sx, sy = X(0.45), Y(0.45)
        hp = await q("() => { const P = chVis()[0], d = chList()[0]; return [(chX(P, d.pts[0].t) + chX(P, d.pts[1].t)) / 2, (chY(P, d.pts[0].p) + chY(P, d.pts[1].p)) / 2]; }")
        cx, cy = box["x"] + hp[0], box["y"] + hp[1]
        await pg.keyboard.down("Meta"); await pg.mouse.move(cx, cy); await pg.mouse.down(); await pg.mouse.move(cx + 60, cy + 40, steps=5); await pg.mouse.up(); await pg.keyboard.up("Meta"); await asyncio.sleep(0.2)
        print("7) cmd-drag clone:", n0, "→", await q("() => chList().length"))
        await q("() => chPickTool('eraser')"); await pg.mouse.click(cx + 60, cy + 40); await asyncio.sleep(0.2)
        await pg.mouse.click(cx, cy, button="right"); await asyncio.sleep(0.2)
        print("   context menu:", await q("() => [...document.querySelectorAll('#chMenu [data-mk] .ml')].map(e => e.textContent).join(', ')")); await pg.keyboard.press("Escape")
        print("   eraser:", await q("() => chList().length"), "| tool after:", await q("() => chTool"))
        # magnet menu, hide menu, remove menu
        await pg.click('#chTools [data-garr="magnet"]'); await asyncio.sleep(0.1); await pg.click('#chMenu [data-mk="strong"]'); print("8) magnet:", await q("() => CH.magnet"), end=" ")
        await pg.click('#chTools [data-garr="hide"]'); await asyncio.sleep(0.1); await pg.click('#chMenu [data-mk="i"]'); print("| hide indicators:", await q("() => chIndHidden + ' series ' + Object.keys(chVis()[0].ix).length"), end=" ")
        await pg.click('#chTools [data-garr="hide"]'); await asyncio.sleep(0.1); await pg.click('#chMenu [data-mk="s"]'); print("| shown again:", await q("() => Object.keys(chVis()[0].ix).length"))
        # right-click context menu
        await pg.mouse.click(cx, cy, button="right"); await asyncio.sleep(0.2)
        print("9) context menu:", await q("() => [...document.querySelectorAll('#chMenu [data-mk] .ml')].map(e => e.textContent).join(', ')")); await pg.keyboard.press("Escape")
        # icon picker
        await pg.click('#chTools [data-garr="icon"]'); await asyncio.sleep(0.1); await pg.click('#chMenu [data-emo="🚀"]'); await pg.mouse.click(X(0.7), Y(0.7)); await asyncio.sleep(0.2)
        print("10) icon:", await q("() => JSON.stringify(chList().at(-1).s)"))
        # old drawings migrate
        r = await q("""() => { CHD.TESTUSDT = [{ id: 'x1', type: 'trend', pts: [{t: 1, p: 1}, {t: 2, p: 2}], color: '#f23645' }, { id: 'x2', type: 'text', pts: [{t: 1, p: 1}], color: '#22ab94', text: 'old note' }]; chNormDrawings(); return JSON.stringify(CHD.TESTUSDT.map(d => d.s)); }""")
        print("11) migrated:", r)
        print("errors:", errs[:5] or "none")
        await b.close()
asyncio.run(main())
