import asyncio, json, sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1440, "height": 950}, color_scheme="dark", permissions=["clipboard-read", "clipboard-write"]); await setup(ctx)
        pg = await ctx.new_page(); errs, csp = [], []
        pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: "Content Security Policy" in m.text and csp.append(m.text[:140]))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        await asyncio.sleep(2)
        R = await pg.evaluate("""() => { const R = data.rotation; return R && { label: R.label, source: R.capsSource, tiers: [R.m.nL, R.m.nM, R.m.nS, R.m.nMe], b30: R.m.b30.toFixed(1), e30: R.m.e30 && R.m.e30.toFixed(1),
            ethbtc: R.m.ethbtc, breadth: R.m.breadth, counts: R.counts, leaders: R.leaders.slice(0, 4).map(x => coin(x.r.symbol) + ' ' + x.c.rel30), checks: R.checks && R.checks.map(c => c.name + ':' + c.pass) }; }""")
        print("money flow:", json.dumps(R, indent=1))
        print("card text:", await pg.evaluate("() => document.getElementById('rotation').innerText.split('\\n').slice(0, 4).join(' | ')"))
        print("playbook note:", await pg.evaluate("() => data.env.why.find(w => w.startsWith('Money flow')) || 'none'"))
        for v in ["Rotation Leaders", "Large-Cap Leaders", "Lagging BTC (30d)"]:
            await pg.evaluate("() => goPage('screener')")
            chip = await pg.evaluate(f"() => (document.querySelector('.qchip[data-v=\"{v}\"] span') || {{}}).textContent")
            await pg.click(f'.qchip[data-v="{v}"]'); await asyncio.sleep(0.3)
            rows = await pg.evaluate("() => [...document.querySelectorAll('#tbody tr[data-s]')].map(t => coinRot(bySym[t.dataset.s]).status + '/' + tierOf(bySym[t.dataset.s]))")
            print(f"view {v}: chip {chip}, table {len(rows)} → {sorted(set(rows))[:6]} | tab: {await pg.evaluate('() => tab')}")
        await pg.click('.qchip[data-v="Lagging BTC (30d)"]'); await asyncio.sleep(0.2)
        print("Money Flow tab columns:", await pg.evaluate("() => { tab = 'rotation'; renderTabs(); renderTable(); return [...document.querySelectorAll('#thead th')].map(t => t.innerText.replace(/\\n/g, ' ')).join(' | '); }"))
        lag = await pg.evaluate("() => (data.all.find(r => coinRot(r).status === 'Laggard' && coinPlay(r).dir === 'Long') || {}).symbol")
        if lag:
            p = await pg.evaluate(f"() => coinPlay(bySym['{lag}']).cautions.find(c => c.startsWith('Laggard'))"); print("laggard long caution:", lag, "→", p)
        ld = await pg.evaluate("() => (data.all.find(r => coinRot(r).status === 'Leader' && coinPlay(r).dir === 'Long') || {}).symbol")
        if ld:
            print("leader long boost:", ld, "→", await pg.evaluate(f"() => (coinPlay(bySym['{ld}']).boosts || []).find(c => c.startsWith('Leader'))"))
            await pg.evaluate(f"() => openDetail('{ld}')"); await asyncio.sleep(1.2)
            print("panel row:", await pg.evaluate("() => [...document.querySelectorAll('.dpane[data-pane=score] .kv span')].find(s => s.textContent === 'vs BTC (30d)').nextElementSibling.innerText"))
            await pg.keyboard.press("Escape")
        print("suggested setups with a rotation reason:", await pg.evaluate("() => (data.suggest || []).map(x => coin(x.r.symbol) + ': ' + x.reasons.join(', ')).join(' | ')"))
        await pg.evaluate("() => { goPage('overview'); document.getElementById('rotation').scrollIntoView(); }"); await asyncio.sleep(0.4)
        await pg.screenshot(path="rot_card.png", full_page=False)
        await pg.click("#copyBtn"); await asyncio.sleep(0.2)
        txt = await pg.evaluate("() => navigator.clipboard.readText()"); print("export:", [l for l in txt.split("\n") if l.startswith("Money flow")][0][:220])
        print("CSP:", csp or "none", "| errors:", errs or "none")
        await b.close()
asyncio.run(main())
