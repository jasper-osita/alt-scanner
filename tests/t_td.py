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
    check("a generic Forex Factory name doesn't pile onto a named holiday", await q("() => holEntries(hdKey(2026, 11, 26), hdKey(2026, 11, 26), [{ key: hdKey(2026, 11, 26), mk: 'US', n: 'Bank Holiday', half: false, src: 'ff' }]).find(e => e.mk === 'US').n === 'Thanksgiving'"))
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

async def part5(q):
    print("5) the written summary")
    S = "tdSay({ key: hdKey(2026, 11, 26), markets: [{ mk: 'Gold', call: 'untilLondon', fc: { ratio: 0.62, why: [{ centre: 'US', n: 3, half: false, factor: 0.62 }] } }, { mk: 'NAS100', call: 'closed', fc: { ratio: 0, why: [] } }], entries: holEntries(hdKey(2026, 11, 26), hdKey(2026, 11, 26)) })"
    check("thin day verdict", await q(f"() => {S}.verdict === 'Thin day'"))
    check("title names the day", "Thursday, Nov 26" in await q(f"() => {S}.title"))
    check("New York line names Thanksgiving", "Thanksgiving" in await q(f"() => {S}.lines.find(l => l.k === 'New York').v"))
    check("Asia and London lines say normal", await q(f"() => ['Asia', 'London'].every(k => {S}.lines.find(l => l.k === k).v.startsWith('Normal'))"))
    check("past years quotes its count", "3" in await q(f"() => ({S}.lines.find(l => l.k === 'Past years') || {{}}).v || ''"))
    check("for you points to London", "London" in await q(f"() => {S}.lines.find(l => l.k === 'For you').v"))
    check("normal day", await q("() => tdSay({ key: hdKey(2026, 12, 2), markets: [{ mk: 'Gold', call: 'ok', fc: { ratio: 1, why: [] } }], entries: [] }).verdict === 'Normal day'"))
    check("no past-years line without examples", await q("() => !tdSay({ key: hdKey(2026, 12, 2), markets: [{ mk: 'Gold', call: 'ok', fc: { ratio: 1, why: [] } }], entries: [] }).lines.some(l => l.k === 'Past years')"))
    check("closed day", await q("() => tdSay({ key: hdKey(2026, 12, 25), markets: [{ mk: 'Gold', call: 'closed', fc: { ratio: 0, why: [] } }, { mk: 'NAS100', call: 'closed', fc: { ratio: 0, why: [] } }], entries: holEntries(hdKey(2026, 12, 25), hdKey(2026, 12, 25)) }).verdict === 'Closed day'"))
    check("markets without data are left out of the verdict", await q("() => tdSay({ key: hdKey(2026, 12, 2), markets: [{ mk: 'Gold', call: 'ok', fc: { ratio: 1, why: [] } }, { mk: 'Silver', call: null, fc: null }], entries: [] }).verdict === 'Normal day'"))
    w = await q("() => tdSayWeek(['Normal day', 'Normal day', 'Normal day', 'Thin day', 'Thin day'].map((v, i) => ({ key: hdKey(2026, 11, 23) + i, verdict: v })))")
    check("the week in one sentence", w == "Normal Monday to Wednesday, thin Thursday and Friday.", w)
    check("a normal week", "normal week" in await q("() => tdSayWeek([0, 1, 2, 3, 4].map(i => ({ key: hdKey(2026, 11, 30) + i, verdict: 'Normal day' })))"))

async def part6(pg, q):
    print("6) loading candles and computing the day")
    # the app's rate limiter waits on the real clock, so the day is passed in rather than freezing time
    r = await q("() => tdLoad(true, Date.UTC(2026, 10, 26, 7, 42)).then(T => JSON.stringify(T.markets.map(m => [m.mk, m.sym, m.call, m.err])), e => 'err ' + e.message)")
    print("   markets:", r[:400])
    check("today's key is Thursday", await q("() => TD.key === hdKey(2026, 11, 26)"))
    check("no crypto ever", await q("() => TD.markets.length > 0 && TD.markets.every(m => tdMk(m.mk) !== null)"))
    check("NAS100 is closed on Thanksgiving", await q("() => (TD.markets.find(m => m.mk === 'NAS100') || {}).call === 'closed'"), r[:200])
    check("Gold has a call and a profile", await q("() => { const g = TD.markets.find(m => m.mk === 'Gold'); return !!g && !!g.call && g.prof.n > 0; }"))
    check("a market whose candles fail says so", await q("() => TD.markets.filter(x => x.err).every(m => m.call === null)"))
    check("history cached for next time", await q("() => scTx('kl', 'readonly', st => st.get('td|' + TD.markets.find(m => m.sym).sym)).then(x => !!(x && x.t.length))"))
    check("calls stored for the week", await q("() => !!JSON.parse(localStorage.getItem('finder-td-calls'))[TD.key]"))
    check("markets fall back to the default seven with an all-crypto watchlist", await q("() => { const keep = CHW; CHW = ['BTCUSDT', 'ETHUSDT']; const L = tdMarkets().map(m => m.mk).join(); CHW = keep; return L === 'Gold,Silver,EURUSD,GBPUSD,USDJPY,AUDUSD,NAS100'; }"))
    check("a default market with no source shows no data, not a call", await q("() => { const keep = CHW; CHW = []; const L = tdMarkets(); CHW = keep; return L.every(m => m.sym || tdCalcMarket(m, null, null, [], TD.key, Date.now()).err === 'No data yet'); }"))

async def part7(pg, q):
    print("7) the Trading day page")
    await q("() => tdLoad(true, Date.UTC(2026, 10, 26, 7, 42))")
    await q("() => goPage('tday')")
    await pg.wait_for_selector("#tdMkts .tdrow", timeout=60000)
    check("sidebar has Trading day under MARKET", await q("() => !!PAGE_INFO.tday && PAGE_INFO.tday.g === 'MARKET'"))
    say = await q("() => document.querySelector('.tdsay').innerText")
    check("summary leads with the verdict", any(v in say for v in ("Thin day", "Normal day", "Closed day")), say[:120])
    check("summary names Thanksgiving", "Thanksgiving" in await q("() => document.querySelector('.tdsay').innerText"))
    check("one row per market, no crypto", await q("() => { const R = [...document.querySelectorAll('#tdMkts .tdrow')]; return R.length === TD.markets.length && R.every(r => !/BTC|ETH|SOL/.test(r.innerText)); }"))
    check("NAS100 row says Closed", "Closed" in await q("() => (document.querySelector('#tdMkts .tdrow[data-mk=\"NAS100\"]') || {}).innerText || ''"))
    check("24 hour bars with PHT labels starting 9 (winter)", await q("() => document.querySelectorAll('.tdhours .tdbar').length === 24 && document.querySelector('.tdhlbl span').innerText.trim() === '9'"))
    await pg.click('#tdMkts .tdrow[data-mk="Silver"]')
    check("clicking a market switches the charts", "Silver" in await q("() => document.querySelector('.tdhourstitle').innerText"))
    check("day of week and 3 months drawn", await q("() => document.querySelectorAll('.tddow .tdbar').length === 5 && !!document.querySelector('.tdvol polyline')"))
    check("why this call quotes holidays", "Thanksgiving" in await q("() => document.querySelector('.tdwhy').innerText"))
    await pg.click('[data-tdview="week"]')
    check("week grid: 5 days × markets", await q("() => document.querySelectorAll('.tdweek .tdcell').length === 5 * TD.markets.length"))
    check("the week in one sentence", len(await q("() => document.querySelector('.tdweeksay').innerText")) > 10)
    check("today's column header stays in the grid", await q("() => { const h = document.querySelector('.tdweek b.tdnow'), g = document.querySelector('.tdweek'); return !!h && /Thu 26/.test(h.innerText) && getComputedStyle(h).position !== 'absolute' && g.contains(h); }"))
    check("ranges in the units people use", await q("() => tdFmt('Gold', 1738.04) === '$1,738' && tdFmt('Gold', 42.26) === '$42.3' && tdFmt('EURUSD', 0.0062) === '62 pips' && tdFmt('USDJPY', 0.95) === '95 pips' && tdFmt('NAS100', 310.4) === '310 pts'"))
    await pg.click('.tdweek .tdcell[data-day="3"]')
    check("a day's story with the call checked", "Thursday" in await q("() => document.querySelector('.tdstory').innerText"))
    check("thin stretches ahead list Christmas", "Dec 25" in await q("() => document.querySelector('.tdahead').innerText"))
    await pg.click('[data-tdview="today"]')
    await q("() => { goPage('charts'); tickClock(); }")
    check("Charts chip shows the day", await q("() => { const c = document.getElementById('chDay'); return !!c && !c.hidden && /Thin day|Normal day|Closed day/.test(c.innerText); }"))
    note = await q("() => { TD.markets.forEach(m => { if (m.call) m.call = 'quiet'; }); goPage('overview'); tickClock(); return document.getElementById('sessNote').innerText; }")
    check("Overview note leads with the day on a thin day", note.startswith("Thin day"), note[:80])
    note2 = await q("() => { TD.markets.forEach(m => { if (m.call) m.call = 'ok'; }); tickClock(); return document.getElementById('sessNote').innerText; }")
    check("no prefix on a normal day", not note2.startswith("Normal day"), note2[:80])

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
            await part5(q)
            await part6(pg, q)
            await part7(pg, q)
        except Exception as e:
            check("ran without a crash", False, str(e)[:300])
        print("errors:", F + errs[:4] or "none")
        await b.close()
asyncio.run(main())
