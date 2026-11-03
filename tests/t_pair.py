import asyncio, sys, re
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OPTS = {"secret": "sec", "token": "tok", "live": True}
# Pair Picker: correlated markets (EUR/USD vs GBP/USD with EUR/GBP and the dollar, majors, yen crosses, Nasdaq vs S&P, gold vs silver) → which one to trade.
# Synthetic rows with known answers (USD weak → long the stronger, USD strong → short the weaker), then the page on cTrader (all groups) and MEXC (dollar pairs only).
SYN = """(usdUp) => {
  const H = 3600e3, now = Math.floor(Date.now() / H) * H, n = 220, f = i => 0.001 * Math.sin(i * 0.7) + 0.0004 * Math.cos(i * 1.3), u = usdUp ? -1 : 1;   // f: the shared dollar wiggle
  const mk = (name, group, pair, logp, s1, s4) => { const t = [], c = []; for (let i = 0; i < n; i++) { t.push(now - (n - 1 - i) * H); c.push(Math.exp(logp(i))); }
    const t4 = t.filter((x, i) => (n - 1 - i) % 4 === 0), c4 = c.filter((x, i) => (n - 1 - i) % 4 === 0);
    return { name, group, pair, symbol: 'SYN:' + name, price: c.at(-1), chg24h: (c.at(-1) / c.at(-25) - 1) * 100, s1h: { state: s1 }, s4h: { state: s4 }, c1: { t, c }, c4: { t: t4, c: c4 }, opens: { t, o: c.map((x, i) => i ? c[i - 1] : x) } }; };
  const B = usdUp ? 'Bear stack' : 'Bull stack', R = usdUp ? 'Bull stack' : 'Bear stack';     // other side vs USD: up when the dollar is weak
  return [
    mk('EUR/USD', 'Forex', 'EURUSD', i => u * 0.0005 * i + f(i) + 0.0002 * Math.sin(i * 2.1), B, B),
    mk('GBP/USD', 'Forex', 'GBPUSD', i => u * 0.0002 * i + 0.9 * f(i) + 0.0002 * Math.cos(i * 1.7), B, B),
    mk('USD/CHF', 'Forex', 'USDCHF', i => -u * 0.0003 * i - 0.95 * f(i) + 0.0002 * Math.sin(i * 1.1), R, R),
    mk('USD/JPY', 'Forex', 'USDJPY', i => -u * 0.0001 * i - 0.8 * f(i) + 0.0003 * Math.sin(i * 0.9) + (usdUp ? 0.0006 : 0.0004) * i, usdUp ? 'Bull stack' : 'Bull stack', 'Bull stack'),
    mk('Gold', 'Metals', null, i => 0.0008 * i + 0.002 * Math.sin(i * 0.5), 'Bull stack', 'Bull stack'),
    mk('Silver', 'Metals', null, i => 0.0004 * i + 0.0024 * Math.sin(i * 0.5) + 0.001 * Math.cos(i * 1.9), 'Bull stack', 'Pullback in bull'),
    mk('Nasdaq 100', 'Indices', null, i => -0.0007 * i + 0.002 * Math.sin(i * 0.6), 'Bear stack', 'Bear stack'),
    mk('S&P 500', 'Indices', null, i => -0.0003 * i + 0.0016 * Math.sin(i * 0.6) + 0.0004 * Math.cos(i * 2.3), 'Bear stack', 'Bear stack')];
}"""
CARD = "(G) => G.map(x => x.a.name + ' vs ' + x.b.name + ': lean ' + (x.lean ? x.lean.v.toFixed(2) : '—') + ', rs ' + x.rs + ', corr ' + (x.raw == null ? '—' : x.raw.toFixed(2)) + ' → ' + (x.pick ? x.pick.dir + ' ' + x.pick.l.name : 'no pick')).join(' | ')"
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1500, "height": 950}, color_scheme="dark"); await setup(ctx); await setup_mexc(ctx)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.route_web_socket("wss://contract.mexc.com/edge", mx_ws_handler)
        await pg.route_web_socket(re.compile(r"wss://(live|demo)\.ctraderapi\.com:5036.*"), ct_handler(OPTS))
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        async def wait(js, secs=200):
            for _ in range(secs * 2):
                if await q(js): return True
                await asyncio.sleep(0.5)
            return False
        print("1) in the menu:", await q("() => [...document.querySelectorAll('#navList .nav')].map(e => e.innerText.trim()).filter(t => /Pair Picker/.test(t)).length === 1"))
        print("2) dollar weak:", await q(f"() => ({CARD})(ppGroups(({SYN})(false)))"))
        print("3) dollar strong:", await q(f"() => ({CARD})(ppGroups(({SYN})(true)))"))
        print("4) card, dollar weak:", await q(f"() => {{ const d = document.createElement('div'); d.innerHTML = ppCardHTML(ppGroups(({SYN})(false))[0]); return d.innerText.replace(/\\s+/g, ' '); }}"))
        print("5) card, EUR/USD vs USD/CHF:", await q(f"() => {{ const G = ppGroups(({SYN})(false)), x = G.find(x => x.b.name === 'USD/CHF' && x.a.name === 'EUR/USD'), d = document.createElement('div'); d.innerHTML = ppCardHTML(x); return d.innerText.replace(/\\s+/g, ' '); }}"))
        # the page on MEXC (dollar pairs, gold, silver, indices; no NZD or yen crosses)
        await q("() => { document.getElementById('exF').value = 'mexc'; goPage('macropair'); macroScan(true); }")
        print("6) MEXC loaded:", await wait("() => !MACRO.running && MACRO.src === 'mexc' && MACRO.rows.length"), "| title:", await q("() => document.getElementById('pageTitle').textContent + ' / ' + document.getElementById('xovTitle').textContent"))
        print("7) MEXC cards:", await q("() => [...document.querySelectorAll('#ppBody .ppcard')].map(c => c.querySelector('.pph').innerText.replace(/\\s+/g, ' ') + ' :: ' + (c.querySelector('.pppick b, .ppno, .ppalt') || {}).innerText).join(' || ')"))
        print("8) MEXC missing note:", await q("() => (document.querySelector('.ppmiss') || {innerText: 'none'}).innerText"), "| badge:", await q("() => document.getElementById('nb-macropair').textContent"))
        # cTrader: all 28 pairs, gold, silver and the indices
        await q("() => { localStorage.setItem('finder-ctrader', JSON.stringify({ clientId: 'cid', clientSecret: 'sec', accessToken: 'tok' })); macroScan(true); }")
        print("9) cTrader loaded:", await wait("() => !MACRO.running && MACRO.rows.some(r => r.ct && r.group === 'Forex')"))
        await q("() => renderMacroBoards()")
        print("10) cTrader groups:", await q(f"() => ({CARD})(ppGroups(xRows()))"))
        print("11) closes kept:", await q("() => { const r = xRows().find(r => r.name === 'EUR/USD'); return r.c1.c.length + ' 1H, ' + r.c4.c.length + ' 4H; coins: ' + data.all.filter(r => r.c1).length; }"), "| missing note:", await q("() => (document.querySelector('.ppmiss') || {innerText: 'none'}).innerText"))
        print("12) first card:", await q("() => document.querySelector('#ppBody .ppcard').innerText.replace(/\\s+/g, ' ')"))
        print("13) pick opens the chart:", await q("() => { const p = document.querySelector('#ppBody .pppick'); if (!p) return 'no pick on this data'; p.click(); return document.getElementById('dlg').open + ' ' + p.dataset.s; }"))
        await q("() => document.getElementById('dlg').open && document.getElementById('dlg').close()")
        el = await pg.query_selector("[data-page='macropair'].ppwrap"); await el.screenshot(path="pair.png")
        await pg.set_viewport_size({"width": 390, "height": 844}); await asyncio.sleep(0.5)
        print("14) phone, no side scroll:", await q("() => document.documentElement.scrollWidth <= innerWidth + 1"), "| too wide:", await q("() => [...document.querySelectorAll('#ppBody *')].filter(e => e.getBoundingClientRect().right > innerWidth + 1).slice(0, 4).map(e => e.className)"))
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
