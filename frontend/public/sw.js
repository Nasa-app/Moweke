// Service worker de mogen: deja abrir la app sin conexión. No toca la API (esa se guarda dentro de la app, en
// lib/cacheLocal.ts, con la edad de cada dato). Solo guarda lo que la app necesita para arrancar:
//   - la página principal (index.html), siempre pidiéndola primero a la red para no quedar con una versión vieja;
//   - los archivos con huella en /assets/ (su nombre cambia con cada versión, así que se pueden guardar para siempre);
//   - los íconos, el manifiesto y la tipografía de Google Fonts (se guarda la primera vez que se ve).
// Los mapas (teselas) y la API quedan fuera: se piden siempre a la red.
const VERSION = 'v1'
const CACHE_APP = `mogen-app-${VERSION}`
const CACHE_ASSETS = `mogen-assets-${VERSION}`
const CACHE_FUENTES = `mogen-fuentes-${VERSION}`
const ASSETS_MAX = 80
const PAGINA = '/index.html'
const ESTATICOS = ['/manifest.webmanifest', '/favicon.png', '/icono-192.png', '/icono-512.png', '/logo.webp']
const ANFITRIONES_FUENTES = ['fonts.googleapis.com', 'fonts.gstatic.com']

self.addEventListener('install', (evento) => {
  evento.waitUntil(
    caches
      .open(CACHE_APP)
      .then((cache) => cache.addAll([PAGINA, ...ESTATICOS]))
      .then(() => self.skipWaiting()),
  )
})

self.addEventListener('activate', (evento) => {
  const vigentes = [CACHE_APP, CACHE_ASSETS, CACHE_FUENTES]
  evento.waitUntil(
    caches
      .keys()
      .then((nombres) => Promise.all(nombres.filter((n) => n.startsWith('mogen-') && !vigentes.includes(n)).map((n) => caches.delete(n))))
      .then(() => self.clients.claim()),
  )
})

async function recortar(nombre, maximo) {
  const cache = await caches.open(nombre)
  const claves = await cache.keys()
  await Promise.all(claves.slice(0, Math.max(0, claves.length - maximo)).map((c) => cache.delete(c)))
}

// Red primero; si no hay, lo último guardado.
async function paginaPrimeroRed(peticion) {
  const cache = await caches.open(CACHE_APP)
  try {
    const respuesta = await fetch(peticion)
    if (respuesta.ok && respuesta.headers.get('content-type')?.includes('text/html')) {
      await cache.put(PAGINA, respuesta.clone())
    }
    return respuesta
  } catch {
    return (await cache.match(PAGINA)) ?? Response.error()
  }
}

// Guardado primero (los archivos con huella no cambian); si no está, a la red y se guarda.
async function guardadoPrimero(peticion, nombre, maximo) {
  const cache = await caches.open(nombre)
  const guardado = await cache.match(peticion)
  if (guardado) return guardado
  const respuesta = await fetch(peticion)
  if (respuesta.ok) {
    await cache.put(peticion, respuesta.clone())
    if (maximo) recortar(nombre, maximo)
  }
  return respuesta
}

// Lo guardado al instante y, en segundo plano, se actualiza para la próxima vez.
async function guardadoYActualizar(peticion, nombre) {
  const cache = await caches.open(nombre)
  const guardado = await cache.match(peticion)
  const actualizando = fetch(peticion)
    .then((respuesta) => {
      if (respuesta.ok || respuesta.type === 'opaque') cache.put(peticion, respuesta.clone())
      return respuesta
    })
    .catch(() => guardado ?? Response.error())
  return guardado ?? actualizando
}

self.addEventListener('fetch', (evento) => {
  const peticion = evento.request
  if (peticion.method !== 'GET') return
  const url = new URL(peticion.url)

  if (ANFITRIONES_FUENTES.includes(url.hostname)) {
    evento.respondWith(guardadoYActualizar(peticion, CACHE_FUENTES))
    return
  }
  if (url.origin !== self.location.origin) return   // la API y los mapas no pasan por aquí

  if (peticion.mode === 'navigate') {
    evento.respondWith(paginaPrimeroRed(peticion))
  } else if (url.pathname.startsWith('/assets/')) {
    evento.respondWith(guardadoPrimero(peticion, CACHE_ASSETS, ASSETS_MAX))
  } else if (ESTATICOS.includes(url.pathname)) {
    evento.respondWith(guardadoYActualizar(peticion, CACHE_APP))
  }
})
