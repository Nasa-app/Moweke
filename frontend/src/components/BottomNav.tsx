import { Link, useLocation } from 'react-router-dom'
import { IconoCultivos, IconoHoy, IconoMas, IconoPlanificar, IconoTerreno } from './icons'
import { useI18n } from '../i18n'

const ITEMS = [
  { ruta: '/hoy', clave: 'nav_hoy', Icono: IconoHoy },
  { ruta: '/cultivo', clave: 'nav_cultivos', Icono: IconoCultivos },
] as const

const ITEMS_DERECHA = [
  { ruta: '/terreno', clave: 'nav_terreno', Icono: IconoTerreno },
  { ruta: '/planificar', clave: 'nav_planificar', Icono: IconoPlanificar },
] as const

export function BottomNav() {
  const { pathname } = useLocation()
  const { t } = useI18n()

  if (pathname === '/') return null

  return (
    <nav className="ps-nav" aria-label={t('nav_hoy')}>
      {ITEMS.map(({ ruta, clave, Icono }) => (
        <Link key={ruta} to={ruta} className={`ps-nav-item ${pathname === ruta ? 'activo' : ''}`} aria-current={pathname === ruta ? 'page' : undefined}>
          <Icono />
          {t(clave)}
        </Link>
      ))}
      <Link to="/reportar" aria-label={t('nav_reportar')} className="ps-nav-cta">
        <IconoMas tamano={26} />
      </Link>
      {ITEMS_DERECHA.map(({ ruta, clave, Icono }) => (
        <Link key={ruta} to={ruta} className={`ps-nav-item ${pathname === ruta ? 'activo' : ''}`} aria-current={pathname === ruta ? 'page' : undefined}>
          <Icono />
          {t(clave)}
        </Link>
      ))}
    </nav>
  )
}
