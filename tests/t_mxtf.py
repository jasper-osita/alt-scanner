import asyncio, json, sys, time
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
async def waitfor(pg, js, secs=400):
    for _ in range(secs * 2):
        if await pg.evaluate(js): return True
        await asyncio.sleep(0.5)
    return False
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1440, "height": 950}, color_scheme="dark")
        await setup(ctx); await setup_mexc(ctx)
        pg = await ctx.new_page(); errs, csp = [], []
        pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: "Content Security Policy" in m.text and csp.append(m.text[:160]))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.route_web_socket("wss://contract.mexc.com/edge", mx_ws_handler)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        # 1) MEXC futures crypto scan, paced, without TradFi contracts
        MX_RL["hits"] = 0; t0 = time.time(); await pg.select_option("#exF", "mexc")
        ok = await waitfor(pg, "() => data && data.exchange === 'mexc' && !document.getElementById('runBtn').disabled", 900)
        print(f"1) MEXC scan ok={ok} {time.time()-t0:.0f}s:", await pg.evaluate("() => data.analysed + ' coins of ' + data.total"), "| rate-limit refusals:", MX_RL["hits"], "served", MX_RL["served"])
        print("   TradFi leaked into crypto?", await pg.evaluate("() => data.all.filter(r => /STOCK|NVIDIA|TESLA|XAU|SILVER|NAS100|EUR|JPY|USOIL/.test(r.symbol)).map(r => r.symbol)"))
        print("   chg24h is rolling 24h:", await pg.evaluate("() => { const r = data.all[0]; return r.symbol + ' chg ' + r.chg24h.toFixed(2) + ' ret24 ' + (r.ret24 * 100).toFixed(2); }"))
        # 2) Forex, Gold & Indices from MEXC
        MX_RL["hits"] = 0; t0 = time.time(); await pg.evaluate("() => goPage('macro')")
        ok = await waitfor(pg, "() => MACRO.rows.some(r => r.mx) && !MACRO.running", 300)
        print(f"2) macro ok={ok} {time.time()-t0:.0f}s | refusals {MX_RL['hits']} | meta:", await pg.evaluate("() => document.getElementById('macroMeta').textContent"))
        print("   boards:", await pg.evaluate("() => [...document.querySelectorAll('#macroBody .board')].map(b => b.querySelector('h2').innerText.replace(/\\s+/g,' ') + ' (' + b.querySelectorAll('.row').length + ')').join(' | ')"))
        print("   rows:", await pg.evaluate("() => MACRO.rows.map(r => r.name + ' ' + fmtPrice(r.price)).join(', ')"))
        print("   read-out:", await pg.evaluate("() => document.getElementById('macroRead').innerText.replace(/\\s+/g,' ').slice(0, 300)"))
        print("   errors so far:", errs or "none")
        await asyncio.sleep(7)
        print("   live XAU (ws push 4321.5):", await pg.evaluate("() => MACRO.by['MX:XAU_USDT'].price + ' · on page ' + (document.querySelector('[data-mp=\"MX:XAU_USDT\"]') || {}).textContent"),
              "| macro kline subs:", sum(1 for m in MXWS_LOG if m.get("method") == "sub.kline" and m["param"]["symbol"] in ("XAU_USDT", "NAS100_USDT", "EUR_USDT")))
        print("   live tick → row:", await pg.evaluate("() => { liveMessage({ channel: 'push.tickers', data: [{ symbol: 'XAU_USDT', lastPrice: 4321.5 }] }); return MACRO.by['MX:XAU_USDT'].price + ' · ' + document.querySelector('[data-mp=\"MX:XAU_USDT\"]').textContent + ' · chg ' + MACRO.by['MX:XAU_USDT'].chg24h.toFixed(2); }"))
        # 3) detail dialog on a MEXC TradFi row
        await pg.evaluate("() => openDetail('MX:NAS100_USDT')"); await asyncio.sleep(4)
        print("3) dialog:", await pg.evaluate("() => document.getElementById('dlg').open + ' · ' + document.querySelector('#dlgBody h3, #dlgBody .dhead').innerText.replace(/\\s+/g,' ').slice(0,80)"),
              "| chart:", await pg.evaluate("() => (document.querySelector('#dlgBody .cload') || {}).textContent || 'drawn'"), "| tv:", await pg.evaluate("() => tvLink('MX:NAS100_USDT')"))
        await pg.evaluate("() => document.getElementById('dlg').close()")
        # 4) charts page: categories and a MEXC index chart
        await pg.evaluate("() => goPage('charts')"); await asyncio.sleep(2)
        for cat in ["metals", "indices", "fx", "stocks"]:
            await pg.evaluate(f"() => {{ chPickClose(); chPickOpen('{cat}'); }}"); await asyncio.sleep(3)
            print(f"4) picker {cat}:", await pg.evaluate("() => [...document.querySelectorAll('#chPick .chprow, #chPick [data-s]')].slice(0, 6).map(x => x.innerText.replace(/\\s+/g,' ')).join(' || ') || document.querySelector('#chPick').innerText.slice(0,120)"))
        await pg.evaluate("() => { chPickClose(); chSetSym('MX:NAS100_USDT'); }"); await asyncio.sleep(5)
        print("   charts:", await pg.evaluate("() => chVis().map(P => P.sym + ' ' + P.tf + ' bars=' + (P.t ? P.t.length : '?') + (P.msg.hidden ? '' : ' MSG ' + P.msg.textContent)).join(' | ')"))
        print("   header:", await pg.evaluate("() => document.querySelector('.chbar').innerText.replace(/\\s+/g,' ').slice(0,80)"), "| streams:", await pg.evaluate("() => chStreams().join(', ')"))
        await pg.evaluate("() => chSetSym('MX:AAPLSTOCK_USDT')"); await asyncio.sleep(4)
        print("   stock chart:", await pg.evaluate("() => chName(CH.sym) + ' · ' + chVis().map(P => P.tf + ' bars=' + (P.t ? P.t.length : '?')).join(' ')"))
        await pg.screenshot(path="mxtf_charts.png")
        # 5) alert on a MEXC TradFi symbol
        r = await pg.evaluate("""async () => { WL.alerts.push({ sym: 'MX:XAU_USDT', price: 1, dir: 'above', at: Date.now() }); await checkPrices(); const a = WL.alerts.find(a => a.sym === 'MX:XAU_USDT'); return a && !!a.fired; }""")
        print("5) alert on MEXC gold fired:", r)
        # 6) backtest on MEXC gold + Nasdaq
        await pg.evaluate("() => goPage('backtest')")
        print("6) backtest TradFi list:", await pg.evaluate("() => btpTradfi().slice(0, 5).map(x => x.sym + ' ' + x.name + ' [' + x.group + ']').join(', ')"))
        await pg.evaluate("() => { BTP.syms = ['MX:XAU_USDT', 'MX:NAS100_USDT', 'MX:EUR_USDT']; }")
        await pg.select_option("#btCoins", "pick"); await pg.select_option("#btDays", "30")
        MX_RL["hits"] = 0; t0 = time.time(); await pg.click("#btRun")
        await waitfor(pg, "() => !btRunning && !!BT", 400)
        print(f"   backtest {time.time()-t0:.0f}s:", await pg.evaluate("() => BT.trades.length + ' trades on ' + [...new Set(BT.trades.map(t => t.sym || t.symbol))].join(', ')"), "| refusals", MX_RL["hits"])
        # 7) back to Binance: macro returns to Binance TradFi
        await pg.evaluate("() => goPage('overview')"); await pg.select_option("#exF", "binance")
        await waitfor(pg, "() => data && data.exchange === 'binance' && !document.getElementById('runBtn').disabled")
        await pg.evaluate("() => goPage('macro')"); await waitfor(pg, "() => !MACRO.running && MACRO.src === 'binance' && MACRO.rows.length && !MACRO.rows.some(r => r.mx)", 200)
        print("7) Binance macro:", await pg.evaluate("() => MACRO.rows.length + ' rows · ' + document.getElementById('macroMeta').textContent"))
        await pg.evaluate("() => goPage('charts')"); await pg.evaluate("() => chPickOpen('stocks')"); await asyncio.sleep(1)
        print("   stocks tab on Binance:", await pg.evaluate("() => document.getElementById('chPick').innerText.replace(/\\s+/g,' ').slice(-120)"))
        print("CSP:", csp or "none", "| errors:", errs or "none")
        await b.close()
asyncio.run(main())
