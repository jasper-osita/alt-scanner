"""Tabs and the Home tab: the tab model, the tab row and router, Home, chart tabs sharing the chart, live hidden tabs, board Chart buttons, sync."""
import asyncio, sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
F = []
def check(name, ok, detail=""):
    print(("   ok " if ok else "   FAIL ") + name + (" · " + str(detail) if detail else ""))
    if not ok: F.append(name)

async def part1(q):
    print("1) the tab model")
    check("first open: Home + a chart tab from the current chart + the last page", await q("""() => {
      const r = tbFirst({ sym: 'CT:XAUUSD', tfs: ['15m','1h','4h','1d'], layout: '2c' }, 'momentum');
      return r.list.map(t => t.kind === 'chart' ? 'chart:' + t.ch.sym + ':' + t.ch.layout : 'page:' + t.page).join() === 'chart:CT:XAUUSD:2c,page:momentum'
        && r.active === r.list[0].id && r.home === 'overview'; }"""))
    check("a Home page last time: Home opens on it, no extra tab", await q("() => { const r = tbFirst({ sym: 'BTCUSDT' }, 'tday'); return r.list.length === 1 && r.home === 'tday'; }"))
    check("removed or unknown pages and broken tabs are dropped", await q("""() => { localStorage.setItem('finder-tabs', JSON.stringify({ list: [{ id: 'a', kind: 'page', page: 'nbbwatch' }, { id: 'b', kind: 'page', page: 'sessions' }, { id: 'c', kind: 'chart', ch: {} }, { id: 'd', kind: 'page', page: 'momentum' }, { id: 'e' }], active: 'a', home: 'bots' }));
      tbRead(); return TB.list.map(t => t.id).join() === 'd' && TB.active === 'home' && TB.home === 'overview'; }"""))
    check("a page opens once", await q("() => { const a = tbOpenPage('day'), b = tbOpenPage('day'); return a.id === b.id && TB.list.filter(t => t.page === 'day').length === 1; }"))
    check("12 chart tabs at most", await q("() => { TB.list = TB.list.filter(t => t.kind !== 'chart'); for (let i = 0; i < 12; i++) tbOpenChart('SYM' + i + 'USDT'); return tbOpenChart('ONEMOREUSDT') === null && TB.list.filter(t => t.kind === 'chart').length === 12; }"))
    check("reuse finds a tab already on that market", await q("() => tbOpenChart('SYM3USDT', { reuse: true }).ch.sym === 'SYM3USDT' && TB.list.filter(t => t.kind === 'chart' && t.ch.sym === 'SYM3USDT').length === 1"))
    check("a new chart tab copies the last-used chart tab's timeframes and layout", await q("() => { const L = TB.list.find(t => t.kind === 'chart'); L.ch.tfs = ['15m','15m','1h','4h']; L.ch.layout = '2c'; TB.last = L.id; TB.list = TB.list.filter(t => t.kind !== 'chart' || t === L); const n = tbOpenChart('NEWUSDT'); return n.ch.tfs.join() === '15m,15m,1h,4h' && n.ch.layout === '2c'; }"))
    check("closing the open tab: right neighbour, else left, else Home", await q("""() => { TB.list = [{ id: 'x', kind: 'page', page: 'day' }, { id: 'y', kind: 'page', page: 'swing' }, { id: 'z', kind: 'page', page: 'aots' }];
      const r = [tbNextAfterClose('y'), tbNextAfterClose('z')]; TB.list = [{ id: 'x', kind: 'page', page: 'day' }]; r.push(tbNextAfterClose('x')); return r.join() === 'z,y,home'; }"""))
    check("tabs survive a reload", await q("() => { tbSave(); const keep = JSON.stringify(TB.list); tbRead(); return JSON.stringify(TB.list) === keep; }"))

async def part2(pg, q):
    print("2) the tab row and the router")
    await q("() => { localStorage.removeItem('finder-tabs'); location.hash = ''; }"); await pg.reload(); await ready(pg)
    check("desktop: no sidebar, a tab row with Home first", await q("() => getComputedStyle(document.getElementById('side')).display === 'none' && document.querySelector('#tabRow [data-tab]').dataset.tab === 'home'"))
    check("opens on the chart tab built from the current chart", await q("() => TB.list[0].kind === 'chart' && TB.active === TB.list[0].id && page === 'charts'"))
    await q("() => goPage('day')")
    check("goPage opens a page tab once", await q("() => page === 'day' && TB.list.filter(t => t.page === 'day').length === 1 && TB.active === TB.list.find(t => t.page === 'day').id"))
    await q("() => goPage('fund')")
    check("a Home page goes to Home", await q("() => TB.active === 'home' && TB.home === 'fund' && page === 'fund'"))
    await pg.click('#tabRow [data-tab="' + await q("() => TB.list.find(t => t.page === 'day').id") + '"]')
    check("clicking a tab shows it", await q("() => page === 'day'"))
    await pg.click("#tabPlus"); await pg.keyboard.type("gold")
    txt = await q("() => document.getElementById('tbMenu').innerText")
    check("+ menu search offers a chart for Gold", "New chart: Gold" in txt, txt[:200])
    await pg.keyboard.press("Escape"); await pg.click("#tabPlus")
    groups = await q("() => [...document.querySelectorAll('#tbMenu .tbgrp')].map(g => g.firstChild.textContent.trim())")
    check("+ menu groups", groups == ["Home pages", "Boards", "Forex · metals · indices", "Screener", "My trading", "More"], groups)
    await pg.keyboard.press("Escape"); await pg.keyboard.press("Alt+1")
    check("Alt+1 is the first tab after Home", await q("() => TB.active === TB.list[0].id"))
    await pg.set_viewport_size({"width": 390, "height": 844}); await asyncio.sleep(0.3)
    check("phone: bottom bar, no tab row", await q("() => getComputedStyle(document.getElementById('mTab')).display !== 'none' && getComputedStyle(document.getElementById('tabRow')).display === 'none'"))
    await pg.set_viewport_size({"width": 1440, "height": 900})

async def part3(pg, q):
    print("3) the Home tab")
    await q("() => tbActivate('home')")
    rail = await q("() => [...document.querySelectorAll('#homeNav a, #homeNav button')].map(e => e.textContent.trim())")
    check("Home rail", rail == ["Overview", "Crypto", "Forex, metals & indices", "Trading day", "Today", "This week", "Calendar", "Fundamentals"], rail)
    await pg.click('#homeNav [data-hp="tday"][data-tdv="week"]')
    check("This week opens Trading day on its week view", await q("() => page === 'tday' && TD_VIEW === 'week' && TB.home === 'tday'"))
    await q("() => goPage('charts')"); await q("() => tbActivate('home')")
    check("Home remembers its section", await q("() => page === 'tday'"))
    await pg.click('[data-page="tday"] [data-owntab="tday"]')
    check("Open in its own tab", await q("() => TB.list.some(t => t.page === 'tday') && TB.active === TB.list.find(t => t.page === 'tday').id && !document.body.classList.contains('homeon')"))
    await q("() => goPage('tday')")
    check("with its own tab open, goPage goes to that tab", await q("() => TB.active === TB.list.find(t => t.page === 'tday').id"))

PARTS = [part1, part2, part3]

async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1440, "height": 900}, color_scheme="dark")
        await setup(ctx, start=None); await setup_mexc(ctx)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.route_web_socket("wss://contract.mexc.com/edge", mx_ws_handler)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        async def wait(js, secs=30):
            for _ in range(secs * 2):
                if await q(js): return True
                await asyncio.sleep(0.5)
            return False
        try:
            for p in PARTS:
                n = p.__code__.co_varnames[:p.__code__.co_argcount]
                await p(*[{"pg": pg, "q": q, "wait": wait}[a] for a in n])
        except Exception as e:
            check("ran without a crash", False, str(e)[:300])
        print("errors:", F + errs[:4] or "none")
        await b.close()
asyncio.run(main())
