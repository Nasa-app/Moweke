// Persistencia local simple -- base de un enfoque offline-first: lo último que se vio
// queda disponible aunque se pierda la señal. Sin sincronización diferida todavía (ver
// CLAUDE.md del handoff, Paso 0): eso es trabajo de una capa de datos real, no de esta UI.
const PREFIJO = 'mowege_'

export function leer<T>(clave: string, porDefecto: T): T {
  try {
    const crudo = localStorage.getItem(PREFIJO + clave)
    return crudo ? (JSON.parse(crudo) as T) : porDefecto
  } catch {
    return porDefecto
  }
}

export function guardar<T>(clave: string, valor: T): void {
  try {
    localStorage.setItem(PREFIJO + clave, JSON.stringify(valor))
  } catch {
    // almacenamiento no disponible (privado/bloqueado) -- seguir sin persistir
  }
}

export function borrar(clave: string): void {
  try {
    localStorage.removeItem(PREFIJO + clave)
  } catch {
    // ignorar
  }
}

export function borrarTodo(): void {
  try {
    Object.keys(localStorage)
      .filter((k) => k.startsWith(PREFIJO))
      .forEach((k) => localStorage.removeItem(k))
  } catch {
    // ignorar
  }
}
