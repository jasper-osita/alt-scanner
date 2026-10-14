import asyncio, sys, time
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
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); t0 = time.time(); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        print(f"scan {time.time() - t0:.0f}s |", await q("() => data.analysed + ' coins'"))
        print("OB on coins:", await q("() => { const all = data.all.flatMap(r => (r.models || []).filter(m => m.model === 'OB').map(m => ({ s: coin(r.symbol), st: m.state, d: m.dir, p: m.poi, c: m.checks.filter(c => c[1]).length }))); const by = {}; all.forEach(x => by[x.st.replace(/Swept the .*,/, 'Swept…,')] = (by[x.st.replace(/Swept the .*,/, 'Swept…,')] || 0) + 1); return JSON.stringify(by) + ' | e.g. ' + all.slice(0, 4).map(x => `${x.s} ${x.d} ${x.st} (${x.p}, ${x.c}/8)`).join('; '); }"))
        print("POIs used:", await q("() => [...new Set(data.all.flatMap(r => (r.models || []).filter(m => m.model === 'OB').map(m => m.poi.replace(/(Asia|London|New York) /, 'Session '))))].join(', ')"))
        print("playbook fit:", await q("() => data.env.label + ' → OB ' + data.env.fit.OB"), "| guide has OB:", await q("() => !!MODELS.OB && MODEL_KEYS[0]"), "| bots include OB:", await q("() => BOT_STRATS().includes('OB')"))
        await q("() => goPage('screener')")
        await pg.click('.qchip[data-v="OB Entries (limit at the OB)"]'); await asyncio.sleep(0.4)
        print("quick view:", await q("() => document.querySelector('.qchip[data-v=\"OB Entries (limit at the OB)\"]').innerText.replace(/\\s+/g,' ') + ' | table rows ' + document.querySelectorAll('#tbody tr').length + ' | tab ' + tab"))
        sym = await q("() => (data.all.find(r => (r.models || []).some(m => m.model === 'OB' && m.trig)) || data.all.find(r => (r.models || []).some(m => m.model === 'OB')) || {}).symbol")
        if sym:
            await q(f"() => openDetail('{sym}')"); await asyncio.sleep(1.5)
            await pg.click('.dtabs [data-pane="setups"]'); await asyncio.sleep(0.3)
            print("popup", sym, "→", await q("() => { const el = [...document.querySelectorAll('.dpane[data-pane=setups] .setup')].find(x => x.innerText.includes('OB')); return el ? el.innerText.replace(/\\n+/g, ' | ').slice(0, 420) : 'no OB block'; }"))
            print("chart opened on:", await q("() => LIVE.chart && LIVE.chart.tf"), "| play:", await q(f"() => coinPlay(bySym['{sym}']).head"))
            await pg.screenshot(path=f"{OUT}/ob_popup.png")
            await pg.keyboard.press("Escape")
        await q("() => goPage('guide')"); await asyncio.sleep(0.3)
        await q("() => { guideSel = 'OB'; renderGuide(); }"); await asyncio.sleep(0.3)
        print("guide:", await q("() => document.getElementById('guide').innerText.split('\\n').filter(Boolean).slice(0, 3).join(' | ').slice(0, 200)"))
        print("CSP:", csp or "none", "| errors:", errs or "none")
        await b.close()
asyncio.run(main())
