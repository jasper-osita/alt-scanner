// The Finder's cloud watcher: runs on GitHub Actions every 5 minutes and sends Telegram alerts while your Mac is off or asleep.
// It reuses the app's own rules (the scanner core inside index.html) and reads MEXC's public market data and Forex Factory's feed.
// Secrets come from the repo's Actions secrets (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID); nothing secret lives in this repo.
import fs from "node:fs"; import vm from "node:vm"; import path from "node:path"; import { fileURLToPath } from "node:url";
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const CFG = JSON.parse(fs.readFileSync(path.join(ROOT, "cloud/watch.json"), "utf8"));
const TOKEN = process.env.TELEGRAM_BOT_TOKEN, CHAT = process.env.TELEGRAM_CHAT_ID, NOW = +(process.env.WATCH_NOW || Date.now());
const STATE_FILE = process.env.WATCH_STATE || path.join(ROOT, ".watch-state.json");
const DRY = process.env.WATCH_DRY === "1";
if (!DRY && (!TOKEN || !CHAT)) { console.log("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID aren't set: nothing to do."); process.exit(0); }

// the app's scanner core, run as-is
const html = fs.readFileSync(path.join(ROOT, "index.html"), "utf8"), a = html.indexOf('<script id="core">');
const src = html.slice(a + '<script id="core">'.length, html.indexOf("</script>", a));
const ctx = { console, fetch: (...x) => globalThis.fetch(...x), URL, Intl, Date, Math, JSON, Promise, setTimeout, clearTimeout,
  localStorage: { getItem: () => null, setItem() {}, removeItem() {} }, document: { querySelectorAll: () => [] }, navigator: {}, location: { hostname: "cloud" } };
ctx.window = ctx; vm.createContext(ctx);
vm.runInContext(src + "\n;this.__F = { nbbWatchRead, mxKlinesF, mxRowsToK, ffNorm, fmtNum };", ctx);
const fmtP = v => v >= 1000 ? v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : F.fmtNum(v);
const F = ctx.__F;

let state = { sent: {} }; try { state = JSON.parse(fs.readFileSync(STATE_FILE, "utf8")); } catch (e) {}
state.sent = state.sent || {}; Object.keys(state.sent).forEach(k => { if (NOW - state.sent[k] > 4 * 864e5) delete state.sent[k]; });
const out = [];
async function send(id, text) {
  if (state.sent[id]) return; state.sent[id] = NOW; out.push(text);
  if (DRY) { console.log("[dry run]", text.replace(/<[^>]+>/g, "")); return; }
  const r = await globalThis.fetch(`https://api.telegram.org/bot${TOKEN}/sendMessage`, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: CHAT, text, parse_mode: "HTML", disable_web_page_preview: true }) });
  const j = await r.json().catch(() => ({})); if (!j.ok) { delete state.sent[id]; console.log("Telegram refused:", j.description || r.status); }
}
const esc = s => String(s).replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
const PHT = 8 * 3600e3, phtMin = ms => { const d = new Date(ms + PHT); return d.getUTCHours() * 60 + d.getUTCMinutes(); };
const hm = s => { const [h, m] = String(s).split(":").map(Number); return h * 60 + (m || 0); };
const phtHM = ms => { const d = new Date(ms + PHT); let h = d.getUTCHours(); const m = String(d.getUTCMinutes()).padStart(2, "0"); return `${h % 12 || 12}:${m} ${h >= 12 ? "PM" : "AM"}`; };
const IV = { "1m": 60e3, "3m": 180e3, "5m": 300e3, "15m": 900e3, "30m": 1800e3, "1h": 3600e3 };
function weekendClosed(ms) {                         // forex, metals and index CFDs: Friday 5 PM to Sunday 5 PM New York
  const p = {}; new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", weekday: "short", hour: "numeric", minute: "numeric", hourCycle: "h23" }).formatToParts(new Date(ms)).forEach(x => p[x.type] = x.value);
  const m = (+p.hour % 24) * 60 + +p.minute; return p.weekday === "Sat" || (p.weekday === "Sun" && m < 1020) || (p.weekday === "Fri" && m >= 1020);
}
const inSession = (it, ms) => { const m = phtMin(ms), x = hm(it.from), y = hm(it.to); return (y <= x ? (m >= x || m < y) : (m >= x && m < y)) && !weekendClosed(ms); };

// 1) NBB on MEXC's perpetuals during your sessions
for (const it of CFG.nbb || []) {
  if (!inSession(it, NOW)) continue;
  const iv = IV[it.tf]; if (!iv) continue;
  try {
    const rows = (await F.mxKlinesF("MX:" + it.contract, it.tf, NOW - 420 * iv, NOW)).filter(r => r[0] + iv <= NOW);
    const k = F.mxRowsToK(rows), r = F.nbbWatchRead(k, iv); if (!r) continue;
    if (r.trig && NOW - r.trig.tClose <= (it.maxAgeMin || 10) * 60e3) {
      const m = r.trig, R = Math.abs(m.entry - m.stop), t3 = m.dir === "Long" ? m.entry + 3 * R : m.entry - 3 * R, f = fmtP;
      await send(`nbb|${it.contract}|${it.tf}|${m.dir}|${m.tClose}`, `☁️ 🥪 <b>NBB ${m.dir.toLowerCase()}: ${esc(it.name)} ${it.tf}</b>\nEntry ${f(m.entry)} · Stop ${f(m.stop)} · 3R ${f(t3)}\n${r.stack === m.dir ? "With" : "Against"} the ${it.tf} trend${m.sweep ? " · base swept first" : ""}${m.room ? "" : " · little room to 2R"}\nClose at ${phtHM(m.tClose)} PHT · MEXC ${it.contract} (your broker's price can differ a little)`);
    } else if (CFG.baseAlerts && r.base && r.base.len === 6)
      await send(`base|${it.contract}|${it.tf}|${r.t}`, `☁️ 🧱 <b>Base forming: ${esc(it.name)} ${it.tf}</b>\nLong above ${fmtP(r.base.hi)} · short below ${fmtP(r.base.lo)} · MEXC ${it.contract}`);
  } catch (e) { console.log(`${it.name}: ${e.message}`); const day = Math.floor(NOW / 864e5); await send(`err|${it.contract}|${day}`, `☁️ ⚠️ Cloud watcher couldn't read ${esc(it.name)} from MEXC: ${esc(e.message)}. It will keep trying.`); }
}
// 2) high-impact news a little before release
if (CFG.news) {
  try {
    const r = await globalThis.fetch("https://nfs.faireconomy.media/ff_calendar_thisweek.json", { headers: { "User-Agent": "Mozilla/5.0 (TheFinder cloud watcher)" } });
    const ev = F.ffNorm(await r.json()), lead = (CFG.news.leadMin || 30) * 60e3;
    for (const x of ev) if (x.at > NOW && x.at - NOW <= lead && (CFG.news.currencies || ["USD"]).includes(x.ccy) && (CFG.news.impact || ["High"]).includes(x.impact))
      await send(`news|${x.id}`, `☁️ 📅 <b>${esc(x.ccy)} ${esc(x.title)}</b> in ${Math.round((x.at - NOW) / 60e3)} min (${phtHM(x.at)} PHT)${x.forecast ? `\nForecast ${esc(x.forecast)} · previous ${esc(x.previous)}` : ""}`);
  } catch (e) { console.log("calendar:", e.message); }
}
fs.writeFileSync(STATE_FILE, JSON.stringify(state));
console.log(`done: ${out.length} alert(s)`);
