import asyncio, sys, json
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
async def run(pw, phone):
    b = await pw.chromium.launch()
    ctx = await b.new_context(**(pw.devices["iPhone 13"] if phone else {"viewport": {"width": 1600, "height": 950}}), color_scheme="dark"); await setup(ctx)
    pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
    await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
    q = lambda js: pg.evaluate(js); tag = "phone" if phone else "desk"; print("==", tag)
    await q("() => goPage('charts')")
    for _ in range(40):
        if await q("() => chVis().length && chVis().every(P => P.t.length && P.msg.hidden)"): break
        await asyncio.sleep(0.5)
    print("legend:", await q("() => document.getElementById('chLeg' + chVis()[0].i).innerText"), "| badge:", await q("() => (document.querySelector('.chsrcb') || {}).textContent"), "| tip:", await q("() => (document.querySelector('.chfeed') || {}).title"))
    await q("() => document.getElementById('chSetBtn').click()"); await asyncio.sleep(0.4)
    print("tabs:", await q("() => [...document.querySelectorAll('[data-cst]')].map(b => b.innerText).join(' | ')"))
    print("symbol tab:", await q("() => document.getElementById('csBody').innerText.replace(/\\s+/g, ' ').slice(0, 300)"))
    if not phone: await pg.screenshot(path="cs_sym.png")
    async def tab(k): await q(f"() => document.querySelector('[data-cst=\"{k}\"]').click()"); await asyncio.sleep(0.2)
    async def ck(k): await q(f"() => document.querySelector('[data-ck=\"{k}\"]').click()"); await asyncio.sleep(0.2)
    async def sel(k, v): await q(f"() => {{ const s = document.querySelector('[data-sel=\"{k}\"]'); s.value = '{v}'; s.dispatchEvent(new Event('change')); }}"); await asyncio.sleep(0.3)
    P = "chVis()[0]"
    await sel("prec", "2"); await ck("prevClose")
    print("precision 2 + prev close:", await q(f"() => [document.getElementById('chLeg' + {P}.i).innerText.slice(0, 120), JSON.stringify({P}.cs.data().at(-2)).slice(0, 140)]"))
    await sel("tz", "UTC"); print("tz UTC:", await q("() => chTimeFmt(Date.UTC(2026, 9, 11, 13, 40) / 1000)"))
    await tab("sl"); await ck("slVol"); await ck("slInputs")
    print("status line:", await q(f"() => [document.getElementById('chLeg' + {P}.i).innerText.includes('Vol'), [...{P}.wrap.querySelectorAll('.chind .nm')].map(e => e.textContent).join(',')]"))
    await tab("sc"); await ck("prevDay"); await ck("hiLo"); await ck("cd"); await sel("h12", "true"); await sel("dateFmt", "iso")
    print("scales:", await q(f"() => [!!{P}.plPD, !!{P}.plHi, !!{P}.plLo, document.getElementById('chCd' + {P}.i).textContent, chTimeFmt(Date.UTC(2026, 9, 11, 13, 40) / 1000)]"))
    await tab("cv"); await ck("vGrid"); await sel("bgType", "gradient"); await sel("wm", "symtf")
    await q("() => { const i = document.querySelector('[data-num=\"mTop\"]'); i.value = 20; i.dispatchEvent(new Event('input')); }"); await asyncio.sleep(0.2)
    print("canvas:", await q(f"() => {{ const o = {P}.chart.options(); return [o.grid.vertLines.visible, o.layout.background.type, o.watermark.visible, o.watermark.text, {P}.chart.priceScale('right').options().scaleMargins.top]; }}"))
    await tab("al"); await q(f"() => {{ WL.alerts.push({{ id: 'x1', sym: CH.sym, price: {P}.c.at(-1) * 1.01, dir: 'above', created: Date.now(), fired: false }}); chLevelLines({P}); }}")
    print("alert line:", await q(f"() => ({P}.alLines || []).length"))
    await tab("ev"); await ck("sessBreaks"); await asyncio.sleep(0.3)
    # templates
    await q("() => document.getElementById('csTplBtn').click()"); await asyncio.sleep(0.2)
    print("tpl menu:", await q("() => document.getElementById('csTplPop').innerText.replace(/\\s+/g,' ')"))
    await q("() => document.querySelector('[data-ta=\"save\"]').click()"); await asyncio.sleep(0.2)
    await pg.fill("#csTplName", "Night desk"); await q("() => document.getElementById('csTplSave').click()"); await asyncio.sleep(0.3)
    print("saved:", await q("() => { const t = CH.csTpl['Night desk']; return [Object.keys(t.cs).length, (t.ind || []).length]; }"))
    await q("() => { document.getElementById('csTplBtn').click(); }"); await asyncio.sleep(0.2)
    await q("() => document.querySelector('[data-ta=\"def\"]').click()"); await asyncio.sleep(0.3)
    print("defaults:", await q(f"() => [JSON.stringify(CH.cs), {P}.chart.options().grid.vertLines.visible, {P}.chart.options().layout.background.type]"))
    await q("() => { document.getElementById('csTplBtn').click(); }"); await asyncio.sleep(0.2)
    print("tpl list:", await q("() => document.getElementById('csTplPop').innerText.replace(/\\s+/g,' ')"))
    if not phone: await pg.screenshot(path="cs_tpl.png")
    await q("() => document.querySelector('[data-tn=\"Night desk\"]').click()"); await asyncio.sleep(0.4)
    print("applied:", await q(f"() => [CH.cs.bgType, CH.cs.prec, {P}.chart.options().layout.background.type, {P}.chart.options().grid.vertLines.visible]"))
    await q("() => document.getElementById('csOk').click()"); await asyncio.sleep(0.3)
    print("saved after Ok:", await q("() => { const c = JSON.parse(localStorage.getItem(CH_KEY)); return [c.cs.bgType, Object.keys(c.csTpl || {})]; }"))
    # cancel reverts
    await q("() => chChartSettings('cv')"); await asyncio.sleep(0.2); await ck("hGrid"); await q("() => document.getElementById('csCancel').click()"); await asyncio.sleep(0.3)
    print("cancel reverts:", await q(f"() => [CH.cs.hGrid, {P}.chart.options().grid.horzLines.visible]"))
    # right-click menu on empty chart
    bx = await pg.locator(f"#chCv{await q('() => chVis()[0].i')}").bounding_box()
    if not phone:
        await pg.mouse.click(bx["x"] + bx["width"] * 0.15, bx["y"] + bx["height"] * 0.1, button="right"); await asyncio.sleep(0.3)
        print("context menu:", await q("() => (document.getElementById('chMenu') || {}).innerText"))
        await pg.keyboard.press("Escape")
    await pg.screenshot(path=f"cs_chart_{tag}.png")
    # dialog chart
    sym = await q("() => data.all[0].symbol")
    await q(f"() => {{ goPage('overview'); openDetail('{sym}'); }}"); await asyncio.sleep(5)
    await q("() => document.querySelector('#dChartHost #chSetBtn').click()"); await asyncio.sleep(0.4)
    print("settings in pop-up:", await q("() => { const m = document.getElementById('chModBg'); if (!m) return 'none'; const r = m.querySelector('.chmod').getBoundingClientRect(), el = document.elementFromPoint(r.left + r.width / 2, r.top + 20); return (m.closest('dialog') ? 'in dialog' : 'outside') + ' · on top ' + (!!el && m.contains(el)) + ' · feed ' + document.querySelector('#dChartHost .chsrcb').textContent; }"))
    if phone:
        print("phone modal:", await q("() => { const m = document.querySelector('.chmcs').getBoundingClientRect(); return [Math.round(m.width), Math.round(m.height), document.querySelector('.chcsn').scrollWidth > document.querySelector('.chcsn').clientWidth]; }"))
        await pg.screenshot(path="cs_phone_modal.png")
    await pg.keyboard.press("Escape"); await asyncio.sleep(0.2); await pg.keyboard.press("Escape")
    print("errors:", errs or "none")
    await b.close()
async def main():
    serve()
    async with async_playwright() as pw:
        await run(pw, False); await run(pw, True)
asyncio.run(main())
