import asyncio, sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
# Event risk: election nights by rule, your own risk events, shock headlines, unusual moves, the weekend; the NBB Watch banner, the calendar, alerts, and "protect your trade".
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1500, "height": 950}, color_scheme="dark"); await setup(ctx); await setup_mexc(ctx); await setup_extra(ctx); await setup_fund(ctx)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.route_web_socket("wss://contract.mexc.com/edge", mx_ws_handler)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        print("1) election days:", await q("() => [2026, 2028, 2030].map(y => y + '-11-' + usElectionDay(y)).join(', ')"))
        print("2) 2026 election night:", await q("""() => { const at = nyAt(2026, 11, 3, 19, 0), f = t => { const R = riskRead(t); return R.level + ' ' + (R.items.find(x => /election/.test(x.txt)) || { short: '—' }).short; };
          return ['9h before: ' + f(at - 9 * 3600e3), '2h before: ' + f(at - 2 * 3600e3), 'during: ' + f(at + 4 * 3600e3), 'after: ' + f(at + 20 * 3600e3)].join(' | ') + ' · window ' + new Date(at).toISOString().slice(0, 16) + 'Z'; }"""))
        print("3) in the calendar:", await q("() => calAll().filter(x => /election/.test(x.title)).map(x => x.title + ' ' + new Date(x.at).toISOString().slice(0, 16) + ' ' + x.impact + '/' + x.type).join(', ')"))
        print("4) headlines:", await q("""() => { const now = Date.now(), it = (t, ago) => ({ title: t, t: now - ago * 60e3, src: 'Test', link: 'https://example.com' }), keep = FUND.news;
          FUND.news = { at: now, items: [it('US to raise tariffs on imports', 20), it('Tariff threat weighs on stocks', 50), it('Markets eye new tariffs', 90)] }; const a = riskRead();
          FUND.news = { at: now, items: [it('Missile attack reported near oil terminal', 10)] }; const b = riskRead(); FUND.news = keep;
          return 'three tariff stories → ' + a.level + ' (' + a.items[0].short + ') · a missile attack → ' + b.level + ' (' + b.items[0].txt.slice(0, 70) + ')'; }"""))
        print("5) unusual move:", await q("""() => { const t0 = Date.now() - 300 * 300e3, K = { t: [], h: [], l: [] }; for (let i = 0; i < 300; i++) { const big = i >= 288; K.t.push(t0 + i * 300e3); K.h.push(100 + (big ? 6 : 0.5)); K.l.push(100 - (big ? 6 : 0.5)); }
          NW_ST['Gold|5m'] = { ...(NW_ST['Gold|5m'] || {}), k: K }; const R = riskRead(); delete NW_ST['Gold|5m'].k; return R.level + ' · ' + (R.items.find(x => /^vol:/.test(x.id)) || { txt: 'none' }).txt; }"""))
        print("6) weekend:", await q("() => { const fri = nyAt(2026, 11, 6, 14, 0), R = riskRead(fri); return R.level + ' ' + (R.items.find(x => /weekend/.test(x.short)) || { short: 'none' }).short; }"))
        # NBB Watch banner: add your own risk event through the form, then remove it
        await q("() => goPage('nbbwatch')"); await asyncio.sleep(1)
        print("7) banner:", await q("() => document.getElementById('riskBar').className + ' · ' + document.getElementById('riskBar').innerText.replace(/\\s+/g, ' ').slice(0, 220)"))
        await q("() => document.getElementById('rkAddB').click()")
        d = await q("() => new Date(Date.now() + PHT_MS + 2 * 3600e3).toISOString().slice(0, 16)")
        await pg.fill("#rkT", "Supreme Court tariff ruling"); await pg.fill("#rkD", d[:10]); await pg.fill("#rkH", d[11:16]); await pg.fill("#rkN", "8")
        await q("() => document.querySelector('#rkForm button').click()"); await asyncio.sleep(0.4)
        print("8) after adding:", await q("() => document.getElementById('riskBar').className + ' · ' + document.getElementById('riskBar').innerText.replace(/\\s+/g, ' ').slice(0, 300)"),
              "| calendar:", await q("() => calAll().filter(x => /Supreme/.test(x.title)).map(x => x.title + ' (' + x.impact + ')').join(', ')"), "| NBB news check:", await q("() => { const n = calNextFor(['USD'], 180, 15); return n ? n.title : 'none'; }"))
        # alerts: one for the event, one to protect an open gold long that's +5R (a trade with its stop past entry is left alone)
        await q("""() => { lsSet(EVR_KEY, [...riskOwn(), { id: 'now1', title: 'Fed emergency statement', at: Date.now() - 30 * 60e3, hours: 4 }]);
          CTT.state = 'ready'; CTT.byId[41] = { symbolName: 'XAUUSD' }; CTT.byId[42] = { symbolName: 'NAS100' }; CTT.spots[41] = { bid: 2050, ask: 2050.4 }; CTT.spots[42] = { bid: 20150, ask: 20151 };
          CTT.positions = [{ positionId: 7, price: 2000, stopLoss: 1990, tradeData: { symbolId: 41, tradeSide: 1 } }, { positionId: 8, price: 20300, stopLoss: 20290, tradeData: { symbolId: 42, tradeSide: 2 } }]; riskTick(); riskTick(); }""")
        print("9) positions:", await q("() => JSON.stringify(riskPositions().map(p => [p.sym, p.buy ? 'long' : 'short', p.r && +p.r.toFixed(1), p.locked]))"))
        print("10) alerts:", await q("() => NC.filter(n => n.kind === 'Event risk').map(n => n.title + ' :: ' + n.detail.slice(0, 110)).join(' || ')"), "| count:", await q("() => NC.filter(n => n.kind === 'Event risk').length"))
        print("11) Telegram + alert tabs:", await q("() => TG_KINDS.some(k => k[0] === 'Event risk') + ' / ' + NC_KINDS.includes('Event risk')"))
        print("12) Today's read:", await q("() => { const d = document.createElement('div'); d.innerHTML = fundReadHTML(); return d.querySelector('.fhead').innerText.replace(/\\s+/g, ' ').slice(0, 160); }"),
              "| card warning:", await q("() => (fundCardsData().find(c => c.k === 'Gold').L.find(x => /Event risk/.test(x[1])) || [0, 'none'])[1]"))
        await q("() => document.querySelector('[data-rkdel=\"now1\"]') && document.querySelector('[data-rkdel=\"now1\"]').click()")
        await q("() => { const b = [...document.querySelectorAll('[data-rkdel]')]; b.forEach(x => x.click()); }"); await asyncio.sleep(0.3)
        print("13) removed:", await q("() => riskOwn().length + ' own events · ' + calAll().filter(x => /Supreme|emergency/.test(x.title)).length + ' in the calendar'"))
        await pg.set_viewport_size({"width": 390, "height": 844}); await asyncio.sleep(0.5)
        print("14) phone, no side scroll:", await q("() => document.documentElement.scrollWidth <= innerWidth + 1"))
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
