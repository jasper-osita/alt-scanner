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
        print("1) btc dir1/dir4:", await q("() => data.btc.dir1 + '/' + data.btc.dir4"), "| NBB states:", await q("() => { const c = {}; data.all.forEach(r => (r.models || []).filter(m => m.model === 'NBB').forEach(m => c[m.state] = (c[m.state] || 0) + 1)); return JSON.stringify(c); }"))
        print("   graded:", await q("() => { const ms = data.all.flatMap(r => (r.models || []).filter(m => m.model === 'NBB')); const g = ms.filter(m => m.grade); return g.length + ' of ' + ms.length + ' graded, A-grade ' + g.filter(m => m.grade.pass).length + ', missed have grade: ' + ms.filter(m => m.missed && m.grade).length; }"))
        print("   missed never in liveModels:", await q("() => data.all.every(r => liveModels(r).every(m => !m.missed))"), "| missed levels null:", await q("() => data.all.flatMap(r => r.models || []).filter(m => m.missed).every(m => m.entry == null && m.stop == null)"))
        print("   sample missed note:", await q("() => { const m = data.all.flatMap(r => r.models || []).find(m => m.missed); return m ? m.dir + ' · ' + m.note : 'none'; }"))
        print("2) session note:", await q("() => document.getElementById('sessNote').innerText"), "| window segs:", await q("() => [...document.querySelectorAll('.seg.window')].map(s => s.title).join(', ')"))
        print("   NY session models:", await q("() => SESSION_DEFS.find(d => d.key === 'NY AM').models.join(',')"))
        # popup for a coin with a graded NBB
        sym = await q("() => { const r = data.all.find(r => (r.models || []).some(m => m.grade && m.trig)) || data.all.find(r => (r.models || []).some(m => m.grade)); return r && r.symbol; }")
        await q(f"() => openDetail({sym!r})"); await asyncio.sleep(1.2); await pg.click('.dtabs [data-pane="setups"]'); await asyncio.sleep(0.3)
        print("3) setups tab", sym, ":", await q("() => { const s = [...document.querySelectorAll('.dpane[data-pane=setups] .setup')].find(x => x.innerText.includes('A-grade checks')); return s ? s.innerText.replace(/\\s+/g, ' ').slice(0, 420) : 'no grade block'; }"))
        await pg.screenshot(path=f"{OUT}/nbb_grade.png")
        await pg.keyboard.press("Escape"); await asyncio.sleep(0.3)
        # A-grade toggle without any edge rules
        await q("() => goPage('playbook')"); await asyncio.sleep(0.3)
        print("4) playbook toggle:", await q("() => { const x = document.getElementById('pbAGrade'); return x ? x.parentElement.innerText : 'missing'; }"))
        before = await q("() => suggestions(data.env).map(x => coin(x.r.symbol) + ' ' + x.m.model).join(', ')")
        await pg.check("#pbAGrade"); await asyncio.sleep(0.4)
        after = await q("() => suggestions(data.env).map(x => coin(x.r.symbol) + ' ' + x.m.model + (x.m.grade ? ' ' + x.m.grade.n + '/4' : '')).join(', ')")
        print("   picks:", before or "none", "→", after or "none", "| only A-grade NBB left:", await q("() => data.all.flatMap(r => liveModels(r)).every(m => m.model === 'NBB' && m.grade.pass)"))
        await pg.uncheck("#pbAGrade"); await asyncio.sleep(0.2)
        # forced checklist: build a fake NBB on a coin and grade it
        print("5) grade unit:", await q("""() => { const T = Date.UTC(2026, 9, 8, 6, 0);   // 2:00 PM PHT
          const m = { model: 'NBB', dir: 'Long', trig: true, withDaily: null, baseLen: 9 };
          const m2 = { ...m, trendAge: 30 }; const a = nbbGrade(m2, 'Long', 'Long', T), b = nbbGrade({ ...m2, trendAge: 120 }, 'Long', 'Long', T), c = nbbGrade(m2, 'Short', 'Long', T), d = nbbGrade(m2, 'Long', 'Long', Date.UTC(2026, 9, 8, 14, 0)), e = nbbGrade({ ...m2, withDaily: true, baseLen: 20 }, 'Long', 'Long', T);
          return [a, b, c, d, e].map(g => g.pass + ' ' + g.n + '/' + g.of).join(' | ') + ' || ' + d.items[2][2]; }"""))
        # backtest
        await q("() => goPage('backtest')"); await pg.select_option("#btCoins", "20"); await pg.select_option("#btDays", "30")
        t0 = time.time(); await pg.click("#btRun")
        for _ in range(500):
            if await q("() => !btRunning && !!BT"): break
            await asyncio.sleep(0.5)
        print(f"6) backtest {time.time() - t0:.0f}s:", await q("() => { const n = BT.trades.filter(t => t.model === 'NBB'); return n.length + ' NBB trades, graded ' + n.filter(t => t.ag != null).length + ', A-grade ' + n.filter(t => t.ag).length; }"))
        print("   rows:", await q("() => [...document.querySelectorAll('#backtest table.sct tbody tr')].filter(tr => /NBB|A-grade|the rest/.test(tr.cells[0].innerText)).map(tr => [...tr.cells].slice(0, 7).map(c => c.innerText).join(' ')).join(' || ')"))
        await pg.evaluate("() => document.querySelector('#backtest table.sct').scrollIntoView()"); await asyncio.sleep(0.2); await pg.screenshot(path=f"{OUT}/nbb_bt.png")
        print("7) edge toggle enabled with no rules:", await q("() => !document.getElementById('edgeAOnly').disabled"))
        await q("() => goPage('guide')"); await q("() => { guideSel = 'NBB'; renderGuide(); }"); await asyncio.sleep(0.2)
        print("8) guide:", await q("() => document.querySelector('.mguide') ? [...document.querySelectorAll('.mguide li')].map(l => l.innerText).filter(t => /Missed|A-grade/.test(t)).join(' || ').slice(0, 300) : 'no guide'"))
        print("CSP:", csp or "none", "| errors:", errs or "none")
        await b.close()
asyncio.run(main())

