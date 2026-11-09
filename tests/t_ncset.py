import asyncio, sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
OUT = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "out", "finder")
# Notification settings: per kind on/off, banner, sound, pop-up, phone (Telegram mocked)
async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1440, "height": 900}, color_scheme="dark"); await setup(ctx); await setup_extra(ctx)
        pg = await ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg); await asyncio.sleep(1)
        q = lambda js: pg.evaluate(js)
        # count beeps and pop-ups instead of making them
        await q("() => { window.BEEPS = 0; window.POPS = []; beep = () => { BEEPS++; }; ncPopup = (t, body) => { POPS.push(t); }; ncClearToasts(); }")
        print("1) defaults:", await q("() => NC_TYPES.map(([k]) => { const p = ncPref(k); return k + ' ' + ['on','banner','sound','device'].filter(w => p[w]).join('/'); }).join(' | ')"))
        # open settings from the bell
        await pg.click("#bellBtn"); await asyncio.sleep(0.3); await pg.click("#ncSetBtn"); await asyncio.sleep(0.2)
        print("2) settings view:", await q("() => ({ title: ncTitle.textContent, pressed: ncSetBtn.getAttribute('aria-pressed'), list: !ncList.hidden, chips: !ncChips.hidden, rows: document.querySelectorAll('#ncSet [data-ncrow]').length, boxes: document.querySelectorAll('#ncSet [data-ncw]').length, phoneDisabled: [...document.querySelectorAll('#ncSet [data-ncw=phone]')].every(x => x.disabled), setupLink: !!document.querySelector('#ncSet [data-ncphone]') })"))
        await pg.screenshot(path=f"{OUT}/ncset.png")
        # turn Bots off: nothing kept, no banner/sound/pop-up
        await pg.click('#ncSet [data-nck="Bots"][data-ncw="on"]'); await asyncio.sleep(0.1)
        print("3) bots row:", await q("() => ({ off: document.querySelector('[data-ncrow=Bots]').classList.contains('off'), others: [...document.querySelectorAll('[data-ncrow=Bots] [data-ncw]')].filter(x => x.dataset.ncw !== 'on').every(x => x.disabled), saved: localStorage.getItem('finder-nc-prefs') })"))
        n0 = await q("() => NC.length")
        r = await q("() => { const it = ncAdd({ sym: data.all[5].symbol, kind: 'Bots', icon: '🤖', tone: 'up', title: 'Bounce bot closed at +2.10R' }); return { muted: !!it.muted, added: NC.length, toasts: document.querySelectorAll('#ncToasts .nctoast').length, beeps: BEEPS, pops: POPS.length }; }")
        print("   bots muted:", r, "| before", n0)
        # Price: banner and sound off, pop-up on
        await pg.click('#ncSet [data-nck="Price"][data-ncw="banner"]'); await pg.click('#ncSet [data-nck="Price"][data-ncw="sound"]')
        await q("() => { BEEPS = 0; POPS = []; }")
        r = await q("() => { notify('TIA reached 6.420', 'Price is 6.447, above your alert level.', { sym: data.all[3].symbol, kind: 'Price', icon: '🔔', tone: 'blue', title: 'Crossed above your 6.420 alert' }); return { kept: NC[0].title, toasts: document.querySelectorAll('#ncToasts .nctoast').length, beeps: BEEPS, pops: POPS }; }")
        print("4) price quiet:", r)
        # Setups default: banner + sound + pop-up; a burst beeps once
        await q("() => { BEEPS = 0; POPS = []; }")
        r = await q("() => { ncAdd({ sym: data.all[1].symbol, kind: 'Setups', icon: '🥪', tone: 'gold', title: 'NBB long triggered', detail: 'Entry 1 · Stop 0.9' }); ncAdd({ sym: data.all[2].symbol, kind: 'Setups', icon: '🥪', tone: 'gold', title: 'NBB short triggered' }); return { toasts: document.querySelectorAll('#ncToasts .nctoast').length, beeps: BEEPS, pops: POPS }; }")
        print("5) setups loud:", r)
        # System default: banner only
        await q("() => { BEEPS = 0; POPS = []; ncClearToasts(); }")
        r = await q("() => { ncAdd({ kind: 'System', icon: '⚠️', tone: 'warn', sym: null, title: 'Order filled' }); return { toasts: document.querySelectorAll('#ncToasts .nctoast').length, beeps: BEEPS, pops: POPS.length }; }")
        print("6) system banner only:", r)
        # phone column: set up Telegram, then muted kinds don't send
        await q("() => { localStorage.setItem('finder-telegram', JSON.stringify({ token: '1:x', chat: '42' })); ncRenderSet(); }")
        print("7) phone column:", await q("() => [...document.querySelectorAll('#ncSet [data-ncw=phone]')].map(x => x.dataset.nck + (x.checked ? '+' : '-') + (x.disabled ? 'd' : '')).join(' ')"))
        await pg.click('#ncSet [data-nck="News"][data-ncw="phone"]'); await asyncio.sleep(0.1)
        print("   news phone off saved:", await q("() => JSON.parse(localStorage.getItem('finder-telegram')).kinds"))
        TG_LOG.clear()
        await q("() => { ncAdd({ kind: 'Bots', icon: '🤖', title: 'muted bot' }); ncAdd({ kind: 'News', icon: '📅', title: 'CPI in 15m' }); ncAdd({ kind: 'Price', icon: '🔔', title: 'phone price', sym: null }); }")
        await asyncio.sleep(3)
        print("   telegram sent:", [m.get("text", "").split("\n")[0] for m in TG_LOG], "(only the price alert)")
        # Telegram dialog notes the muted kind
        await q("() => openTGSettings()"); await asyncio.sleep(0.3)
        print("   tg dialog note:", await q("() => [...document.querySelectorAll('.tgkinds label')].filter(l => l.textContent.includes('turned off')).map(l => l.textContent.trim()).join(' | ')"))
        await q("() => document.getElementById('dlg').close()")
        # persists over reload, drawer opens on the list again
        await pg.reload(); await asyncio.sleep(2)
        print("8) after reload:", await q("() => ({ bots: ncPref('Bots').on, priceBanner: ncPref('Price').banner, priceSound: ncPref('Price').sound })"))
        await pg.click("#bellBtn"); await asyncio.sleep(0.3)
        print("   drawer opens on list:", await q("() => ({ list: !ncList.hidden, set: !ncSet.hidden, title: ncTitle.textContent })"))
        await pg.click("#ncSetBtn"); await asyncio.sleep(0.2); await pg.click("#ncSetReset"); await asyncio.sleep(0.2)
        print("9) reset:", await q("() => ({ prefs: localStorage.getItem('finder-nc-prefs'), bots: ncPref('Bots').on, tgKinds: JSON.parse(localStorage.getItem('finder-telegram')).kinds || 'defaults', botsRow: document.querySelector('[data-ncrow=Bots]').classList.contains('off') })"))
        await pg.click("#ncSetBtn"); await asyncio.sleep(0.2)
        print("   back to list:", await q("() => ({ list: !ncList.hidden, readAll: !ncReadAll.hidden, title: ncTitle.textContent })"))
        # phone width
        await pg.set_viewport_size({"width": 390, "height": 844}); await asyncio.sleep(0.3)
        await pg.click("#ncSetBtn"); await asyncio.sleep(0.2)
        print("10) mobile:", await q("() => { const g = document.querySelector('.ncsgrid').getBoundingClientRect(), s = ncSet.getBoundingClientRect(); return { gridW: Math.round(g.width), panelW: Math.round(s.width), overflow: document.documentElement.scrollWidth - innerWidth, inside: g.right <= s.right + 1 }; }"))
        await pg.screenshot(path=f"{OUT}/ncset_mobile.png")
        print("errors:", errs or "none")
        await b.close()
asyncio.run(main())
