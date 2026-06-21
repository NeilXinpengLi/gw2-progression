// GW2 Progression — Service Worker for offline caching
const CACHE = 'gw2-progression-v1';
const STATIC_URLS = ['/', '/static/app.js', '/static/app-value.js', '/static/app-characters.js',
  '/static/app-items.js', '/static/app-crafting.js', '/static/app-goals.js', '/static/app-planner.js',
  '/static/style.css', '/static/index.html'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(cache => cache.addAll(STATIC_URLS)));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))));
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (url.pathname.startsWith('/api') || url.pathname.startsWith('/auth') || url.pathname === '/analyze') {
    return; // Never cache API calls
  }
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request).then(resp => {
      const clone = resp.clone();
      caches.open(CACHE).then(cache => cache.put(e.request, clone));
      return resp;
    }).catch(() => caches.match('/static/index.html')))
  );
});
