"""TradingView-style chart extras: chart types, chart alerts, bar replay, compare, object tree, data window, snapshot, scripts."""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "finder")
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1600, "height": 950}, color_scheme="dark"); await setup(ctx)
        pg = await ctx.new_page(); errs, csp = [], []
        pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: ("Content Security Policy" in m.text and csp.append(m.text[:140])) or (m.type == "error" and "Failed to load resource" not in m.text and errs.append("console: " + m.text[:160])))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        await pg.click('#side [data-go="charts"]')
        for _ in range(60):
            if await q("() => CHP.length === 4 && CHP.every(P => P.t.length > 0)"): break
            await asyncio.sleep(0.25)
        # ---- chart types
        await pg.click("#chTypeBtn"); print("1) type menu:", await q("() => [...document.querySelectorAll('#chMenu [data-mk]')].map(b => b.dataset.mk + (b.classList.contains('on') ? '*' : '')).join(' ')"))
        for k in ["hollow", "ha", "bars", "line", "area", "base", "candles"]:
            if await q("() => !!document.getElementById('chMenu')"): await pg.click(f'#chMenu [data-mk="{k}"]')
            else: await q(f"() => chSetType('{k}')")
            await asyncio.sleep(0.15)
            print(f"   {k}:", await q("() => CHP.map(P => P.cs.seriesType() + ':' + P.cs.data().length + '/' + P.t.length).join(' ')"),
                  "| legend:", await q("() => document.getElementById('chLeg1').innerText.replace(/\\s+/g, ' ').slice(0, 90)"))
            if k == "ha": print("   HA check (o = avg prev o/c, c = ohlc/4):", await q("() => { const P = CHP[1], a = P.ha, i = 100, d = P.cs.data()[i]; return Math.abs(a.o[i] - (a.o[i-1] + a.c[i-1]) / 2) < 1e-9 && Math.abs(a.c[i] - (P.o[i] + P.h[i] + P.l[i] + P.c[i]) / 4) < 1e-9 && d.close === a.c[i]; }"))
            if k == "base": await pg.screenshot(path=f"{OUT}/tvx_base.png")
        await q("() => chSetType('ha')"); await q("() => { const P = CHP[1], n = P.t.length; chBar(P, { t: P.t[n - 1], o: P.o[n - 1], h: P.h[n - 1] * 1.01, l: P.l[n - 1], c: P.h[n - 1] * 1.005, v: 1 }); }")
        print("   HA live bar:", await q("() => { const P = CHP[1], n = P.t.length, d = P.cs.data().at(-1); return d.close === P.ha.c[n - 1] && P.ha.c.length === n; }"))
        await pg.reload(); await ready(pg); await pg.click('#side [data-go="charts"]')
        for _ in range(60):
            if await q("() => typeof CHP !== 'undefined' && CHP.length === 4 && CHP.every(P => P.t.length > 0)"): break
            await asyncio.sleep(0.25)
        print("   after reload:", await q("() => CH.ctype + ' ' + CHP.map(P => P.csType + ':' + P.cs.seriesType()).join(',')"))
        await q("() => chSetType('candles')")
        # ---- chart alerts
        await q("() => { CHP.forEach(P => P.userAt = 0); CHP[1].userAt = Date.now(); }")
        await pg.click("#chAlertBtn"); await asyncio.sleep(0.2)
        print("2) alert dialog:", await q("() => document.querySelector('.chmal h3').textContent + ' | when: ' + [...document.querySelectorAll('#chaL option')].map(o => o.textContent).join(' / ').slice(0, 160) + ' | trig: ' + [...document.querySelectorAll('#chaT option')].map(o => o.textContent).join(', ')"))
        await pg.select_option("#chaL", index=0); await pg.select_option("#chaOp", "up"); await pg.fill("#chaV", str(await q("() => +(CHP[1].c.at(-1) * 1.002).toFixed(2)"))); await pg.fill("#chaMsg", "BTC breakout"); await pg.click("#chaOk"); await asyncio.sleep(0.3)
        print("   created:", await q("() => CHA.map(a => a.sym + ' ' + a.tf + ' ' + chaDesc(a) + ' ' + a.trig + ' msg=' + a.msg).join(' | ')"), "| line on 1H:", await q("() => (CHP[1].alLines || []).length"))
        await asyncio.sleep(3.5)   # first check stores the crossing state
        nc0 = await q("() => NC.length")
        await q("() => { const P = CHP[1], n = P.t.length; chBar(P, { t: P.t[n - 1], o: P.o[n - 1], h: P.c[n - 1] * 1.006, l: P.l[n - 1], c: P.c[n - 1] * 1.005, v: 1 }); }")
        await asyncio.sleep(3.5)
        print("   after price crossed:", await q(f"() => 'on ' + CHA[0].on + ' fired ' + !!CHA[0].fired + ' | bell: ' + NC.slice(0, NC.length - {nc0}).map(n => n.title + ' / ' + n.detail + ' / ' + n.action).join(' ; ')"), "| line gone:", await q("() => (CHP[1].alLines || []).length === 0"))
        # indicator alert: RSI greater than 0, once per bar
        await q("() => { const P = CHP[1], o = chaIndOpts(P); window.__o = o.map(x => x.l); const r = o.find(x => x.src.type === 'rsi'); chaAdd({ sym: chPS(P), tf: P.tf, L: r.src, op: 'gt', R: { k: 'val', v: 1 }, trig: 'bar' }); }")
        print("   indicator lines offered:", await q("() => __o.join(' / ').slice(0, 200)"))
        await asyncio.sleep(7)
        print("   RSI > 1 (once per bar):", await q("() => { const a = CHA.at(-1); return 'n ' + a.n + ' on ' + a.on + ' bar ' + (a.bar === CHP[1].t.at(-1)); }"))
        # a horizontal line alert from the drawing menu
        await q("() => { const P = CHP[1], px = P.c.at(-1) * 0.995; CHD[CH.sym] = CHD[CH.sym] || []; CHD[CH.sym].push({ id: 'hl1', type: 'hline', pts: [{ t: P.t.at(-5), p: px }], s: {} }); chSel = 'hl1'; chSelPane = 1; chDirty = true; }")
        print("   drawing menu has alert:", await q("() => chMoreItems(CHD[CH.sym].find(d => d.id === 'hl1')).some(x => x.k === 'alert')"))
        await q("() => chMoreDo('alert', CHD[CH.sym].find(d => d.id === 'hl1'))"); await asyncio.sleep(0.2)
        print("   dialog for the line:", await q("() => document.querySelector('#chaR').selectedOptions[0].textContent + ' | value box hidden ' + document.getElementById('chaV').hidden"))
        await pg.select_option("#chaOp", "down"); await pg.click("#chaOk"); await asyncio.sleep(3.5)
        await q("() => { const P = CHP[1], n = P.t.length; chBar(P, { t: P.t[n - 1], o: P.o[n - 1], h: P.h[n - 1], l: P.c[n - 1] * 0.98, c: P.c[n - 1] * 0.985, v: 1 }); }"); await asyncio.sleep(3.5)
        print("   line alert:", await q("() => { const a = CHA.find(x => x.R.k === 'draw'); return chaDesc(a) + ' | fired ' + !!a.fired + ' on ' + a.on; }"))
        # right-click menu
        box = await pg.locator("#chCv1").bounding_box(); await pg.mouse.click(box["x"] + box["width"] * 0.4, box["y"] + box["height"] * 0.3, button="right"); await asyncio.sleep(0.2)
        print("   right-click:", await q("() => [...document.querySelectorAll('#chMenu [data-mk]')].map(b => b.innerText.replace(/\s+/g, ' ')).slice(0, 3).join(' | ')"))
        await pg.click('#chMenu [data-mk="alq"]'); await asyncio.sleep(0.3)
        print("   quick alert:", await q("() => chaDesc(CHA.at(-1)) + ' ' + CHA.at(-1).trig + ' | lines on 4 panes ' + CHP.map(P => (P.alLines || []).length).join(',')"))
        # the list
        await q("() => chaList()"); await asyncio.sleep(0.2)
        print("   list:", await q("() => [...document.querySelectorAll('#chaListB .chaRow')].map(r => r.innerText.replace(/\s+/g, ' ').slice(0, 90)).join(' || ')"))
        await pg.screenshot(path=f"{OUT}/tvx_alerts.png")
        await pg.click('#chaListB .chaRow:first-child [data-ca="rm"]'); await asyncio.sleep(0.2)
        print("   delete:", await q("() => CHA.length + ' left, rows ' + document.querySelectorAll('#chaListB .chaRow').length"))
        await q("() => chModalClose()")
        print("CSP:", csp[:3] or "none", "| errors:", errs[:5] or "none")
        await b.close()
asyncio.run(main())
