"""TradingView-style market picker: categories, sources, one row per market with its other sources under +N, compare uses it too."""
import asyncio, sys, os, re, functools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
print = functools.partial(print, flush=True)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "finder")
OPTS = {"secret": "sec", "token": "tok", "live": True}
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1500, "height": 950}, color_scheme="dark"); await setup(ctx); await setup_mexc(ctx)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.route_web_socket(re.compile(r"wss://(live|demo)\.ctraderapi\.com:5036.*"), ct_handler(OPTS))
        await pg.goto("http://localhost:8765/")
        await pg.evaluate("() => { localStorage.clear(); localStorage.setItem('finder-ctrader', JSON.stringify({ clientId: 'cid', clientSecret: 'sec', accessToken: 'tok', prefer: true })); }")
        await pg.goto("http://localhost:8765/#charts"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        for _ in range(80):
            if await q("() => CT.state === 'ready' && CHP.length === 4 && chVis().every(P => P.t.length > 0)"): break
            await asyncio.sleep(0.25)
        await pg.click("#chSymBtn"); await asyncio.sleep(0.3)
        print("1) open:", await q("() => !document.getElementById('chPick').hidden"), "| centred:", await q("() => { const r = document.getElementById('chPick').getBoundingClientRect(); return Math.abs((r.left + r.right) / 2 - innerWidth / 2) < 40; }"),
              "| chips:", await q("() => [...document.querySelectorAll('#chPick [data-pc]')].map(b => b.textContent).join(' · ')"),
              "| sources btn:", await q("() => (document.getElementById('pkSrcB') || {}).textContent"), "| focus:", await q("() => document.activeElement.id"),
              "| placeholder:", await q("() => document.getElementById('chPickQ').placeholder"))
        print("   backdrop:", await q("() => { const b = document.getElementById('chPickBg'), r = b.getBoundingClientRect(), top = document.elementFromPoint(30, innerHeight - 20); return getComputedStyle(b).backgroundColor + ' ' + Math.round(r.width) + 'x' + Math.round(r.height) + ' covers corner ' + (top === b); }"))
        await pg.screenshot(path=f"{OUT}/picker_all.png")
        await pg.keyboard.type("gold"); await asyncio.sleep(0.3)
        print("2) gold rows:", await q("() => document.querySelectorAll('#chPick [data-pk]').length"), "| row:", await q("() => document.querySelector('#chPick [data-pk]').innerText.replace(/\\s+/g, ' ')"),
              "| more:", await q("() => (document.querySelector('#chPick [data-more]') || {}).textContent"))
        await pg.click("#chPick [data-more]"); await asyncio.sleep(0.2)
        print("   expanded:", await q("() => [...document.querySelectorAll('#chPick .pksub:not([hidden]) [data-ps], #chPick .pksubs:not([hidden]) [data-ps]')].map(x => x.dataset.ps).join(',')"))
        await pg.screenshot(path=f"{OUT}/picker_gold.png")
        await pg.click('#chPick [data-ps="MX:XAU_USDT"]'); await asyncio.sleep(0.4)
        print("3) picked MEXC gold:", await q("() => CH.sym + ' closed ' + document.getElementById('chPick').hidden"))
        F = []
        def check(name, ok, detail=""):
            print(("   ok " if ok else "   FAIL ") + name + (" · " + str(detail) if detail else ""))
            if not ok: F.append(name)
        check("a source under +N sticks", await q("() => CH.sym === 'MX:XAU_USDT' && CH.symExact === true"), await q("() => CH.sym + ' ' + CH.symExact"))
        await pg.click("#chSymBtn"); await pg.keyboard.type("gold"); await asyncio.sleep(0.3); await pg.click('#chPick .pkrow .n'); await asyncio.sleep(0.4)
        check("a plain row click doesn't pin the source", await q("() => CH.symExact === false"), await q("() => CH.sym + ' ' + CH.symExact"))
        await q("() => { CH.symExact = true; openInCharts('ETHUSDT'); }"); await asyncio.sleep(0.3)
        check("opening a market from elsewhere clears the pin", await q("() => CH.sym === 'ETHUSDT' && CH.symExact === false"), await q("() => CH.sym + ' ' + CH.symExact"))
        await pg.click("#chSymBtn"); await asyncio.sleep(0.2); await pg.click("#pkSrcB"); await pg.click('#chPick [data-src="mexc"]'); await asyncio.sleep(0.2)
        await pg.keyboard.type("gold"); await asyncio.sleep(0.3); await pg.click('#chPick .pkrow .n'); await asyncio.sleep(0.4)
        check("a row picked with a source filter on sticks", await q("() => CH.sym === 'MX:XAU_USDT' && CH.symExact === true"), await q("() => CH.sym + ' ' + CH.symExact"))
        await pg.click("#chSymBtn"); await asyncio.sleep(0.2); await pg.click("#pkSrcB"); await pg.click('#chPick [data-src="all"]'); await asyncio.sleep(0.2); await pg.keyboard.press("Escape")
        await pg.click("#chSymBtn"); await asyncio.sleep(0.2); await pg.click('#chPick [data-pc="fx"]'); await asyncio.sleep(0.3)
        print("4) forex:", await q("() => { const r = [...document.querySelectorAll('#chPick [data-pk]')]; return r.length + ' rows, all fx ' + r.every(x => chCatOf(x.dataset.ps) === 'fx') + ' · ' + r.slice(0, 4).map(x => x.querySelector('.n b').textContent).join(', '); }"))
        await pg.click("#pkSrcB"); await asyncio.sleep(0.2)
        print("   sources page:", await q("() => document.querySelector('#chPick h4').textContent + ': ' + [...document.querySelectorAll('#chPick [data-src]')].map(x => x.innerText.replace(/\\s+/g, ' ')).join(' | ')"))
        await pg.click('#chPick [data-src="mexc"]'); await asyncio.sleep(0.3)
        print("   MEXC only:", await q("() => { const r = [...document.querySelectorAll('#chPick [data-pk]')]; return r.length + ' rows, all MEXC ' + r.every(x => x.dataset.ps.startsWith('MX:')) + ' · button ' + document.getElementById('pkSrcB').textContent; }"))
        await pg.click("#pkSrcB"); await pg.click('#chPick [data-src="all"]'); await asyncio.sleep(0.3)
        print("   all sources again:", await q("() => document.querySelectorAll('#chPick [data-pk]').length + ' rows · ' + document.getElementById('pkSrcB').textContent"))
        await pg.keyboard.press("Escape"); await asyncio.sleep(0.2)
        print("7) Esc closes:", await q("() => document.getElementById('chPick').hidden"))
        await q("() => { ctClose(); CT.state = 'closed'; const c = ctCfg(); c.prefer = false; ctSaveCfg(c); }")
        await pg.click("#chSymBtn"); await pg.keyboard.type("gold"); await asyncio.sleep(0.3)
        print("5) no cTrader:", await q("() => { const r = document.querySelector('#chPick [data-pk]'); return r.dataset.ps + ' · ' + r.querySelector('.pksrc').textContent + ' · ' + (r.querySelector('[data-more]') || {}).textContent; }"))
        await pg.keyboard.press("Escape")
        await pg.click("#chCmpBtn"); await asyncio.sleep(0.2)
        print("6) compare:", await q("() => (document.querySelector('#chPick .chpfor') || {}).textContent"))
        s0 = await q("() => CH.sym"); await pg.keyboard.press("ArrowDown"); await pg.keyboard.press("ArrowDown")
        sel = await q("() => document.querySelector('#chPick .pkrow.sel').dataset.ps"); await pg.keyboard.press("Enter"); await asyncio.sleep(1.5)
        print("   arrows chose", sel, "→ compared:", await q("() => (CH.cmp || []).map(x => x.sym).join(',')"), "| chart still", s0 == await q("() => CH.sym"))
        # leftovers: on Binance or Bybit the Stocks tab says where stocks come from (not "Loading" forever); an empty list never shows empty quotes
        await pg.keyboard.press("Escape"); await asyncio.sleep(0.2); await q("() => { CH.cmpPick = false; }")
        await pg.click("#chSymBtn"); await asyncio.sleep(0.2); await pg.fill("#chPickQ", ""); await pg.click('#chPick [data-pc="stocks"]'); await asyncio.sleep(0.3)
        st = await q("() => [EXCHANGE, document.querySelector('#chPick .chplist').innerText.trim().slice(0, 140)]")
        check("stocks tab off MEXC says where stocks come from", st[0] != "mexc" and "Loading" not in st[1] and "MEXC" in st[1], st)
        em = await q("() => { const keep = pkMarkets; pkMarkets = () => []; chPickCat = 'indices'; chPickQ = ''; chPickRender(); const t = document.querySelector('#chPick .chplist').innerText.trim(); pkMarkets = keep; chPickCat = 'all'; chPickRender(); return t; }")
        check("an empty list has no empty quotes", "“”" not in em and em != "", em)
        await pg.keyboard.press("Escape"); await asyncio.sleep(0.2)
        await pg.set_viewport_size({"width": 390, "height": 844}); await asyncio.sleep(0.4); await pg.click("#chSymBtn"); await asyncio.sleep(0.3)
        print("8) phone:", await q("() => { const r = document.getElementById('chPick').getBoundingClientRect(); return Math.round(r.left) + '-' + Math.round(r.right) + ' of ' + innerWidth; }"), "| overflow:", await q("() => document.documentElement.scrollWidth - innerWidth"))
        await pg.screenshot(path=f"{OUT}/picker_phone.png")
        print("errors:", F + errs[:4] or "none")
        await b.close()
asyncio.run(main())
