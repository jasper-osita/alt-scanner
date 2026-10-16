import asyncio, sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
# 2R target checks: the bot's 2R shadow on NBB (3R) trades, the backtest's 2R variant, and NBB Watch's "2R reached".
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1400, "height": 1000}); await setup(ctx)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        # three NBB longs, entry 100, stop 99 (3R = 103, 2R = 102): ran to 3R; reached 2R then stopped; stopped without reaching 2R
        print("1) bot:", await q("""() => { botLoad(); BOT.running = true; BOT.fee = 0; BOT.slip = 0; BOT.notify = false; BOT.bots.NBB.positions = []; BOT.bots.NBB.closed = [];
          const r = data.all.filter(x => !x.macro)[0], sym = r.symbol, m = { model: 'NBB', dir: 'Long', state: 'Breakout', entry: 100, stop: 99, t2: 103 };
          const res = [];
          for (const path of [[101.5, 102.5, 103.1], [102.2, 98.9], [100.5, 98.9]]) {
            bySym[sym].price = 100; r.price = 100; botOpen('NBB', r, m); const p = BOT.bots.NBB.positions.at(-1);
            for (const px of path) { bySym[sym].price = px; botCheckExits(); }
            const c = BOT.bots.NBB.closed.at(-1); res.push([p.t2r, c.reason, +c.r.toFixed(2), +c.r2.toFixed(2)]);
          }
          return res; }"""))
        print("   expect: [102,Target,3,2] [102,Stop,-1,2] [102,Stop,-1,-1]")
        await q("() => { goPage('bots'); renderBot(); }"); await asyncio.sleep(0.5)
        print("2) review:", await q("() => [...document.querySelectorAll('#botSim .brnotes')].map(x => x.innerText.replace(/\\s+/g, ' ')).find(t => /2R target instead/.test(t))"))
        print("3) V-Trade (2R target) gets no shadow:", await q("""() => { const r = data.all.filter(x => !x.macro)[1]; bySym[r.symbol].price = 100; r.price = 100;
          botOpen('V-Trade', r, { model: 'V-Trade', dir: 'Long', state: 'x', entry: 100, stop: 99, t2: 102 }); return BOT.bots['V-Trade'].positions.at(-1).t2r === undefined; }"""))
        # backtest variant: candles reach 2R, then fall to the stop
        print("4) btVariants t2:", await q("""() => { const k = { t: [], o: [], h: [], l: [], c: [] }; const add = (h, l, c) => { k.t.push(k.t.length * 36e5); k.o.push(100); k.h.push(h); k.l.push(l); k.c.push(c); };
          add(100, 100, 100); add(101, 99.5, 100.8); add(102.1, 100.5, 101.5); add(101, 98.8, 99);
          return btVariants(k, 0, { dir: 'Long', entry: 100, stop: 99, t2: 103 }, 48, null, 0); }"""), "expect t2: 2")
        print("5) NBB Watch:", await q("""() => { const k = { t: [1, 2, 3], h: [101, 102.2, 100], l: [99.5, 100.5, 98.9], c: [100.5, 101.8, 99] };
          return [nbbOutcome({ dir: 'Long', entry: 100, stop: 99, tClose: 0 }, k), nbbOutcome({ dir: 'Long', entry: 100, stop: 99, tClose: 0 }, { t: [1], h: [100.5], l: [99.5], c: [100.2] })]; }"""))
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
