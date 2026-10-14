import asyncio, sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OUT = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "out", "finder")
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1440, "height": 900}, color_scheme="dark"); await setup(ctx)
        pg = await ctx.new_page(); errs, csp = [], []
        pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: "Content Security Policy" in m.text and csp.append(m.text[:140]))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload()
        ok = await ready(pg); print("crypto scan ok:", ok, "| coins:", await pg.evaluate("() => data.all.length"), "| tradfi in crypto list:", await pg.evaluate("() => data.all.filter(r => /^(XAU|SPY|AAPL)USDT$/.test(r.symbol)).length"))
        await pg.evaluate("() => goPage('macro')")
        for _ in range(60):
            if await pg.evaluate("() => MACRO.rows.length > 0 && !MACRO.running"): break
            await asyncio.sleep(0.5)
        print("rows:", await pg.evaluate("() => MACRO.rows.map(r => r.name + '[' + r.group + ']').join(', ')"))
        print("excluded AAPL/USDBRL:", await pg.evaluate("() => !MACRO.by.AAPLUSDT && !MACRO.by.USDBRLUSDT"), "| err:", await pg.evaluate("() => MACRO.err"))
        print("sample:", await pg.evaluate("() => { const r = MACRO.by.XAUUSDT; const p = coinPlay(r); return `${r.name} ${fmtPrice(r.price)} ${r.rating} 1H ${r.s1h.state} 4H ${r.s4h.state} D ${r.s1d.state} RSI ${r.rsi.h1} | play: ${p.short} | stance: ${p.stance} | day ${r.dayScore} | mom ${r.mom.score}`; }"))
        print("read chips:", await pg.evaluate("() => document.getElementById('macroRead').innerText.replace(/\\s+/g, ' ')"))
        print("group headers:", await pg.evaluate("() => [...document.querySelectorAll('#macroBody .board-head')].map(h => h.innerText.replace(/\\s+/g, ' ')).join(' | ')"))
        print("badge:", await pg.evaluate("() => { navBadges(); return document.getElementById('nb-macro').textContent; }"), "| meta:", await pg.evaluate("() => document.getElementById('macroMeta').textContent"))
        print("session clocks: US", await pg.evaluate("() => [Date.UTC(2026,9,7,15,0), Date.UTC(2026,9,7,22,0), Date.UTC(2026,9,10,15,0), Date.UTC(2026,11,7,15,0)].map(t => usSession(t).label).join(' / ')"),
              "| CME", await pg.evaluate("() => [Date.UTC(2026,9,7,15,0), Date.UTC(2026,9,7,21,30), Date.UTC(2026,9,10,15,0), Date.UTC(2026,9,11,23,0)].map(t => cmeSession(t).label).join(' / ')"))
        print("tv link:", await pg.evaluate("() => tvLink('XAUUSDT') + ' | ' + tvLink('SPYUSDT')"))
        await pg.screenshot(path=f"{OUT}/macro.png")
        # popup
        await pg.click('#macroBody .row[data-s="XAUUSDT"]'); await asyncio.sleep(2)
        print("popup:", await pg.evaluate("() => ({ open: document.getElementById('dlg').open, head: document.querySelector('.dhead h3').innerText.replace(/\\s+/g,' '), canvases: document.querySelectorAll('#dChartHost canvas').length, tabs: [...document.querySelectorAll('.dtabs .tab')].map(t => t.innerText).join(','), chartSym: CHDLG.on && CH.sym })"))
        await pg.click('.dtabs [data-pane="why"]'); await asyncio.sleep(1)
        print("why:", await pg.evaluate("() => document.getElementById('drv').innerText.slice(0, 160).replace(/\\s+/g,' ')"), "| links:", await pg.evaluate("() => [...document.querySelectorAll('.dpane[data-pane=why] .links a, .dpane[data-pane=why] .links button')].map(a => a.innerText).join(',')"))
        await pg.click('.dtabs [data-pane="score"]'); await asyncio.sleep(0.3)
        print("score rows:", await pg.evaluate("() => [...document.querySelectorAll('.dpane[data-pane=score] .kv > span:not([hidden]):nth-child(odd)')].map(s => s.innerText).join(', ')"))
        await pg.screenshot(path=f"{OUT}/macro_popup.png")
        await pg.keyboard.press("Escape")
        # live price polling path
        await pg.evaluate("() => { MACRO.at = Date.now(); }"); await asyncio.sleep(11)
        print("polled price cell:", await pg.evaluate("() => document.querySelector('[data-mp=XAUUSDT]').textContent"))
        await pg.click("#copyBtn"); await asyncio.sleep(0.2)
        print("export:", await pg.evaluate("() => claudeText().split('\\n').find(l => l.startsWith('Forex, gold')).slice(0, 200)"))
        await pg.set_viewport_size({"width": 390, "height": 844}); await asyncio.sleep(0.5)
        print("mobile overflow:", await pg.evaluate("() => document.documentElement.scrollWidth - innerWidth"))
        await pg.screenshot(path=f"{OUT}/macro_mobile.png")
        print("CSP:", csp or "none", "| errors:", errs or "none")
        await b.close()
asyncio.run(main())
