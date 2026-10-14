import asyncio, sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OUT = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "out", "finder")
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1600, "height": 950}, color_scheme="dark"); await setup(ctx)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        await q("() => goPage('charts')")
        for _ in range(60):
            if await q("() => CHP.length === 4 && chVis().every(P => P.t.length > 0)"): break
            await asyncio.sleep(0.25)
        print("1) category buttons:", await q("() => [...document.querySelectorAll('.chcats [data-cat]')].map(b => b.innerText.replace(' ▾', '')).join(' | ')"))
        for cat in ["crypto", "metals", "indices", "fx", "recent"]:
            await pg.click(f'.chcats [data-cat="{cat}"]'); await asyncio.sleep(0.6)
            print(f"   {cat}:", await q("() => document.querySelectorAll('#chPick [data-ps]').length + ' rows: ' + [...document.querySelectorAll('#chPick [data-ps] .n b')].slice(0, 6).map(x => x.textContent).join(', ') + ' ' + ((document.querySelector('#chPick .chpnote') || {}).innerText || '').slice(0, 80)"))
            if cat == "metals": await pg.screenshot(path=f"{OUT}/chpick_metals.png")
            await pg.keyboard.press("Escape"); await asyncio.sleep(0.1)
        print("   closes on Esc:", await q("() => document.getElementById('chPick').hidden"))
        # search all + keyboard
        await pg.click("#chSymBtn"); await pg.keyboard.type("gold"); await asyncio.sleep(0.2)
        print("2) search 'gold':", await q("() => [...document.querySelectorAll('#chPick [data-ps]')].map(r => r.dataset.ps).join(',')"), "| tab:", await q("() => chPickCat"))
        await pg.keyboard.press("Enter")
        for _ in range(40):
            if await q("() => CH.sym === 'XAUUSDT' && chVis().every(P => P.sym === 'XAUUSDT')"): break
            await asyncio.sleep(0.25)
        print("   chose:", await q("() => CH.sym + ' ' + document.getElementById('chSymName').textContent"))
        await pg.click('.chcats [data-cat="crypto"]'); await asyncio.sleep(0.4)
        await pg.keyboard.press("ArrowDown"); await pg.keyboard.press("ArrowDown"); want = await q("() => document.querySelector('#chPick .chprow.sel').dataset.ps")
        await pg.keyboard.press("Enter"); await asyncio.sleep(1.5)
        print("3) arrow keys picked:", want, "→", await q("() => CH.sym"))
        # star from the picklist
        await pg.click('.chcats [data-cat="indices"]'); await asyncio.sleep(0.4)
        await pg.click('#chPick [data-star="IWMUSDT"]'); await asyncio.sleep(0.2)
        print("4) starred Russell:", await q("() => CHW.includes('IWMUSDT') && !!document.querySelector('#chWL .chwr[data-s=\"IWMUSDT\"]')"), "| still open:", await q("() => !document.getElementById('chPick').hidden"))
        await pg.mouse.click(900, 600); await asyncio.sleep(0.2)
        print("   outside click closes:", await q("() => document.getElementById('chPick').hidden"))
        await pg.click('.chcats [data-cat="recent"]'); await asyncio.sleep(0.3)
        print("5) recent:", await q("() => [...document.querySelectorAll('#chPick [data-ps]')].map(r => r.dataset.ps).join(',')"))
        await pg.keyboard.press("Escape")
        # countdowns
        c1 = await q("() => chVis().map(P => document.getElementById('chCd' + P.i).textContent).join(' | ')"); await asyncio.sleep(2.2)
        c2 = await q("() => chVis().map(P => document.getElementById('chCd' + P.i).textContent).join(' | ')")
        print("6) countdowns:", c1, "→", c2)
        await pg.screenshot(path=f"{OUT}/chcountdown.png")
        await pg.set_viewport_size({"width": 390, "height": 844}); await asyncio.sleep(0.5)
        await pg.click('#chSymBtn'); await asyncio.sleep(0.4)
        print("7) mobile picker:", await q("() => { const r = document.getElementById('chPick').getBoundingClientRect(); return Math.round(r.left) + '-' + Math.round(r.right) + ' tabs ' + document.querySelectorAll('#chPick [data-pc]').length; }"))
        print("   mobile overflow with picker open:", await q("() => document.documentElement.scrollWidth - innerWidth"))
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
