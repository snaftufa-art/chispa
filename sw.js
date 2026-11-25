// Chispa offline engine: keeps the whole app, fonts and all the sound on the phone.
const VERSION = '46021603d2';
const CACHE = 'chispa-' + VERSION;
const FILES = ["./", "index.html", "manifest.webmanifest", "audio/chat.b16aec4a.mp3", "audio/ga1.8f1cb85a.mp3", "audio/ga2.09d254e1.mp3", "audio/gb1.44a0c362.mp3", "audio/mg.70aeeb32.mp3", "audio/r_ayto.40c4c352.mp3", "audio/r_banco.5b0fbd99.mp3", "audio/r_bar.7e12e3dd.mp3", "audio/r_barrio.a300632d.mp3", "audio/r_biblio.fe03fc71.mp3", "audio/r_calle.636e2d7e.mp3", "audio/r_casa.d42e75d9.mp3", "audio/r_chiringuito.d6e915d0.mp3", "audio/r_colmena.b2d643e8.mp3", "audio/r_enchufe.a532c093.mp3", "audio/r_estacion.ee4e6e25.mp3", "audio/r_farmacia.54622514.mp3", "audio/r_ferreteria.6cb804f4.mp3", "audio/r_inmo.2bed9031.mp3", "audio/r_kebab.b162c18e.mp3", "audio/r_nave.5fd549d3.mp3", "audio/r_peluqueria.2aa6243f.mp3", "audio/r_piso.ec0979f4.mp3", "audio/r_playa.9eea3c0e.mp3", "audio/r_salud.5542e49d.mp3", "audio/r_super.e2e45a24.mp3", "audio/r_taller.489628b4.mp3", "audio/r_vet.2076bbca.mp3", "audio/u1.1faf2342.mp3", "audio/u10.c308b8e4.mp3", "audio/u101.bfc2405f.mp3", "audio/u102.570942b3.mp3", "audio/u103.784b509b.mp3", "audio/u104.93ca677a.mp3", "audio/u105.cf16a2ef.mp3", "audio/u106.58611105.mp3", "audio/u107.5d90fba8.mp3", "audio/u108.7e1e34fc.mp3", "audio/u109.3c4f803c.mp3", "audio/u11.35a7d3d4.mp3", "audio/u110.bc55363c.mp3", "audio/u111.1156a1d0.mp3", "audio/u112.8ad400b1.mp3", "audio/u113.dfb253e4.mp3", "audio/u114.012250d2.mp3", "audio/u12.a881b6fe.mp3", "audio/u13.b40d748c.mp3", "audio/u14.67e5bc93.mp3", "audio/u15.ac78330d.mp3", "audio/u16.76794d8a.mp3", "audio/u17.17117627.mp3", "audio/u18.d1d65a6f.mp3", "audio/u19.c60e69cd.mp3", "audio/u2.76433094.mp3", "audio/u20.991a07b0.mp3", "audio/u21.86bb0a22.mp3", "audio/u22.dfd10a7c.mp3", "audio/u23.155062ba.mp3", "audio/u24.35b14f11.mp3", "audio/u25.022bb76c.mp3", "audio/u26.1ce05c17.mp3", "audio/u27.015e8944.mp3", "audio/u28.13e326bd.mp3", "audio/u29.14535bbc.mp3", "audio/u3.8c955343.mp3", "audio/u30.a5d16c06.mp3", "audio/u4.0e6e58ad.mp3", "audio/u5.daad6e3b.mp3", "audio/u6.d03dbc0c.mp3", "audio/u7.0a98686e.mp3", "audio/u8.c3805bae.mp3", "audio/u9.369036c4.mp3", "audio/wilma.235b9bad.mp3", "dict.json", "fonts/lexend-400.woff2", "fonts/lexend-500.woff2", "fonts/lexend-600.woff2", "fonts/lexend-700.woff2", "fonts/lexend-800.woff2", "fonts/tilt-neon.woff2", "icons/icon-180.png", "icons/icon-192.png", "icons/icon-512.png", "icons/maskable-512.png", "icons/preview.png"];

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
