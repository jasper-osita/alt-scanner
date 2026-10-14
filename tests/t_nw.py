import asyncio, sys, re, json
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OPTS = {"secret": "sec", "token": "tok", "live": True}
OV = "() => { const W = document.documentElement.clientWidth; return document.documentElement.scrollWidth <= W + 1; }"
async def run(pw, phone):
    b = await pw.chromium.launch()
    ctx = await b.new_context(**(pw.devices["iPhone 13"] if phone else {"viewport": {"width": 1600, "height": 950}}), color_scheme="dark")
    await setup(ctx); await setup_mexc(ctx); await setup_extra(ctx)
    pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
    await pg.route_web_socket("wss://contract.mexc.com/edge", mx_ws_handler)
    await pg.route_web_socket(re.compile(r"wss://(live|demo)\.ctraderapi\.com:5036.*"), ct_handler(OPTS))
    await pg.goto("http://localhost:8765/")
    await pg.evaluate("() => { localStorage.clear(); localStorage.setItem('finder-ctrader', JSON.stringify({ clientId: 'cid', clientSecret: 'sec', accessToken: 'tok' })); }"); await pg.reload(); await ready(pg)
    q = lambda js: pg.evaluate(js); tag = "phone" if phone else "desk"; print("==", tag)
    # Telegram settings
    await q("() => openTGSettings()"); await asyncio.sleep(0.3)
    await pg.fill("#tgToken", "111:AAA"); await q("() => document.getElementById('tgFind').click()"); await asyncio.sleep(0.8)
    print("tg find:", await q("() => [document.getElementById('tgChat').value, document.getElementById('tgMsg').innerText]"))
    await q("() => document.getElementById('tgTest').click()"); await asyncio.sleep(1.5)
    print("tg test:", await q("() => document.getElementById('tgMsg').innerText"), "| sent:", len(TG_LOG), (TG_LOG[-1]["text"][:60] if TG_LOG else ""))
    await q("() => document.getElementById('dlg').close()")
    # calendar
    await q("() => goPage('calendar')"); await asyncio.sleep(2)
    print("cal meta:", await q("() => document.getElementById('calMeta').textContent"), "| up next:", await q("() => document.getElementById('calUp').innerText.replace(/\\s+/g,' ')"))
    print("ff rows (default High+Holiday):", await q("() => [...document.querySelectorAll('.caltbl tbody tr:not(.calday)')].map(r => r.querySelector('.ce').innerText.split('\\n')[0]).join(' | ')"))
    await q("() => document.getElementById('calFilterBtn').click()"); await asyncio.sleep(0.3)
    print("filter sections:", await q("() => [...document.querySelectorAll('.calfh')].map(h => h.innerText.split(' ')[0]).join(',')"))
    if not phone: await pg.screenshot(path="cal_filter.png")
    await q("() => { document.querySelector('[data-cf=\"imp\"][value=\"Medium\"]').checked = true; document.querySelector('[data-cfnone=\"ccy\"]').click(); document.querySelector('[data-cf=\"ccy\"][value=\"USD\"]').checked = true; document.querySelector('[data-cfa=\"apply\"]').click(); }"); await asyncio.sleep(0.4)
    print("USD High+Medium:", await q("() => [...document.querySelectorAll('.caltbl tbody tr:not(.calday)')].map(r => r.querySelector('.cc').innerText + ' ' + r.querySelector('.ce').innerText.split('\\n')[0] + ' [' + r.querySelector('.cty').innerText + ']').join(' | ')"))
    await asyncio.sleep(31)
    print("reminder:", await q("() => NC.filter(n => n.kind === 'News').map(n => n.title).join(' | ')"), "| telegram:", [m["text"][:50] for m in TG_LOG if "📅" in m["text"]][:2])
    await q("() => document.querySelector('[data-ct=\"idx\"]').click()"); await asyncio.sleep(3)
    print("indices up:", await q("() => document.getElementById('calUp').innerText.replace(/\\s+/g,' ').slice(0, 260)"))
    print("indices rows:", await q("() => [...document.querySelectorAll('.caltbl tbody tr:not(.calday)')].slice(0, 14).map(r => r.querySelector('.ct').innerText + ' ' + r.querySelector('.ce').innerText.split('\\n')[0].slice(0, 45)).join(' | ')"))
    print("earnings asked:", sorted(set(EARN_HITS))[:12], "| overflow ok:", await q(OV))
    await pg.screenshot(path=f"cal_idx_{tag}.png", full_page=not phone)
    # NBB Watch
    await q("() => { document.getElementById('exF').value = 'mexc'; goPage('nbbwatch'); }"); await asyncio.sleep(8)
    print("nw meta:", await q("() => document.getElementById('nwMeta').textContent"))
    print("nw cards:", await q("() => [...document.querySelectorAll('.nwcard')].map(c => c.querySelector('.nwh').innerText.replace(/\\s+/g,' ') + ' :: ' + c.querySelector('.nwst').innerText.replace(/\\s+/g,' ').slice(0, 110)).join(' || ')"))
    print("nw syms:", await q("() => Object.entries(NW_ST).map(([k, s]) => k + '=' + s.sym + ' bars ' + (s.k ? s.k.t.length : 0) + ' state ' + (s.read && s.read.state) + ' spec ' + !!s.spec).join(' | ')"))
    # synthetic NBB trigger on 5m candles: trend up, 8-candle base, displacing breakout
    trig = await q("""() => { const k = { t: [], o: [], h: [], l: [], c: [], qv: [] }; let p = 100; const t0 = Date.now() - 200 * 300e3;
      for (let i = 0; i < 180; i++) { const o = p; p += 0.25 + Math.sin(i) * 0.1; k.t.push(t0 + i * 300e3); k.o.push(o); k.c.push(p); k.h.push(Math.max(o, p) + 0.1); k.l.push(Math.min(o, p) - 0.1); k.qv.push(1); }
      for (let i = 0; i < 9; i++) { const o = p, c = p + (i % 2 ? 0.15 : -0.15); k.t.push(t0 + k.t.length * 300e3); k.o.push(o); k.c.push(c); k.h.push(Math.max(o, c) + 0.1); k.l.push(Math.min(o, c) - 0.1); k.qv.push(1); }
      const o = p, c = p + 1.6; k.t.push(Date.now() - 300e3); k.o.push(o); k.c.push(c); k.h.push(c + 0.05); k.l.push(o - 0.05); k.qv.push(1);
      const r = nbbWatchRead(k, 300e3); if (!r) return 'no read';
      const it = NW.items[0], st = NW_ST[nwKey(it)]; st.k = k; st.read = r; nwSignals(it, st); nwRender(it);
      return r.state + ' ' + (r.trig ? r.trig.dir + ' E ' + r.trig.entry.toFixed(2) + ' S ' + r.trig.stop.toFixed(2) + ' tClose ' + Math.round((r.trig.tClose - Date.now()) / 1000) + 's' : ''); }""")
    print("synthetic:", trig)
    await asyncio.sleep(1.5)
    print("trigger card:", await q("() => document.querySelector('.nwcard .nwst').innerText.replace(/\\s+/g,' ').slice(0, 300)"))
    print("alert:", await q("() => NC.filter(n => n.kind === 'NBB Watch').map(n => n.title + ' :: ' + n.detail.slice(0, 90)).join(' | ')"), "| tg:", [m["text"][:60] for m in TG_LOG if "NBB" in m["text"]][:1])
    print("log:", await q("() => (document.querySelector('.nwlog') || {innerText: ''}).innerText.replace(/\\s+/g,' ')"))
    print("awake pings:", AWAKE_LOG[:2])
    await pg.screenshot(path=f"nw_{tag}.png", full_page=not phone)
    # editor
    await q("() => document.getElementById('nwEditB').click()"); await asyncio.sleep(0.3)
    print("editor rows:", await q("() => document.querySelectorAll('.nwer').length"), "| options:", await q("() => document.querySelector('.nwer select').options.length"))
    await q("() => { document.getElementById('nwAdd').click(); const r = [...document.querySelectorAll('.nwer')].at(-1); const s = r.querySelector('[data-k=\"name\"]'); s.value = 'EUR/USD'; s.dispatchEvent(new Event('change')); const t = r.querySelector('[data-k=\"tf\"]'); t.value = '15m'; t.dispatchEvent(new Event('change')); document.getElementById('nwSaveB').click(); }"); await asyncio.sleep(4)
    print("after add:", await q("() => NW.items.map(nwKey).join(', ')"), "| eurusd:", await q("() => { const s = NW_ST['EUR/USD|15m']; return s ? s.sym + ' ' + (s.read ? s.read.state : s.err) : 'none'; }"))
    print("overflow ok:", await q(OV))
    # broker sizing in the pop-up
    await q("() => goPage('macro')"); await asyncio.sleep(1)
    ok = False
    for _ in range(120):
        if await q("() => !MACRO.running && !!MACRO.by['CT:XAUUSD']"): ok = True; break
        await asyncio.sleep(1)
    if ok:
        await q("() => openDetail('CT:XAUUSD')"); await asyncio.sleep(1.5)
        await q("() => document.querySelector('.dtabs [data-pane=\"size\"]').click()"); await asyncio.sleep(0.3)
        await q("() => { const r = MACRO.by['CT:XAUUSD']; document.getElementById('cEntry').value = r.price; document.getElementById('cStop').value = +(r.price * 0.99).toFixed(4); document.getElementById('cEntry').dispatchEvent(new Event('input')); }"); await asyncio.sleep(1.5)
        print("size tab:", await q("() => document.getElementById('cOut').innerText.replace(/\\s+/g,' ')"))
        await q("() => document.getElementById('dlg').close()")
    print("errors:", errs or "none")
    await b.close()
async def main():
    serve()
    async with async_playwright() as pw:
        await run(pw, False); await run(pw, True)
asyncio.run(main())
