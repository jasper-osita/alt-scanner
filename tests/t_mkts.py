"""The boards across markets: crypto plus forex (cTrader, faked), indices and metals & energy (Binance TradFi perps, faked), same detectors."""
import asyncio, sys, os, re, functools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
print = functools.partial(print, flush=True)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "finder")
OPTS = {"secret": "sec", "token": "tok", "live": True}
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1500, "height": 1000}, color_scheme="dark"); await setup(ctx)
        pg = await ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: m.type == "error" and "Failed to load resource" not in m.text and errs.append("console: " + m.text[:160]))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.route_web_socket(re.compile(r"wss://(live|demo)\.ctraderapi\.com:5036.*"), ct_handler(OPTS))
        await pg.goto("http://localhost:8765/")
        await pg.evaluate("() => { localStorage.clear(); localStorage.setItem('finder-ctrader', JSON.stringify({ clientId: 'cid', clientSecret: 'sec', accessToken: 'tok', prefer: false })); }")
        await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        await q("() => goPage('day')"); await asyncio.sleep(0.3)
        print("1) switch:", await q("() => [...document.querySelectorAll('#mktSeg button')].map(b => b.textContent + (b.classList.contains('on') ? '*' : '')).join(' ') + ' | shown on day: ' + (getComputedStyle(document.querySelector('.mktbar')).display !== 'none')"))
        crypto_day = await q("() => [...document.querySelectorAll('#dayBoard .row')].map(r => r.dataset.s).join(',')")
        print("   crypto day board:", crypto_day)
        await pg.click('#mktSeg [data-mk="all"]')
        for _ in range(120):
            if await q("() => MACRO.rows.some(r => r.ct) && !MACRO.running"): break
            await asyncio.sleep(0.5)
        await asyncio.sleep(2)
        print("2) loaded:", await q("() => MACRO.rows.length + ' rows: ' + [...new Set(MACRO.rows.map(r => r.group))].join(', ') + ' | note: ' + document.getElementById('mktNote').textContent"))
        print("   classes:", await q("() => ['fx', 'idx', 'metals'].map(k => k + ' ' + MACRO.rows.filter(r => mkCls(r) === k).length).join(', ')"))
        for k in ["all", "fx", "idx", "metals", "crypto"]:
            await pg.click(f'#mktSeg [data-mk="{k}"]'); await asyncio.sleep(0.4)
            out = []
            for pgid, sel in [("day", "#dayBoard"), ("swing", "#swingBoard"), ("aots", "#aotsBoard"), ("momentum", "#momoBoard")]:
                await q(f"() => goPage('{pgid}')")
                rows = await q(f"() => [...document.querySelectorAll('{sel} .row')].map(r => r.dataset.s)")
                cls = await pg.evaluate("(L) => L.map(s => { const r = rowOf(s); return r ? mkCls(r) : '?'; })", rows)
                out.append(f"{pgid} {len(rows)} [{','.join(sorted(set(cls)))}]")
            await q("() => goPage('screener')"); await asyncio.sleep(0.2)
            out.append("screener " + await q("() => document.getElementById('count').textContent.split('·')[0].trim()"))
            print(f"3) {k}:", " | ".join(out))
        await pg.click('#mktSeg [data-mk="fx"]'); await q("() => goPage('day')"); await asyncio.sleep(0.3)
        print("4) forex day rows:", await q("() => [...document.querySelectorAll('#dayBoard .row')].map(r => r.querySelector('.tick').textContent + ' · ' + r.querySelector('.ln').textContent.slice(0, 80)).join(' || ')"))
        print("   no 'Against BTC' on forex:", await q("() => ![...document.querySelectorAll('#dayBoard .tag')].some(t => t.textContent === 'Against BTC')"))
        first = await q("() => { const r = document.querySelector('#dayBoard .row'); return r ? r.dataset.s : ''; }")
        if first:
            await pg.click(f'#dayBoard .row[data-s="{first}"]'); await asyncio.sleep(1.5)
            print("   popup:", await q("() => document.getElementById('dlg').open + ' ' + document.querySelector('.dhead h3').innerText.replace(/\\s+/g, ' ').slice(0, 60)"))
            await pg.keyboard.press("Escape")
        await q("() => goPage('screener')"); await asyncio.sleep(0.3)
        for t in await q("() => TABS.map(t => t.id)"):
            await q(f"() => {{ tab = '{t}'; renderTabs && renderTabs(); renderTable(); }}")
        print("5) every screener tab renders with forex:", await q("() => document.querySelectorAll('#tbody tr').length > 0"), "| search 'eur':", await q("() => { tab = 'overview'; renderTabs(); $('search').value = 'eur'; renderTable(); const n = document.querySelectorAll('#tbody tr[data-s]').length; $('search').value = ''; renderTable(); return n; }"))
        await pg.screenshot(path=f"{OUT}/mkts_screener.png")
        await q("() => goPage('day')"); await pg.click('#mktSeg [data-mk="all"]'); await asyncio.sleep(0.4); await pg.screenshot(path=f"{OUT}/mkts_day.png")
        print("6) history and streams stay on coins:", await q("() => (data.day || []).every(p => bySym[p.symbol]) && focusSymbols().every(s => bySym[s] || WL.coins[s])"))
        await pg.reload(); await ready(pg)
        print("7) after reload:", await q("() => MK.sel + ' ' + document.querySelector('#mktSeg .on').textContent"))
        print("errors:", errs[:5] or "none")
        await b.close()
asyncio.run(main())
