import asyncio, sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OUT = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "out")
# Bot Simulator: filters (setups, side, session, result, exit, period, coin), the trade review, and a closed trade
# marked on the chart (cTrader style) with a docked panel to study it. Trades are seeded paper trades.
SEED = """() => {
  const now = Date.now(), H = 3600e3, A = data.all.filter(r => !r.macro)[0].symbol, B = data.all.filter(r => !r.macro)[1].symbol, mk = (model, sym, dir, hAgo, hold, r, reason) => {
    const px = bySym[sym].price, R0 = px * 0.006, long = dir === 'Long', entry = px * (1 + (long ? -1 : 1) * 0.004), stop = entry + (long ? -1 : 1) * R0, target = entry + (long ? 1 : -1) * R0 * 2;
    const exit = entry + (long ? 1 : -1) * R0 * r, opened = now - hAgo * H, closed = opened + hold * H;
    return { sym, dir, model, entry, exit, stop, target, pnl: r * 10, r, reason, opened, closed, env: 'Risk-off', session: sessOf(opened) }; };
  const T = [];
  for (let i = 0; i < 12; i++) T.push(mk('NBB', A, i % 3 ? 'Long' : 'Short', 6 + i * 5, 3, i % 4 === 0 ? -1 : 1.8, i % 4 === 0 ? 'Stop' : 'Target'));
  for (let i = 0; i < 8; i++) T.push(mk('Pullback', B, 'Short', 8 + i * 7, 5, i % 2 ? -1 : -0.4, i % 2 ? 'Stop' : 'Time limit'));
  for (let i = 0; i < 4; i++) T.push(mk('OB', B, 'Long', 30 + i * 9, 2, 1.2, 'Target'));
  botLoad(); BOT_STRATS().forEach(k => { BOT.bots[k].closed = T.filter(t => t.model === k); }); botSave();
  localStorage.removeItem('altscan-bot-filter'); BOTF = { ...BOTF_DEF }; return T.length; }"""
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1500, "height": 1000}, color_scheme="dark"); await setup(ctx)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e) + " @ " + (e.stack or "")[:300]))
        pg.on("console", lambda m: errs.append("console: " + m.text) if "paint skipped" in m.text else None)
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        async def wait(js, secs=30):
            for _ in range(secs * 4):
                if await q(js): return True
                await asyncio.sleep(0.25)
            return False
        print("seeded:", await q(SEED))
        await q("() => { goPage('bots'); renderBot(); }"); await asyncio.sleep(0.5)
        counts = "() => [document.querySelectorAll('#botSim [data-bstudy]').length, (document.querySelector('#botSim .brt b') || {}).textContent, [...document.querySelectorAll('#botSim .sct')][0].querySelectorAll('tbody tr').length]"
        print("1) all: [closed rows, review trades, bot rows]", await q(counts))
        print("2) review:", await q("() => document.querySelector('#botSim .brtiles').innerText.replace(/\\s+/g, ' ')"))
        print("3) notes:", await q("() => document.querySelector('#botSim .brnotes').innerText.replace(/\\s+/g, ' ')"))
        await q("() => document.querySelector('#botSim [data-bf=\"set\"][data-v=\"NBB\"]').click()")
        print("4) NBB only:", await q(counts), await q("() => [...new Set([...document.querySelectorAll('#botSim [data-bstudy]')].map(b => b.dataset.bstudy.split('|')[0]))].join(',')"))
        await q("() => document.querySelector('#botSim [data-bf=\"side\"][data-v=\"Short\"]').click()")
        print("5) NBB shorts:", await q(counts), "| saved:", await q("() => JSON.parse(localStorage.getItem('altscan-bot-filter')).side"))
        await q("() => document.getElementById('bfClear').click()"); await q("() => document.querySelector('#botSim [data-bf=\"res\"][data-v=\"loss\"]').click()")
        print("6) losers:", await q(counts), "| all losing:", await q("() => botClosedF().every(c => c.pnl < 0)"))
        await q("() => document.getElementById('bfClear').click()")
        cB = await q("() => coin(data.all.filter(r => !r.macro)[1].symbol).toLowerCase()")
        await pg.fill("#bfCoin", cB); await asyncio.sleep(0.6)
        print("7) coin", cB + ":", await q(counts), "| still typing:", await q("() => document.activeElement && document.activeElement.id === 'bfCoin'"))
        await q("() => document.getElementById('bfClear').click()")
        el = await pg.query_selector("#botSim"); await el.screenshot(path=f"{OUT}/botrev_page.png")
        # study a trade on the chart
        await q("() => document.querySelector('#botSim [data-bstudy]').click()")
        print("8) study:", await wait("() => !!document.getElementById('chStudy') && CHM && chVis()[0].sym === CHM.list[CHM.i].sym && chVis()[0].t.length > 20", 30))
        await asyncio.sleep(1.5)
        print("9) chart:", await q("() => { const c = CHM.list[CHM.i], P = chVis()[0], r = P.chart.timeScale().getVisibleLogicalRange(), a = chLogical(P, c.opened), z = chLogical(P, c.closed); return { page, sym: CH.sym, tf: P.tf, inView: a >= r.from && z <= r.to, docked: document.querySelector('#chPage .chbody').classList.contains('trdock') }; }"))
        print("10) panel:", await q("() => document.getElementById('chStudy').innerText.replace(/\\s+/g, ' ').slice(0, 260)"))
        await q("() => { CH.layout = '1'; chApplyLayout(); }"); await asyncio.sleep(1); await q("() => chStudyGo()"); await asyncio.sleep(2)
        # rebuild the studied trade from the chart's own candles (like a real bot fill): entry at a candle's close, exit at a later candle's high (stop on a short)
        print("9b) anchored on candles:", await q("""() => { const P = chVis()[0], c = CHM.list[CHM.i], n = P.t.length, i = n - 30, j = n - 14, iv = CH_IV[P.tf];
          c.dir = 'Short'; c.opened = P.t[i] + 60e3; c.entry = P.c[i]; c.closed = P.t[j] + 120e3; c.exit = P.h[j]; c.stop = c.exit; c.target = c.entry - (c.exit - c.entry) * 2; c.reason = 'Stop';
          chStudyGo(); const ok = [P.l[i] <= c.entry && c.entry <= P.h[i], P.l[j] <= c.exit && c.exit <= P.h[j]]; return ok; }"""))
        await asyncio.sleep(2)
        el = await pg.query_selector("#chPage"); await el.screenshot(path=f"{OUT}/botrev_chart.png")
        await q("() => document.getElementById('csNext').click()"); await asyncio.sleep(1.5)
        print("11) next:", await q("() => [CHM.i, CH.sym, document.querySelector('#chStudy .cstitle').innerText]"))
        await pg.fill("#csNote", "Swept the Asia high first"); await q("() => document.querySelector('#chStudy [data-cst=\"good\"]').click()")
        print("12) notes saved:", await q("() => { const n = JSON.parse(localStorage.getItem('altscan-bot-notes')), k = botKey(CHM.list[CHM.i]); return n[k]; }"))
        await q("() => document.getElementById('csAll').click()"); await asyncio.sleep(0.5)
        print("13) all on coin:", await q("() => [CHM.all, botAllClosed(CH.sym).length]"))
        await q("() => document.getElementById('csClose').click()"); await asyncio.sleep(0.5)
        print("14) closed:", await q("() => [CHM, !!document.getElementById('chStudy'), document.querySelector('#chPage .chbody').classList.contains('trdock')]"))
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
