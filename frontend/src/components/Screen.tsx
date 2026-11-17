import type { MouseEvent, ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { IconoVolver } from './icons'
import { useI18n } from '../i18n'

export function Screen({ children, sinMenu }: { children: ReactNode; sinMenu?: boolean }) {
  return (
    <div className="ps-app">
      <div className="ps-screen" style={sinMenu ? { paddingBottom: 0 } : undefined}>{children}</div>
    </div>
  )
}

// "Volver" lleva a la pantalla de la que se vino, no a una fija: casi todas se alcanzan desde varios lados. `volverA` es
// el respaldo cuando no hay historial dentro de la app (un enlace directo, la app instalada). `fijo` fuerza `volverA`
// donde volver atrás repetiría algo que ya se hizo (marcar el predio otra vez).
export function BarraSuperior({
  volverA,
  derecha,
  fijo = false,
}: {
  volverA?: string
  derecha?: ReactNode
  fijo?: boolean
}) {
  const { t } = useI18n()
  const navigate = useNavigate()
  function volver(e: MouseEvent) {
    if (fijo || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey) return
    const idx = (window.history.state as { idx?: number } | null)?.idx ?? 0
    if (idx > 0) {
      e.preventDefault()
      navigate(-1)
    }
  }
  return (
    <div className="ps-topbar" style={{ justifyContent: derecha ? 'space-between' : undefined }}>
      {volverA ? (
        <Link to={volverA} onClick={volver} className="ps-back">
          <IconoVolver tamano={18} />
          {t('volver')}
        </Link>
      ) : (
        <span />
      )}
      {derecha}
    </div>
  )
}

export function Titulo({ children, sub }: { children: ReactNode; sub?: ReactNode }) {
  return (
    <>
      <h1 className="ps-h1">{children}</h1>
      {sub ? <p className="ps-pad ps-detalle" style={{ margin: '6px 20px 0 20px' }}>{sub}</p> : null}
    </>
  )
}
