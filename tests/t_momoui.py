import asyncio, json, sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1440, "height": 950}, color_scheme="dark", permissions=["notifications", "clipboard-read", "clipboard-write"]); await setup(ctx)
        pg = await ctx.new_page(); errs, csp = [], []
        pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: "Content Security Policy" in m.text and csp.append(m.text[:140]))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        print("specials:", await pg.evaluate("() => ['LONGXIAUSDT','COOLXUSDT','RUNXUSDT'].map(s => { const r = bySym[s]; return s + ': ' + (r && r.momo ? r.momo.dir + ' ' + r.momo.stage + (r.momo.stretched ? ' (stretched)' : '') + ' RSI ' + r.rsi.h1 + ' 4H ' + r.rsi.h4 + (r.momo.volx ? ' vol×' + r.momo.volx : '') : 'none') + ' | wicky ' + (r && r.wicky); }).join('\\n   ')"))
        print("Ignition on LONGXIA:", await pg.evaluate("() => { const m = (bySym.LONGXIAUSDT.models || []).find(x => x.model === 'Ignite'); return m ? m.dir + ' · ' + m.state + ' · trig ' + m.trig + ' · E ' + fmtPrice(m.entry) + ' S ' + fmtPrice(m.stop) + ' 2R ' + fmtPrice(m.t2) : 'none'; }"))
        board = await pg.evaluate("() => { const R = momoRows(); return Object.fromEntries(['momentum','awaiting','breakout'].map(k => [k, R[k].map(x => coin(x.r.symbol) + (x.m.stretched ? '*' : '') + ' ' + x.s)])); }")
        print("board:", json.dumps(board))
        print("alert fired:", await pg.evaluate("() => NC.length ? coin(NC[0].sym) + ' ' + NC[0].title + ' (' + NC.length + ' in the bell)' : 'none'"), "| seen:", await pg.evaluate("() => Object.keys(JSON.parse(localStorage.getItem('altscan-momo-seen') || '{}'))"))
        await pg.evaluate("() => renderMomentum()"); await asyncio.sleep(0.3)
        print("no repeat alert on re-render:", await pg.evaluate("() => Object.keys(JSON.parse(localStorage.getItem('altscan-momo-seen') || '{}')).length"))
        await pg.select_option("#dirF", "Short"); await asyncio.sleep(0.4)
        print("shorts only:", await pg.evaluate("() => { const R = momoRows(); return [...new Set(['momentum','awaiting','breakout'].flatMap(k => R[k].map(x => x.m.dir)))].join(',') || 'empty'; }"))
        await pg.select_option("#dirF", "Both"); await asyncio.sleep(0.3)
        for v in ["Breaking Out (MA + RSI)", "Awaiting Momentum"]:
            await pg.evaluate("() => goPage('screener')")
            chip = await pg.evaluate(f"() => (document.querySelector('.qchip[data-v=\"{v}\"] span') || {{}}).textContent")
            await pg.click(f'.qchip[data-v="{v}"]'); await asyncio.sleep(0.3)
            print(f"view {v}: chip {chip}, table {await pg.evaluate('() => document.querySelectorAll(\"#tbody tr[data-s]\").length')}")
        await pg.evaluate("() => openDetail('LONGXIAUSDT')"); await asyncio.sleep(1.5)
        print("panel:", await pg.evaluate("() => [...document.querySelectorAll('.dpane[data-pane=score] .kv span')].find(s => s.textContent === 'Momentum Stage').nextElementSibling.innerText.replace(/\\n/g, ' ')"))
        print("play:", await pg.evaluate("() => document.querySelector('.dright .play .phead').innerText"))
        await pg.keyboard.press("Escape")
        await pg.click("#copyBtn"); await asyncio.sleep(0.2)
        print("export:", [l for l in (await pg.evaluate("() => navigator.clipboard.readText()")).split("\n") if l.startswith("Momentum board")][0][:200])
        print("guide + playbook fit:", await pg.evaluate("() => !!MODELS.Ignite + ' · ' + data.env.label + ' → ' + data.env.fit.Ignite"), "| bots include it:", await pg.evaluate("() => BOT_STRATS().includes('Ignite')"))
        await pg.evaluate("() => goPage('momentum')"); await asyncio.sleep(0.3); await pg.screenshot(path="momo_card.png")
        print("CSP:", csp or "none", "| errors:", errs or "none")
        await b.close()
asyncio.run(main())
