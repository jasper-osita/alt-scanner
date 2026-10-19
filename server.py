#!/usr/bin/env python3
"""Serves Alt Scanner on http://localhost (this Mac only) with the same security headers as the Vercel deploy."""
import http.server, socketserver, sys, os, json, urllib.request, urllib.error, subprocess, threading, time
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8787
ROOT = os.path.dirname(os.path.abspath(__file__))
CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
       "img-src 'self' data: https://s3-symbol-logo.tradingview.com; "
       "connect-src 'self' https://fapi.binance.com https://api.binance.com https://data-api.binance.vision https://api.bybit.com https://api.bytick.com https://contract.mexc.com https://api.mexc.com https://api.coingecko.com https://api.alternative.me https://api.telegram.org https://openapi.ctrader.com wss://fstream.binance.com wss://stream.binance.com:9443 wss://data-stream.binance.vision wss://stream.bybit.com wss://contract.mexc.com wss://live.ctraderapi.com:5036 wss://demo.ctraderapi.com:5036; "
       "manifest-src 'self'; worker-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'none'")
# Relay for Bybit's public market data, used when Bybit refuses requests made directly from a web page.
# Only /v5/market/* paths are forwarded: read-only prices, candles, funding and open interest. No account endpoints.
BYBIT_UPSTREAMS = [u for u in os.environ.get("ALTSCAN_BYBIT_UPSTREAM", "https://api.bybit.com,https://api.bytick.com").split(",") if u]
def relay_bybit(rest):
    last = None
    for up in BYBIT_UPSTREAMS:
        try:
            req = urllib.request.Request(up + rest, headers={"User-Agent": "AltScanner/1.0", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
        except Exception as e:
            last = e
    return 502, json.dumps({"retCode": -1, "retMsg": f"relay could not reach Bybit: {last}"}).encode()
# Relay for MEXC's public market data (futures contract API and spot v3), for when MEXC refuses requests from a web page.
# Only read-only market paths are forwarded.
MEXC_UPSTREAMS = {"/proxy/mexc-fut": ("https://contract.mexc.com", "/api/v1/contract/"), "/proxy/mexc-spot": ("https://api.mexc.com", "/api/v3/")}
def relay_mexc(prefix, rest):
    up, allowed = MEXC_UPSTREAMS[prefix]
    if not rest.startswith(allowed) or any(x in rest for x in ("/private", "/account", "/order", "..", "%2e", "%2E")): return 403, b'{"success":false,"message":"not allowed"}'
    try:
        req = urllib.request.Request(up + rest, headers={"User-Agent": "Mozilla/5.0 (TheFinder)", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r: return r.status, r.read()
    except urllib.error.HTTPError as e: return e.code, e.read()
    except Exception as e: return 502, json.dumps({"success": False, "message": f"relay could not reach MEXC: {e}"}).encode()
# Relay for Forex Factory's weekly calendar feed and Nasdaq's earnings calendar (neither allows calls from a web page).
# Cached so the sources are asked at most every few minutes.
CACHE = {}
def cached_get(key, url, ttl, headers):
    hit = CACHE.get(key)
    if hit and time.time() - hit[0] < ttl: return 200, hit[1]
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read(); CACHE[key] = (time.time(), body)
            if len(CACHE) > 200: CACHE.pop(next(iter(CACHE)))
            return r.status, body
    except urllib.error.HTTPError as e:
        if hit: return 200, hit[1]
        return e.code, e.read()
    except Exception as e:
        if hit: return 200, hit[1]
        return 502, json.dumps({"error": f"relay could not reach the source: {e}"}).encode()
BROWSER = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36",
           "Accept": "application/json, text/plain, */*", "Accept-Language": "en-US,en;q=0.9"}
def relay_ff():
    return cached_get("ff", "https://nfs.faireconomy.media/ff_calendar_thisweek.json", 600, BROWSER)
def relay_earnings(q):
    import re
    m = re.match(r"^date=(\d{4}-\d{2}-\d{2})$", q or "")
    if not m: return 400, b'{"error":"date=YYYY-MM-DD"}'
    return cached_get("earn" + m.group(1), "https://api.nasdaq.com/api/calendar/earnings?date=" + m.group(1), 6 * 3600,
                      {**BROWSER, "Origin": "https://www.nasdaq.com", "Referer": "https://www.nasdaq.com/"})
# Fundamentals page: US Treasury yield curves, CFTC positioning, FRED series (your own free key, passed through) and news RSS.
UST_TYPES = ("daily_treasury_yield_curve", "daily_treasury_real_yield_curve")
RSS_FEEDS = {"fxstreet": "https://www.fxstreet.com/rss/news", "marketwatch": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
             "investing": "https://www.investing.com/rss/news_25.rss", "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/"}
def relay_fund(path, q):
    import re
    m = re.match(r"^/proxy/ust/([a-z_]+)/(\d{4})$", path)
    if m and m.group(1) in UST_TYPES:
        t, y = m.group(1), m.group(2)
        return cached_get("ust" + t + y, f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{y}/all?type={t}&field_tdr_date_value={y}&page&_format=csv", 3600, {**BROWSER, "Accept": "text/csv,*/*"})
    if path == "/proxy/cot":
        return cached_get("cot" + q, "https://publicreporting.cftc.gov/resource/6dca-aqww.json?" + q, 6 * 3600, BROWSER)
    if path == "/proxy/fred/series/observations":
        return cached_get("fred" + q, "https://api.stlouisfed.org/fred/series/observations?" + q, 1800, BROWSER)
    m = re.match(r"^/proxy/rss/([a-z]+)$", path)
    if m and m.group(1) in RSS_FEEDS:
        return cached_get("rss" + m.group(1), RSS_FEEDS[m.group(1)], 300, {**BROWSER, "Accept": "application/rss+xml,application/xml,text/xml,*/*"})
    return 404, b'{"error":"unknown source"}'
# Keep this Mac awake while a trading session is on (asked for by the app; caffeinate stops by itself after the time given).
AWAKE = {"proc": None, "until": 0}
def keep_awake(minutes):
    minutes = max(1, min(240, int(minutes)))
    until = time.time() + minutes * 60
    if AWAKE["proc"] and AWAKE["proc"].poll() is None and AWAKE["until"] >= until - 60: return AWAKE["until"]
    try:
        if AWAKE["proc"] and AWAKE["proc"].poll() is None: AWAKE["proc"].terminate()
        AWAKE["proc"] = subprocess.Popen(["caffeinate", "-i", "-s", "-t", str(minutes * 60)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        AWAKE["until"] = until
    except Exception: return 0
    return until
class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".webmanifest": "application/manifest+json", ".js": "text/javascript"}
    def __init__(self, *a, **k): super().__init__(*a, directory=ROOT, **k)
    def end_headers(self):
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        if self.path.split("?")[0] in ("/", "/index.html", "/sw.js", "/manifest.webmanifest"): self.send_header("Cache-Control", "no-cache")
        if self.path.startswith("/version.json"): self.send_header("Cache-Control", "no-store")
        super().end_headers()
    def do_GET(self):
        if self.path.startswith("/proxy/mexc-priv/"): return self.relay_mexc_private("GET")
        if self.path.startswith("/proxy/bybit/"):
            rest = self.path[len("/proxy/bybit"):]
            if not rest.startswith("/v5/market/"):
                self.send_response(403); self.end_headers(); return
            code, body = relay_bybit(rest)
            self.send_response(code)
            self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
            return
        path, _, query = self.path.partition("?")
        if path.startswith(("/proxy/ust/", "/proxy/cot", "/proxy/fred/", "/proxy/rss/")):
            code, body = relay_fund(path, query)
            ctype = "text/csv" if path.startswith("/proxy/ust/") else "application/xml" if path.startswith("/proxy/rss/") else "application/json"
            self.send_response(code)
            self.send_header("Content-Type", ctype); self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
            return
        if path in ("/proxy/ff", "/proxy/earnings", "/api/awake"):
            if path == "/proxy/ff": code, body = relay_ff()
            elif path == "/proxy/earnings": code, body = relay_earnings(query)
            else:
                mins = 0
                for kv in query.split("&"):
                    if kv.startswith("min="): mins = int("".join(ch for ch in kv[4:] if ch.isdigit()) or 0)
                until = keep_awake(mins) if mins else AWAKE["until"]
                code, body = 200, json.dumps({"awakeUntil": int(until * 1000), "running": bool(AWAKE["proc"] and AWAKE["proc"].poll() is None)}).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
            return
        for prefix in MEXC_UPSTREAMS:
            if self.path.startswith(prefix + "/"):
                code, body = relay_mexc(prefix, self.path[len(prefix):])
                self.send_response(code)
                self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
                return
        return super().do_GET()
    def relay_mexc_private(self, method):
        # MEXC futures trading for the Trade page. The browser signs every request itself (the secret never leaves it);
        # this only forwards the signed request, because MEXC doesn't accept these headers from a web page.
        rest = self.path[len("/proxy/mexc-priv"):]
        if not rest.startswith("/api/v1/private/") or ".." in rest or "%2e" in rest.lower():
            self.send_response(403); self.end_headers(); return
        origin = self.headers.get("Origin", "")
        if origin and not origin.startswith(("http://localhost:", "http://127.0.0.1:")):
            self.send_response(403); self.end_headers(); return
        hdr = {"User-Agent": "TheFinder/1.0", "Accept": "application/json", "Content-Type": "application/json"}
        for k in ("ApiKey", "Request-Time", "Signature", "Recv-Window"):
            if self.headers.get(k): hdr[k] = self.headers.get(k)
        body = None
        if method == "POST": body = self.rfile.read(min(int(self.headers.get("Content-Length", "0") or 0), 65536))
        try:
            req = urllib.request.Request("https://contract.mexc.com" + rest, data=body, headers=hdr, method=method)
            try:
                with urllib.request.urlopen(req, timeout=20) as r: code, out = r.status, r.read()
            except urllib.error.HTTPError as e: code, out = e.code, e.read()
        except Exception:
            code, out = 502, json.dumps({"success": False, "code": 502, "message": "couldn't reach MEXC"}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(out))); self.end_headers(); self.wfile.write(out)
    def do_POST(self):
        if self.path.startswith("/proxy/mexc-priv/"): return self.relay_mexc_private("POST")
        # cTrader sign-in: swap the one-minute sign-in code (or a refresh token) for tokens. Only for pages served
        # by this Mac app; the request goes straight to openapi.ctrader.com and nothing is logged or stored here.
        if self.path.split("?")[0] != "/api/ct-token":
            self.send_response(404); self.end_headers(); return
        origin = self.headers.get("Origin", "")
        if origin and not origin.startswith(("http://localhost:", "http://127.0.0.1:")):
            self.send_response(403); self.end_headers(); return
        try:
            n = min(int(self.headers.get("Content-Length", "0") or 0), 8192)
            p = json.loads(self.rfile.read(n) or b"{}")
            keep = ("grant_type", "code", "redirect_uri", "client_id", "client_secret", "refresh_token")
            q = {k: str(p[k]) for k in keep if p.get(k)}
            if q.get("grant_type") not in ("authorization_code", "refresh_token"): raise ValueError("grant_type")
            from urllib.parse import urlencode
            req = urllib.request.Request("https://openapi.ctrader.com/apps/token?" + urlencode(q), headers={"Accept": "application/json", "User-Agent": "TheFinder/1.0"})
            try:
                with urllib.request.urlopen(req, timeout=20) as r: code, body = r.status, r.read()
            except urllib.error.HTTPError as e: code, body = e.code, e.read()
            except Exception: code, body = 502, json.dumps({"errorCode": "UNREACHABLE", "description": "couldn't reach cTrader's sign-in service"}).encode()
        except Exception:
            code, body = 400, json.dumps({"errorCode": "BAD_REQUEST", "description": "the sign-in request was incomplete"}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass

# Auto-update: when this folder is a Git clone, pull new versions every 2 minutes.
# Files are served fresh from disk, so the app sees an update on its next check; if this server
# file itself changed, the server restarts in place to run the new code.
UPDATE_EVERY = int(os.environ.get("ALTSCAN_UPDATE_INTERVAL", "120"))
def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=60).stdout.strip()
def auto_update_loop():
    if not os.path.isdir(os.path.join(ROOT, ".git")): return
    while True:
        time.sleep(UPDATE_EVERY)
        try:
            old = _git("rev-parse", "HEAD")
            if subprocess.run(["git", "fetch", "--quiet", "origin"], cwd=ROOT, timeout=60).returncode != 0: continue
            _git("reset", "--hard", "--quiet", "@{upstream}")
            new = _git("rev-parse", "HEAD")
            if old and new and old != new:
                print(time.strftime("%F %T"), "updated", new[:7], flush=True)
                if "server.py" in _git("diff", "--name-only", old, new).split():
                    os.execv(sys.executable, [sys.executable, os.path.abspath(__file__)] + sys.argv[1:])
        except Exception as e:
            print(time.strftime("%F %T"), "update check failed:", e, flush=True)

class Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True; daemon_threads = True
if __name__ == "__main__":
    threading.Thread(target=auto_update_loop, daemon=True).start()
    with Server(("127.0.0.1", PORT), Handler) as s:       # 127.0.0.1 only: nothing outside this Mac can reach it
        s.serve_forever()
