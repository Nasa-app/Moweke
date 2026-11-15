import type { ReactNode } from 'react'
import { Screen, Titulo } from './Screen'
import { useAuth } from '../state/AuthContext'
import { useI18n } from '../i18n'

// Ya no hay inicio de sesión: la cuenta anónima se crea sola al abrir la app. Esta ruta solo espera a que
// esté lista y, si no se pudo (sin conexión), deja reintentar en vez de mandar a una pantalla de login.
export function RutaPrivada({ children }: { children: ReactNode }) {
  const { t } = useI18n()
  const { autenticado, cargando, reintentarSesion } = useAuth()
  if (cargando) return null
  if (!autenticado) {
    return (
      <Screen>
        <Titulo sub={t('ruta_privada_sub')}>{t('ruta_privada_titulo')}</Titulo>
        <div className="ps-pad-16" style={{ marginTop: 16 }}>
          <button type="button" className="ps-btn" onClick={reintentarSesion}>
            {t('reintentar')}
          </button>
        </div>
      </Screen>
    )
  }
  return <>{children}</>
}
