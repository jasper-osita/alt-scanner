import asyncio, sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OUT = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "out", "finder")
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1600, "height": 950}, color_scheme="dark"); await setup(ctx)
        pg = await ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e) + ' @ ' + (e.stack or '')[:300]))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        await q("() => goPage('filters')")
        print("0) filters panel open before Charts:", await q("() => document.body.classList.contains('fopen')"))
        await q("() => goPage('charts')")
        for _ in range(60):
            if await q("() => CHP.length === 4 && CHP.every(P => P.t.length > 0)"): break
            await asyncio.sleep(0.25)
        W = "() => chVis().map(P => P.i + ':' + Math.round(P.pane.getBoundingClientRect().width) + 'x' + Math.round(P.pane.getBoundingClientRect().height)).join(' ')"
        print("1) default 4g:", await q(W), "| grid width", await q("() => Math.round(document.getElementById('chGrid').getBoundingClientRect().width)"), "| filters panel shown:", await q("() => getComputedStyle(document.getElementById('fPanel')).display"))
        # nav + watchlist collapse
        w0 = await q("() => CHP[0].pane.getBoundingClientRect().width")
        await pg.click("#navTog"); await asyncio.sleep(0.4)
        await pg.click("#chWLHide"); await asyncio.sleep(0.4)
        print("2) sidebar hidden:", await q("() => getComputedStyle(document.getElementById('side')).display"), "| watchlist strip:", await q("() => !!document.getElementById('chWLOpen')"), "| pane 0 width", round(w0), "→", await q("() => Math.round(CHP[0].pane.getBoundingClientRect().width)"), "| chart canvas width follows:", await q("() => CHP[0].chart.timeScale().width() > 0 && Math.abs(CHP[0].cv.clientWidth - CHP[0].pane.clientWidth) < 4"))
        # layout picker
        await pg.click("#chLayBtn"); await asyncio.sleep(0.2)
        print("3) picker rows:", await q("() => [...document.querySelectorAll('#chLayPop .chlr')].map(r => r.querySelector('span').textContent + ':' + r.querySelectorAll('button').length).join(' ')"))
        await pg.screenshot(path=f"{OUT}/chlay_pop.png")
        await pg.click('#chLayPop [data-lay="3L"]'); await asyncio.sleep(1.2)
        print("   3L:", await q(W), "| layout", await q("() => CH.layout"))
        # drag the main gutter right by 200px
        g = await pg.locator(".chroot > .chgut").first.bounding_box()
        await pg.mouse.move(g["x"] + 3, g["y"] + g["height"] / 2); await pg.mouse.down(); await pg.mouse.move(g["x"] + 203, g["y"] + g["height"] / 2, steps=8); await pg.mouse.up(); await asyncio.sleep(0.4)
        print("4) after drag:", await q(W), "| sizes", await q("() => JSON.stringify(CH.sizes['3L'].r.map(x => +x.toFixed(2)))"))
        # inner gutter (between the two right charts)
        g2 = await pg.locator(".chroot .chsp.chv > .chgut").first.bounding_box()
        await pg.mouse.move(g2["x"] + g2["width"] / 2, g2["y"] + 3); await pg.mouse.down(); await pg.mouse.move(g2["x"] + g2["width"] / 2, g2["y"] - 150, steps=6); await pg.mouse.up(); await asyncio.sleep(0.4)
        print("   inner drag:", await q(W))
        await pg.dblclick(".chroot .chsp.chv > .chgut"); await asyncio.sleep(0.3)
        print("   double-click evens:", await q(W))
        await pg.screenshot(path=f"{OUT}/chlay_3L.png")
        # maximize pane 1 and back
        await pg.click('[data-max="1"]'); await asyncio.sleep(0.6)
        print("5) maximized:", await q(W))
        await pg.click('[data-max="1"]'); await asyncio.sleep(0.6)
        print("   restored:", await q(W))
        # every layout renders the right number of panes
        res = await q("() => Object.keys(CH_LAYOUTS).map(id => { CH.layout = id; CH.max = null; chApplyLayout(); return id + ':' + chVis().length + '/' + document.querySelectorAll('#chGrid .chpane').length; }).join(' ')")
        print("6) all layouts:", res)
        await q("() => { CH.layout = '4L'; chApplyLayout(); chSave(); }"); await asyncio.sleep(1.2)
        print("   4L:", await q(W))
        # fit button resets a dragged price scale
        await q("() => CHP[1].chart.priceScale('right').applyOptions({ autoScale: false })")
        await pg.click('[data-fit="1"]'); await asyncio.sleep(0.2)
        print("7) fit restores auto-scale:", await q("() => CHP[1].chart.priceScale('right').options().autoScale"))
        # focus mode
        await pg.click("#chFocus"); await asyncio.sleep(0.4)
        print("8) focus:", await q("() => ({ topbar: getComputedStyle(document.querySelector('.topbar')).display, h: Math.round(document.getElementById('chPage').getBoundingClientRect().height) })"))
        await pg.screenshot(path=f"{OUT}/chlay_focus.png")
        await pg.keyboard.press("Escape"); await asyncio.sleep(0.3)
        print("   esc leaves focus:", await q("() => !document.body.classList.contains('chfocus')"))
        # persistence
        await pg.reload(); await asyncio.sleep(2.5)
        for _ in range(40):
            if await q("() => typeof CHP !== 'undefined' && CHP.length === 4 && chVis().every(P => P.t.length > 0)"): break
            await asyncio.sleep(0.25)
        print("9) after reload:", await q("() => ({ layout: CH.layout, navcol: document.body.classList.contains('navcol'), wl: CH.wl, sizes3L: JSON.stringify(CH.sizes['3L'].r.map(x => +x.toFixed(2))) })"))
        await pg.click("#navTog"); await asyncio.sleep(0.2)
        print("   sidebar back:", await q("() => getComputedStyle(document.getElementById('side')).display"))
        await q("() => goPage('overview')"); await asyncio.sleep(0.3); await pg.click("#navTog"); await asyncio.sleep(0.3)
        print("10) other page full width:", await q("() => Math.round(document.querySelector('main').getBoundingClientRect().width)"), "of", 1600)
        await pg.click("#navTog")
        await pg.set_viewport_size({"width": 390, "height": 844}); await q("() => goPage('charts')"); await asyncio.sleep(0.8)
        print("11) mobile overflow:", await q("() => document.documentElement.scrollWidth - innerWidth"))
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
