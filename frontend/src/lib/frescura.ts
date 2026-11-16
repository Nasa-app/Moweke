import { useSyncExternalStore } from 'react'

// Qué datos de la pantalla vienen de lo guardado y no del servidor (porque no hubo conexión). Cada uno anota desde
// cuándo es; en cuanto se pide de nuevo y llega, se quita. La app muestra el más viejo de todos.
const viejos = new Map<string, number>()
const escuchas = new Set<() => void>()
let masViejo: number | null = null

function avisar() {
  masViejo = viejos.size ? Math.min(...viejos.values()) : null
  escuchas.forEach((f) => f())
}

export function registrarViejo(clave: string, momento: number): void {
  if (viejos.get(clave) === momento) return
  viejos.set(clave, momento)
  avisar()
}

export function registrarFresco(clave: string): void {
  if (viejos.delete(clave)) avisar()
}

export function esViejo(clave: string): boolean {
  return viejos.has(clave)
}

export function olvidarViejos(): void {
  if (viejos.size) {
    viejos.clear()
    avisar()
  }
}

// Desde cuándo (ms) es el dato guardado más antiguo que se está mostrando, o null si todo es reciente.
export function useDatoViejo(): number | null {
  return useSyncExternalStore(
    (f) => {
      escuchas.add(f)
      return () => escuchas.delete(f)
    },
    () => masViejo,
  )
}

export function useConexion(): boolean {
  return useSyncExternalStore(
    (f) => {
      window.addEventListener('online', f)
      window.addEventListener('offline', f)
      return () => {
        window.removeEventListener('online', f)
        window.removeEventListener('offline', f)
      }
    },
    () => navigator.onLine,
    () => true,
  )
}
