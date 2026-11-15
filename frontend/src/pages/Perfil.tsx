import { Link, useNavigate } from 'react-router-dom'
import { Screen, BarraSuperior } from '../components/Screen'
import { useAuth } from '../state/AuthContext'
import { usePredio } from '../state/PredioContext'
import { IconoCandado, IconoUbicacion, IconoReloj } from '../components/icons'
import { useI18n } from '../i18n'

export default function Perfil() {
  const { t } = useI18n()
  const { usuario, cerrarSesion } = useAuth()
  const { idParcela } = usePredio()
  const navigate = useNavigate()

  function manejarBorrado() {
    if (!confirm(t('perfil_confirmar_borrado'))) return
    cerrarSesion()
    navigate('/')
  }

  const mosaicos = [
    { a: '/terreno/parcelas', icono: IconoUbicacion, titulo: t('perfil_mi_parcela'), chip: idParcela ? t('perfil_marcada') : t('perfil_sin_marcar'), tonoChip: idParcela ? 'ps-chip-favorable' : 'ps-chip-precaucion' },
    { a: '/historial', icono: IconoReloj, titulo: t('perfil_anio_pasado'), chip: t('perfil_agregar'), tonoChip: 'ps-chip-neutro' },
  ] as const

  return (
    <Screen>
      <BarraSuperior volverA="/hoy" />
      <div style={{ margin: '16px 20px 0 20px', display: 'flex', alignItems: 'center', gap: 14 }}>
        <span aria-hidden="true" style={{ width: 64, height: 64, borderRadius: 32, background: 'var(--menta)', color: 'var(--verde)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 28, fontWeight: 800 }}>
          {(usuario?.nombre ?? 'A')[0]?.toUpperCase()}
        </span>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <h1 style={{ margin: 0, fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 28, lineHeight: 1 }}>{usuario?.nombre === 'Anónimo' ? t('perfil_anonimo') : (usuario?.nombre ?? t('perfil_agricultor'))}</h1>
          <span className="ps-contexto">{idParcela ? t('perfil_parcela_n', { n: idParcela }) : t('perfil_sin_parcela')}</span>
        </div>
      </div>

      <div className="ps-grid-2 ps-pad-16" style={{ marginTop: 20 }}>
        {mosaicos.map(({ a, icono: Icono, titulo, chip, tonoChip }) => (
          <Link key={titulo} to={a} className="ps-card" style={{ textDecoration: 'none', color: 'var(--carbon)', display: 'flex', flexDirection: 'column', gap: 8, minHeight: 128 }}>
            <span style={{ width: 48, height: 48, borderRadius: 24, background: 'var(--hundido)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Icono tamano={24} stroke="var(--verde)" />
            </span>
            <span style={{ fontSize: 18, fontWeight: 800, lineHeight: 1.1 }}>{titulo}</span>
            <span className={`ps-chip ${tonoChip}`} style={{ alignSelf: 'flex-start' }}>
              {chip}
            </span>
          </Link>
        ))}
      </div>


      <div style={{ marginTop: 'auto', padding: '24px 16px 32px 16px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        <button
          type="button"
          onClick={manejarBorrado}
          style={{ minHeight: 56, borderRadius: 16, border: '2px solid var(--riesgo-texto)', background: 'transparent', color: 'var(--riesgo-texto)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, font: "800 17px 'Alegreya Sans', sans-serif", cursor: 'pointer' }}
        >
          <IconoCandado stroke="currentColor" />
          {t('perfil_borrar_datos')}
        </button>
        <button
          type="button"
          onClick={() => {
            cerrarSesion()
            navigate('/')
          }}
          className="ps-btn-texto"
        >
          {t('perfil_cerrar_sesion')}
        </button>
      </div>
    </Screen>
  )
}
