import asyncio, sys, re, json, hmac, hashlib
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
from urllib.parse import urlparse
OPTS = {"secret": "sec", "token": "tok", "live": True, "scope": "SCOPE_TRADE", "demo2": True, "names": True}   # names: enums by name, ids as strings, like the real feed
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
        await q("() => { const c = ctCfg(); c.scope = 'trading'; ctSaveCfg(c); goPage('charts'); chSetSym('CT:XAUUSD'); }"); await wait("() => chVis().length && chVis()[0].sym === 'CT:XAUUSD' && chVis()[0].t.length > 5", 30); await asyncio.sleep(1)
        await q("""() => { const P = chVis()[0], n = P.t.length, e = P.c.at(-1); CHD[CH.sym] = [{ id: 'pz', type: 'short', pts: [{ t: P.t[n - 5], p: e * 1.002 }, { t: P.t[n - 1], p: e * 1.012 }, { t: P.t[n - 1], p: e * 0.982 }], s: {} }]; chSaveDraw(); chDirty = true; }""")
        await wait("() => { const d = CHD[CH.sym][0]; return !!trPosSize(d, 0.5); }", 20)
        print("20) chart size:", await q("() => JSON.stringify(trPosSize(CHD[CH.sym][0], 0.5))"))
        n06 = [t for t, p in CT_TRADE["log"]].count(2106)
        await q("() => trFromPos(CHD[CH.sym][0])"); await wait("() => document.getElementById('tpSize') && +document.getElementById('tpSize').value > 0", 15)
        print("21) panel:", await q("() => [TR.posId, document.getElementById('tpVenue').innerText, document.getElementById('tpType').value, document.getElementById('tpSize').value, document.getElementById('tpLv').innerText.replace(/\\s+/g, ' ')]"))
        # the order list must not be rebuilt under you (it closed the list before you could pick Market or Stop)
        await q("() => { window._opt0 = document.getElementById('tpType').options[0]; }"); await asyncio.sleep(1.2)
        print("21b) list kept:", await q("() => document.getElementById('tpType').options[0] === window._opt0"), "| options:", await q("() => [...document.getElementById('tpType').options].map(o => o.value).join(',')"))
        t0 = await q("() => document.getElementById('tpType').value")
        for k in ("market", "stop"):
            await pg.select_option("#tpType", k); await asyncio.sleep(1.2)
            print(f"21c) picked {k}:", await q("() => document.getElementById('tpType').value"))
        await pg.select_option("#tpType", t0)
        print("21d) placed top-left:", await q("() => { const a = document.getElementById('trPosPanel').getBoundingClientRect(), p = chVis()[0].cv.getBoundingClientRect(); return [Math.round(a.left - p.left), Math.round(a.top - p.top), a.left >= p.left && a.left - p.left < 420 && a.top - p.top < 140]; }"))
        # drag the red stop line with the mouse: the size follows
        box = await q("() => { const P = chVis()[0], r = P.cv.getBoundingClientRect(), d = CHD[CH.sym][0]; return [r.left, r.top, chPlotW(P), chY(P, d.pts[1].p), chY(P, d.pts[0].p)]; }")
        x0 = box[0] + box[2] - 40; ys = box[1] + box[3]          # near the right edge, where the position sits (the order panel hovers top-left)
        hit = await q(f"() => JSON.stringify(chHitTest(chVis()[0], {box[2] - 40}, {box[3]}))"); s0 = await q("() => [CHD[CH.sym][0].pts[1].p, document.getElementById('tpSize').value]")
        await pg.mouse.move(x0, ys); await pg.mouse.down(); await pg.mouse.move(x0, ys - 25, steps=6); await pg.mouse.up(); await asyncio.sleep(1.2)
        s1 = await q("() => [CHD[CH.sym][0].pts[1].p, document.getElementById('tpSize').value, document.getElementById('tpLv').innerText.replace(/\\s+/g, ' ')]")
        print("22) drag stop line:", hit, "|", s0, "→", s1)
        await pg.screenshot(path=f"{OUT}/trade_chart.png")
        await q("() => document.getElementById('tpGo').click()"); print("22b) armed:", await q("() => document.getElementById('tpGo').innerText"))
        await q("() => document.getElementById('tpGo').click()"); await asyncio.sleep(1.5)
        sent2 = [p for t, p in CT_TRADE["log"] if t == 2106][-1]
        print("23) chart order:", [t for t, p in CT_TRADE["log"]].count(2106) - n06, {k: sent2.get(k) for k in ("tradeSide", "orderType", "limitPrice", "stopPrice", "stopLoss", "takeProfit", "volume")}, "| panel closed:", await q("() => !document.getElementById('trPosPanel') && TR.posId == null"))
        await wait("() => trChartOrders(CH.sym).length > 0", 10)
        print("23c) on the chart:", await q("() => trChartOrders(CH.sym).map(l => l.txt + ' @' + l.p).join(' | ')"))
        await q("() => { document.getElementById('chAcctPop').hidden = true; document.getElementById('chAcctBtn').click(); }"); await asyncio.sleep(0.5)
        print("23d) account menu:", await q("() => document.getElementById('chAcctPop').innerText.split('Open on this account')[1].split('Refresh')[0].trim()"))
        await q("() => { document.getElementById('chAcctPop').hidden = true; }")
        await pg.screenshot(path=f"{OUT}/trade_lines.png")
        # broker lines: drag the pending order, its SL, × to cancel; a market position: drag its line to add a stop, × to close
        BK = "() => JSON.stringify((chVis()[0].bk || []).map(b => [b.key.replace(/:\\d+:/, ':'), Math.round(b.y), b.xb && b.xb.map(Math.round)]))"
        await q("() => { CH.max = 0; chApplyLayout(); }"); await asyncio.sleep(1.5)
        print("40) hit list:", await q(BK))
        async def drag_line(role, kind, dy):
            bx = await q(f"() => {{ const P = chVis()[0], r = P.cv.getBoundingClientRect(), b = P.bk.find(b => b.key.startsWith('{kind}:') && b.key.endsWith(':{role}')); return b && [r.left, r.top, chPlotW(P), b.y]; }}")
            if not bx: return "no line"
            x = bx[0] + bx[2] * 0.6; y = bx[1] + bx[3]
            await pg.mouse.move(x, y); await pg.mouse.down(); await pg.mouse.move(x, y + dy, steps=6); await pg.mouse.up(); await asyncio.sleep(1.2)
            return "ok"
        n0 = len(CT_TRADE["log"])
        await drag_line("entry", "ord", 30)
        print("41) drag pending entry:", [(t, {k: v for k, v in p.items() if k in ("stopPrice", "limitPrice", "stopLoss", "takeProfit", "volume")}) for t, p in CT_TRADE["log"][n0:] if t == 2109], "| lines:", await q("() => trChartOrders(CH.sym).map(l => l.txt).join(' | ')"))
        n0 = len(CT_TRADE["log"]); await drag_line("sl", "ord", -20)
        print("42) drag pending SL:", [(t, p.get("stopLoss"), p.get("stopPrice")) for t, p in CT_TRADE["log"][n0:] if t == 2109])
        async def click_x(kind):
            ln = await q(f"() => {{ const P = chVis()[0], r = P.cv.getBoundingClientRect(), b = P.bk.find(b => b.key.startsWith('{kind}:') && b.key.endsWith(':entry')); return b && [r.left + 200, r.top + b.y]; }}")
            if ln: await pg.mouse.move(ln[0], ln[1]); await asyncio.sleep(0.3)
            bx = await q(f"() => {{ const P = chVis()[0], r = P.cv.getBoundingClientRect(), b = P.bk.find(b => b.key.startsWith('{kind}:') && b.xb); return b && [r.left + (b.xb[0] + b.xb[1]) / 2, r.top + b.y]; }}")
            if not bx: return "no ×"
            await pg.mouse.click(bx[0], bx[1]); await asyncio.sleep(0.3)
            armed = await q("() => !!(TW.arm && TW.arm.key)")
            bx = await q(f"() => {{ const P = chVis()[0], r = P.cv.getBoundingClientRect(), b = P.bk.find(b => b.key.startsWith('{kind}:') && b.xb); return b && [r.left + (b.xb[0] + b.xb[1]) / 2, r.top + b.y]; }}")
            await pg.mouse.click(bx[0], bx[1]); await asyncio.sleep(1.2); return armed
        await pg.screenshot(path=f"{OUT}/trade_bk.png")
        print("43) × cancel (armed first):", await click_x("ord"), "| 2108 sent:", [t for t, p in CT_TRADE["log"]].count(2108), "| orders left:", await q("() => CTT.orders.length"))
        await q("() => cttPlace({ x: cttSym(CH.sym), side: 'buy', type: 'market', lots: 1 })"); await wait("() => CTT.positions.length > 0", 10); await asyncio.sleep(0.6)
        n0 = len(CT_TRADE["log"]); await drag_line("entry", "pos", 40)
        print("44) drag position line down → SL:", [(t, p.get("stopLoss"), p.get("takeProfit")) for t, p in CT_TRADE["log"][n0:] if t == 2110], "| lines:", await q("() => trChartOrders(CH.sym).map(l => l.txt).join(' | ')"))
        n0 = len(CT_TRADE["log"]); await drag_line("entry", "pos", -40)
        print("45) drag up → TP (SL kept):", [(t, p.get("stopLoss"), p.get("takeProfit")) for t, p in CT_TRADE["log"][n0:] if t == 2110])
        hv = await q("() => { const P = chVis()[0], r = P.cv.getBoundingClientRect(), b = P.bk.find(b => /:(sl|tp)$/.test(b.key)); return b && [r.left + 200, r.top + b.y, b.key]; }")
        await pg.mouse.move(hv[0], hv[1] - 30); await asyncio.sleep(0.3); x_before = await q("() => chVis()[0].bk.filter(b => b.xb).length")
        await pg.mouse.move(hv[0], hv[1]); await asyncio.sleep(0.3)
        print("45a) hover a level: × before/after", x_before, await q("() => chVis()[0].bk.filter(b => b.xb).map(b => b.key.split(':').pop()).join()"), "| hovered:", await q("() => { const l = trChartOrders(CH.sym).find(l => l.key === TW.hover.key); return l && [l.txt, ...l.parts].join(' | '); }"))
        await pg.screenshot(path=f"{OUT}/trade_hover.png")
        n0 = len(CT_TRADE["log"])
        for _ in range(2):
            bx = await q("() => { const P = chVis()[0], r = P.cv.getBoundingClientRect(), b = P.bk.find(b => /:(sl|tp)$/.test(b.key) && b.xb); return b && [r.left + (b.xb[0] + b.xb[1]) / 2, r.top + b.y]; }")
            if bx: await pg.mouse.click(bx[0], bx[1]); await asyncio.sleep(0.6)
        await asyncio.sleep(0.6)
        print("45c) × on the level removes it:", [(t, p.get("stopLoss"), p.get("takeProfit")) for t, p in CT_TRADE["log"][n0:] if t in (2110, 2109)], "| lines:", await q("() => trChartOrders(CH.sym).map(l => l.txt).join(' ')"))
        print("45b) lines in the price area only:", await q("() => chVis().map(P => { const H = chPlotH(P), top = P.oscL && P.oscL.length ? P.oscL[0].top * H : H; return (P.bk || []).every(b => b.y <= top) + '/' + (P.bk || []).length; }).join(' ')"))
        await q("() => { CH.max = null; chApplyLayout(); }")
        # trade watch
        await asyncio.sleep(1.2)
        TWQ = "() => [document.querySelector('#trWatch .trwtabs').innerText.replace(/\\s+/g, ' '), document.getElementById('twSum').innerText, [...document.querySelectorAll('#twBody th')].map(t => t.innerText).join('|'), [...document.querySelectorAll('#twBody tbody tr')].slice(0, 3).map(r => r.innerText.replace(/\\s+/g, ' ')).join(' // ')]"
        print("46) watch positions:", await q(TWQ))
        await q("() => document.querySelector('[data-twt=\"hist\"]').click()"); await wait("() => !TW.histBusy && TW.histAt", 10); await asyncio.sleep(1.2)
        print("47) watch history:", await q(TWQ))
        await q("() => { document.getElementById('twColBtn').click(); }"); await asyncio.sleep(0.2)
        await q("() => { const c = document.querySelector('[data-twc=\"gross\"]'); c.checked = true; c.dispatchEvent(new Event('change')); const d = document.querySelector('[data-twc=\"pips\"]'); d.checked = false; d.dispatchEvent(new Event('change')); }"); await asyncio.sleep(0.3)
        print("48) columns: +Gross −Pips:", await q("() => [...document.querySelectorAll('#twBody th')].map(t => t.innerText).join('|')"), "| saved:", await q("() => JSON.stringify(TWS().cols)"))
        await pg.screenshot(path=f"{OUT}/trade_watch.png")
        await q("() => document.querySelector('[data-twt=\"pos\"]').click()"); await asyncio.sleep(0.4)
        for _ in range(2): await q("() => document.querySelector('#twBody [data-twx]').click()"); await asyncio.sleep(0.5)
        await asyncio.sleep(1); print("49) watch Close (Sure? then close):", [t for t, p in CT_TRADE["log"]].count(2111), "| positions:", await q("() => CTT.positions.length"))
        print("24) toolbar button:", await q("() => { chSel = 'pz'; chSelBar(); return !!document.querySelector('#chFloat [data-fl=\"trade\"]'); }"), "| menu:", await q("() => chMoreItems(CHD[CH.sym][0]).map(x => x.l).filter(Boolean).slice(0, 2).join(', ')"))
        # account size: synced from the account by default, or typed (manual); the risk % stays, the size follows the stop
        d0 = "CHD[CH.sym][0]"
        await q(f"() => {{ TPS.clear(); chDirty = true; chDrawSettings({d0}); }}"); await asyncio.sleep(1.5)
        print("25) synced:", await q("() => [[...document.querySelectorAll('[data-am]')].map(b => b.innerText + (b.classList.contains('on') ? '*' : '')).join('/'), (document.getElementById('chAmV') || {}).innerText]"))
        sz = lambda: q(f"() => {{ const d = {d0}, s = chDS(d); const v = trPosSize(d, s.risk > 0 ? s.risk : trCfg().risk, s.am === 'manual' ? +s.acct || 0 : 0); return v && [v.qty, v.src, +v.bal.toFixed(2), +v.risk.toFixed(2)]; }}")
        a1 = await sz()
        await q("() => document.querySelector('[data-am=\"manual\"]').click()"); await asyncio.sleep(0.3)
        await pg.fill("[data-n='acct']", "50000"); await asyncio.sleep(0.3); await pg.fill("[data-n='risk']", "1"); await asyncio.sleep(0.3)
        await wait(f"() => {{ const c = TPS.get({d0}.id); return c && c.val && c.val.src === 'manual'; }}", 10); a2 = await sz()
        await q(f"() => {{ const d = {d0}; d.pts[1] = {{ t: d.pts[1].t, p: d.pts[0].p + (d.pts[1].p - d.pts[0].p) * 2 }}; chDirty = true; }}"); await asyncio.sleep(0.2); await sz(); await asyncio.sleep(1); a3 = await sz()
        print("26) sync → manual 50,000 @1% → stop twice as far:", a1, "→", a2, "→", a3, "| label:", await q(f"() => chDS({d0}).am"))
        await q("() => document.querySelector('[data-am=\"sync\"]').click()"); await asyncio.sleep(1.5); print("27) back to sync:", await sz(), "| balance row:", await q("() => (document.getElementById('chAmV') || {}).innerText"))
        await pg.screenshot(path=f"{OUT}/trade_acct.png")
        # reward:risk lock: the target follows the stop at the locked ratio
        await q("() => { $('dlg').open && $('dlg').close(); }")
        R = "(() => { const d = CHD[CH.sym][0], [e, s, t] = d.pts.map(x => x.p); return +((t - e) / (e - s)).toFixed(3); })()"
        print("33) lock 1:2:", await q(f"() => {{ const d = CHD[CH.sym][0]; chRRSet(d, 2); const a = {R}; chPosDrag(d, 1, {{ t: d.pts[1].t, p: d.pts[0].p * 1.02 }}); const b = {R}; chPosDrag(d, 0, {{ t: d.pts[0].t, p: d.pts[0].p * 0.995 }}); return [a, b, {R}, chDS(d).rr]; }}"))
        print("34) drag target to ~3.2R:", await q(f"() => {{ const d = CHD[CH.sym][0], e = d.pts[0].p, s = d.pts[1].p; chPosDrag(d, 2, {{ t: d.pts[2].t, p: e + 3.2 * (e - s) }}); return [chDS(d).rr, {R}]; }}"))
        await q("() => chDrawSettings(CHD[CH.sym][0])"); await asyncio.sleep(0.5)
        await q("() => document.querySelector('[data-rr=\"1\"]').click()"); r1 = await q(f"() => [{R}, [...document.querySelectorAll('[data-rr]')].map(b => b.innerText + (b.classList.contains('on') ? '*' : '')).join(' ')]")
        await pg.fill("[data-rrv]", "2.5"); await pg.press("[data-rrv]", "Enter"); await asyncio.sleep(0.2)
        print("35) settings: 1:1 →", r1, "| custom 2.5 →", await q(f"() => [{R}, chDS(CHD[CH.sym][0]).rr]"))
        await pg.screenshot(path=f"{OUT}/trade_rr.png")
        await q("() => { $('dlg').open && $('dlg').close(); document.querySelector('.chdsbox') && document.querySelector('.chdsbox').remove(); }")
        await q("() => trFromPos(CHD[CH.sym][0])"); await wait("() => document.querySelector('#tpRR [data-rr]')", 10)
        await q("() => document.querySelector('#tpRR [data-rr=\"3\"]').click()"); await asyncio.sleep(0.5)
        box = await q("() => { const P = chVis()[0], r = P.cv.getBoundingClientRect(), d = CHD[CH.sym][0]; return [r.left, r.top, chPlotW(P), chY(P, d.pts[1].p)]; }")
        x0 = box[0] + box[2] - 260; ys = box[1] + box[3]
        await pg.mouse.move(x0, ys); await pg.mouse.down(); await pg.mouse.move(x0, ys - 30, steps=6); await pg.mouse.up(); await asyncio.sleep(0.8)
        print("36) panel 1:3, drag stop line:", await q(f"() => [{R}, document.getElementById('tpLv').innerText.replace(/\\s+/g, ' '), [...document.querySelectorAll('#tpRR [data-rr]')].filter(b => b.classList.contains('on')).map(b => b.innerText).join()]"))
        await q("() => { trPosClose(); chRRSet(CHD[CH.sym][0], 0); }")
        # adaptive: dragging the stop past the entry flips short ↔ long
        st = "(() => { const d = CHD[CH.sym][0], [e, s, t] = d.pts.map(x => x.p); return [d.type, s < e ? 'stop below' : 'stop above', t > e ? 'target above' : 'target below', +(Math.abs(t - e) / Math.abs(e - s)).toFixed(2)]; })()"
        print("37) flip unlocked:", await q(f"() => {{ const d = CHD[CH.sym][0]; const a = {st}; chPosDrag(d, 1, {{ t: d.pts[1].t, p: d.pts[0].p * 0.99 }}); const b = {st}; chRRSet(d, 2); chPosDrag(d, 1, {{ t: d.pts[1].t, p: d.pts[0].p * 1.01 }}); return JSON.stringify([a, b, {st}]); }}"))
        print("38) draw a short with the stop below:", await q("() => { const d = { id: 'tmp', type: 'short', pts: [{ t: 1, p: 100 }, { t: 2, p: 98 }], s: {} }; chPosFinish(d, chVis()[0]); return [d.type, d.pts.map(x => +x.p.toFixed(2))].join(' '); }"))
        await q("() => trFromPos(CHD[CH.sym][0])"); await wait("() => document.getElementById('tpHead')", 10); h0 = await q("() => document.getElementById('tpHead').innerText")
        box = await q("() => { const P = chVis()[0], r = P.cv.getBoundingClientRect(), d = CHD[CH.sym][0]; return [r.left, r.top, chPlotW(P), chY(P, d.pts[1].p), chY(P, d.pts[0].p)]; }")
        x0 = box[0] + box[2] - 260
        await pg.mouse.move(x0, box[1] + box[3]); await pg.mouse.down(); await pg.mouse.move(x0, box[1] + box[4] + (box[4] - box[3]), steps=8); await pg.mouse.up(); await asyncio.sleep(1)
        print("39) panel, drag stop across entry:", h0, "→", await q(f"() => [document.getElementById('tpHead').innerText, document.getElementById('tpGo').className, JSON.stringify({st})]"))
        await q("() => { trPosClose(); chRRSet(CHD[CH.sym][0], 0); }")
        # account picker on the chart toolbar
        await q("() => { $('dlg').open && $('dlg').close(); document.querySelectorAll('.chdsbox,.chdrawdlg').forEach(x => x.remove()); }"); await asyncio.sleep(1.2)
        print("28) chip:", await q("() => document.getElementById('chAcctBtn').innerText.replace(/\\s+/g, ' ')"))
        await q("() => document.getElementById('chAcctBtn').click()"); await asyncio.sleep(0.5)
        print("29) menu:", await q("() => [...document.querySelectorAll('#chAcctPop .chacctrow')].map(b => b.innerText.replace(/\\s+/g, ' ') + (b.classList.contains('on') ? '*' : '') + (b.disabled ? '(off)' : '')).join(' | ')"))
        await pg.screenshot(path=f"{OUT}/trade_acctmenu.png")
        print("29b) toggle:", await q("() => [...document.querySelectorAll('#chAcctPop [data-ag]')].map(b => b.innerText.replace(/\\s+/g, ' ') + (b.disabled ? '(none)' : '')).join(' | ')"))
        await q("() => document.querySelector('#chAcctPop [data-ag=\"off\"]:not(:disabled)')?.click()"); await asyncio.sleep(0.2)
        print("29c) inactive open:", await q("() => [...document.querySelectorAll('#chAcctPop .chacctlist .chacctrow')].map(b => b.innerText.replace(/\\s+/g, ' ') + (b.disabled ? '(off)' : '')).join(' | ')"))
        await q("() => { trSave({ ...trCfg(), live: true }); TRA.open = 'on'; trAcctPop(); }"); await asyncio.sleep(0.3)
        other = await q("() => { const b = [...document.querySelectorAll('#chAcctPop .chacctrow')].find(b => !b.classList.contains('on') && !b.disabled); if (!b) return null; b.click(); return b.dataset.acct; }")
        await wait(f"() => CTT.state === 'ready' && String(CTT.acct.ctidTraderAccountId) === '{other}'", 15)
        await asyncio.sleep(1.5)
        print("30) switched to", other, ":", await q("() => [String(CTT.acct.ctidTraderAccountId), trCfg().acct, document.getElementById('chAcctTxt').innerText, trPosAcct(CHD[CH.sym][0])]"))
        await q("() => { trSave({ ...trCfg(), live: false, acct: null }); }")
        await q("() => { const c = ctCfg(); c.scope = 'accounts'; ctSaveCfg(c); cttClose(); CTT.state = 'off'; TPS.clear(); chDirty = true; }"); await asyncio.sleep(2.5)
        print("31) read-only sign-in:", await q("() => [document.getElementById('chAcctTxt').innerText, trPosAcct(CHD[CH.sym][0])]"))
        await q("() => { document.getElementById('chAcctPop').hidden = true; document.getElementById('chAcctBtn').click(); }"); await asyncio.sleep(0.4)
        print("32) menu read-only:", await q("() => document.getElementById('chAcctPop').innerText.replace(/\\s+/g, ' ').slice(0, 160)"))
        # price scale menu in the bottom-right corner
        sb = await q("() => { const b = document.getElementById('chScB0'), r = b.getBoundingClientRect(), P = chVis()[0]; return [Math.round(r.width), Math.round(r.height), Math.round(P.chart.priceScale('right').width()), Math.round(P.chart.timeScale().height())]; }")
        await q("() => document.getElementById('chScB0').click()"); await asyncio.sleep(0.3)
        print("50) scale button", sb, "menu:", await q("() => [...document.querySelectorAll('#chMenu button')].map(b => b.innerText.replace(/\\s+/g, ' ').trim()).join(' | ')"))
        await pg.screenshot(path=f"{OUT}/trade_scale.png")
        await q("() => document.querySelector('#chMenu [data-mk=\"m1\"]').click()"); await asyncio.sleep(0.3)
        await q("() => { document.getElementById('chScB0').click(); }"); await asyncio.sleep(0.2); await q("() => document.querySelector('#chMenu [data-mk=\"bidAsk\"]').click()"); await asyncio.sleep(1.5)
        print("51) log + bid/ask:", await q("() => { const P = chVis()[0], o = P.chart.priceScale('right').options(); return [o.mode, o.invertScale, !!P._babid, chCS().bidAsk]; }"))
        await q("() => { CH.cs = { ...CH.cs, scMode: 0, bidAsk: false }; chApplyCSAll(); }")
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
