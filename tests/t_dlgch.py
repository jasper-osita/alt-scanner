import asyncio, sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
async def run(pw, phone):
    b = await pw.chromium.launch()
    ctx = await b.new_context(**(pw.devices["iPhone 13"] if phone else {"viewport": {"width": 1600, "height": 950}}), color_scheme="dark"); await setup(ctx)
    pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
    await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
    q = lambda js: pg.evaluate(js); tag = "phone" if phone else "desk"
    print(f"== {tag}")
    before = await q("() => [CH.sym, CH.tfs[0], CH.max, CH.layout]")
    sym = await q("() => (data.day[0] || data.all[0]).symbol")
    await q(f"() => openDetail('{sym}')"); await asyncio.sleep(5)
    print("in dialog:", await q("() => [!!document.querySelector('#dChartHost #chPage'), CHDLG.on, CH.sym, chVis().length, chVis()[0].tf, chVis()[0].t.length, chVis()[0].msg.hidden]"), "sym", sym)
    print("tf options:", await q("() => [...document.querySelectorAll('#dChartHost .chtf')[0].options].map(o => o.textContent).join(' ')"))
    print("visible bits:", await q("() => ['.chtools', '.chcats', '.chwl', '.chlay', '#chIndBtn', '#chUndoB'].map(s => { const e = document.querySelector('#dChartHost ' + s); return s + ':' + (e ? e.offsetParent !== null : 'none'); }).join(' ')"))
    print("old level lines gone:", await q("() => !document.querySelector('#tfRow') && !document.querySelector('#mchart')"))
    # timeframe change
    await q("() => { const s = document.querySelector('#dChartHost .chtf'); s.value = '4h'; s.dispatchEvent(new Event('change')); }"); await asyncio.sleep(2)
    print("tf -> 4h:", await q("() => [chVis()[0].tf, chVis()[0].t.length, chVis()[0].msg.hidden, chVis()[0].t.length > 1 ? (chVis()[0].t[1] - chVis()[0].t[0]) / 3600e3 + 'h bars' : '']"))
    # draw a trend line
    bx = await pg.locator("#chCv0").bounding_box()
    await q("() => chPickTool('trend')")
    a = (bx["x"] + bx["width"] * 0.3, bx["y"] + bx["height"] * 0.4); c = (bx["x"] + bx["width"] * 0.6, bx["y"] + bx["height"] * 0.3)
    if phone:
        await pg.touchscreen.tap(*a); await asyncio.sleep(0.2); await pg.touchscreen.tap(*c)
    else:
        await pg.mouse.click(*a); await pg.mouse.move(*c, steps=5); await pg.mouse.click(*c)
    await asyncio.sleep(0.4)
    print("drawn:", await q(f"() => (CHD['{sym}'] || []).map(d => d.type).join(',')"), "| float bar in dialog:", await q("() => { const f = document.getElementById('chFloat'); return f ? (f.closest('dialog') ? 'inside' : 'outside') + (f.hidden ? ' hidden' : ' shown') : 'none'; }"))
    # menus inside the modal and clickable
    await q("() => { const b = document.querySelector('#dChartHost .chtools .chtarr'); if (b) b.click(); }"); await asyncio.sleep(0.4)
    print("flyout:", await q("() => { const m = document.getElementById('chMenu'); if (!m) return 'none'; const r = m.getBoundingClientRect(), el = document.elementFromPoint(r.left + r.width / 2, r.top + 12); return (m.closest('dialog') ? 'in dialog' : 'outside') + ' · on top ' + (!!el && m.contains(el)); }"))
    await pg.keyboard.press("Escape"); await asyncio.sleep(0.3)
    print("esc closes menu only:", await q("() => [!document.getElementById('chMenu'), document.getElementById('dlg').open]"))
    await q("() => chIndDialog()"); await asyncio.sleep(0.4)
    print("indicator dialog:", await q("() => { const m = document.getElementById('chModBg'); if (!m) return 'none'; const r = m.querySelector('.chmod').getBoundingClientRect(), el = document.elementFromPoint(r.left + r.width / 2, r.top + 20); return (m.closest('dialog') ? 'in dialog' : 'outside') + ' · on top ' + (!!el && m.contains(el)); }"))
    await pg.keyboard.press("Escape"); await asyncio.sleep(0.3)
    print("after esc:", await q("() => [!!document.getElementById('chModBg'), document.getElementById('dlg').open]"))
    await q("() => chPickTool('hline')"); await pg.keyboard.press("Escape"); await asyncio.sleep(0.3)
    print("esc with tool: dialog still open", await q("() => document.getElementById('dlg').open"), "tool", await q("() => chTool"))
    print("overflow:", await q("() => { const d = document.getElementById('dlg'); return [d.scrollWidth, d.clientWidth, document.querySelector('#dChartHost').getBoundingClientRect().height | 0]; }"))
    await pg.screenshot(path=f"dlgch_{tag}.png")
    await pg.keyboard.press("Escape"); await asyncio.sleep(0.5)
    after = await q("() => [CH.sym, CH.tfs[0], CH.max, CH.layout]")
    print("closed:", await q("() => [document.getElementById('dlg').open, CHDLG.on, !!document.querySelector('section#chPage, #chPage') && !document.querySelector('#dlg #chPage'), CH.dlgTf]"), "| restored", after == before, before, after)
    await q("() => goPage('charts')"); await asyncio.sleep(2.5)
    print("charts page:", await q("() => chVis().map(P => P.sym + ' ' + P.tf + ' ' + P.t.length).join(' | ')"))
    await q(f"() => {{ goPage('overview'); openDetail('{sym}'); }}"); await asyncio.sleep(2.5)
    print("reopen remembers tf:", await q("() => chVis()[0].tf"), "| drawing shown:", await q("() => chList().length"))
    await q("() => document.querySelector('#dlgBody [data-openchart]').click()"); await asyncio.sleep(2.5)
    print("Charts button:", await q("() => [page, document.getElementById('dlg').open, CH.sym, chVis().map(P => P.sym).join(',')]"))
    mx = await q("() => { const r = MACRO.rows.find(r => r.mx || TRADFI_SYMS.has(r.symbol)); return r ? r.symbol : null; }")
    if mx:
        await q(f"() => {{ goPage('overview'); openDetail('{mx}'); }}"); await asyncio.sleep(3)
        print("macro dialog:", mx, await q("() => [CH.sym, chVis()[0].tf, chVis()[0].t.length, chVis()[0].msg.hidden ? 'ok' : chVis()[0].msg.textContent]"))
        await pg.keyboard.press("Escape")
    print("errors:", errs or "none")
    await b.close()
async def main():
    serve()
    async with async_playwright() as pw:
        await run(pw, False); await run(pw, True)
asyncio.run(main())
