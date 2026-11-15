import type { ReactNode } from 'react'
import { Screen, Titulo } from './Screen'
import { useAuth } from '../state/AuthContext'

// Ya no hay inicio de sesión: la cuenta anónima se crea sola al abrir la app. Esta ruta solo espera a que
// esté lista y, si no se pudo (sin conexión), deja reintentar en vez de mandar a una pantalla de login.
export function RutaPrivada({ children }: { children: ReactNode }) {
  const { autenticado, cargando, reintentarSesion } = useAuth()
  if (cargando) return null
  if (!autenticado) {
    return (
      <Screen>
        <Titulo sub="Revisa tu conexión e inténtalo de nuevo.">No pudimos conectar</Titulo>
        <div className="ps-pad-16" style={{ marginTop: 16 }}>
          <button type="button" className="ps-btn" onClick={reintentarSesion}>
            Reintentar
          </button>
        </div>
      </Screen>
    )
  }
  return <>{children}</>
}
