#!/usr/bin/env python3
"""Serves Alt Scanner on http://localhost (this Mac only) with the same security headers as the Vercel deploy."""
import http.server, socketserver, sys, os, json, urllib.request, urllib.error
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8787
ROOT = os.path.dirname(os.path.abspath(__file__))
CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
       "img-src 'self' data: https://s3-symbol-logo.tradingview.com; "
       "connect-src 'self' https://fapi.binance.com https://api.binance.com https://data-api.binance.vision https://api.bybit.com https://api.bytick.com https://api.coingecko.com https://api.alternative.me; "
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
class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".webmanifest": "application/manifest+json", ".js": "text/javascript"}
    def __init__(self, *a, **k): super().__init__(*a, directory=ROOT, **k)
    def end_headers(self):
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        if self.path in ("/", "/index.html", "/sw.js"): self.send_header("Cache-Control", "no-cache")
        if self.path.startswith("/version.json"): self.send_header("Cache-Control", "no-store")
        super().end_headers()
    def do_GET(self):
        if self.path.startswith("/proxy/bybit/"):
            rest = self.path[len("/proxy/bybit"):]
            if not rest.startswith("/v5/market/"):
                self.send_response(403); self.end_headers(); return
            code, body = relay_bybit(rest)
            self.send_response(code)
            self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
            return
        return super().do_GET()
    def log_message(self, *a): pass
class Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True; daemon_threads = True
if __name__ == "__main__":
    with Server(("127.0.0.1", PORT), Handler) as s:       # 127.0.0.1 only: nothing outside this Mac can reach it
        s.serve_forever()
