const CACHE_NAME = 'pea-tracker-v4';
const ASSETS_TO_CACHE = [
    './',
    './index.html',
    './style.css',
    './manifest.json',
    'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap',
    'https://cdn.jsdelivr.net/npm/chart.js'
];

self.addEventListener('install', event => {
    self.skipWaiting(); // Activate new SW immediately
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS_TO_CACHE))
    );
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        ).then(() => self.clients.claim()) // Take control immediately
    );
});

// Network-first for JS/CSS (always get latest), cache-first for fonts/CDN
self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);
    
    // API calls: always network, never cache
    if (url.pathname.startsWith('/api/')) return;
    
    // JS and CSS: network first, fallback to cache
    if (url.pathname.endsWith('.js') || url.pathname.endsWith('.css') || url.pathname.endsWith('.html') || url.pathname === '/') {
        event.respondWith(
            fetch(event.request).then(response => {
                const clone = response.clone();
                caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
                return response;
            }).catch(() => caches.match(event.request))
        );
        return;
    }
    
    // Everything else: cache first
    event.respondWith(
        caches.match(event.request).then(cached => cached || fetch(event.request))
    );
});

self.addEventListener('push', (event) => {
    if (event.data) {
        const data = event.data.json();
        const options = {
            body: data.body,
            icon: './icon.png',
            badge: './icon.png',
            vibrate: [200, 100, 200],
            requireInteraction: true
        };
        event.waitUntil(self.registration.showNotification(data.title, options));
    }
});
