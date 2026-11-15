import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { IconoVolver } from './icons'
import { useI18n } from '../i18n'

export function Screen({ children, sinMenu }: { children: ReactNode; sinMenu?: boolean }) {
  return (
    <div className="ps-app">
      <div className="ps-screen" style={sinMenu ? { paddingBottom: 0 } : undefined}>{children}</div>
    </div>
  )
}

export function BarraSuperior({
  volverA,
  derecha,
}: {
  volverA?: string
  derecha?: ReactNode
}) {
  const { t } = useI18n()
  return (
    <div className="ps-topbar" style={{ justifyContent: derecha ? 'space-between' : undefined }}>
      {volverA ? (
        <Link to={volverA} className="ps-back">
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
