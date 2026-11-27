"""Trading day: holiday rules, the trading-day clock, profiles, the day's calls and the page (index.html core + extras)."""
import asyncio, sys, datetime, os, re
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

async def part2(q):
    print("2) the trading-day clock and the holiday merge")
    check("3:00 AM PHT Fri is Thursday's trading day", await q("() => tdKey(Date.UTC(2026, 10, 26, 19, 0)) === hdKey(2026, 11, 26)"))
    check("8:30 AM PHT Fri is still Thursday (before the winter Asia open)", await q("() => tdKey(Date.UTC(2026, 10, 27, 0, 30)) === hdKey(2026, 11, 26)"))
    check("9:15 AM PHT Fri is Friday, bin 0", await q("() => tdKey(Date.UTC(2026, 10, 27, 1, 15)) === hdKey(2026, 11, 27) && tdBin(Date.UTC(2026, 10, 27, 1, 15)) === 0"))
    check("summer time: 3:00 AM PHT is still the day before", await q("() => tdKey(Date.UTC(2026, 6, 15, 19, 0)) === hdKey(2026, 7, 15)"))
    check("July: 8:15 AM PHT is already bin 0", await q("() => tdBin(Date.UTC(2026, 6, 15, 0, 15)) === 0"))
    check("tdStart inverts tdKey (winter and summer)", await q("() => [hdKey(2026, 11, 27), hdKey(2026, 7, 15)].every(k => tdKey(tdStart(k)) === k && tdBin(tdStart(k)) === 0)"))
    check("centre bins", await q("() => TD_CENTRE_BINS.US.join() === '13,14,15,16,17,18,19' && TD_CENTRE_BINS.UK.join() === '4,5,6,7,8,9,10' && TD_CENTRE_BINS.JP.join() === '0,1,2,3' && TD_CENTRE_BINS.CA.join() === '13,14,15,16,17'"))
    check("a range over New Year has Dec 31 and Jan 1", await q("() => { const E = holEntries(hdKey(2026, 12, 30), hdKey(2027, 1, 2)); return E.some(e => e.key === hdKey(2026, 12, 31)) && E.some(e => e.key === hdKey(2027, 1, 1)); }"))
    check("one entry per day and market, full close wins", await q("() => { const E = holEntries(hdKey(2026, 11, 26), hdKey(2026, 11, 26), [{ key: hdKey(2026, 11, 26), mk: 'US', n: 'Thanksgiving', half: true, src: 'broker' }]); const us = E.filter(e => e.mk === 'US'); return us.length === 1 && us[0].half === false && us[0].srcs.join() === 'rules,broker'; }"))
    check("Forex Factory USD holiday maps to the US", await q("() => ffHolidays([{ at: Date.parse('2026-11-26T00:00:00-05:00'), ccy: 'USD', title: 'Bank Holiday', impact: 'Holiday' }])[0].key === hdKey(2026, 11, 26)"))
    check("Forex Factory: other currencies and other impacts dropped", await q("() => ffHolidays([{ at: Date.parse('2026-11-26T00:00:00-05:00'), ccy: 'NZD', title: 'Bank Holiday', impact: 'Holiday' }, { at: Date.parse('2026-11-26T08:30:00-05:00'), ccy: 'USD', title: 'GDP', impact: 'High' }]).length === 0"))
    check("plain wording", await q("() => holSay({ mk: 'US', n: 'Day after Thanksgiving', half: true }) === 'US half day (Day after Thanksgiving)' && holSay({ mk: 'US', n: 'Thanksgiving', half: false }) === 'US Thanksgiving' && holSay({ mk: 'FX', n: 'Christmas', half: false }) === 'Your broker Christmas'"))
    check("no cTrader: a clear error, not a crash", (await q("() => ctHolidays(true).then(() => 'ok', e => 'err ' + e.message)")) == "err cTrader isn't connected")

async def part2b(ctx):
    print("2b) the broker's holiday list from cTrader")
    pg2 = await ctx.new_page(); e2 = []; pg2.on("pageerror", lambda e: e2.append(str(e)))
    await pg2.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
    await pg2.route_web_socket(re.compile(r"wss://(live|demo)\.ctraderapi\.com:5036.*"), ct_handler({"secret": "sec", "token": "tok", "live": True}))
    await pg2.goto("http://localhost:8765/"); await pg2.evaluate("() => { localStorage.clear(); localStorage.setItem('finder-ctrader', JSON.stringify({ clientId: 'cid', clientSecret: 'sec', accessToken: 'tok' })); }"); await pg2.reload(); await ready(pg2)
    await pg2.wait_for_function("() => typeof CT !== 'undefined' && CT.state === 'ready'", timeout=30000)
    q2 = lambda js: pg2.evaluate(js)
    r = await q2("() => ctHolidays(true).then(x => JSON.stringify({ c: x.count, m: x.markets }), e => 'err ' + e.message)")
    check("broker list read", '"c":4' in r and '"m":3' in r, r)
    check("recurring broker holiday repeats", await q2("() => brokerHolidays(JSON.parse(localStorage.getItem('finder-hol')).bySym, hdKey(2026, 12, 1), hdKey(2026, 12, 31)).some(h => h.mk === 'FX' && h.key === hdKey(2026, 12, 25))"))
    check("broker half day", await q2("() => brokerHolidays(JSON.parse(localStorage.getItem('finder-hol')).bySym, hdKey(2026, 11, 27), hdKey(2026, 11, 27))[0].half === true"))
    check("cached: a second read reuses the stored list", await q2("() => { const at = JSON.parse(localStorage.getItem('finder-hol')).at; return ctHolidays(false).then(x => x.at === at && x.count === 4); }"))
    await pg2.close()
    return e2

FIXTURE_JS = """
window.TD_TEST_SHAPE = [5, 5, 4.5, 4.5, 5, 6.5, 12, 16, 14, 12, 10, 9, 13, 18, 20, 16, 12, 9, 7, 5, 3, 3, 3.5, 4.5];
window.tdFixture = function (seed, opts) {          // 1-hour candles for every weekday 2025-06-02 → 2026-12-31, ranges shaped like TD_TEST_SHAPE
  opts = opts || {}; let s = seed * 9301 + 49297; const rnd = () => (s = (s * 16807) % 2147483647) / 2147483647;
  const K = { t: [], o: [], h: [], l: [], c: [], qv: [] };
  for (let k = hdKey(2025, 6, 2); k <= hdKey(2026, 12, 31); k++) {
    const wd = new Date(k * 864e5).getUTCDay(); if (wd === 0 || wd === 6) continue;
    const t0 = tdStart(k), f = (opts.thin && opts.thin[k]) || 1;
    for (let b = 0; b < 24; b++) { const r = TD_TEST_SHAPE[b] * (opts.flat ? 1 : 0.9 + 0.2 * rnd()) * f;
      K.t.push(t0 + b * 3600e3); K.o.push(100); K.c.push(100); K.h.push(100 + r / 2); K.l.push(100 - r / 2); K.qv.push(1); }
  }
  return K;
};
"""

async def part3(q):
    print("3) profiles and holiday effects")
    check("profile ignores holidays", await q("() => { const K = tdFixture(1, { thin: { [hdKey(2026, 11, 23)]: 0.3 } }), D = tdDays(K); const a = tdProfile(D, new Set([hdKey(2026, 11, 23)]), hdKey(2026, 11, 27)), b = tdProfile(D, new Set(), hdKey(2026, 11, 27)); return a.n === 20 && !a.keys.includes(hdKey(2026, 11, 23)) && b.keys.includes(hdKey(2026, 11, 23)); }"))
    check("a Monday holiday doesn't drag the median down", await q("() => { const D = tdDays(tdFixture(6, { flat: true, thin: { [hdKey(2026, 11, 23)]: 0.3 } })); const a = tdProfile(D, new Set([hdKey(2026, 11, 23)]), hdKey(2026, 11, 27)); return Math.abs(a.day - 20) < 1e-6; }"))
    check("profile median of a flat fixture equals its shape", await q("() => { const P = tdProfile(tdDays(tdFixture(2, { flat: true })), new Set(), hdKey(2026, 11, 27)); return Math.abs(P.bins[6] / P.bins[0] - TD_TEST_SHAPE[6] / TD_TEST_SHAPE[0]) < 0.01; }"))
    check("weekends dropped from the days", await q("() => { const D = tdDays(tdFixture(2, {})); return ![...D.keys()].some(k => [0, 6].includes(new Date(k * 864e5).getUTCDay())); }"))
    r = await q("() => { const E = holEntries(hdKey(2025, 7, 1), hdKey(2026, 11, 20)); const K = tdFixture(3, { thin: Object.fromEntries(E.filter(e => e.mk === 'US').map(e => [e.key, 0.6])) }); const fx = tdFx(tdDays(K), E, ['US'])['US']; return JSON.stringify({ n: fx.n, day: fx.day, b: fx.bins.length }); }")
    check("US holiday effect measured at about 0.6 with its count", '"b":24' in r and (lambda d: d["n"] >= 8 and abs(d["day"] - 0.6) < 0.08)(__import__("json").loads(r)), r)
    check("a centre with no past holidays has n 0", await q("() => { const D = tdDays(tdFixture(4, {})); return tdFx(D, [], ['JP'])['JP'].n === 0; }"))
    check("day of week has five values", await q("() => tdDow(tdDays(tdFixture(4, {})), new Set()).length === 5"))
    check("series is the latest 65 trading days", await q("() => { const S = tdSeries(tdDays(tdFixture(5, {}))); return S.length === 65 && S[64].key > S[0].key; }"))

async def part4(q):
    print("4) forecast, calls, live check, room left")
    P = "{ bins: TD_TEST_SHAPE.slice(), day: 60, n: 20 }"
    check("no holiday: Tradeable", await q(f"() => tdCall(tdForecast('EURUSD', {P}, {{}}, []), {P}) === 'ok'"))
    check("US closed, no history: Tradeable until London", await q(f"() => tdCall(tdForecast('EURUSD', {P}, {{}}, [{{ mk: 'US', half: false }}]), {P}) === 'untilLondon'"))
    check("US closed: NAS100 Closed", await q(f"() => tdCall(tdForecast('NAS100', {P}, {{}}, [{{ mk: 'US', half: false }}]), {P}) === 'closed'"))
    check("US half day: NAS100 not Closed", await q(f"() => tdCall(tdForecast('NAS100', {P}, {{}}, [{{ mk: 'US', half: true }}]), {P}) !== 'closed'"))
    check("UK and US closed: Gold Likely quiet", await q(f"() => tdCall(tdForecast('Gold', {P}, {{}}, [{{ mk: 'UK', half: false }}, {{ mk: 'US', half: false }}]), {P}) === 'quiet'"))
    check("Japan holiday leaves Gold Tradeable", await q(f"() => tdCall(tdForecast('Gold', {P}, {{}}, [{{ mk: 'JP', half: false }}]), {P}) === 'ok'"))
    check("measured effect wins with 2+ examples", await q(f"() => tdForecast('Gold', {P}, {{ US: {{ n: 3, day: 0.95, bins: Array(24).fill(0.95) }} }}, [{{ mk: 'US', half: false }}]).ratio > 0.9"))
    check("forecast says why, with the example count", await q(f"() => {{ const f = tdForecast('Gold', {P}, {{ US: {{ n: 3, day: 0.6, bins: Array(24).fill(0.6) }} }}, [{{ mk: 'US', half: false }}]); return f.why.length === 1 && f.why[0].centre === 'US' && f.why[0].n === 3 && Math.abs(f.day - 60 * f.ratio) < 1e-9; }}"))
    check("live: waking up at twice the hour", await q(f"() => tdLive({{ bins: TD_TEST_SHAPE.map((v, i) => i === 6 ? v * 2.2 : i < 6 ? v : null), range: 70 }}, {P}, 6).state === 'waking'"))
    check("live: quiet under 60%", await q(f"() => tdLive({{ bins: TD_TEST_SHAPE.map((v, i) => i <= 6 ? v * 0.4 : null), range: 6 }}, {P}, 6).state === 'quiet'"))
    check("live: moving normally at 80%+", await q(f"() => tdLive({{ bins: TD_TEST_SHAPE.map((v, i) => i <= 6 ? v : null), range: 12 }}, {P}, 6).state === 'normal'"))
    check("room left", await q("() => Math.abs(tdRoom(15, 40) - 0.625) < 1e-9 && tdRoom(50, 40) === 0"))
    check("market ids", await q("() => ['CT:XAUUSD', 'XAUUSDT', 'MX:XAU_USDT', 'Gold'].every(s => tdMk(s) === 'Gold') && tdMk('QQQUSDT') === 'NAS100' && tdMk('Nasdaq 100') === 'NAS100' && tdMk('CT:US500') === 'US500' && tdMk('CT:EURUSD') === 'EURUSD' && tdMk('EUR/USD') === 'EURUSD' && tdMk('BTCUSDT') === null && tdMk('ETHUSDT') === null"))
    check("no candles: no call, says so", await q("() => { const r = tdCalcMarket({ mk: 'Gold', sym: 'CT:XAUUSD' }, null, null, [], hdKey(2026, 11, 26), Date.UTC(2026, 10, 26, 7, 42)); return r.call === null && r.err === 'No data yet'; }"))
    r = await q("() => { const E = holEntries(hdKey(2025, 6, 1), hdKey(2026, 12, 31)); const K = tdFixture(7, { thin: Object.fromEntries(E.filter(e => e.mk === 'US').map(e => [e.key, 0.6])) }); const m = tdCalcMarket({ mk: 'NAS100', sym: 'CT:NAS100' }, K, null, E, hdKey(2026, 11, 26), Date.UTC(2026, 10, 26, 7, 42)); return JSON.stringify({ call: m.call, n: m.prof.n, err: m.err || null }); }")
    check("a full market on Thanksgiving: NAS100 Closed from candles + holidays", '"call":"closed"' in r and '"n":20' in r, r)

async def main():
    serve()
    async with async_playwright() as pw:
        b = await pw.chromium.launch(); ctx = await b.new_context(viewport={"width": 1400, "height": 950}, color_scheme="dark")
        await setup(ctx); await setup_mexc(ctx); await setup_extra(ctx); await ctx.add_init_script(FIXTURE_JS)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route_web_socket("wss://fstream.binance.com/stream", lambda ws: None)
        await pg.goto("http://localhost:8765/"); await pg.evaluate("() => localStorage.clear()"); await pg.reload(); await ready(pg)
        q = lambda js: pg.evaluate(js)
        try:
            await part1(q)
            await part2(q)
            errs += await part2b(ctx)
            await part3(q)
            await part4(q)
        except Exception as e:
            check("ran without a crash", False, str(e)[:300])
        print("errors:", F + errs[:4] or "none")
        await b.close()
asyncio.run(main())
