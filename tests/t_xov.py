import asyncio, sys, time
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
async def waitfor(pg, js, secs=400):
    for _ in range(secs * 2):
        if await pg.evaluate(js): return True
        await asyncio.sleep(0.5)
    return False
OV = "() => { const W = document.documentElement.clientWidth; return { sw: document.documentElement.scrollWidth, W, bad: [...document.querySelectorAll('body *')].filter(e => { const r = e.getBoundingClientRect(); return r.width && r.right > W + 1 && getComputedStyle(e).position !== 'fixed' && e.offsetParent !== null && !e.closest('.chcv,.tbl-wrap,.scroll-x'); }).slice(0, 5).map(e => (e.id ? '#' + e.id : '') + '.' + String(e.className).split(' ')[0] + ':' + Math.round(e.getBoundingClientRect().right)) }; }"
async def run(pw, mexc, phone):
    b = await pw.chromium.launch()
    ctx = await b.new_context(**(pw.devices["iPhone 13"] if phone else {"viewport": {"width": 1440, "height": 950}}), color_scheme="dark")
    await setup(ctx); await setup_mexc(ctx)
    pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
    await pg.route_web_socket("wss://contract.mexc.com/edge", mx_ws_handler)
    await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
    q = lambda js: pg.evaluate(js); tag = ("mexc" if mexc else "bn") + ("_phone" if phone else "")
    if mexc: await q("() => { document.getElementById('exF').value = 'mexc'; }")
    print(f"== {tag} nav:", await q("() => [...document.querySelectorAll('#navList .ngrp, #navList .nav')].map(e => e.innerText.trim()).join(' | ')"))
    t0 = time.time(); await q("() => goPage('macroov')")
    ok = await waitfor(pg, "() => !MACRO.running && MACRO.rows.length", 400)
    await asyncio.sleep(1)
    print(f"  loaded={ok} {time.time()-t0:.0f}s title:", await q("() => document.getElementById('pageTitle').textContent + ' / ' + document.title"), "| meta:", await q("() => document.querySelector('.xmeta').textContent"))
    print("  hours:", await q("() => [...document.querySelectorAll('.xhr')].map(e => e.innerText.replace(/\\s+/g,' ')).join(' || ')"))
    print("  status:", await q("() => document.getElementById('xStat').innerText.replace(/\\s+/g,' ')"))
    for k in ["fx", "cmd", "idx"]:
        print(f"  movers {k}:", await q(f"() => document.getElementById('xMv_{k}').innerText.replace(/\\s+/g,' ').slice(0,160)"))
    await q("() => document.querySelector('[data-xc=\"fx\"] [data-xm=\"l\"]').click()"); await asyncio.sleep(0.3)
    print("  fx losers:", await q("() => [...document.querySelectorAll('#xMv_fx .mv')].length + ' rows · ' + document.getElementById('xMv_fx').innerText.replace(/\\s+/g,' ').slice(0,120)"))
    print("  flow:", await q("() => document.getElementById('xFlow').innerText.replace(/\\s+/g,' ').slice(0,900)"))
    print("  overflow:", await q(OV))
    await pg.screenshot(path=f"xov_{tag}.png", full_page=True)
    await q("() => goPage('macromomo')"); await asyncio.sleep(1)
    print("  momo tabs:", await q("() => document.getElementById('xMomoTabs').innerText.replace(/\\s+/g,' ')"))
    print("  momo sections:", await q("() => [...document.querySelectorAll('#xMomo .xmsec')].map(x => x.querySelector('.xmsech').innerText + ' :: ' + [...x.querySelectorAll('.row .mname')].map(e => e.innerText).join(', ')).join(' || ')"))
    await q("() => document.querySelector('[data-xmt=\"idx\"]').click()"); await asyncio.sleep(0.3)
    print("  idx tab:", await q("() => [...document.querySelectorAll('#xMomo .xmsec .xmsech')].map(h => h.innerText).join(' | ')"))
    await q("() => document.querySelector('[data-xmt=\"all\"]').click()"); await asyncio.sleep(0.3)
    print("  momo row:", await q("() => (document.querySelector('#xMomo .row') || {innerText:''}).innerText.replace(/\\s+/g,' ')"), "| badge:", await q("() => document.getElementById('nb-macromomo').textContent"))
    print("  dup names?", await q("() => { const n = [...document.querySelectorAll('#xMomo .mname')].map(e => e.innerText); return n.length - new Set(n).size; }"), "| overflow:", await q(OV))
    await pg.screenshot(path=f"xmomo_{tag}.png", full_page=True)
    await q("() => document.querySelector('#xMomo .row') && document.querySelector('#xMomo .row').click()"); await asyncio.sleep(2)
    print("  row opens detail:", await q("() => document.getElementById('dlg').open"))
    await q("() => document.getElementById('dlg').close()")
    sym = await q("() => MACRO.rows[0].symbol")
    await q(f"() => {{ const r = MACRO.by['{sym}']; r.price = 12345.67; macroPaint(r); }}")
    print("  live paint reaches all:", await q(f"() => [...document.querySelectorAll('[data-mp=\"{sym}\"]')].map(e => e.textContent).join(',')"))
    await q("() => goPage('macro')"); await asyncio.sleep(1)
    print("  all-instruments page still:", await q("() => document.querySelectorAll('#macroBody .row').length + ' rows · ' + document.getElementById('pageTitle').textContent"))
    print("  errors:", errs or "none")
    await b.close()
async def main():
    serve()
    async with async_playwright() as pw:
        for mexc, phone in [(False, False), (True, False), (True, True)]:
            await run(pw, mexc, phone)
asyncio.run(main())
