import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { loginAgricultor, olvidarLecturas, quienSoy, registrarAgricultor, type Usuario } from '../lib/api'
import { borrarTodo, leer } from './storage'

interface AuthContextValor {
  usuario: Usuario | null
  cargando: boolean
  autenticado: boolean
  iniciarSesion: (telefono: string, password: string) => Promise<void>
  registrarse: (datos: { nombre: string; telefono: string; password: string; lat: number; lon: number }) => Promise<void>
  cerrarSesion: () => void
}

const AuthContext = createContext<AuthContextValor | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null)
  const [cargando, setCargando] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('mowege_token')
    if (!token) {
      setCargando(false)
      return
    }
    quienSoy()
      .then(setUsuario)
      .catch(() => {
        localStorage.removeItem('mowege_token')
        setUsuario(null)
      })
      .finally(() => setCargando(false))
  }, [])

  const iniciarSesion = useCallback(async (telefono: string, password: string) => {
    const { access_token } = await loginAgricultor({ telefono, password })
    olvidarLecturas()
    localStorage.setItem('mowege_token', access_token)
    setUsuario(await quienSoy())
  }, [])

  const registrarse = useCallback(
    async (datos: { nombre: string; telefono: string; password: string; lat: number; lon: number }) => {
      const { access_token } = await registrarAgricultor(datos)
      olvidarLecturas()
      localStorage.setItem('mowege_token', access_token)
      setUsuario(await quienSoy())
    },
    [],
  )

  const cerrarSesion = useCallback(() => {
    localStorage.removeItem('mowege_token')
    olvidarLecturas()
    borrarTodo()
    setUsuario(null)
  }, [])

  const valor = useMemo(
    () => ({ usuario, cargando, autenticado: usuario !== null, iniciarSesion, registrarse, cerrarSesion }),
    [usuario, cargando, iniciarSesion, registrarse, cerrarSesion],
  )

  return <AuthContext.Provider value={valor}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValor {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth debe usarse dentro de AuthProvider')
  return ctx
}

export function nombrePorDefecto(): string {
  return leer('ultimo_nombre', '')
}
