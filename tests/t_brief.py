import asyncio, sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OUT = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "out")
# Market brief: clicking a market on Fundamentals opens a floating box (page dimmed behind) instead of the chart.
async def main():
    serve(); FUND_SRV["key"] = True        # the relay's own FRED key: rates and the Fed lines fill in
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1440, "height": 950}, color_scheme="dark")
        await ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin="http://localhost:8765")
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
        await q("() => goPage('fund')")
        await wait("() => FUND.ust && FUND.cot && FUND.news && !FUND.busy && document.querySelector('#fundBody .fcurve')", 40); await wait("() => MACRO.rows.length > 5", 60); await q("() => fundRender()")
        print("1) clickable:", await q("() => ['.fworld [data-fmk]', '#fundRead [data-fmk]', '.fcot [data-fmk]'].map(s => document.querySelectorAll(s).length).join(' / ')"), "| feeds:", await q("() => [...new Set(FUND.news.items.map(x => x.src))].join(', ')"))
        await q("() => document.querySelector('.fworld tr[data-fmk=\"Gold\"]').click()"); await asyncio.sleep(0.4)
        print("2) open, still on Fundamentals:", await q("() => [document.getElementById('fbDlg').open, page, FB.k, getComputedStyle(document.getElementById('fbDlg'), '::backdrop').backgroundColor]"))
        print("   head:", await q("() => document.getElementById('fbHead').innerText.replace(/\\s+/g, ' ')"))
        print("   lean:", await q("() => document.querySelector('.fblean').innerText.replace(/\\s+/g, ' ')"))
        print("   drivers:", await q("() => [...document.querySelectorAll('.fbcols > div:first-child > .fbs:first-child .ftbl tr')].map(tr => tr.innerText.replace(/\\s+/g, ' ')).join(' | ')"))
        await wait("() => FB.lv.Gold && (FB.lv.Gold.k || FB.lv.Gold.err)", 30); await q("() => fbRender()")
        print("3) levels:", await q("() => (document.querySelector('.fblv') || document.querySelector('.fblv1')).innerText.replace(/\\s+/g, ' ')"))
        print("4) sections:", await q("() => [...document.querySelectorAll('#fbBody .fbsh')].map(x => x.firstChild.textContent.trim()).join(' | ')"))
        print("   Fed expects:", await q("() => { const s = [...document.querySelectorAll('#fbBody .fbs')].find(x => /expects from the Fed/.test(x.textContent)); return s ? s.innerText.replace(/\\s+/g, ' ') : 'none'; }"))
        print("   coming up:", await q("() => { const s = [...document.querySelectorAll('#fbBody .fbs')].find(x => /Coming up/.test(x.textContent)); return s.innerText.replace(/\\s+/g, ' ').slice(0, 220); }"))
        print("   headlines:", await q("() => [document.querySelectorAll('.fbnews a').length, document.querySelectorAll('.fbnews .fbnew').length, (document.querySelector('.fbnews a') || {}).innerText]"))
        print("   chart + window:", await q("() => [...document.querySelectorAll('#fbBody .fbs')].slice(-2).map(x => x.innerText.replace(/\\s+/g, ' ')).join(' || ')"))
        print("   top strip:", await q("() => [...document.querySelectorAll('.fbal')].map(x => x.className.split(' ')[1] + ': ' + x.innerText.slice(0, 90)).join(' | ') || 'none'"))
        await q("() => { document.getElementById('fbHead')._h = null; fbRender(); }")            # a price tick redraws the header (and the focused button with it)
        print("   focus after a redraw:", await q("() => document.getElementById('fbDlg').contains(document.activeElement)"))
        await pg.keyboard.press("ArrowRight"); await asyncio.sleep(0.2); k1 = await q("() => FB.k")
        await pg.keyboard.press("ArrowLeft"); await asyncio.sleep(0.2)
        print("5) arrows:", k1, "→ back to", await q("() => FB.k"), "| lean Silver drivers:", await q("() => fbDrivers(fbMk('Silver'), fundSignals()).map(x => x.name + (x.v > 0 ? '▲' : x.v < 0 ? '▼' : '–')).join(', ')"))
        await pg.keyboard.press("Escape"); await asyncio.sleep(0.2)
        print("6) Esc closes:", await q("() => [document.getElementById('fbDlg').open, FB.k, FB.t]"))
        await q("() => document.querySelector('#fundRead [data-fmk=\"US dollar\"]').click()"); await asyncio.sleep(0.3)
        print("7) card → brief:", await q("() => [FB.k, document.getElementById('fbTitle').textContent, document.querySelector('.fblean .fverd').textContent]"))
        await pg.mouse.click(8, 8); await asyncio.sleep(0.2)
        print("   click outside closes:", await q("() => !document.getElementById('fbDlg').open"))
        await q("() => document.querySelector('.fcot tr[data-fmk=\"EUR/USD\"]').click()"); await asyncio.sleep(0.3)
        print("8) positioning row → EUR/USD:", await q("() => FB.k"), "| sections:", await q("() => [...document.querySelectorAll('#fbBody .fbsh')].map(x => x.firstChild.textContent.trim()).join(' | ')"))
        print("   pair drivers:", await q("() => fbDrivers(fbMk('EUR/USD'), fundSignals()).map(x => x.name + (x.v > 0 ? '▲' : x.v < 0 ? '▼' : '–')).join(', ')"), "| USD/CAD risk:", await q("() => fbDrivers(fbMk('USD/CAD'), fundSignals()).filter(x => /Risk/.test(x.name)).map(x => x.v).join()"))
        print("   positioning:", await q("() => { const s = [...document.querySelectorAll('#fbBody .fbs')].find(x => /Positioning/.test(x.textContent)); return s ? s.innerText.replace(/\\s+/g, ' ') : 'none'; }"))
        print("   strength (fake rows):", await q("""() => { const keep = MACRO.rows; MACRO.rows = [['CT:EURUSD', 0.4, 0.01], ['CT:GBPUSD', 0.2, 0.004], ['CT:USDJPY', -0.5, -0.012], ['CT:EURJPY', 0.9, 0.02], ['CT:AUDUSD', -0.1, 0], ['CT:USDCAD', 0.1, 0.003]].map(([symbol, chg24h, ret7]) => ({ symbol, chg24h, ret7 }));
            const r = fbStrength().sort((a, b) => b.d - a.d).map(x => x.c + ' ' + x.d.toFixed(2)).join(', '); MACRO.rows = keep; return r; }"""))
        await pg.keyboard.press("Escape")
        # sudden news: a live jump, an event due and one just out, a fresh headline
        await q("() => fbOpen('Gold')"); await asyncio.sleep(0.2)
        await q("""() => { const m = fbMk('Gold'), p = fbQuote(m).price, now = Date.now(); FBM.Gold = Array.from({ length: 30 }, (_, i) => [now - 170e3 + i * 5e3, p * 0.97 + i * 1e-6]); delete FB.shock.Gold; fbSample(); }""")
        print("9) sudden move:", await q("() => JSON.stringify(FB.shock.Gold && { pct: +FB.shock.Gold.pct.toFixed(2), mins: FB.shock.Gold.mins })"), "| alert:", await q("() => NC[0] && NC[0].kind + ' ' + NC[0].title"))
        print("   strip:", await q("() => (document.querySelector('.fbal.shock') || {}).innerText"))
        await q("() => { fbSample(); }"); n_before = await q("() => NC.filter(x => /Gold (jumped|dropped)/.test(x.title)).length")
        print("   no repeat alert:", n_before)
        print("   quiet market, no shock:", await q("() => { const now = Date.now(); return fbShockOf(fbMk('EUR/USD'), Array.from({ length: 30 }, (_, i) => [now - 170e3 + i * 5e3, 1.1 + i * 1e-6]), now); }"), "| scan jump, not live:", await q("() => { const now = Date.now(); return fbShockOf(fbMk('EUR/USD'), [[now - 200e3, 1.10], [now - 2e3, 1.12]], now); }"))
        await q("""() => { CAL.items.push({ id: 'T|soon', at: Date.now() + 8 * 60e3, ccy: 'USD', title: 'Test CPI m/m', impact: 'High', type: 'Inflation', forecast: '0.3%', previous: '0.4%' },
            { id: 'T|out', at: Date.now() - 5 * 60e3, ccy: 'USD', title: 'Test jobs report', impact: 'High', type: 'Employment' });
            FUND.news.items.unshift({ title: 'BREAKING: Gold spikes on a test headline', link: 'https://example.com/x', t: Date.now() - 60e3, src: 'FinancialJuice', tag: 'GOLD' }); fbRender(); }""")
        print("10) strip:", await q("() => [...document.querySelectorAll('.fbal')].map(x => x.className.split(' ')[1] + ': ' + x.innerText.replace(/\\s+/g, ' ').slice(0, 110)).join(' | ')"))
        await q("() => document.getElementById('fbCopy').click()"); await asyncio.sleep(0.3)
        cb = await q("() => navigator.clipboard.readText()")
        print("11) copy brief:", len(cb.splitlines()), "lines |", cb.splitlines()[0][:80], "|", cb.splitlines()[1][:60])
        print("12) refreshes while open:", await q("() => !!FB.t"))
        await q("() => document.getElementById('fbChart').click()"); await asyncio.sleep(1)
        print("13) Open chart:", await q("() => [page, CH.sym, document.getElementById('fbDlg').open]"))
        # headline alerts on any page (we're on Charts now)
        await q("""() => { const t = Date.now(); FUND.news.items.unshift({ title: 'Gold plunges as Powell signals more hikes', link: 'https://example.com/g', t: t - 90e3, src: 'FinancialJuice', tag: 'GOLD' },
            { title: 'Gold edges up in quiet trade', link: 'https://example.com/q', t: t - 60e3, src: 'FXStreet', tag: 'GOLD' }, { title: 'US CPI hotter than expected at 0.5%', link: 'https://example.com/c', t: t - 30e3, src: 'FXStreet', tag: 'MACRO' },
            { title: 'Oil soars on supply fears', link: 'https://example.com/o', t: t - 30e3, src: 'FXStreet', tag: 'OIL' }); window.__n0 = NC.length; naCheck(); }""")
        print("15) headline alerts:", await q("() => NC.slice(0, NC.length - window.__n0).map(n => n.title + ' [' + n.action + ' → ' + n.mk + ']').join(' | ')"))
        print("    again (no repeats):", await q("() => { const n = NC.length; naCheck(); return NC.length - n; }"), "| telegram text:", await q("() => tgText(NC[0]).replace(/\\n/g, ' / ').slice(0, 150)"))
        await q("() => ncGo(NC[0].id)"); await asyncio.sleep(0.6)
        print("    Open brief:", await q("() => [page, FB.k, document.getElementById('fbDlg').open]"))
        # the release read: prices 2 minutes after a high-impact release
        await q("""() => { const now = Date.now(), x = { id: 'T|cpi', at: now - 150e3, ccy: 'USD', title: 'Test CPI m/m', impact: 'High', type: 'Inflation' }; CAL.items.push(x);
            const p = rxPx(); RX_PRE[x.id] = { ...p, gold: p.gold && p.gold * 1.006, nas: p.nas && p.nas * 1.005, eu: p.eu && p.eu * 1.003 }; window.__n1 = NC.length; rxTick(now); fbRender(); }""")
        print("16) release read:", await q("() => JSON.stringify({ read: RX_LIVE['T|cpi'].read, gold: +RX_LIVE['T|cpi'].mv.gold.toFixed(2), nas: +RX_LIVE['T|cpi'].mv.nas.toFixed(2) })"), "| alert:", await q("() => NC.length > window.__n1 ? NC[0].title + ' · ' + NC[0].detail : 'none'"))
        print("    strip:", await q("() => [...document.querySelectorAll('.fbal.out')].map(x => x.innerText).find(t => /Test CPI/.test(t))"))
        await q("() => { rxTick(Date.now() + 7.6 * 60e3); CAL.items.push({ id: 'T|cpi2', at: Date.now() + 20 * 60e3, ccy: 'USD', title: 'Test CPI m/m', impact: 'High', type: 'Inflation' }); fbRender(); }")
        print("    kept:", await q("() => RX.length && RX[0].title + ' ' + RX[0].read10"), "| last time:", await q("() => { const r = [...document.querySelectorAll('#fbBody .ftbl tr')].find(tr => /Test CPI/.test(tr.innerText) && /last time/.test(tr.innerText)); return r ? r.innerText.replace(/\\s+/g, ' ') : 'none'; }"))
        # the US open levels on the Nasdaq brief
        await q("() => fbOpen('Nasdaq 100')"); await wait("() => FB.lv['Nasdaq 100'] && (FB.lv['Nasdaq 100'].k15 || FB.lv['Nasdaq 100'].err)", 30); await q("() => fbRender()")
        print("17) Nasdaq levels:", await q("() => (document.querySelector('.fblv') || document.querySelector('.fblv1')).innerText.replace(/\\s+/g, ' ')"))
        print("    US open helper:", await q("() => { const u = fbLvCalc(fbMk('Nasdaq 100'), fbQuote(fbMk('Nasdaq 100')).price).us; return JSON.stringify({ pc: u.pc, on: !!u.on, open: u.open, openPHT: phtHM(u.openAt), or: !!u.or }); }"))
        await pg.keyboard.press("Escape")
        await pg.set_viewport_size({"width": 390, "height": 844}); await q("() => goPage('fund')"); await asyncio.sleep(0.5); await q("() => fbOpen('Nasdaq 100')"); await asyncio.sleep(0.4)
        print("14) phone:", await q("() => { const d = document.getElementById('fbDlg'), r = d.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height), d.scrollWidth <= d.clientWidth + 1, document.getElementById('fbBody').scrollWidth <= document.getElementById('fbBody').clientWidth + 1, getComputedStyle(document.querySelector('.fbcols')).gridTemplateColumns.split(' ').length]; }"))
        await pg.screenshot(path=f"{OUT}/brief_phone.png")
        await pg.set_viewport_size({"width": 1440, "height": 950}); await asyncio.sleep(0.3); await q("() => fbOpen('Gold')"); await asyncio.sleep(0.4)
        await pg.screenshot(path=f"{OUT}/brief.png")
        print("errors:", errs[:5] if errs else "none")
        await b.close()
asyncio.run(main())
