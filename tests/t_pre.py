import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
# synthetic candles: a downtrend, a base, then a turn back up through the 20 and 50 (Reclaiming), and a tight squeeze (Coiling)
SYN = """(kind) => {
  const n = 200, t = [], o = [], h = [], l = [], c = [], qv = []; let p = 100;
  for (let i = 0; i < n; i++) {
    let d;
    if (kind === 'reclaim') d = i < 110 ? -0.004 : i < 182 ? 0.0006 * Math.sin(i) : 0.0024;      // down, base, turn up
    else if (kind === 'coil') d = i < 60 ? -0.002 : i < 100 ? 0.002 : 0.0003 * Math.sin(i / 2) + 0.00004;   // down, recover, then flat & tight
    else d = 0.003;                                                                       // plain uptrend
    const op = p; p = p * (1 + d); const w = kind === 'coil' && i > 150 ? 0.0006 : 0.003;
    t.push(i * 36e5); o.push(op); c.push(p); h.push(Math.max(op, p) * (1 + w)); l.push(Math.min(op, p) * (1 - w)); qv.push(i > 194 ? 1.6e6 : 1e6);
  }
  return { t, o, h, l, c, qv };
}"""
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1440, "height": 900}, color_scheme="dark"); await setup(ctx)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload()
        print("scan ok:", await ready(pg))
        q = lambda js: pg.evaluate(js)
        for kind in ["reclaim", "trend"]:
            print(kind, "→", await q(f"() => {{ const k = ({SYN})('{kind}'); const p = preAots(k, ema, '1H', null), a = aots(k, ema, '1H'); return JSON.stringify({{ pre: p && [p.dir, p.stage, p.dist, p.spread, p.squeeze, p.score, p.flags], aots: a && a.stage }}); }}"))
        print("rows with pre:", await q("() => data.all.filter(r => r.pre4h || r.pre1h).length + ' of ' + data.all.length + ' · ' + data.all.filter(r => r.pre4h || r.pre1h).slice(0, 6).map(r => coin(r.symbol) + ' ' + [r.pre4h, r.pre1h].filter(Boolean).map(a => a.tf + ' ' + a.stage + ' ' + a.dist).join('/')).join(', ')"))
        print("never both:", await q("() => data.all.every(r => !(r.aots4h && r.pre4h) && !(r.aots1h && r.pre1h))"))
        await q("() => goPage('aots')"); await asyncio.sleep(0.6)
        print("on deck board:", await q("() => document.getElementById('preBoard').innerText.replace(/\\s+/g, ' ').slice(0, 300)"))
        await pg.screenshot(path=f"{OUT}/pre_board.png", full_page=True)
        await q("() => { tab = 'preaots'; sortKey = null; renderTabs(); renderTable(); }"); await asyncio.sleep(0.5)
        print("tab:", await q("() => [tab, document.querySelectorAll('#tbody tr').length, document.getElementById('thead').innerText.replace(/\\s+/g, ' '), document.getElementById('tbody').innerText.split('\\n').slice(0, 3).join(' | ')]"))
        # alert when an on-deck coin breaks
        print("promotion:", await q("""() => { const r = data.all.find(x => x.vol24h >= AOTS_MIN_VOL); const fake = { tf: '4H', dir: 'Long', stage: 'Reclaiming', score: 50, dist: 0.4, distPct: 1, trig: r.price * 1.01, spread: 1, squeeze: 0.8, vr: 1.2, bars: 3, flags: [], early: true };
            const keep = [r.aots4h, r.pre4h]; localStorage.removeItem('finder-pre-seen');
            r.aots4h = null; r.pre4h = { ...fake }; aotsPromotions();            // first pass only records
            r.pre4h = { ...fake }; aotsPromotions();
            const n0 = NC.length; r.pre4h = null; r.aots4h = { tf: '4H', dir: 'Long', stage: 'Breaking out', bars: 1, spread: 0.9, vr: 1.8, ext: 0.5, score: 70, flags: [] }; aotsPromotions(); aotsPromotions();
            const out = [NC.length - n0, NC[0] && NC[0].title]; r.aots4h = keep[0]; r.pre4h = keep[1]; return out; }"""))
        print("filter stage:", await q("() => testFilter(data.all.find(r => r.pre4h || r.pre1h) || {}, { kind: 'aots', tf: 'any', dir: 'any', stage: 'Reclaiming' }) + ' / coil ' + data.all.filter(r => testFilter(r, { kind: 'aots', tf: 'any', dir: 'any', stage: 'Coiling' })).length") if await q("() => typeof testFilter === 'function'") else "n/a")
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
