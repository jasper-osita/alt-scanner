import asyncio, sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OUT = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "out")
# Fundamentals page (terminal style): strip, world markets, central banks (FRED key), yield curve (Treasury), positioning (CFTC), headlines (RSS), calendar.
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1500, "height": 1000}, color_scheme="dark")
        await setup(ctx); await setup_mexc(ctx); await setup_extra(ctx); await setup_fund(ctx)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        async def wait(js, secs=30):
            for _ in range(secs * 4):
                if await q(js): return True
                await asyncio.sleep(0.25)
            return False
        print("1) in the menu:", await q("() => [...document.querySelectorAll('#navList [data-go], #navList button, #navList a')].map(x => x.textContent.trim()).filter(t => /Fundamentals/.test(t)).length > 0 || document.getElementById('navList').innerText.includes('Fundamentals')"))
        await q("() => goPage('fund')")
        await wait("() => FUND.ust && FUND.cot && FUND.news && !FUND.busy && document.querySelector('#fundBody .fcurve')", 40); await wait("() => MACRO.rows.length > 5", 60); await q("() => fundRender()")
        print("2) panels:", await q("() => [...document.querySelectorAll('#fundBody .fph')].map(x => x.firstChild.textContent.trim()).join(' | ')"))
        print("3) strip:", await q("() => document.getElementById('fundStrip').innerText.replace(/\\s+/g, ' ')"))
        print("4) world:", await q("() => [document.querySelectorAll('.fworld tr[data-fsym]').length, document.querySelector('.fworld').innerText.includes('Gold'), document.querySelector('.fworld').innerText.includes('Fear')]"))
        print("5) curve:", await q("() => [document.querySelectorAll('.fcurve polyline').length, document.querySelector('.fkv').innerText.replace(/\\s+/g, ' ')]"))
        print("6) positioning:", await q("() => [document.querySelectorAll('.fcot .ftbl tr').length - 1, document.querySelector('.fcot .ftbl tr:nth-child(2)').innerText.replace(/\\s+/g, ' ')]"))
        print("7) headlines:", await q("() => [document.querySelectorAll('.fnews .fni').length, document.querySelector('.fnews .fni').innerText.replace(/\\s+/g, ' '), document.querySelector('.fnews .fni').target, document.querySelector('.fnews .fni').rel]"))
        await q("() => document.querySelector('[data-ftag=\"GOLD\"]').click()"); await asyncio.sleep(0.2)
        print("8) GOLD only:", await q("() => [...document.querySelectorAll('.fnews .fni')].every(a => a.innerText.includes('GOLD')) && document.querySelectorAll('.fnews .fni').length"))
        print("9) no key yet:", await q("() => [!!document.getElementById('fredKey'), document.querySelector('.fcb .ftbl tr:nth-child(2)').innerText.replace(/\\s+/g, ' ')]"))
        await pg.fill("#fredKey", "bad0000000000000000000000000000k"); await q("() => document.getElementById('fredSave').click()"); await wait("() => FUND.err.fred", 15); await q("() => fundRender()")
        print("10) wrong key:", await q("() => document.querySelector('.fcb .fkey').innerText.trim()"))
        await q("() => document.getElementById('fredClear').click()"); await asyncio.sleep(0.2)
        await pg.fill("#fredKey", "abcdef0123456789abcdef0123456789"); await q("() => document.getElementById('fredSave').click()"); await wait("() => FUND.fred && FUND.fred.s && !FUND.busy", 20); await q("() => fundRender()")
        print("11) rates:", await q("() => [...document.querySelectorAll('.fcb .ftbl tr')].slice(1, 4).map(tr => tr.innerText.replace(/\\s+/g, ' ')).join(' / ')"), "| key stored:", await q("() => localStorage.getItem('finder-fred').length"))
        print("12) US gauges:", await q("() => document.querySelector('.fkv').innerText.replace(/\\s+/g, ' ')"), "| VIX:", await q("() => document.querySelector('.fworld').innerText.match(/VIX[^\\n]*\\n?[^\\n]*/)[0].replace(/\\s+/g, ' ')"))
        FUND_SRV["key"] = True
        await q("() => { lsSet('finder-fred', ''); FUND.fred = {}; FUND.err.fred = null; }"); await q("() => fundLoad(true)"); await wait("() => FUND.fred && FUND.fred.s && FUND.fred.k === 'server' && !FUND.busy", 20); await q("() => fundRender()")
        print("11b) no key pasted, the server's own:", await q("() => [!!document.getElementById('fredKey'), document.querySelector('.fcb .ftbl tr:nth-child(2)').innerText.replace(/\\s+/g, ' ')]"),
              "| key sent from the page:", any("api_key=" in h for h in FUND_HITS[-3:]))
        print("13) calendar:", await q("() => document.querySelectorAll('.fnewsp .ftbl tr').length"))
        print("16) read:", await q("() => document.querySelector('#fundRead .fhead').innerText.replace(/\\s+/g, ' ')"))
        print("17) cards:", await q("() => [...document.querySelectorAll('#fundRead .fcard')].map(c => c.querySelector('.ft b').textContent + ' → ' + c.querySelector('.fverd').textContent + ' [' + [...c.querySelectorAll('.fwhy li')].map(li => li.innerText.replace(/\\s+/g, ' ')).join('; ') + ']').join(' || ')"))
        G = "() => { const c = [...document.querySelectorAll('#fundRead .fcard')].find(c => c.querySelector('.ft b').textContent === 'Gold'), tr = [...document.querySelectorAll('.fworld tr[data-fsym]')].find(t => t.children[0].textContent === 'Gold'); return [c.querySelector('.flp').textContent, tr.children[1].textContent]; }"
        before = await q(G)
        await q("() => { const r = fRow(['Gold']); r.price = r.price * 1.01; }"); await asyncio.sleep(1.3)
        print("18) live tick:", before, "→", await q(G), "| flashed:", await q("() => !!document.querySelector('#fundRead .flp.tick-up')"))
        el = await pg.query_selector(".fundcard"); await el.screenshot(path=f"{OUT}/fund.png")
        await q("() => document.querySelector('.fworld tr[data-fsym]').click()"); await asyncio.sleep(1)
        print("14) click a market → chart:", await q("() => page"))
        await pg.set_viewport_size({"width": 420, "height": 900}); await q("() => goPage('fund')"); await asyncio.sleep(1)
        print("15) phone width, no side scroll:", await q("() => document.documentElement.scrollWidth <= window.innerWidth + 1"))
        print("15b) too wide:", await q("() => [...document.querySelectorAll('.fundcard *')].filter(e => e.getBoundingClientRect().right > window.innerWidth + 1).slice(0, 6).map(e => e.tagName + '.' + e.className + ':' + Math.round(e.getBoundingClientRect().right))"))
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
