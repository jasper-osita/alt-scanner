import asyncio, sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1600, "height": 950}); await setup(ctx)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        await pg.click('#side [data-go="charts"]'); await asyncio.sleep(3)
        await q("() => { CH.layout = '1'; CH.max = null; chApplyLayout(); }"); await asyncio.sleep(2.5)
        P = await q("() => chVis()[0].i"); bx = await pg.locator(f"#chCv{P}").bounding_box()
        X = lambda f: bx["x"] + bx["width"] * 0.8 * f; Y = lambda f: bx["y"] + bx["height"] * 0.65 * f
        px = "(d, j) => { const P = chVis()[0]; return [chX(P, d.pts[j].t), chY(P, d.pts[j].p)]; }"
        async def draw(tool, a, c, shift=True):
            await q(f"() => chPickTool('{tool}')"); await pg.mouse.move(*a); await pg.mouse.click(*a)
            if shift: await pg.keyboard.down("Shift")
            await pg.mouse.move(*c, steps=6); await pg.mouse.click(*c)
            if shift: await pg.keyboard.up("Shift")
            await asyncio.sleep(0.15)
            return await q(f"() => {{ const d = chList().at(-1), f = {px}; const a = f(d, 0), b = f(d, 1); return [d.type, Math.round(b[0] - a[0]), Math.round(b[1] - a[1]), d.pts[0].p === d.pts[1].p, d.pts[0].t === d.pts[1].t]; }}")
        print("near-flat trend :", await draw("trend", (X(0.2), Y(0.5)), (X(0.6), Y(0.47))), "→ same price")
        print("near-45 trend   :", await draw("trend", (X(0.2), Y(0.8)), (X(0.4), Y(0.8) - (X(0.4) - X(0.2)) * 0.85)), "→ |dx|=|dy|")
        print("near-vert trend :", await draw("trend", (X(0.5), Y(0.8)), (X(0.51), Y(0.3))), "→ same time")
        print("no shift        :", await draw("trend", (X(0.2), Y(0.5)), (X(0.6), Y(0.47)), False))
        print("rect square     :", await draw("rect", (X(0.3), Y(0.3)), (X(0.5), Y(0.4))), "→ square")
        print("ellipse circle  :", await draw("ellipse", (X(0.6), Y(0.3)), (X(0.7), Y(0.6))))
        print("fib flat?       :", await draw("fib", (X(0.1), Y(0.5)), (X(0.3), Y(0.2))))
        # shift-drag a whole line: moves only sideways
        await q("() => { CHD[CH.sym] = CHD[CH.sym].slice(0, 1); chSel = null; chCommit(); }")
        mid = await q("() => { const P = chVis()[0], d = chList()[0], r = P.cv.getBoundingClientRect(); return [r.left + (chX(P, d.pts[0].t) + chX(P, d.pts[1].t)) / 2, r.top + chY(P, d.pts[0].p)]; }")
        p0 = await q("() => chList()[0].pts[0].p"); t0 = await q("() => chList()[0].pts[0].t")
        await pg.mouse.move(*mid); await pg.mouse.down(); await pg.keyboard.down("Shift"); await pg.mouse.move(mid[0] + 80, mid[1] + 18, steps=6); await pg.mouse.up(); await pg.keyboard.up("Shift"); await asyncio.sleep(0.15)
        print("shift-move      : price kept", await q(f"() => chList()[0].pts[0].p === {p0}"), "| time moved", await q(f"() => chList()[0].pts[0].t !== {t0}"))
        # shift-drag a handle to near-flat
        h = await q("() => { const P = chVis()[0], d = chList()[0], r = P.cv.getBoundingClientRect(); return [r.left + chX(P, d.pts[1].t), r.top + chY(P, d.pts[1].p)]; }")
        await pg.mouse.move(*h); await pg.mouse.down(); await pg.keyboard.down("Shift"); await pg.mouse.move(h[0] + 40, h[1] - 60, steps=6); await pg.mouse.up(); await pg.keyboard.up("Shift"); await asyncio.sleep(0.15)
        print("shift-handle    :", await q(f"() => {{ const d = chList()[0], f = {px}; const a = f(d, 0), b = f(d, 1); return [Math.round(b[0] - a[0]), Math.round(b[1] - a[1])]; }}"), "→ snapped to 45° or flat")
        # shift-click on empty chart still measures
        await pg.keyboard.down("Shift"); await pg.mouse.click(X(0.8), Y(0.9)); await pg.keyboard.up("Shift"); print("shift-click empty → tool:", await q("() => chTool"), "| hint:", await q("() => document.getElementById('chHint').textContent"))
        await pg.keyboard.press("Escape"); await q("() => chPickTool('trend')"); print("trend hint:", await q("() => document.getElementById('chHint').textContent"))
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
