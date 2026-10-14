import asyncio, sys, re, json, hmac, hashlib
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
from urllib.parse import urlparse
OPTS = {"secret": "sec", "token": "tok", "live": True, "scope": "SCOPE_TRADE", "demo2": True}
OUT = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "out")
MX = {"pos": [], "orders": [], "log": [], "badsig": 0}
async def mexc_priv(route):
    rq = route.request; u = urlparse(rq.url); h = rq.headers
    signed = u.query if rq.method == "GET" else (rq.post_data or "")
    good = hmac.new(b"ms", (h.get("apikey", "") + h.get("request-time", "") + signed).encode(), hashlib.sha256).hexdigest()
    if h.get("signature") != good: MX["badsig"] += 1; return await route.fulfill(status=200, content_type="application/json", body=json.dumps({"success": False, "code": 602, "message": "Signature verification failed"}))
    path = u.path.replace("/proxy/mexc-priv", ""); d = None
    if path.endswith("/position/open_positions"): d = MX["pos"]
    elif path.endswith("/account/asset/USDT"): d = {"currency": "USDT", "equity": 100000, "availableBalance": 90000}
    elif "/order/list/open_orders" in path: d = MX["orders"]
    elif path.endswith("/order/create"):
        b = json.loads(rq.post_data); MX["log"].append(b)
        if b["side"] in (1, 3): MX["pos"].append({"positionId": 70 + len(MX["pos"]), "symbol": b["symbol"], "positionType": 1 if b["side"] == 1 else 2, "holdVol": b["vol"], "holdAvgPrice": b["price"], "leverage": b.get("leverage"), "openType": b["openType"]})
        else: MX["pos"] = [p for p in MX["pos"] if p["positionId"] != b.get("positionId")]
        d = {"orderId": "mx" + str(len(MX["log"])), "ts": 1}
    await route.fulfill(status=200, content_type="application/json", body=json.dumps({"success": True, "code": 0, "data": d}))
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1500, "height": 1000}, color_scheme="dark"); await setup(ctx); await setup_mexc(ctx)
        await ctx.route(re.compile(r".*/proxy/mexc-priv/.*"), mexc_priv)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e) + " @ " + (e.stack or "")[:300]))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.route_web_socket("wss://contract.mexc.com/edge", mx_ws_handler)
        await pg.route_web_socket(re.compile(r"wss://(live|demo)\.ctraderapi\.com:5036.*"), ct_handler(OPTS))
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => { localStorage.clear(); localStorage.setItem('finder-ctrader', JSON.stringify({ clientId: 'cid', clientSecret: 'sec', accessToken: 'tok' })); localStorage.setItem('finder-mexc-trade', JSON.stringify({ key: 'mk', secret: 'ms' })); }"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        async def wait(js, secs=60):
            for _ in range(secs * 4):
                if await q(js): return True
                await asyncio.sleep(0.25)
            return False
        await q("() => { document.getElementById('exF').value = 'mexc'; goPage('macro'); macroScan(true); }")
        print("loaded:", await wait("() => !MACRO.running && MACRO.rows.some(r => r.ct)", 200))
        await q("() => openTrade('CT:XAUUSD')")
        print("1) venue:", await wait("() => CTT.state === 'ready'"), await q("() => document.getElementById('trVenue').innerText"), "| nav:", await q("() => document.querySelector('.nav.on').innerText.trim()"))
        await wait("() => !!(CTT.spots[cttSym('CT:XAUUSD').symbolId] || {}).bid", 10)
        e = await q("() => trEntry()"); print("2) quote:", await q("() => document.getElementById('trQuote').innerText"))
        await pg.fill("#trSL", str(round(e * 1.01, 2)))
        print("3) wrong-side stop:", await q("() => [document.getElementById('trWarn').innerText, document.getElementById('trGo').disabled]"))
        await pg.fill("#trSL", str(round(e * 0.99, 2))); await pg.fill("#trTP", str(round(e * 1.02, 2))); await pg.fill("#trRisk", "0.5")
        await pg.click("#trRiskBtn"); await asyncio.sleep(1)
        print("4) sized:", await q("() => [document.getElementById('trSize').value, document.getElementById('trSizeNote').innerText, document.getElementById('trRR').innerText, document.getElementById('trGo').innerText]"))
        await pg.click("#trGo"); print("5) armed:", await q("() => document.getElementById('trGo').innerText")); n0 = len(CT_TRADE["log"])
        await pg.click("#trGo"); await wait("() => CTT.positions.length > 0", 10); await asyncio.sleep(1)
        sent = [p for t, p in CT_TRADE["log"] if t == 2106][-1]
        print("6) sent:", {k: sent.get(k) for k in ("ctidTraderAccountId", "orderType", "tradeSide", "volume", "relativeStopLoss", "relativeTakeProfit")})
        print("7) book:", await q("() => document.getElementById('trBook').innerText.replace(/\\s+/g, ' ').slice(0, 220)"))
        await q("() => { const r = document.querySelector('#trBook tr[data-ct] [data-k=\"sl\"]'); r.value = '123.45'; }")
        for _ in range(2): await q("() => document.querySelector('#trBook tr[data-ct] [data-a=\"amend\"]').click()"); await asyncio.sleep(0.4)
        await asyncio.sleep(0.8); print("8) amend:", [p for t, p in CT_TRADE["log"] if t == 2110][-1:])
        for _ in range(2): await q("() => document.querySelector('#trBook tr[data-ct] [data-a=\"close\"]').click()"); await asyncio.sleep(0.4)
        await wait("() => CTT.positions.length === 0", 10); print("9) closed:", [t for t, p in CT_TRADE["log"]].count(2111), await q("() => document.getElementById('trBook').innerText.replace(/\\s+/g, ' ').slice(0, 80)"))
        # pending limit order with absolute stop/target, then cancel
        await q("() => { TR.type = 'limit'; trRender(); }"); await pg.fill("#trPrice", str(round(e * 0.995, 2))); await pg.fill("#trSL", str(round(e * 0.985, 2))); await pg.fill("#trTP", "")
        await pg.fill("#trSize", "0.1"); await pg.click("#trGo"); await pg.click("#trGo"); await wait("() => CTT.orders.length > 0", 10)
        lim = [p for t, p in CT_TRADE["log"] if t == 2106][-1]; print("10) limit:", {k: lim.get(k) for k in ("orderType", "limitPrice", "stopLoss", "volume")})
        for _ in range(2): await q("() => document.querySelector('#trBook tr[data-cto] [data-a=\"cancel\"]').click()"); await asyncio.sleep(0.4)
        await wait("() => CTT.orders.length === 0", 10); print("11) cancelled:", [t for t, p in CT_TRADE["log"]].count(2108))
        # read-only sign-in is caught
        OPTS["scope"] = "SCOPE_VIEW"; await q("() => { cttClose(); CTT.state = 'off'; return cttConnect().catch(e => window.__te = e.message); }"); await asyncio.sleep(1)
        print("12) read-only token:", await q("() => [window.__te, !!document.getElementById('trScope') || 'n/a']")); OPTS["scope"] = "SCOPE_TRADE"
        # live accounts stay off until allowed
        print("13) live off:", await q("() => { trSettings(); const o = [...document.querySelectorAll('#tsAcct option')].map(x => x.textContent + (x.disabled ? ' (off)' : '')); document.getElementById('dlg').close(); return o; }"))
        # MEXC futures
        await q("() => { cttClose(); CTT.state = 'off'; openTrade('BTCUSDT'); TR.type = 'market'; trRender(); }"); await asyncio.sleep(1.5)
        print("14) mexc venue:", await q("() => [trVenue(TR.sym), document.getElementById('trVenue').innerText, document.getElementById('trMx').hidden, document.getElementById('trUnit').innerText]"))
        e2 = await q("() => trEntry()"); await pg.fill("#trSL", str(round(e2 * 0.98, 2))); await pg.fill("#trTP", "")
        await q("() => document.getElementById('trRiskBtn').click()"); await asyncio.sleep(1.5); print("15) mexc size:", await q("() => [document.getElementById('trSize').value, document.getElementById('trSizeNote').innerText]"))
        await pg.fill("#trLev", "5"); await q("() => document.getElementById('trGo').click()"); await asyncio.sleep(0.2); await q("() => document.getElementById('trGo').click()"); await wait("() => MXT.positions.length > 0", 10)
        print("16) mexc order:", {k: MX["log"][-1].get(k) for k in ("symbol", "side", "type", "vol", "leverage", "openType", "stopLossPrice")}, "| bad signatures:", MX["badsig"])
        print("17) mexc book:", await q("() => document.getElementById('trBook').innerText.replace(/\\s+/g, ' ').slice(0, 200)"))
        for _ in range(2): await q("() => document.querySelector('#trBook tr[data-mx] [data-a=\"mxclose\"]').click()"); await asyncio.sleep(0.4)
        await wait("() => MXT.positions.length === 0", 10); print("18) mexc close:", {k: MX["log"][-1].get(k) for k in ("side", "type", "vol", "positionId")})
        print("19) activity:", await q("() => document.getElementById('trLog').innerText.split('\\n').slice(0, 4).join(' | ')"))
        await pg.screenshot(path=f"{OUT}/trade.png")
        # trade straight from a Short position drawn on the chart: sized from the account and risk %
        await q("() => { const c = ctCfg(); c.scope = 'trading'; ctSaveCfg(c); goPage('charts'); chSetSym('CT:XAUUSD'); }"); await asyncio.sleep(4)
        await q("""() => { const P = chVis()[0], n = P.t.length, e = P.c.at(-1); CHD[CH.sym] = [{ id: 'pz', type: 'short', pts: [{ t: P.t[n - 5], p: e * 1.002 }, { t: P.t[n - 1], p: e * 1.012 }, { t: P.t[n - 1], p: e * 0.982 }], s: {} }]; chSaveDraw(); chDirty = true; }""")
        await wait("() => { const d = CHD[CH.sym][0]; return !!trPosSize(d, 0.5); }", 20)
        print("20) chart size:", await q("() => JSON.stringify(trPosSize(CHD[CH.sym][0], 0.5))"))
        n06 = [t for t, p in CT_TRADE["log"]].count(2106)
        await q("() => trFromPos(CHD[CH.sym][0])"); await wait("() => document.getElementById('tpSize') && +document.getElementById('tpSize').value > 0", 15)
        print("21) dialog:", await q("() => [document.getElementById('tpVenue').innerText, document.getElementById('tpType').value, [...document.getElementById('tpType').options].map(o => o.text).join(' | '), document.getElementById('tpSize').value, document.getElementById('tpNote').innerText]"))
        await pg.screenshot(path=f"{OUT}/trade_chart.png")
        await q("() => document.getElementById('tpGo').click()"); print("22) armed:", await q("() => document.getElementById('tpGo').innerText"))
        await q("() => document.getElementById('tpGo').click()"); await asyncio.sleep(1.5)
        sent2 = [p for t, p in CT_TRADE["log"] if t == 2106][-1]
        print("23) chart order:", [t for t, p in CT_TRADE["log"]].count(2106) - n06, {k: sent2.get(k) for k in ("tradeSide", "orderType", "limitPrice", "stopLoss", "takeProfit", "volume")}, "| modal closed:", await q("() => !document.getElementById('chModBg')"))
        print("24) toolbar button:", await q("() => { chSel = 'pz'; chSelBar(); return !!document.querySelector('#chFloat [data-fl=\"trade\"]'); }"), "| menu:", await q("() => chMoreItems(CHD[CH.sym][0]).map(x => x.l).filter(Boolean).slice(0, 2).join(', ')"))
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
