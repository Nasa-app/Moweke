// Lo último que respondió el servidor, guardado en el teléfono (IndexedDB) para poder mostrarlo sin conexión.
// IndexedDB y no localStorage porque aguanta datos grandes (las celdas del mapa, las series de clima) sin el tope de
// ~5 MB. Si el navegador no deja usarla (modo privado, bloqueada) se guarda en memoria durante la visita. Ningún
// acceso lanza: sin caché la app funciona igual que antes, solo que sin respaldo.
const BASE = 'mogen-cache'
const TABLA = 'lecturas'

export interface Guardado<T = unknown> {
  momento: number
  valor: T
}

const enMemoria = new Map<string, Guardado>()
let abierta: Promise<IDBDatabase | null> | null = null

function abrir(): Promise<IDBDatabase | null> {
  if (!abierta) {
    abierta = new Promise((resolver) => {
      try {
        const pedido = indexedDB.open(BASE, 1)
        pedido.onupgradeneeded = () => pedido.result.createObjectStore(TABLA)
        pedido.onsuccess = () => resolver(pedido.result)
        pedido.onerror = () => resolver(null)
        pedido.onblocked = () => resolver(null)
      } catch {
        resolver(null)
      }
    })
  }
  return abierta
}

function esperar<T>(pedido: IDBRequest<T>): Promise<T | undefined> {
  return new Promise((resolver) => {
    pedido.onsuccess = () => resolver(pedido.result)
    pedido.onerror = () => resolver(undefined)
  })
}

export async function leerLocal<T>(clave: string): Promise<Guardado<T> | null> {
  try {
    const bd = await abrir()
    if (bd) {
      const guardado = await esperar<Guardado<T> | undefined>(bd.transaction(TABLA, 'readonly').objectStore(TABLA).get(clave))
      if (guardado) return guardado
    }
  } catch {
    // se sigue con la memoria
  }
  return (enMemoria.get(clave) as Guardado<T> | undefined) ?? null
}

export async function guardarLocal<T>(clave: string, valor: T): Promise<void> {
  const guardado: Guardado<T> = { momento: Date.now(), valor }
  enMemoria.set(clave, guardado)
  try {
    const bd = await abrir()
    if (bd) await esperar(bd.transaction(TABLA, 'readwrite').objectStore(TABLA).put(guardado, clave))
  } catch {
    // quedó en memoria
  }
}

// Al cerrar sesión o cambiar de cuenta: nada de la cuenta anterior debe verse en la siguiente.
export async function borrarCacheLocal(): Promise<void> {
  enMemoria.clear()
  try {
    const bd = await abrir()
    if (bd) await esperar(bd.transaction(TABLA, 'readwrite').objectStore(TABLA).clear())
  } catch {
    // ignorar
  }
}
