const CACHE_VERSION = 'sam-career-pwa-2026-11-20-6';
const SHELL_CACHE = `${CACHE_VERSION}-shell`;
const DATA_CACHE = `${CACHE_VERSION}-data`;
const SHELL = [
  '/',
  '/manifest.webmanifest',
  '/static/styles.css',
  '/static/app.js',
  '/static/scene.js',
  '/static/three.min.js',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/icons/icon-maskable-512.png'
];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(SHELL_CACHE).then(cache => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(key => ![SHELL_CACHE, DATA_CACHE].includes(key)).map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

async function networkFirst(request, cacheName, ignoreSearch = false) {
  const cache = await caches.open(cacheName);
  try {
    const response = await fetch(request);
    if (response.ok) {
      await cache.put(request, response.clone());
      return response;
    }
    if (response.status >= 500) {
      const cached = await cache.match(request, {ignoreSearch});
      if (cached) return cached;
    }
    return response;
  } catch (error) {
    const cached = await cache.match(request, {ignoreSearch});
    if (cached) return cached;
    throw error;
  }
}

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok) (await caches.open(SHELL_CACHE)).put(request, response.clone());
  return response;
}

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === 'navigate') {
    event.respondWith(networkFirst(request, SHELL_CACHE, true).catch(() => caches.match('/')));
    return;
  }
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirst(request, DATA_CACHE));
    return;
  }
  if (url.pathname.startsWith('/static/') || url.pathname === '/manifest.webmanifest') {
    event.respondWith(cacheFirst(request));
  }
});

self.addEventListener('message', event => {
  if (event.data === 'SKIP_WAITING') self.skipWaiting();
});
