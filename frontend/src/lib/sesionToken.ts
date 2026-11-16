// El token de la cuenta anónima. Como el token ES la cuenta, perderlo deja sin dueño los predios: se guarda con
// cuidado. En los móviles el almacenamiento falla de formas distintas (navegadores dentro de otras apps, modo
// privado, datos del sitio borrados por el sistema): ningún acceso lanza, el token vive también en memoria durante
// la visita y se copia a sessionStorage, que sobrevive a recargar la pestaña aunque localStorage no deje escribir.
const CLAVE = 'mowege_token'
const DIAS_PARA_RENOVAR = 90

let enMemoria: string | null = null

function almacen(tipo: 'localStorage' | 'sessionStorage'): Storage | null {
  try {
    return window[tipo]
  } catch {
    return null
  }
}

function leerDe(tipo: 'localStorage' | 'sessionStorage'): string | null {
  try {
    return almacen(tipo)?.getItem(CLAVE) || null
  } catch {
    return null
  }
}

export function leerToken(): string | null {
  if (enMemoria) return enMemoria
  const guardado = leerDe('localStorage') ?? leerDe('sessionStorage')
  if (guardado) enMemoria = guardado
  return enMemoria
}

// Devuelve si quedó en localStorage (lo único que sobrevive a cerrar el navegador).
export function guardarToken(token: string): boolean {
  enMemoria = token
  for (const tipo of ['sessionStorage', 'localStorage'] as const) {
    try {
      almacen(tipo)?.setItem(CLAVE, token)
    } catch {
      // sin cupo o bloqueado: queda en memoria
    }
  }
  return leerDe('localStorage') === token
}

export function borrarToken(): void {
  enMemoria = null
  for (const tipo of ['localStorage', 'sessionStorage'] as const) {
    try {
      almacen(tipo)?.removeItem(CLAVE)
    } catch {
      // ignorar
    }
  }
}

// Segundos que le quedan al token, leídos de su payload (sin verificar la firma: eso es del servidor), o null si
// no se pueden leer.
export function segundosRestantes(token: string, ahora = Date.now()): number | null {
  try {
    const cuerpo = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    const exp = (JSON.parse(atob(cuerpo.padEnd(Math.ceil(cuerpo.length / 4) * 4, '='))) as { exp?: unknown }).exp
    return typeof exp === 'number' ? exp - ahora / 1000 : null
  } catch {
    return null
  }
}

export function convieneRenovar(token: string, ahora = Date.now()): boolean {
  const restantes = segundosRestantes(token, ahora)
  return restantes !== null && restantes < DIAS_PARA_RENOVAR * 86_400
}
