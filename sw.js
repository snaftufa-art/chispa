// Chispa offline engine: keeps the whole app, fonts and all the sound on the phone.
const VERSION = '15f20351d7';
const CACHE = 'chispa-' + VERSION;
const FILES = ["./", "index.html", "manifest.webmanifest", "audio/chat.mp3", "audio/r_bar.mp3", "audio/r_calle.mp3", "audio/r_casa.mp3", "audio/r_colmena.mp3", "audio/r_kebab.mp3", "audio/r_super.mp3", "audio/r_taller.mp3", "audio/u1.mp3", "audio/u10.mp3", "audio/u101.mp3", "audio/u102.mp3", "audio/u103.mp3", "audio/u104.mp3", "audio/u105.mp3", "audio/u106.mp3", "audio/u107.mp3", "audio/u108.mp3", "audio/u109.mp3", "audio/u11.mp3", "audio/u110.mp3", "audio/u12.mp3", "audio/u13.mp3", "audio/u14.mp3", "audio/u15.mp3", "audio/u16.mp3", "audio/u17.mp3", "audio/u18.mp3", "audio/u19.mp3", "audio/u2.mp3", "audio/u20.mp3", "audio/u3.mp3", "audio/u4.mp3", "audio/u5.mp3", "audio/u6.mp3", "audio/u7.mp3", "audio/u8.mp3", "audio/u9.mp3", "audio/wilma.mp3", "fonts/lexend-400.woff2", "fonts/lexend-500.woff2", "fonts/lexend-600.woff2", "fonts/lexend-700.woff2", "fonts/lexend-800.woff2", "fonts/tilt-neon.woff2", "icons/icon-180.png", "icons/icon-192.png", "icons/icon-512.png", "icons/maskable-512.png", "icons/preview.png"];

self.addEventListener('install', e => {
  e.waitUntil((async () => {
    const c = await caches.open(CACHE);
    // copy unchanged files from the previous version instead of downloading them again
    const old = (await caches.keys()).filter(k => k.startsWith('chispa-') && k !== CACHE);
    for (const f of FILES) {
      const url = new URL(f, self.registration.scope).href;
      let hit = null;
      if (/\.(mp3|woff2|png)$/.test(f)) for (const k of old) { hit = await (await caches.open(k)).match(url); if (hit) break; }
      if (hit) await c.put(url, hit);
      else { const r = await fetch(url, {cache: 'reload'}); if (r.ok) await c.put(url, r); }
    }
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', e => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) if (k.startsWith('chispa-') && k !== CACHE) await caches.delete(k);
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== location.origin) return;
  e.respondWith((async () => {
    const c = await caches.open(CACHE);
    const hit = await c.match(req, {ignoreSearch: true}) || (req.mode === 'navigate' ? await c.match(new URL('index.html', self.registration.scope).href) : null);
    if (hit) return hit;
    try { const r = await fetch(req); if (r.ok) c.put(req, r.clone()); return r; }
    catch (err) { return new Response('', {status: 504}); }
  })());
});
