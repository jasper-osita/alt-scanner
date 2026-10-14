import asyncio, sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OUT = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "out", "finder")
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1440, "height": 900}, color_scheme="dark"); await setup(ctx)
        pg = await ctx.new_page(); errs, csp = [], []
        pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: "Content Security Policy" in m.text and csp.append(m.text[:140]))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg); await asyncio.sleep(1)
        q = lambda js: pg.evaluate(js)
        print("1) after scan:", await q("() => ({ total: NC.length, unread: NC.filter(n => !n.read).length, kinds: [...new Set(NC.map(n => n.kind))].join(','), bell: document.getElementById('bellCt').textContent, toasts: document.querySelectorAll('#ncToasts .nctoast').length, more: (document.querySelector('#ncToasts .ncmore') || {}).textContent || '' })"))
        await pg.screenshot(path=f"{OUT}/nc_toasts.png")
        # other sources
        await q("() => { notify('TIA reached 6.420', 'Price is 6.447, above your alert level.', { sym: data.all[3].symbol, kind: 'Price', icon: '🔔', tone: 'blue', title: 'Crossed above your 6.420 alert' }); }")
        await q("() => ncAdd({ sym: data.all[5].symbol, kind: 'Bots', icon: '🤖', tone: 'up', title: 'Bounce bot closed at +2.10R', detail: 'Paper trade · Target · +$21.40' })")
        await q("() => ncAdd({ kind: 'System', icon: '⚠️', tone: 'warn', sym: null, action: 'ctrader', title: \"cTrader didn't connect\", detail: 'The access token is invalid or expired.' })")
        print("2) toasts now:", await q("() => document.querySelectorAll('#ncToasts .nctoast').length"), "| more:", await q("() => (document.querySelector('#ncToasts .ncmore') || {}).textContent || 'none'"))
        # bell → drawer
        await pg.click("#bellBtn"); await asyncio.sleep(0.4)
        print("3) drawer:", await q("() => ({ open: ncOpen(), expanded: document.getElementById('bellBtn').getAttribute('aria-expanded'), groups: [...document.querySelectorAll('#ncList .ncgrp')].map(g => g.textContent).join('/'), items: document.querySelectorAll('#ncList .ncitem').length, chips: [...document.querySelectorAll('#ncChips button')].map(b => b.textContent).join(' | '), toastsLeft: document.querySelectorAll('#ncToasts .nctoast').length })"))
        await pg.screenshot(path=f"{OUT}/nc_drawer.png")
        await pg.click('#ncChips [data-k="Price"]'); await asyncio.sleep(0.2)
        print("   Price filter:", await q("() => [...document.querySelectorAll('#ncList .nct')].map(x => x.textContent).join(' || ')"))
        await pg.click('#ncChips [data-k="All"]')
        # click a breakout → popup for that market
        sym = await q("() => (NC.find(n => n.kind === 'Breakouts') || NC.find(n => n.sym)).sym")
        before = await q("() => NC.filter(n => !n.read).length")
        await pg.click(f'#ncList .ncitem[data-nc="{await q(f"() => NC.find(n => n.sym === {sym!r}).id")}"]'); await asyncio.sleep(1.8)
        print("4) click item:", await q("() => ({ drawerOpen: ncOpen(), dlg: document.getElementById('dlg').open, dlgSym: document.getElementById('dlgBody').dataset.sym, chart: CHDLG.on && CH.sym })"), "expected", sym,
              "| unread", before, "→", await q("() => NC.filter(n => !n.read).length"), "| bell:", await q("() => document.getElementById('bellCt').textContent"))
        await pg.keyboard.press("Escape"); await asyncio.sleep(0.3)
        # system notification opens cTrader settings
        await pg.click("#bellBtn"); await asyncio.sleep(0.3)
        sid = await q("() => NC.find(n => n.kind === 'System').id")
        await pg.click(f'#ncList .ncitem[data-nc="{sid}"]'); await asyncio.sleep(0.6)
        print("5) system item:", await q("() => ({ page, dlg: document.getElementById('dlg').open, form: !!document.getElementById('ctId') })"))
        await pg.keyboard.press("Escape"); await asyncio.sleep(0.3)
        # toast Open market button
        await q("() => ncAdd({ sym: data.all[1].symbol, kind: 'Setups', icon: '🥪', tone: 'gold', title: 'NBB long triggered', detail: 'Entry 1 · Stop 0.9' })"); await asyncio.sleep(0.3)
        await pg.click("#ncToasts .nctoast .go"); await asyncio.sleep(1.5)
        print("6) toast → market:", await q("() => document.getElementById('dlg').open && document.getElementById('dlgBody').dataset.sym"), "expected", await q("() => data.all[1].symbol"))
        await pg.keyboard.press("Escape"); await asyncio.sleep(0.3)
        # Escape closes drawer; mark all read; persistence
        await pg.click("#bellBtn"); await asyncio.sleep(0.2); await pg.keyboard.press("Escape"); await asyncio.sleep(0.3)
        print("7) esc closes:", not await q("() => ncOpen()"))
        await pg.click("#bellBtn"); await asyncio.sleep(0.2); await pg.click("#ncReadAll"); await asyncio.sleep(0.2)
        print("   read all:", await q("() => ({ unread: NC.filter(n => !n.read).length, bellHidden: document.getElementById('bellCt').hidden, newGrp: !!document.querySelector('#ncList .ncgrp') && document.querySelector('#ncList .ncgrp').textContent })"))
        n_before = await q("() => NC.length")
        await pg.reload(); await asyncio.sleep(2)
        print("8) after reload:", await q("() => NC.length"), "kept of", n_before, "| bell hidden:", await q("() => document.getElementById('bellCt').hidden"))
        await ready(pg); await asyncio.sleep(1)
        print("   no repeat breakout alerts on rescan:", await q("() => NC.filter(n => n.kind === 'Breakouts' && !n.read).length"))
        # forex/gold triggers: first read records, later new triggers notify
        await q("() => goPage('macro')")
        for _ in range(80):
            if await q("() => MACRO.rows.length > 0 && !MACRO.running"): break
            await asyncio.sleep(0.5)
        await q("() => { localStorage.setItem('finder-macro-seen', JSON.stringify({ dummy: Date.now() })); }")
        n0 = await q("() => NC.length"); await q("() => macroAlerts(MACRO.rows)")
        print("9) macro triggers:", await q(f"() => NC.slice(0, NC.length - {n0}).map(n => coin(n.sym) + ': ' + n.title).slice(0, 4).join(' || ')"), "| count", await q(f"() => NC.length - {n0}"))
        await q("() => macroAlerts(MACRO.rows)"); print("   repeat call adds:", await q(f"() => NC.length - {n0}"), "(same as above means no duplicates)")
        await pg.click("#ncClear") if await q("() => ncOpen()") else None
        # phone
        await pg.set_viewport_size({"width": 390, "height": 844}); await asyncio.sleep(0.3)
        await pg.click("#bellBtn"); await asyncio.sleep(0.4)
        print("10) mobile drawer width:", await q("() => document.getElementById('ncDrawer').getBoundingClientRect().width"), "| overflow:", await q("() => document.documentElement.scrollWidth - innerWidth"))
        await pg.screenshot(path=f"{OUT}/nc_mobile.png")
        await pg.click("#ncClear"); await asyncio.sleep(0.2)
        print("   cleared:", await q("() => ({ n: NC.length, empty: document.querySelector('#ncList .ncempty').innerText.slice(0, 40) })"))
        print("CSP:", csp or "none", "| errors:", errs or "none")
        await b.close()
asyncio.run(main())
