import asyncio, sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OUT = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "out", "finder")
SYNTH = r"""
() => {
  let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  const envs = ["Trend Up: Risk-On Alts", "Chop: Range Day"], sess = ["🇯🇵 Asia", "🇬🇧 London", "🇺🇸 NY AM"], T = [], t0 = Date.UTC(2026, 7, 1);
  const mk = (model, i, p, extra = {}) => { const win = rnd() < p, d = rnd() < 0.5 ? "Long" : "Short";
    const t = { sym: "X", model, dir: extra.dir || d, tf: "1H", t: t0 + i * 3600e3, r: win ? 1.9 : -1.1, reason: win ? "Target" : "Stop", bars: 5,
      session: extra.session || sess[Math.floor(rnd() * 3)], env: envs[Math.floor(rnd() * 2)], rsi: "50–60", rot: "In line", wd: rnd() < 0.5, sw: rnd() < 0.4 };
    t.v = { t15: win || rnd() < 0.15 ? 1.4 : -1.1, t1: win || rnd() < 0.3 ? 0.9 : -1.1, pbe: win ? 1.4 : rnd() < 0.2 ? 0.4 : -1.1 }; return t; };
  // NBB: London longs win 65%, everything else 30% (a real, stable edge)
  for (let i = 0; i < 600; i++) { const london = rnd() < 0.35, long = rnd() < 0.5; T.push(mk("NBB", i, london && long ? 0.65 : 0.3, { session: london ? "🇬🇧 London" : (rnd() < 0.5 ? "🇯🇵 Asia" : "🇺🇸 NY AM"), dir: long ? "Long" : "Short" })); }
  // Fade: pure noise at 34%
  for (let i = 0; i < 400; i++) T.push(mk("Fade", i, 0.34));
  // Breaker: Asia wins 70% in the OLDER two-thirds only, then 25% (a lucky pattern that should be rejected)
  for (let i = 0; i < 450; i++) { const asia = rnd() < 0.4; T.push(mk("Breaker", i, asia ? (i < 300 ? 0.7 : 0.25) : 0.3, { session: asia ? "🇯🇵 Asia" : "🇬🇧 London" })); }
  // ORB: only 12 trades (too few)
  for (let i = 0; i < 12; i++) T.push(mk("ORB", i, 0.6));
  const res = edgeSearch(T, 30);
  return res.map(r => `${r.model} n=${r.n} base ${r.base.base.win.toFixed(0)}%/${r.base.base.avg.toFixed(2)}R | ` +
    (r.n < 30 ? "too few" : r.rules.length ? r.rules.map(c => `${c.verdict.toUpperCase()} ${edgeCondText(c.cs)} [${c.v}] older ${c.train.win.toFixed(0)}% ${c.train.avg.toFixed(2)}R n${c.train.n} / newest ${c.test ? c.test.win.toFixed(0) + "% " + c.test.avg.toFixed(2) + "R n" + c.test.n : "—"}`).join(" ;; ") : `no rules (tested ${r.tested}, failed ${r.failed})`)).join("\n");
}
"""
VAR = r"""
() => {   // management variants on a hand-built path: entry 100, stop 99 (R = 1), model target 102
  const K = (rows) => ({ t: rows.map((_, i) => i * 3600e3), o: rows.map(r => r[0]), h: rows.map(r => r[1]), l: rows.map(r => r[2]), c: rows.map(r => r[3]) });
  const m = { dir: "Long", entry: 100, stop: 99, t2: 102 };
  const a = K([[100, 100, 100, 100], [100, 100.5, 99.6, 100.2], [100.2, 101.1, 100.1, 101], [101, 101.6, 100.9, 101.5], [101.5, 102.2, 101.4, 102.1]]);   // 1R, 1.5R then 2R
  const b = K([[100, 100, 100, 100], [100, 101.05, 99.8, 100.9], [100.9, 101.0, 99.9, 100.0], [100, 100.2, 98.8, 98.9]]);                          // 1R, back to entry, then stop
  const c = K([[100, 100, 100, 100], [100, 100.4, 98.9, 99.0]]);                                                                                  // straight to the stop
  const f = x => JSON.stringify(btVariants(x, 0, m, 48, null, 0));
  return `rally to 2R: ${f(a)} | 1R then back: ${f(b)} | straight stop: ${f(c)}`;
}
"""
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1440, "height": 900}, color_scheme="dark"); await setup(ctx)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await asyncio.sleep(1.5)
        print("== planted-edge search ==\n" + await pg.evaluate(SYNTH))
        print("== variants ==\n" + await pg.evaluate(VAR))
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
