import asyncio, sys, time
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OUT = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "out", "finder")
PLANT = r"""
() => {   // replace the backtest with trades where NBB longs in the CURRENT session have a real edge, so live matching can be checked
  let seed = 11; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  const now = sessOf(Date.now()), other = ["🇯🇵 Asia", "🇬🇧 London", "🇺🇸 NY AM"].filter(x => x !== now), env = data.env.label, T = [], t0 = Date.now() - 50 * 864e5;
  for (let i = 0; i < 500; i++) { const hot = rnd() < 0.4, long = rnd() < 0.55, p = hot && long ? 0.66 : 0.3, win = rnd() < p;
    T.push({ sym: "X", model: "NBB", dir: long ? "Long" : "Short", tf: "1H", t: t0 + i * 2 * 3600e3, r: win ? 1.9 : -1.1, gross: 0, reason: win ? "Target" : "Stop", bars: 4,
      session: hot ? now : other[i % 2], env, state: "Breakout", rsi: "50–60", rot: "In line", wd: true, sw: false,
      v: { t15: win ? 1.4 : -1.1, t1: win ? 0.9 : -1.1, pbe: win ? 1.4 : -1.1 } }); }
  BT = { ...BT, trades: [...BT.trades.filter(t => t.model !== "NBB"), ...T] }; EDGE_AT = null; renderBacktest();
  return now;
}
"""
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1440, "height": 900}, color_scheme="dark"); await setup(ctx)
        pg = await ctx.new_page(); errs, csp = [], []
        pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: "Content Security Policy" in m.text and csp.append(m.text[:140]))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        await q("() => goPage('backtest')"); await pg.select_option("#btCoins", "20"); await pg.select_option("#btDays", "30")
        t0 = time.time(); await pg.click("#btRun")
        for _ in range(500):
            if await q("() => !btRunning && !!BT"): break
            await asyncio.sleep(0.5)
        print(f"1) backtest {time.time() - t0:.0f}s:", await q("() => BT.trades.length + ' trades, ' + BT.trades.filter(t => t.v).length + ' with variants'"),
              "| sample:", await q("() => { const t = BT.trades.find(t => t.v); return t.model + ' base ' + t.r + ' | 1.5R ' + t.v.t15 + ' | 1R ' + t.v.t1 + ' | half ' + t.v.pbe; }"))
        print("   OB variants:", await q("() => { const t = BT.trades.find(t => t.model === 'OB'); return t ? JSON.stringify(t.v) + ' wd ' + t.wd : 'no OB trades'; }"))
        print("2) edge card on mock data:", await q("() => document.querySelector('#edgeCard .schead .meta').innerText"), "|", await q("() => [...document.querySelectorAll('#edgeCard .edgesub')].slice(0, 2).map(x => x.innerText.slice(0, 90)).join(' || ')"))
        sess = await q(PLANT)
        print("3) planted (NBB longs in", sess + "):", await q("() => document.querySelector('#edgeCard .schead .meta').innerText"))
        print("   NBB rules:", await q("() => [...document.querySelectorAll('#edgeCard .edgerule')].map(x => x.innerText.replace(/\\s+/g, ' ')).slice(0, 3).join(' || ')"))
        await pg.screenshot(path=f"{OUT}/edge_card.png", full_page=False)
        await pg.evaluate("() => document.getElementById('edgeCard').scrollIntoView()"); await asyncio.sleep(0.3); await pg.screenshot(path=f"{OUT}/edge_card.png")
        await pg.click("#edgeAll"); await asyncio.sleep(0.3)
        print("4) rules in use:", await q("() => EDGE.rules.map(r => r.model + ': ' + edgeCondText(r.cs) + ' [' + r.v + ']').join(' | ')"), "| A-grade box enabled:", await q("() => !document.getElementById('edgeAOnly').disabled"))
        # live effect: plant a live NBB long and short on two coins so matching can be checked
        await q("() => { const a = data.all[0], b2 = data.all[1]; a.models = [...(a.models || []).filter(m => m.model !== 'NBB'), { model: 'NBB', dir: 'Long', state: 'Breakout', trig: true, entry: a.price, stop: a.price * 0.98, t2: a.price * 1.04, tf: '1H', withDaily: true, sweep: false }];"
                "b2.models = [...(b2.models || []).filter(m => m.model !== 'NBB'), { model: 'NBB', dir: 'Short', state: 'Breakout', trig: true, entry: b2.price, stop: b2.price * 1.02, t2: b2.price * 0.96, tf: '1H', withDaily: true, sweep: false }]; }")
        print("5) matching:", await q("() => { const a = data.all[0], b2 = data.all[1]; const ma = a.models.find(m => m.model === 'NBB'), mb = b2.models.find(m => m.model === 'NBB'); return `long ${edgeOK(a, ma)} · short ${edgeOK(b2, mb)}`; }"))
        before = await q("() => suggestions(data.env).map(x => coin(x.r.symbol) + ' ' + x.m.model).join(', ')")
        await pg.check("#edgeAOnly"); await asyncio.sleep(0.4)
        after = await q("() => suggestions(data.env).map(x => coin(x.r.symbol) + ' ' + x.m.model).join(', ')")
        print("6) A-grade only → playbook picks:", before or "none", "→", after or "none (nothing qualifies)")
        print("   coin play now:", await q("() => coinPlay(data.all[0]).short + ' | other coin: ' + coinPlay(data.all[1]).short"))
        print("   trigger keys (alerts):", await q("() => trigKeys(data.all[0]).length + ' vs ' + trigKeys(data.all[1]).length"), "| bots would consider:", await q("() => data.all.flatMap(r => liveModels(r)).length"), "setups")
        await q("() => goPage('playbook')"); await asyncio.sleep(0.3)
        print("7) playbook switch:", await q("() => { const x = document.getElementById('pbAGrade'); return x ? (x.checked + ' · ' + x.parentElement.innerText) : 'missing'; }"))
        await q(f"() => openDetail(data.all[0].symbol)"); await asyncio.sleep(1.2); await pg.click('.dtabs [data-pane="setups"]'); await asyncio.sleep(0.2)
        print("8) setups tab tags:", await q("() => [...document.querySelectorAll('.dpane[data-pane=setups] .setup')].map(x => [...x.querySelectorAll('.tag')].map(t => t.innerText).join('/')).slice(0, 3).join(' || ')"))
        await pg.keyboard.press("Escape")
        await q("() => goPage('backtest')"); await pg.click("#edgeCopy"); await asyncio.sleep(0.2)
        print("9) copy text:", await q("() => edgeText().split('\\n').filter(Boolean).slice(0, 4).join(' / ').slice(0, 300)"))
        await pg.reload(); await asyncio.sleep(1.5)
        print("10) after reload:", await q("() => ({ rules: EDGE.rules.length, aOnly: EDGE.aOnly })"))
        print("CSP:", csp or "none", "| errors:", errs or "none")
        await b.close()
asyncio.run(main())
