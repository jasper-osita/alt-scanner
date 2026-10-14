import asyncio, sys, time
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
async def waitfor(pg, js, secs=600):
    for _ in range(secs * 2):
        if await pg.evaluate(js): return True
        await asyncio.sleep(0.5)
    return False
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1500, "height": 950}); await setup(ctx); await setup_mexc(ctx)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None); await pg.route_web_socket("wss://contract.mexc.com/edge", mx_ws_handler)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        # Binance futures panel: own full set
        print("1) Binance:", await q("async () => { const r = data.all.find(x => x.symbol === 'ARBUSDT'); const d = await drivers(r); return JSON.stringify({ oi: d.oiChg != null, top: d.topLS, glob: d.globLS, taker: d.takerRatio && +d.takerRatio.toFixed(2), fund: d.fundNow, src: d.src }); }"))
        # MEXC futures scan speed
        MX_RL["hits"] = 0; MX_RL["served"] = 0; t0 = time.time(); await pg.select_option("#exF", "mexc")
        ok = await waitfor(pg, "() => data && data.exchange === 'mexc' && !document.getElementById('runBtn').disabled")
        print(f"2) MEXC scan ok={ok} {time.time()-t0:.0f}s (was ~225s): {await q('() => data.analysed')} coins | contract calls {MX_RL['served']} | refusals {MX_RL['hits']} | pace now {await q('() => MX_GAP')}ms")
        print("   4h from 1h == MEXC 4h:", await q("async () => { const a = await klines('ETHUSDT', '4h', 160), now = Date.now(), b = await mxKlinesF('ETHUSDT', '4h', now - 162 * 14400e3, now), bb = b.filter(r => r[0] + 14400e3 <= now).slice(-160); return a.t.length === bb.length && a.t.every((t, i) => t === bb[i][0] && Math.abs(a.c[i] - bb[i][4]) < 1e-9 && Math.abs(a.h[i] - bb[i][2]) < 1e-9 && Math.abs(a.qv[i] - bb[i][5]) / bb[i][5] < 1e-9); }"))
        r = await q("""async () => { const r = data.all.find(x => x.symbol === 'ARBUSDT'); const d = await drivers(r); return JSON.stringify({ oiChg: d.oiChg != null, oiUsd: Math.round(d.oiUsd), top: d.topLS, glob: d.globLS, taker: d.takerRatio != null, fund: d.fundNow, src: d.src, head: d.head }); }""")
        print("3) MEXC panel:", r)
        await q("() => openDetail('ARBUSDT')"); await asyncio.sleep(3)
        print("   panel text:", await q("() => (document.querySelector('.drv-src') || {}).textContent || 'no sources line'"), "|", await q("() => [...document.querySelectorAll('#dlgBody .meta')].map(m => m.textContent).find(t => /Taker/.test(t)) || ''"))
        await q("() => document.getElementById('dlg').close()")
        # MEXC 3m / 2h charts
        r = await q("""async () => { const out = {}; for (const tf of ['3m', '2h']) { const k = await klines('ETHUSDT', tf, 300); const st = k.t.slice(1).map((t, i) => t - k.t[i]); const fb = await formingBar('ETHUSDT', tf);
          out[tf] = { n: k.t.length, step: [...new Set(st)].map(x => x / 60000 + 'm').join(','), aligned: k.t.every(t => t % ({ '3m': 180e3, '2h': 7200e3 }[tf]) === 0), forming: fb && (fb.t > k.t.at(-1)) }; } return JSON.stringify(out); }""")
        print("4) MEXC 3m/2h:", r)
        await q("() => goPage('charts')"); await asyncio.sleep(2)
        await q("() => { CHP[2].tf = CH.tfs[2] = '3m'; CHP[3].tf = CH.tfs[3] = '2h'; chLoad(CHP[2]); chLoad(CHP[3]); }"); await asyncio.sleep(4)
        print("   charts:", await q("() => CHP.map(P => P.tf + ' bars=' + P.t.length + (P.msg.hidden ? '' : ' MSG ' + P.msg.textContent)).join(' | ')"))
        # MEXC spot: taker flow from Binance spot + positioning
        await q("() => goPage('overview')"); await pg.select_option("#market", "spot")
        await waitfor(pg, "() => data && data.mode === 'spot' && !document.getElementById('runBtn').disabled")
        print("5) MEXC spot panel:", await q("async () => { const r = data.all.find(x => x.symbol === 'ARBUSDT'); const d = await drivers(r); return JSON.stringify({ oi: d.oiChg != null, top: d.topLS, taker: d.takerRatio != null, src: d.src }); }"))
        # Binance spot: now also futures positioning
        await pg.select_option("#exF", "binance"); await waitfor(pg, "() => data && data.exchange === 'binance' && !document.getElementById('runBtn').disabled")
        print("6) Binance spot panel:", await q("async () => { const r = data.all.find(x => x.symbol === 'ARBUSDT'); const d = await drivers(r); return JSON.stringify({ mode: data.mode, oi: d.oiChg != null, top: d.topLS, glob: d.globLS, taker: d.takerRatio != null, src: d.src }); }"))
        print("7) Bybit intervals:", await q("() => Object.keys(BY_IV).join(',') + ' | back ' + BY_IV_BACK['120'] + ',' + BY_IV_BACK['W']"))
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
