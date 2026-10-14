import asyncio, sys, time, json
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OUT = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "out", "finder")
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1600, "height": 950}, color_scheme="dark"); await setup(ctx)
        pg = await ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: m.type == "error" and "s3-symbol-logo" not in m.text and errs.append("console: " + m.text[:200]))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        await pg.click('#side [data-go="charts"]')
        for _ in range(60):
            if await q("() => CHP.length === 4 && CHP.every(P => P.t.length > 0)"): break
            await asyncio.sleep(0.25)
        await asyncio.sleep(1)
        print("1) indicators:", await q("() => CH.ind.map(I => I.type).join(',')"), "| legends pane1:", await q("() => document.querySelector('#chWrap1 .chind').innerText.replace(/\\s+/g,' ')"))
        print("   osc layout:", await q("() => JSON.stringify(CHP[1].oscL)"), "| series:", await q("() => Object.values(CHP[1].ix).map(x => Object.keys(x.ser).join('+')).join(' | ')"))
        print("   toolbar groups:", await q("() => [...document.querySelectorAll('#chTools .chtb')].map(b => b.title).join(' | ')"))
        print("   fav bar:", await q("() => [...document.querySelectorAll('#chFavBar button')].map(b => b.title).join(', ')"))
        print("   errors:", errs[:5] or "none")
        await pg.screenshot(path=f"{OUT}/chx_1.png")
        # indicators dialog: add several
        await pg.click("#chIndBtn"); await asyncio.sleep(0.4)
        print("2) dialog cats:", await q("() => [...document.querySelectorAll('#chIndNav button')].map(b => b.innerText.trim()).join(' | ')"))
        await pg.screenshot(path=f"{OUT}/chx_dlg.png")
        await pg.fill("#chIndQ", "bollinger"); await asyncio.sleep(0.2); print("   search:", await q("() => [...document.querySelectorAll('#chIndList [data-add]')].map(r => r.dataset.add).join(',')"))
        await pg.keyboard.press("Enter"); await asyncio.sleep(0.3)
        for k in ["macd", "vwap", "fvg", "vol", "ichi", "st", "levels"]:
            await q(f"() => {{ CH.ind.push(indNew('{k}')); }}")
        await q("() => { chIndChanged(); chModalClose(); }"); await asyncio.sleep(1.5)
        print("   now:", await q("() => CH.ind.map(I => indTitle(I)).join(' · ')"))
        print("   pane1 osc:", await q("() => CHP[1].oscL.map(o => CH.ind.find(I => I.id === o.id).type + '@' + o.top.toFixed(2)).join(' ')"), "| legend:", await q("() => document.querySelector('#chWrap1 .chind').innerText.replace(/\\s+/g,' ').slice(0, 400)"))
        print("   errors:", errs[:5] or "none")
        await pg.screenshot(path=f"{OUT}/chx_2.png")
        # settings dialog of RSI: change length and a colour; cancel restores
        rsi = await q("() => CH.ind.find(I => I.type === 'rsi').id")
        await q(f"() => chIndSettings(CH.ind.find(I => I.id === '{rsi}'))"); await asyncio.sleep(0.3)
        await pg.fill("#ci_len", "7"); await asyncio.sleep(0.4)
        print("3) live preview len:", await q(f"() => CH.ind.find(I => I.id === '{rsi}').p.len"), "| legend:", await q(f"() => document.querySelector('#chWrap1 [data-iid=\"{rsi}\"] .nm').textContent"))
        await pg.click('.chtabs [data-tab="style"]'); await asyncio.sleep(0.2); await pg.screenshot(path=f"{OUT}/chx_set_style.png")
        await pg.click('.chtabs [data-tab="vis"]'); await asyncio.sleep(0.2)
        await pg.click("#chSetCancel"); await asyncio.sleep(0.3)
        print("   after cancel len:", await q(f"() => CH.ind.find(I => I.id === '{rsi}').p.len"))
        # legend buttons: hide and remove via hover
        await q(f"() => {{ const r = document.querySelector('#chWrap1 [data-iid=\"{rsi}\"] [data-ia=\"eye\"]'); r.click(); }}"); await asyncio.sleep(0.3)
        print("4) hidden rsi:", await q(f"() => CH.ind.find(I => I.id === '{rsi}').hide"), "| osc count:", await q("() => CHP[1].oscL.length"))
        await q(f"() => document.querySelector('#chWrap1 [data-iid=\"{rsi}\"] [data-ia=\"eye\"]').click()"); await asyncio.sleep(0.3)
        print("   errors:", errs[:5] or "none")
        await b.close()
asyncio.run(main())
