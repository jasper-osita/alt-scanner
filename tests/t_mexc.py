import asyncio, json, sys, time
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
async def waitfor(pg, js, secs=700):
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
        print("binance:", await pg.evaluate("() => data.exchange + ' ' + data.analysed"))
        # ---- MEXC futures
        t0 = time.time(); await pg.select_option("#exF", "mexc")
        ok = await waitfor(pg, "() => data && data.exchange === 'mexc' && !document.getElementById('runBtn').disabled")
        print(f"MEXC futures scan ok={ok} {time.time()-t0:.0f}s:", await pg.evaluate("() => data.analysed + ' coins · ' + data.env.label + ' · day ' + data.day.length + ' · swing ' + data.swing.length"))
        print("  title:", await pg.evaluate("() => document.getElementById('title').textContent"), "| status:", await pg.evaluate("() => document.getElementById('status').textContent.slice(0, 160)"))
        print("  OLD (delisted) present?", await pg.evaluate("() => !!bySym.OLDUSDT"), "| ZRO funding:", await pg.evaluate("() => bySym.ZROUSDT && bySym.ZROUSDT.funding"), "| BTC price:", await pg.evaluate("() => bySym.BTCUSDT && bySym.BTCUSDT.price"))
        print("  host paths hit:", sorted(set(p.split('/kline/')[0] for p in MX_LOG))[:12])
        await asyncio.sleep(8)
        print("  live:", await pg.evaluate("() => LIVE.kind + ' ' + (LIVE.ws && LIVE.ws.readyState) + ' subs=' + LIVE.subs.size"), "| ws methods:", sorted(set(m.get('method') for m in MXWS_LOG)), "n=", len(MXWS_LOG))
        print("  XRP after push:", await pg.evaluate("() => bySym.XRPUSDT.price + ' chg ' + bySym.XRPUSDT.chg24h + ' fund ' + bySym.XRPUSDT.funding"))
        r = await pg.evaluate("""async () => { const out = {};
          const now = Date.now();
          const k = await klinesRange('ETHUSDT', '1h', now - 3000 * 3600e3, now); out.range1h = k.t ? k.t.length : (k.length || JSON.stringify(k).slice(0,80));
          const k15 = await klinesRange('ETHUSDT', '15m', now - 5 * 86400e3, now); out.range15 = k15.t ? k15.t.length : (k15.length || 0);
          const f = await formingBar('ETHUSDT', '1h'); out.forming = f && { age_min: Math.round((now - f.t) / 60000), c: f.c };
          try { const s = await klinesSince('SOLUSDT', now - 50 * 3600e3, '1h', 200, 'MEXC', 'futures'); out.since = s && (s.t ? s.t.length : s.length); } catch (e) { out.since = 'ERR ' + e.message; }
          try { await checkPrices(); out.check = 'ok'; } catch (e) { out.check = 'ERR ' + e.message; }
          try { await klines('ETHUSDT', '3m', 10); out.k3m = 'no error?'; } catch (e) { out.k3m = e.message; }
          return out; }""")
        print("  data paths:", r)
        # coin dialog (drivers)
        sym = await pg.evaluate("() => (data.day[0] || data.swing[0] || data.all[0]).symbol")
        await pg.evaluate(f"() => openDetail('{sym}')"); await asyncio.sleep(2.5)
        print("  dialog:", sym, await pg.evaluate("() => document.getElementById('dlg').open"), "|", await pg.evaluate("() => (document.getElementById('dlgBody').innerText.match(/Funding[^\\n]*/) || ['no funding line'])[0].slice(0,100)"))
        print("  TradingView links:", await pg.evaluate("() => [...document.querySelectorAll('a[href*=tradingview]')].slice(0,2).map(a => a.href.split('symbol=')[1]).join(', ')"))
        await pg.evaluate("() => document.getElementById('dlg').open && document.getElementById('dlg').close()")
        # charts page
        await pg.evaluate("() => goPage('charts')"); await asyncio.sleep(4)
        print("  charts:", await pg.evaluate("() => chVis().map(P => P.sym + ' ' + P.tf + ' bars=' + (P.t ? P.t.length : '?') + ' last=' + (P.c ? (+P.c.at(-1)).toPrecision(6) : '') + (P.msg.hidden ? '' : ' MSG ' + P.msg.textContent)).join(' | ')"))
        print("  chart streams:", await pg.evaluate("() => chStreams().slice(0, 6).join(', ')"))
        await asyncio.sleep(3)
        print("  watchlist quotes:", await pg.evaluate("() => [...document.querySelectorAll('#chWL [data-sym]')].slice(0,3).map(x => x.innerText.replace(/\\s+/g,' ')).join(' || ')"))
        print("  WL text:", await pg.evaluate("() => document.getElementById('chWL').innerText.replace(/\\s+/g,' ').slice(0,200)"))
        print("  tvLink:", await pg.evaluate("() => tvLink('ARBUSDT')"))
        print("  ws kline -> chart:", await pg.evaluate("""() => { const P = chVis().find(P => P.tf === '15m'); const t = P.t.at(-1);
            liveMessage({ channel: 'push.kline', data: { symbol: 'BTC_USDT', interval: 'Min15', t: t / 1000, o: 1, h: 99999, l: 1, c: 12345 } });
            const a = P.c.at(-1);
            liveMessage({ channel: 'push.kline', data: { symbol: 'BTC_USDT', interval: 'Min15', t: t / 1000 + 900, o: 12345, h: 12400, l: 12300, c: 12350 } });
            return 'same candle c=' + a + ' | next candle: n ' + P.t.length + ' c=' + P.c.at(-1); }"""))
        await pg.screenshot(path="mexc_charts.png")
        # backtest
        await pg.evaluate("() => goPage('backtest')")
        await pg.select_option("#btDays", "30")
        try: await pg.select_option("#btCoins", "20")
        except Exception as e: print("  btCoins:", str(e)[:80])
        t0 = time.time(); await pg.click("#btRun")
        await waitfor(pg, "() => !btRunning && !!BT", 400)
        print(f"  backtest {time.time()-t0:.0f}s:", await pg.evaluate("() => BT.trades.length + ' trades · ' + (BT.ex || BT.exchange || '') + ' · ' + (document.querySelector('#backtest') || {}).innerText.slice(0, 160).replace(/\\s+/g, ' ')"))
        # ---- MEXC spot
        await pg.evaluate("() => goPage('overview')")
        MXWS_LOG.clear(); t0 = time.time(); await pg.select_option("#market", "spot")
        ok = await waitfor(pg, "() => data && data.exchange === 'mexc' && data.mode === 'spot' && !document.getElementById('runBtn').disabled")
        print(f"MEXC spot scan ok={ok} {time.time()-t0:.0f}s:", await pg.evaluate("() => data.analysed + ' coins · day ' + data.day.length + ' · swing ' + data.swing.length + ' · title ' + document.getElementById('title').textContent"))
        print("  C001 (futures-only) present?", await pg.evaluate("() => !!bySym.C001USDT"), "| live badge:", await pg.evaluate("() => document.getElementById('liveBadge').className + ' / ' + document.getElementById('liveBadge').title.slice(0, 80)"))
        r = await pg.evaluate("""async () => { const now = Date.now(); const out = {};
          const k = await klinesRange('ETHUSDT', '1h', now - 1500 * 3600e3, now); out.range1h = k.t ? k.t.length : k.length;
          const f = await formingBar('ETHUSDT', '4h'); out.forming4h = f && Math.round((now - f.t) / 60000) + 'min';
          try { await checkPrices(); out.check = 'ok'; } catch (e) { out.check = 'ERR ' + e.message; } return out; }""")
        print("  data paths:", r)
        await pg.evaluate("() => goPage('charts')"); await asyncio.sleep(4)
        print("  charts:", await pg.evaluate("() => chVis().map(P => P.sym + ' ' + P.tf + ' bars=' + (P.t ? P.t.length : '?') + ' last=' + (P.c ? (+P.c.at(-1)).toPrecision(6) : '') + (P.msg.hidden ? '' : ' MSG ' + P.msg.textContent)).join(' | ')"))
        # back to binance still works
        await pg.evaluate("() => goPage('overview')"); await pg.select_option("#exF", "binance")
        ok = await waitfor(pg, "() => data && data.exchange === 'binance' && !document.getElementById('runBtn').disabled")
        print("back to Binance:", ok, await pg.evaluate("() => data.analysed + ' ' + data.mode"))
        print("CSP:", csp or "none", "| errors:", errs or "none")
        await b.close()
asyncio.run(main())
