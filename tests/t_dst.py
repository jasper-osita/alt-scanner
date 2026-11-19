import asyncio, sys, datetime
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
# Daylight saving: the New York based session map lands 1 hour later in PHT while New York is on winter time (first Sunday of November to second Sunday of March).
UTC = datetime.timezone.utc
NOV = datetime.datetime(2026, 11, 11, 14, 45, tzinfo=UTC)      # Wed 10:45 PM PHT, New York on winter time
JUL = datetime.datetime(2026, 7, 15, 13, 45, tzinfo=UTC)       # Wed 9:45 PM PHT, New York on summer time
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1400, "height": 950}, color_scheme="dark")
        await setup(ctx); await setup_mexc(ctx); await setup_extra(ctx)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        # the clock itself, any date (no fake time needed)
        print("1) switch dates 2026:", await q("() => dstRange(2026).map(t => new Date(t).toISOString().slice(0, 16)).join(' · ')"))
        print("2) New York on summer time: Jul", await q("() => nyDst(Date.UTC(2026, 6, 15))"), "| 31 Oct", await q("() => nyDst(Date.UTC(2026, 9, 31, 12))"), "| 2 Nov", await q("() => nyDst(Date.UTC(2026, 10, 2))"), "| Mar 9 2027", await q("() => nyDst(Date.UTC(2027, 2, 9))"))
        print("3) session clock at 9:45 PM PHT: July", await q("() => sessH(Date.UTC(2026, 6, 15, 13, 45))"), "| November", await q("() => sessH(Date.UTC(2026, 10, 11, 13, 45))"), "| 10:45 PM Nov", await q("() => sessH(Date.UTC(2026, 10, 11, 14, 45))"))
        print("5) Fed decision 9 Dec 2026, PHT:", await q("() => new Date(fomcAt('2026-12-09') + PHT_MS).toISOString().slice(0, 16)"))
        print("6) NBB window check, 8:30 AM PHT Nov:", await q("() => nbbGrade({ model: 'NBB', dir: 'Long', trendAge: 9, trig: true }, 'Long', 'Long', Date.UTC(2026, 10, 11, 0, 30)).items[2].join(' | ')"))
        # winter
        await pg.clock.set_fixed_time(NOV); await q("() => tickClock()")
        print("7) Nov ribbon:", await q("() => [...document.querySelectorAll('#bar .seg')].map(s => s.title.replace(/^\\S+ /, '') + ' ' + s.dataset.s + '-' + s.dataset.e).join(', ')"))
        print("   on now:", await q("() => document.querySelector('#bar .seg.on').title"), "| note:", await q("() => document.getElementById('sessNote').innerText"))
        print("9) Nov overview timeframes (session clock):", await q("() => { const n = sessH(); return [n, n >= 21.5 ? 'NAS100 1m' : 'NAS100 off', n >= 12 && n < 18 ? 'Gold 5m' : 'Gold off'].join(' · '); }"))
        await q("() => goPage('charts')"); await asyncio.sleep(1.5)
        await q("() => { window.__vl = indNew('vlines'); chIndSettings(window.__vl); }"); await asyncio.sleep(0.3)
        print("11) Nov time lines dialog:", await q("() => [1, 2, 3, 4].map(j => (document.getElementById('ci_n' + j) || {}).value + ' ' + (document.getElementById('ci_t' + j) || {}).value + ' (' + (document.getElementById('ci_z' + j) || {}).value + ')').join(' / ')"))
        await pg.fill("#ci_t2", "22:00"); await asyncio.sleep(0.1)
        print("    typed 22:00 for NY open → stored:", await q("() => window.__vl.p.t2"))
        await q("() => { const s = document.getElementById('ci_z2'); s.value = \"Doesn't move\"; s.dispatchEvent(new Event('change')); }"); await asyncio.sleep(0.1)
        print("    NY open set to not move → shows:", await q("() => document.getElementById('ci_t2').value"), "stored:", await q("() => window.__vl.p.t2"))
        await q("() => document.getElementById('chSetCancel').click()")
        await q("() => { window.__ss = indNew('sess'); chIndSettings(window.__ss); }"); await asyncio.sleep(0.3)
        print("12) Nov session boxes dialog:", await q("() => [1, 2, 3, 4].map(j => document.getElementById('ci_n' + j).value + ' ' + document.getElementById('ci_a' + j).value + '–' + document.getElementById('ci_b' + j).value).join(' / ')"))
        await q("() => document.getElementById('chSetCancel').click()")
        # summer
        await pg.clock.set_fixed_time(JUL); await q("() => tickClock()")
        print("13) Jul ribbon:", await q("() => [...document.querySelectorAll('#bar .seg')].map(s => s.title.replace(/^\\S+ /, '') + ' ' + s.dataset.s + '-' + s.dataset.e).join(', ')"))
        print("   on now:", await q("() => document.querySelector('#bar .seg.on').title"), "| note:", await q("() => document.getElementById('sessNote').innerText"))
        await q("() => { window.__vl = indNew('vlines'); chIndSettings(window.__vl); }"); await asyncio.sleep(0.3)
        print("15) Jul time lines dialog:", await q("() => [1, 2, 3, 4].map(j => document.getElementById('ci_n' + j).value + ' ' + document.getElementById('ci_t' + j).value).join(' / ')"))
        await q("() => document.getElementById('chSetCancel').click()")
        print("errors:", errs[:5] if errs else "none")
        await b.close()
asyncio.run(main())
