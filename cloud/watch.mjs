// The Finder's cloud watcher: runs on GitHub Actions every 5 minutes and sends Telegram alerts while your Mac is off or asleep.
// It reuses the app's own rules (the scanner core inside index.html) and reads Forex Factory's feed and the news feeds.
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
vm.runInContext(src + "\n;this.__F = { ffNorm, rssItems, newsTag, newsBig, NEWS_FEEDS };", ctx);
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
const PHT = 8 * 3600e3;
const phtHM = ms => { const d = new Date(ms + PHT); let h = d.getUTCHours(); const m = String(d.getUTCMinutes()).padStart(2, "0"); return `${h % 12 || 12}:${m} ${h >= 12 ? "PM" : "AM"}`; };
// 1) high-impact news a little before release
if (CFG.news) {
  try {
    const r = await globalThis.fetch("https://nfs.faireconomy.media/ff_calendar_thisweek.json", { headers: { "User-Agent": "Mozilla/5.0 (TheFinder cloud watcher)" } });
    const ev = F.ffNorm(await r.json()), lead = (CFG.news.leadMin || 30) * 60e3;
    for (const x of ev) if (x.at > NOW && x.at - NOW <= lead && (CFG.news.currencies || ["USD"]).includes(x.ccy) && (CFG.news.impact || ["High"]).includes(x.impact))
      await send(`news|${x.id}`, `☁️ 📅 <b>${esc(x.ccy)} ${esc(x.title)}</b> in ${Math.round((x.at - NOW) / 60e3)} min (${phtHM(x.at)} PHT)${x.forecast ? `\nForecast ${esc(x.forecast)} · previous ${esc(x.previous)}` : ""}`);
  } catch (e) { console.log("calendar:", e.message); }
}
// 2) market-moving headlines on your markets (the app's own tags and filter), straight from the feeds
if (CFG.headlines) {
  const tags = CFG.headlines.tags || ["GOLD", "NDX", "FED", "USD", "MACRO"], maxAge = (CFG.headlines.maxAgeMin || 20) * 60e3;
  await Promise.all(Object.entries(F.NEWS_FEEDS).map(async ([name, url]) => {
    try { const r = await globalThis.fetch(url, { headers: { "User-Agent": "Mozilla/5.0 (TheFinder cloud watcher)", Accept: "application/rss+xml,application/xml,text/xml,*/*" } });
      if (!r.ok) throw new Error("HTTP " + r.status);
      for (const x of F.rssItems(await r.text())) { const tag = F.newsTag(x.title);
        if (!tags.includes(tag) || !F.newsBig(x.title) || !x.t || NOW - x.t > maxAge || x.t > NOW + 5 * 60e3) continue;
        await send(`hl|${x.title.toLowerCase().slice(0, 80)}`, `☁️ 📰 <b>${esc(tag)}</b> ${esc(x.title)}\n<i>${esc(name)} · ${phtHM(x.t)} PHT</i>${x.link ? "\n" + esc(x.link) : ""}`); } }
    catch (e) { console.log(`headlines ${name}:`, e.message); } }));
}
fs.writeFileSync(STATE_FILE, JSON.stringify(state));
console.log(`done: ${out.length} alert(s)`);
