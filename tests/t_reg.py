import asyncio, json, sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1260, "height": 760}, color_scheme="dark", permissions=["notifications"]); await setup(ctx)
        pg = await ctx.new_page(); errs, csp = [], []
        pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: "Content Security Policy" in m.text and csp.append(m.text[:140]))
        WS = {"ws": None}
        def wsh(ws): WS["ws"] = ws; ws.on_message(lambda m: ws.send(json.dumps({"result": None, "id": json.loads(m).get("id")})) if "SUBSCRIBE" in m else None)
        await pg.route_web_socket("wss://fstream.binance.com/stream", wsh)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        for _ in range(40):
            if await pg.evaluate("() => LIVE.state === 'live'"): break
            await asyncio.sleep(0.25)
        print("1) live stream:", await pg.evaluate("() => LIVE.state"))
        sym = await pg.evaluate("() => document.querySelector('#tbody .lp').dataset.sym"); p0 = await pg.evaluate(f"() => bySym['{sym}'].price")
        await pg.evaluate(f"() => WL.alerts.push({{id:'x',sym:'{sym}',price:{p0}*1.02,dir:'above',created:Date.now(),fired:false}})")
        WS["ws"].send(json.dumps({"stream": "!miniTicker@arr", "data": [{"s": sym, "c": str(p0 * 1.03), "o": str(p0), "q": "1"}]})); await asyncio.sleep(1.5)
        print("2) live price + instant alert:", await pg.evaluate(f"() => bySym['{sym}'].price.toFixed(4) + ' fired=' + !!WL.alerts.find(a => a.id === 'x').fired"))
        print("3) session picks:", await pg.evaluate("() => Object.entries(sessionPicks()).map(([k, v]) => k + ' ' + v.length).join(', ')"), "| playbook top 3:", await pg.evaluate("() => (data.suggest || []).length"))
        await pg.evaluate(f"() => openDetail(data.all[2].symbol)"); await asyncio.sleep(1.8)
        print("4) panel:", await pg.evaluate("() => ({ canvas: document.querySelectorAll('#dChartHost canvas').length, rsiPane: CH.ind.some(I => I.type === 'rsi' && !I.hide), scrolls: document.getElementById('dlg').scrollHeight > document.getElementById('dlg').clientHeight + 2 })"))
        await pg.click('.dtabs [data-pane="size"]'); await pg.fill("#cAcct", "1000"); await asyncio.sleep(0.3)
        print("   size tab:", await pg.evaluate("() => document.querySelector('#cOut').innerText.split('\\n')[0]"))
        await pg.keyboard.press("Escape")
        await pg.evaluate("() => goPage('bots')"); await pg.click("#botRun"); await asyncio.sleep(1.5)
        print("5) bots:", await pg.evaluate("() => JSON.stringify(Object.fromEntries(BOT_STRATS().map(k => [k, BOT.bots[k].positions.length])))"))
        await pg.select_option("#dirF", "Short"); await asyncio.sleep(0.4)
        print("6) shorts only:", await pg.evaluate("() => [...new Set([...data.day.map(p => p.dir), ...data.swing.map(p => p.dir), ...(data.suggest || []).map(x => x.m.dir)])].join(',')"))
        await pg.select_option("#dirF", "Both")
        print("7) counter-trend guard: untriggered counters in top 3 =", await pg.evaluate("() => (data.suggest || []).filter(x => isCounter(x.r, x.m) && !x.m.trig).length"))
        print("8) app shell:", await pg.evaluate("() => navigator.serviceWorker.getRegistration().then(r => !!r)"), "| version", await pg.evaluate("() => APP_VERSION"))
        print("CSP:", csp or "none", "| errors:", errs or "none")
        await b.close()
asyncio.run(main())
