"""Trading day: holiday rules, the trading-day clock, profiles, the day's calls and the page (index.html core + extras)."""
import asyncio, sys, datetime, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from mock import *
from playwright.async_api import async_playwright
UTC = datetime.timezone.utc
F = []
def check(name, ok, detail=""):
    print(("   ok " if ok else "   FAIL ") + name + (" · " + str(detail) if detail else ""))
    if not ok: F.append(name)

async def has(q, mk, y, m, d, half=None):
    extra = "" if half is None else f" && !!h.half === {str(half).lower()}"
    return await q(f"() => (holRules('{mk}', {y}) || []).some(h => h.m === {m} && h.d === {d}{extra})")

async def part1(q):
    print("1) holiday rules")
    check("US Thanksgiving 2026 closed", await has(q, "US", 2026, 11, 26, False))
    check("US day after Thanksgiving 2026 half", await has(q, "US", 2026, 11, 27, True))
    check("UK Boxing Day 2026 moved to Mon 28", await has(q, "UK", 2026, 12, 28, False))
    check("UK Christmas Eve 2026 half", await has(q, "UK", 2026, 12, 24, True))
    check("Frankfurt shut Dec 24 and 31 2026", await has(q, "EU", 2026, 12, 24, False) and await has(q, "EU", 2026, 12, 31, False))
    check("Japan Coming of Age 2027-01-11", await has(q, "JP", 2027, 1, 11, False))
    check("Japan citizens' holiday 2026-09-22", await has(q, "JP", 2026, 9, 22, False))
    check("Japan vernal equinox 2027 moved to Mon 22", await has(q, "JP", 2027, 3, 22, False))
    check("Hong Kong Lunar New Year 2026-02-17", await has(q, "HK", 2026, 2, 17, False))
    check("Hong Kong Christmas Eve 2026 half", await has(q, "HK", 2026, 12, 24, True))
    check("Korea Chuseok 2026-09-24", await has(q, "KR", 2026, 9, 24, False))
    check("Australia Boxing Day 2026 moved to Mon 28", await has(q, "AU", 2026, 12, 28, False))
    check("Canada Boxing Day 2026 moved to Mon 28", await has(q, "CA", 2026, 12, 28, False))
    check("Switzerland Ascension 2026-05-14", await has(q, "CH", 2026, 5, 14, False))
    check("no weekend entries", await q("() => HOL_MKTS.every(([k]) => (holRules(k, 2026) || []).every(h => ![0, 6].includes(new Date(Date.UTC(2026, h.m - 1, h.d)).getUTCDay())))"))
    check("Hong Kong 2028 has no data", await q("() => holRules('HK', 2028) === null && holRules('KR', 2028) === null"))
    check("day keys round-trip", await q("() => hdYmd(hdKey(2026, 11, 26)).join('-') === '2026-11-26'"))

async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1400, "height": 950}, color_scheme="dark")
        await setup(ctx); await setup_mexc(ctx); await setup_extra(ctx)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        try:
            await part1(q)
        except Exception as e:
            check("ran without a crash", False, str(e)[:300])
        print("errors:", F + errs[:4] or "none")
        await b.close()
asyncio.run(main())
