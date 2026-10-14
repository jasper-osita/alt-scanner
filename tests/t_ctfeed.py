import asyncio, sys, re
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OPTS = {"secret": "sec", "token": "tok", "live": True}
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1600, "height": 950}, color_scheme="dark"); await setup(ctx); await setup_mexc(ctx)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.route_web_socket("wss://contract.mexc.com/edge", mx_ws_handler)
        await pg.route_web_socket(re.compile(r"wss://(live|demo)\.ctraderapi\.com:5036.*"), ct_handler(OPTS))
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => { localStorage.clear(); localStorage.setItem('finder-ctrader', JSON.stringify({ clientId: 'cid', clientSecret: 'sec', accessToken: 'tok' })); }"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        async def wait(js, secs=200):
            for _ in range(secs * 2):
                if await q(js): return True
                await asyncio.sleep(0.5)
            return False
        await q("() => { document.getElementById('exF').value = 'mexc'; goPage('macro'); macroScan(true); }")
        print("loaded:", await wait("() => !MACRO.running && MACRO.src === 'mexc' && MACRO.rows.some(r => r.ct)"))
        print("boards:", await q("() => [...document.querySelectorAll('#macroBody .board-head h2')].map(h => h.innerText.replace(/\\s+/g,' ') + ' (' + h.closest('.board').querySelectorAll('.row').length + ')').join(' | ')"))
        print("exchange rows left:", await q("() => MACRO.rows.filter(r => !r.ct).map(r => r.name + ' [' + macroSrcName(r) + ']').join(', ')"))
        print("broker rows:", await q("() => MACRO.rows.filter(r => r.ct && r.group !== 'Forex').map(r => r.name + '=' + coin(r.symbol) + ' ' + r.group).join(', ')"))
        print("no duplicates:", await q("() => { const n = MACRO.rows.map(r => r.name); return n.length === new Set(n).size; }"), "| bar:", await q("() => document.getElementById('ctBar').innerText"))
        print("read-out:", await q("() => document.getElementById('macroRead').innerText.replace(/\\s+/g,' ').slice(0, 220)"))
        await q("() => goPage('macroov')"); await asyncio.sleep(1)
        print("overview movers:", await q("() => document.getElementById('xMv_fx').innerText.replace(/\\s+/g,' ').slice(0, 160)"))
        print("flow classes:", await q("() => [...document.querySelectorAll('#xFlow .xkv > span')].filter((e, i) => i % 4 === 0).map(e => e.textContent).filter(Boolean).join(', ')"))
        await q("() => goPage('macromomo')"); await asyncio.sleep(1)
        print("momentum sources:", await q("() => [...document.querySelectorAll('#xMomo .row')].map(r => r.dataset.s).join(', ')"))
        # charts
        await q("() => goPage('charts')"); await asyncio.sleep(3)
        print("watchlist:", await q("() => [...document.querySelectorAll('.chwr')].map(r => r.dataset.s).join(', ')"))
        await q("() => chSetSym('MX:NAS100_USDT')"); await asyncio.sleep(3)
        print("MEXC Nasdaq → ", await q("() => [CH.sym, chName(CH.sym), document.querySelector('.chsrcb').textContent, document.querySelector('.chfeed').textContent, chVis().map(P => P.tf + ':' + P.t.length).join(' ')]"))
        await q("() => { chPickClose(); chPickOpen('indices'); }"); await asyncio.sleep(2)
        print("indices picker:", await q("() => chCatList('indices').join(', ')"), "|", await q("() => document.getElementById('chPick').innerText.replace(/\\s+/g,' ').slice(0, 300)"))
        print("fx list:", await q("() => { const L = chCatList('fx'); return L.filter(s => s.startsWith('CT:')).length + ' broker · MEXC: ' + L.filter(s => s.startsWith('MX:')).join(','); }"), "| metals:", await q("() => chCatList('metals').join(', ')"))
        await q("() => chPickClose()")
        for tf in ["1m", "2h", "1w"]:
            await q(f"() => {{ const s = document.querySelector('.chtf[data-i=\"' + chVis()[0].i + '\"]'); s.value = '{tf}'; s.dispatchEvent(new Event('change')); }}"); await asyncio.sleep(2.5)
            print(f"tf {tf}:", await q("() => { const P = chVis()[0]; return [P.tf, P.t.length, P.msg.hidden ? 'ok' : P.msg.textContent, P.t.length > 2 ? (P.t.at(-1) - P.t.at(-2)) / 60000 + 'min' : '']; }"))
        print("live tick:", await q("() => { const x = CT.symbols['NAS100']; CT.onSpot({ symbolId: x.symbolId, bid: 3123456700 }); return chVis().map(P => P.c.at(-1)).join(','); }"))
        # pop-up from a MEXC leftover and from a broker row
        await q("() => { goPage('overview'); openDetail(MACRO.rows.find(r => r.ct && r.name === 'Gold').symbol); }"); await asyncio.sleep(3)
        print("pop-up gold:", await q("() => [CH.sym, document.querySelector('#dChartHost .chsrcb').textContent, chVis()[0].t.length]"))
        await q("() => document.getElementById('dlg').close()"); await asyncio.sleep(0.3)
        # prefer off: exchange rows come back next to the broker's
        await q("() => { const c = ctCfg(); c.prefer = false; ctSaveCfg(c); goPage('macro'); macroScan(true); }")
        await wait("() => !MACRO.running && MACRO.rows.some(r => r.mx) && MACRO.rows.some(r => r.ct)")
        print("prefer off:", await q("() => [MACRO.rows.filter(r => r.mx).length, MACRO.rows.filter(r => r.ct).length, !!MACRO.by['MX:XAU_USDT'], document.getElementById('ctBar').innerText.slice(-60)]"), "| chart equiv:", await q("() => ctEquiv('MX:NAS100_USDT')"))
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
