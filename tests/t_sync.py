"""Sync across devices through a private GitHub gist (GitHub faked here): two browsers share drawings, alerts and chart style, not layout."""
import asyncio, sys, os, json, functools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
print = functools.partial(print, flush=True)
GISTS, AUTH = {}, []
async def route_gh(route):
    r = route.request; u = r.url.split("api.github.com")[1]; AUTH.append(r.headers.get("authorization", ""))
    if r.headers.get("authorization") != "Bearer ghp_test123": return await route.fulfill(status=401, body="{}")
    if u.startswith("/gists?"): return await route.fulfill(json=[{"id": k, "description": g["description"], "files": {n: {} for n in g["files"]}} for k, g in GISTS.items()])
    if u == "/gists" and r.method == "POST":
        b = json.loads(r.post_data); k = f"g{len(GISTS) + 1}"; GISTS[k] = {"description": b["description"], "public": b["public"], "files": {n: f["content"] for n, f in b["files"].items()}}
        return await route.fulfill(json={"id": k})
    k = u.split("/gists/")[1]
    if r.method == "PATCH":
        b = json.loads(r.post_data); GISTS[k]["files"].update({n: f["content"] for n, f in b["files"].items()}); return await route.fulfill(json={"id": k})
    return await route.fulfill(json={"id": k, "files": {n: {"content": c, "truncated": False} for n, c in GISTS[k]["files"].items()}})
async def device(b, name):
    ctx = await b.new_context(viewport={"width": 1500, "height": 900}); await setup(ctx); await ctx.route("https://api.github.com/**", route_gh)
    pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(name + ": " + str(e)))
    await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
    await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
    await pg.click('#side [data-go="charts"]')
    for _ in range(60):
        if await pg.evaluate("() => CHP.length === 4 && CHP.every(P => P.t.length > 0)"): break
        await asyncio.sleep(0.25)
    return pg, errs
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        A, ea = await device(b, "A"); B, eb = await device(b, "B")
        draw = lambda id: f"() => {{ const P = CHP[1]; CHD.BTCUSDT = [...(CHD.BTCUSDT || []), {{ id: '{id}', type: 'hline', pts: [{{ t: P.t.at(-9), p: P.c.at(-9) }}], s: {{}} }}]; chSaveDraw(); chDirty = true; }}"
        await A.evaluate(draw("fromA")); await A.evaluate("() => chaAdd({ sym: 'BTCUSDT', tf: '1h', L: { k: 'price' }, op: 'cross', R: { k: 'val', v: 1 }, trig: 'once' })")
        # connect A through the settings tab
        await A.evaluate("() => chChartSettings('sy')"); await asyncio.sleep(0.2)
        print("1) A sync tab:", await A.evaluate("() => document.getElementById('syBox').innerText.replace(/\\s+/g, ' ').slice(0, 150)"))
        await A.fill("#syTok", "ghp_test123"); await A.click("#syOn"); await asyncio.sleep(1)
        print("   A connected:", await A.evaluate("() => document.getElementById('syBox').innerText.replace(/\\s+/g, ' ').slice(0, 120)"), "| gists", len(GISTS))
        g = json.loads(GISTS["g1"]["files"]["finder-sync.json"]); print("   gist private:", not GISTS["g1"]["public"], "| parts", sorted(g["parts"]), "| A's line in gist:", any(d["id"] == "fromA" for d in g["parts"]["draw"]["v"].get("BTCUSDT", [])), "| token in gist:", "ghp_test123" in GISTS["g1"]["files"]["finder-sync.json"])
        await A.evaluate("() => chModalClose()")
        # B joins with its own drawing and a phone layout
        await B.evaluate(draw("fromB")); await B.evaluate("() => { CH.layout = '1'; chSave(); chApplyLayout(); }")
        await B.evaluate("() => { localStorage.setItem('finder-sync', JSON.stringify({ token: 'ghp_test123' })); return syNow('manual'); }"); await asyncio.sleep(0.5)
        print("2) B joined:", await B.evaluate("() => (CHD.BTCUSDT || []).map(d => d.id).join(',') + ' | alerts ' + CHA.length + ' | gist ' + SY().gist"), "| gists", len(GISTS))
        await A.evaluate("() => syNow('manual')"); await asyncio.sleep(0.3)
        print("   A got B's line:", await A.evaluate("() => (CHD.BTCUSDT || []).map(d => d.id).join(',')"))
        # B changes the chart type and an indicator: pushed by itself a few seconds later
        await B.evaluate("() => { chSetType('ha'); CH.ind = CH.ind.filter(I => I.type !== 'rsi'); chIndChanged(); }"); await asyncio.sleep(9)
        await A.evaluate("() => syNow('manual')"); await asyncio.sleep(0.5)
        print("3) A after B's change:", await A.evaluate("() => 'type ' + CH.ctype + ' series ' + CHP[1].cs.seriesType() + ' | rsi ' + CH.ind.some(I => I.type === 'rsi') + ' | layout stays ' + CH.layout"), "| B layout", await B.evaluate("() => CH.layout"))
        # deleting on A reaches B
        await A.evaluate("() => { CHD.BTCUSDT = CHD.BTCUSDT.filter(d => d.id !== 'fromA'); chSaveDraw(); }"); await asyncio.sleep(9)
        await B.evaluate("() => syNow('manual')"); await asyncio.sleep(0.3)
        print("4) B after A deleted its line:", await B.evaluate("() => (CHD.BTCUSDT || []).map(d => d.id).join(',')"))
        # a bad token shows an error
        await B.evaluate("() => { sySave({ token: 'nope' }); return syNow('manual'); }")
        print("5) bad token:", await B.evaluate("() => SY().err"))
        print("   only the token went to GitHub:", all(a in ("Bearer ghp_test123", "Bearer nope") for a in AUTH))
        print("errors:", (ea + eb)[:4] or "none")
        await b.close()
asyncio.run(main())
