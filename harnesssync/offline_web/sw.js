/* Only public app assets are cached. Private snapshots live in IndexedDB. */
// Bump this version whenever any public app asset changes in a release.
const CACHE = "harnesssync-offline-v4";
const SHELL = ["./", "index.html", "app.js", "i18n.js", "locales.js", "style.css", "manifest.webmanifest", "icon.svg"];
const urls = SHELL.map(path => new URL(path, self.registration.scope).href);
self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(urls)));
});
self.addEventListener("activate", event => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) {
      if (key.startsWith("harnesssync-offline-") && key !== CACHE) await caches.delete(key);
    }
    await self.clients.claim();
  })());
});
self.addEventListener("fetch", event => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  url.hash = "";
  if (!urls.includes(url.href)) return;
  event.respondWith(caches.open(CACHE).then(async cache =>
    (await cache.match(url.href)) || fetch(event.request)));
});
