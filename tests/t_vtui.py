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
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        print("1) V-Trade states:", await q("() => { const c = {}; data.all.forEach(r => (r.models || []).filter(m => m.model === 'V-Trade').forEach(m => c[m.state] = (c[m.state] || 0) + 1)); return JSON.stringify(c); }"),
              "| graded:", await q("() => { const ms = data.all.flatMap(r => (r.models || []).filter(m => m.model === 'V-Trade')); return ms.filter(m => m.grade).length + '/' + ms.length + ', A ' + ms.filter(m => m.grade && m.grade.pass).length + ', missed graded ' + ms.filter(m => m.missed && m.grade).length; }"))
        print("   unit:", await q("""() => { const m = { model: 'V-Trade', dir: 'Long', trig: true, trend1h: true };
          return [vtGrade(m, 'Long', 'Long'), vtGrade(m, 'Long', 'Short'), vtGrade({ ...m, trend1h: false }, 'Long', 'Long'), vtGrade({ ...m, missed: true }, 'Long', 'Long')].map(g => g ? g.pass + ' ' + g.n + '/' + g.of : 'null').join(' | '); }"""))
        sym = await q("() => { const r = data.all[0]; r.models = [...(r.models || []), { model: 'V-Trade', state: 'Star at the OEZ', trig: true, dir: 'Long', tf: '1H', entry: r.price, stop: r.price * 0.98, t2: r.price * 1.04, t3: r.price * 1.06, trend1h: true, note: 'With-trend re-entry off the OEZ.' }]; gradeModels(r, { dir1: 'Long', dir4: 'Short' }); return r.symbol; }")
        if sym:
            await q(f"() => openDetail({sym!r})"); await asyncio.sleep(1.2); await pg.click('.dtabs [data-pane="setups"]'); await asyncio.sleep(0.3)
            print("2) setups", sym, ":", await q("() => { const s = [...document.querySelectorAll('.dpane[data-pane=setups] .setup')].find(x => x.innerText.includes('V-Trade')); return s ? s.innerText.replace(/\\s+/g, ' ').slice(0, 520) : 'none'; }"))
            await pg.screenshot(path=f"{OUT}/vt_grade.png"); await pg.keyboard.press("Escape"); await asyncio.sleep(0.3)
        await q("() => goPage('guide')"); await q("() => { guideSel = 'V-Trade'; renderGuide(); }"); await asyncio.sleep(0.2)
        print("4) guide:", await q("() => [...document.querySelectorAll('.mguide li')].map(l => l.innerText).filter(t => /Missed V|A-grade/.test(t)).join(' || ').slice(0, 300)"))
        print("CSP:", csp or "none", "| errors:", errs or "none")
        await b.close()
asyncio.run(main())
