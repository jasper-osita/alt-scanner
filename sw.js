/* The Finder service worker: keeps the app shell available, never caches market data. */
const SHELL = "the-finder-shell-2026.10.09.1058";
const FILES = ["/", "/index.html", "/manifest.webmanifest", "/icons/finder-192.png", "/icons/finder-512.png", "/fonts/space-grotesk-latin-400-normal.woff2", "/fonts/space-grotesk-latin-500-normal.woff2", "/fonts/space-grotesk-latin-600-normal.woff2", "/fonts/space-grotesk-latin-700-normal.woff2", "/lib/lightweight-charts.standalone.production.js"];
self.addEventListener("install", e => { e.waitUntil(caches.open(SHELL).then(c => c.addAll(FILES))); self.skipWaiting(); });
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== SHELL).map(k => caches.delete(k)))));
  self.clients.claim();
});
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;     // market data and logos always go to the network
  // network first so new deploys show up immediately; fall back to the cached shell when offline
  e.respondWith(fetch(e.request).then(res => {
    const copy = res.clone(); caches.open(SHELL).then(c => c.put(e.request, copy)); return res;
  }).catch(() => caches.match(e.request).then(r => r || caches.match("/index.html"))));
});
