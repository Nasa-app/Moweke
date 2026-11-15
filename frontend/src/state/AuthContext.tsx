import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { ApiError, crearSesionAnonima, olvidarLecturas, quienSoy, type Usuario } from '../lib/api'
import { borrarTodo } from './storage'

// No hay pantalla de registro ni de inicio de sesión: al abrir la app se usa la cuenta anónima de este
// dispositivo, y si no existe se crea sola. El token guardado ES la cuenta (el servidor no tiene con qué
// volver a identificarla), así que solo se descarta cuando el servidor dice que ya no vale.
interface AuthContextValor {
  usuario: Usuario | null
  cargando: boolean
  autenticado: boolean
  // No se pudo obtener la sesión (casi siempre, sin conexión). El token guardado, si lo hay, se conserva.
  errorSesion: boolean
  reintentarSesion: () => void
  // Abandona la cuenta de este dispositivo y empieza de cero: los predios anteriores dejan de ser accesibles.
  cerrarSesion: () => void
}

const AuthContext = createContext<AuthContextValor | null>(null)

interface ResultadoSesion {
  usuario: Usuario
  // Se descartó una cuenta anterior: lo que estaba en memoria (parcela activa, cultivo) era de ella.
  cuentaNueva: boolean
}

async function establecerSesion(): Promise<ResultadoSesion> {
  const token = localStorage.getItem('mowege_token')
  if (token) {
    try {
      return { usuario: await quienSoy(), cuentaNueva: false }
    } catch (err) {
      // Sin conexión o el servidor caído: se conserva el token. Crear otra cuenta dejaría sin dueño los predios.
      if (!(err instanceof ApiError) || err.status !== 401) throw err
      borrarTodo()
    }
  }
  const { access_token } = await crearSesionAnonima()
  olvidarLecturas()
  localStorage.setItem('mowege_token', access_token)
  return { usuario: await quienSoy(), cuentaNueva: token !== null }
}

// Una sola petición a la vez: React en desarrollo ejecuta el efecto dos veces y eso crearía dos cuentas.
let enCurso: Promise<ResultadoSesion> | null = null
function asegurarSesion(): Promise<ResultadoSesion> {
  if (!enCurso) enCurso = establecerSesion().finally(() => (enCurso = null))
  return enCurso
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null)
  const [cargando, setCargando] = useState(true)
  const [errorSesion, setErrorSesion] = useState(false)
  const [intento, setIntento] = useState(0)

  useEffect(() => {
    let vigente = true
    asegurarSesion()
      .then(({ usuario: u, cuentaNueva }) => {
        // Los demás contextos ya leyeron el almacenamiento de la cuenta anterior: se vuelve a empezar limpio.
        if (cuentaNueva) {
          window.location.reload()
          return
        }
        if (vigente) setUsuario(u)
      })
      .catch(() => vigente && setErrorSesion(true))
      .finally(() => vigente && setCargando(false))
    return () => {
      vigente = false
    }
  }, [intento])

  const reintentarSesion = useCallback(() => {
    setErrorSesion(false)
    setCargando(true)
    setIntento((n) => n + 1)
  }, [])

  const cerrarSesion = useCallback(() => {
    olvidarLecturas()
    borrarTodo()
    window.location.assign('/')
  }, [])

  const valor = useMemo(
    () => ({ usuario, cargando, autenticado: usuario !== null, errorSesion, reintentarSesion, cerrarSesion }),
    [usuario, cargando, errorSesion, reintentarSesion, cerrarSesion],
  )

  return <AuthContext.Provider value={valor}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValor {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth debe usarse dentro de AuthProvider')
  return ctx
}
