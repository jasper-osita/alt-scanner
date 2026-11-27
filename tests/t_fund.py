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
        await wait("() => FUND.bis && FUND.fy && FUND.fy.JP && !FUND.busy", 20); await q("() => fundRender()")
        ROW = "n => [...document.querySelectorAll('.fcb .ftbl tr')].find(tr => tr.children[0].innerText.startsWith(n))"
        print("19) BIS rates:", await q(f"() => ['BoE', 'BoJ', 'RBNZ', 'SNB'].map(n => {{ const tr = ({ROW})(n); return tr.innerText.replace(/\\s+/g, ' ') + ' {{' + tr.children[1].title + '}}'; }}).join(' / ')"))
        print("19b) vs Fed:", await q(f"() => [({ROW})('Fed').children[2].textContent, ({ROW})('ECB').children[2].textContent, ({ROW})('ECB').children[2].title]"))
        print("20) yield gaps:", await q("() => [...document.querySelectorAll('.fgaps tr')].map(tr => tr.innerText.replace(/\\s+/g, ' ')).join(' / ')"))
        print("20b) JGB history fetched:", sum("/proxy/rates/jgb-all" in h for h in FUND_HITS), "time(s) · rows kept:", await q("() => [FUND.fy.EU.length, FUND.fy.JP.length]"))
        print("21) FX cards:", await q("() => [...document.querySelectorAll('#fundRead .fcard')].filter(c => /EUR|JPY/.test(c.querySelector('.ft b').textContent)).map(c => c.querySelector('.ft b').textContent + ' → ' + c.querySelector('.fverd').textContent + ' [' + [...c.querySelectorAll('.fwhy li')].map(li => li.innerText.replace(/\\s+/g, ' ')).join('; ') + ']').join(' || ')"))
        print("21b) card order:", await q("() => [...document.querySelectorAll('#fundRead .fcard .ft b')].map(b => b.textContent).join(', ')"))
        print("22) parsers:", await q("""() => [JSON.stringify(jgbParse('Interest Rate\\nDate,1Y,2Y,10Y\\nR8.10.30,0.7,0.95,1.8\\n2026/10/29,0.7,-,1.79')),
          JSON.stringify(sdmxRows('FREQ,REF_AREA,TIME_PERIOD,OBS_VALUE\\nD,GB,2026-10-30,4\\nD,"KR: Korea, Republic of",2026-10-30,2.5').map(r => r.REF_AREA + '=' + r.OBS_VALUE))]"""))
        print("25) world, new rows:", await q("() => [...document.querySelectorAll('.fworld tr')].filter(tr => /Broad dollar|volatility|liquidity|^\\s*(VOLATILITY|CRYPTO)/i.test(tr.innerText)).map(tr => tr.innerText.replace(/\\s+/g, ' ').trim()).join(' / ')"))
        print("26) Fed cuts priced:", await q("() => { const e = [...document.querySelectorAll('.fkv span')].find(x => x.textContent === 'Fed cuts priced'); return e ? e.textContent + ': ' + e.nextElementSibling.innerText + ' {' + e.title.slice(0, 60) + '…}' : 'missing'; }"), "| raw:", await q("() => { const c = fundCuts(); return c && [c.n.toFixed(2), c.then != null && c.then.toFixed(2), c.eff]; }"))
        print("27) header + new card lines:", await q("() => document.querySelector('#fundRead .fhead').innerText.replace(/\\s+/g, ' ')"), "||", await q("() => [...document.querySelectorAll('#fundRead .fwhy li')].map(li => li.closest('.fcard').querySelector('.ft b').textContent + ': ' + li.innerText.replace(/\\s+/g, ' ').trim()).filter(t => /volatility|liquidity|CPI/i.test(t)).join(' / ')"))
        print("28) ratios:", await q("() => [...document.querySelectorAll('.fworld tr')].filter(tr => /÷|Gold in/.test(tr.innerText)).map(tr => tr.innerText.replace(/\\s+/g, ' ').trim()).join(' / ')"))
        print("29) positioning groups:", await q("() => [...document.querySelectorAll('.fcot .fgrp')].map(td => td.textContent + ' (' + (() => { let n = 0, tr = td.parentElement.nextElementSibling; while (tr && !tr.querySelector('.fgrp')) { n++; tr = tr.nextElementSibling; } return n; })() + ')').join(', ')"), "| new rows:", await q("() => [...document.querySelectorAll('.fcot tr')].filter(tr => /Platinum|Kiwi|Corn/.test(tr.innerText)).map(tr => tr.innerText.replace(/\\s+/g, ' ').trim()).join(' / ')"))
        print("30) gold card, dollar check:", await q("() => { const G = fGoldIn(), g = G.au; return 'gold 1W ' + (g.ret7 * 100).toFixed(2) + '%, in euros ' + (G.eur ? G.eur.w.toFixed(2) + '%' : 'n/a') + ' → ' + ([...document.querySelectorAll('#fundRead .fcard')].find(c => c.querySelector('.ft b').textContent === 'Gold').innerText.match(/Mostly the dollar[^\\n]*/) || ['no dollar note'])[0]; }"))
        print("31) card order:", await q("() => [...document.querySelectorAll('#fundRead .fcard .ft b')].map(b => b.textContent).join(', ')"), "| per row:", await q("() => getComputedStyle(document.querySelector('.fcards')).gridTemplateColumns.split(' ').length"))
        print("32) silver and oil cards:", await q("() => [...document.querySelectorAll('#fundRead .fcard')].filter(c => /Silver|Oil/.test(c.querySelector('.ft b').textContent)).map(c => c.querySelector('.ft b').textContent + ' → ' + c.querySelector('.fverd').textContent + ' [' + [...c.querySelectorAll('.fwhy li')].map(li => li.innerText.replace(/\\s+/g, ' ').trim()).join('; ') + ']').join(' || ')"))
        print("33a) mismatched feeds hidden:", await q("() => ![...document.querySelectorAll('.fworld tr')].some(tr => /Brent − WTI/.test(tr.innerText))"))
        await q("() => { const b = fRow(['Brent Crude Oil', 'UKOIL']), w = fRow(['WTI Crude Oil', 'USOIL']); if (b && w) { b.price = w.price + 4.2; b.chg24h = 1.0; b.ret7 = 0.03; } fundRender(); }")
        print("33) Brent − WTI:", await q("() => { const tr = [...document.querySelectorAll('.fworld tr')].find(tr => /Brent − WTI/.test(tr.innerText)); return tr ? tr.innerText.replace(/\\s+/g, ' ').trim() : 'not shown (Brent: ' + !!fRow(['Brent Crude Oil', 'UKOIL']) + ', WTI: ' + !!fRow(['WTI Crude Oil', 'USOIL']) + ')'; }"))
        print("34) seasonality without a broker:", await q("() => document.querySelector('.fseasp').innerText.replace(/\\s+/g, ' ').slice(0, 120)"))
        # stub the broker: 20 years of monthly gold candles stamped 22:00 on the last day of the month before (broker time); November up in 16 of 20 years
        print("35) seasonality, 20 years:", await q("""async () => {
          const bars = []; for (let y = 2006; y <= 2026; y++) for (let m = 0; m < 12; m++) { if (y === 2026 && m > 10) break;
            const t = Date.UTC(y, m, 1) - 2 * 3600e3, up = m === 10 ? (y % 5 !== 0) : m === 8 ? (y % 4 === 0) : ((y + m) % 2 === 0), o = 1000 + y; bars.push([t, o, o * (up ? 1.02 : 0.985)]); }
          localStorage.setItem('finder-ctrader', JSON.stringify({ clientId: 'cid', clientSecret: 'sec', accessToken: 'tok' })); window.ctList = () => [{ name: 'Gold', x: { symbolName: 'XAUUSD' } }, { name: 'Silver', x: { symbolName: 'XAGUSD' } }]; CT.state = 'ready'; window.__calls = [];
          window.ctKlines = async (sym, tf, limit, keep, to) => { __calls.push(sym + ' ' + tf + ' ' + new Date(to).getUTCFullYear()); const B = sym === 'CT:XAUUSD' ? bars.filter(b => b[0] <= to && b[0] > to - 5 * 365.25 * 864e5) : [];
            return { t: B.map(b => b[0]), o: B.map(b => b[1]), h: B.map(b => b[2]), l: B.map(b => b[1]), c: B.map(b => b[2]), qv: B.map(() => 0) }; };
          await fundSeas(true); localStorage.removeItem('finder-ctrader'); if (!FUND.seas) return 'no result: ' + FUND.err.seas; const R = FUND.seas.rows.Gold;
          return 'requests: ' + __calls.join(', ') + ' | rows: ' + Object.keys(FUND.seas.rows).join(',') + ' | gold ' + R.years + 'y from ' + new Date(R.from).toISOString().slice(0, 7) + ' · Nov ' + JSON.stringify(R.m[10]) + ' · Sep ' + R.m[8].ups + '/' + R.m[8].n + ' · Novembers counted ' + R.m[10].n + ' (2007–2025: 20 years back starts after Nov 2006, and this November is not finished)'; }"""))
        await q("() => fundRender()")
        print("36) panel:", await q("() => [...document.querySelectorAll('.fseas tr')].map(tr => tr.innerText.replace(/\\s+/g, ' ').trim()).join(' / ')"), "| now cell:", await q("() => document.querySelectorAll('.fseas tr:nth-child(2) td.fsc.now').length"))
        print("37) gold card seasonal line:", await q("() => (fundCardsData().find(c => c.k === 'Gold').L.find(x => /Seasonally/.test(x[1])) || ['', 'none'])[1]"), "| others:", await q("() => seasLine('Silver') + ' / ' + seasLine('Nasdaq 100')"))
        # calendar actuals: three past US releases with known answers (mock FRED: CPI +0.2% m/m, payrolls +150K, claims 221K)
        await q("""() => { const now = Date.now(), ev = (title, at, fc) => ({ id: 'USD|' + title + '|' + at, at, ccy: 'USD', title, impact: 'High', type: ffType(title), forecast: fc, previous: '' });
          CAL.items = [...CAL.items.filter(x => !/^(CPI m\\/m|Non-Farm Employment Change|Unemployment Claims)$/.test(x.title)), ev('CPI m/m', now - 3 * 3600e3, '0.3%'), ev('Unemployment Claims', now - 2.5 * 3600e3, '221K'), ev('Non-Farm Employment Change', now - 2 * 3600e3, '120K')].sort((a, b) => a.at - b.at); }""")
        await q("() => { CALA.at = {}; return calActFetch(); }"); await wait("() => !CALA.busy && CALA.s.CPIAUCSL && CALA.s.PAYEMS && CALA.s.ICSA", 15)      # the page's first try ran before the mock FRED key was on
        print("38) actuals:", await q("() => calAll().filter(x => calActDef(x) && x.at > Date.now() - 864e5).map(x => { const a = calActual(x); return x.title + ' ' + (a ? a.txt + ' vs ' + x.forecast + ' (' + a.word + ', dollar ' + a.dir + ')' : 'waiting'); }).join(' | ')"))
        print("38b) CPI series:", await q("() => (CALA.s.CPIAUCSL || []).slice(0, 4).map(p => new Date(p[0]).toISOString().slice(0, 10) + '=' + p[1]).join(', ') + ' | events: ' + calAll().filter(x => x.title === 'CPI m/m').map(x => new Date(x.at).toISOString().slice(0, 16) + ' F ' + x.forecast).join(', ')"))
        await q("() => fundRender()")
        print("39) read + cards:", await q("() => document.querySelector('#fundRead .fhead').innerText.replace(/\\s+/g, ' ')"), "||", await q("() => fundCardsData().map(c => c.k + ' ' + ((c.L.find(x => /expected/.test(x[1])) || [0, '—'])[0])).join(', ')"))
        await q("() => goPage('calendar')"); await asyncio.sleep(1)
        print("40) calendar rows:", await q("() => [...document.querySelectorAll('.caltbl tbody tr:not(.calday)')].filter(tr => /CPI m\\/m|Non-Farm|Claims/.test(tr.innerText)).map(tr => tr.querySelector('.ce').innerText.split('\\n')[0] + ' → ' + tr.querySelector('.cw').innerText).join(' | ')"))
        await q("() => goPage('fund')"); await asyncio.sleep(0.5)
        HF = "() => [...document.querySelectorAll('.fcot tr')].filter(tr => /^(Euro|Yen|Nasdaq 100|Gold|Crude oil|Silver)\\b/.test(tr.innerText.trim())).map(tr => tr.children[0].innerText.trim() + ' ' + tr.lastElementChild.innerText.replace(/\\s+/g, ' ') + (tr.lastElementChild.title ? ' {' + tr.lastElementChild.title + '}' : '')).join(' / ')"
        print("41) hedge funds:", await q(HF), "| header:", await q("() => [...document.querySelectorAll('.fcot tr.mu td')].map(td => td.textContent).join(' | ')"))
        FUND_SRV["cotsel"] = False
        await q("() => { FUND.cotf = null; return fundCOTFunds(true); }"); await q("() => fundRender()")
        print("42) columns named differently, fallback:", await q(HF), "| years for rank:", await q("() => FUND.cotf && Object.values(FUND.cotf.rows).map(r => r.pct).join(',')"))
        FUND_SRV["cotsel"] = True
        EIA = "() => [...document.querySelectorAll('.fworld tr')].filter(tr => /OIL & GAS|^(Crude oil|Gasoline|Distillates|Cushing|Natural gas storage)|EIA/i.test(tr.innerText.trim())).map(tr => tr.innerText.replace(/\\s+/g, ' ').trim()).join(' / ')"
        print("43) EIA, no key yet:", await q(EIA))
        await pg.fill("#eiaKey", "eia0123456789abcdef0123456789abcdef01234"); await q("() => document.getElementById('eiaSave').click()")
        await wait("() => FUND.eia && FUND.eia.s && !FUND.eiaBusy", 15); await q("() => fundRender()")
        print("44) EIA with a key:", await q(EIA), "| key sent:", any("/proxy/eia" in h and "api_key=eia0" in h for h in FUND_HITS[-8:]))
        print("45) oil card:", await q("() => (fundCardsData().find(c => c.k === 'Oil (WTI)').L.find(x => /crude stocks/.test(x[1])) || [0, 'none']).join(' ')"))
        await q("""() => { const now = Date.now(), d = new Date(now), wed = now - ((d.getUTCDay() + 4) % 7 || 7) * 864e5;
          CAL.items = [...CAL.items, { id: 'USD|Crude Oil Inventories|' + wed, at: wed, ccy: 'USD', title: 'Crude Oil Inventories', impact: 'Medium', type: ffType('Crude Oil Inventories'), forecast: '-1.2M', previous: '' }]; }""")
        print("46) calendar actual:", await q("() => { const x = calAll().find(x => x.title === 'Crude Oil Inventories'); const a = calActual(x); return new Date(x.at).toISOString().slice(0, 10) + ' ' + (a ? a.txt + ' vs ' + x.forecast + ' (' + a.word + ', dollar ' + a.dir + ')' : 'waiting'); }"))
        print("24) rates panel, nothing cut off:", await q("() => { const p = document.querySelector('.fcb').getBoundingClientRect(); return [...document.querySelectorAll('.fcb td')].filter(td => td.getBoundingClientRect().right > p.right + 1).map(td => td.innerText.trim()).slice(0, 4); }"))
        await pg.set_viewport_size({"width": 1180, "height": 1000}); await asyncio.sleep(0.3)
        print("24b) at 1180px:", await q("() => { const p = document.querySelector('.fcb').getBoundingClientRect(); return [Math.round(p.width), [...document.querySelectorAll('.fcb td')].filter(td => td.getBoundingClientRect().right > p.right + 1).map(td => td.innerText.trim()).slice(0, 4)]; }"))
        await pg.set_viewport_size({"width": 1500, "height": 1000}); await asyncio.sleep(0.3)
        el = await pg.query_selector(".fundcard"); await el.screenshot(path=f"{OUT}/fund.png")
        await q("() => document.querySelector('.fworld tr[data-fsym]').click()"); await asyncio.sleep(1)
        print("14) click a market → chart:", await q("() => page"))
        await pg.set_viewport_size({"width": 420, "height": 900}); await q("() => goPage('fund')"); await asyncio.sleep(1)
        print("15) phone width, no side scroll:", await q("() => document.documentElement.scrollWidth <= window.innerWidth + 1"))
        print("15b) too wide:", await q("() => [...document.querySelectorAll('.fundcard *')].filter(e => e.getBoundingClientRect().right > window.innerWidth + 1).slice(0, 6).map(e => e.tagName + '.' + e.className + ':' + Math.round(e.getBoundingClientRect().right))"))
        FUND_SRV["rates"] = False; await pg.set_viewport_size({"width": 1500, "height": 1000})
        await q("() => { FUND.bis = null; FUND.fy = null; }"); await q("() => fundLoad(true)"); await wait("() => FUND.err.bis && FUND.err.fy && !FUND.busy", 20); await q("() => fundRender()")
        print("23) sources down, OECD fallback:", await q(f"() => {{ const tr = ({ROW})('BoE'); return tr.innerText.replace(/\\s+/g, ' ') + ' {{' + tr.children[1].title + '}}'; }}"), "| gaps:", await q("() => document.querySelector('.fcb').innerText.match(/yield gaps[\\s\\S]*$/i)[0].replace(/\\s+/g, ' ').slice(0, 160)"))
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
