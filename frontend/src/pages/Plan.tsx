import { Link } from 'react-router-dom'
import { Screen, BarraSuperior, Titulo } from '../components/Screen'
import { planTemporada } from '../lib/mock'
import { useI18n } from '../i18n'

export default function Plan() {
  const { t } = useI18n()
  return (
    <Screen>
      <BarraSuperior volverA="/planificar" derecha={<span className="ps-contexto">2027</span>} />
      <Titulo>{t('plan_titulo')}</Titulo>

      <ol className="ps-pad-16" style={{ marginTop: 20, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 14 }}>
        {planTemporada.map((p) => (
          <li
            key={p.tarea}
            className="ps-card"
            style={{ display: 'flex', alignItems: 'center', gap: 14, boxShadow: p.estado === 'actual' ? '0 0 0 3px var(--verde)' : 'var(--sombra-1)' }}
          >
            <span style={{ width: 56, height: 56, borderRadius: 28, background: 'var(--hundido)', flexShrink: 0 }} aria-hidden="true" />
            <span style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
              <span style={{ fontSize: 20, fontWeight: 800 }}>{p.tarea}</span>
              <span style={{ fontSize: 15, color: 'var(--texto-tenue)' }}>{p.detalle}</span>
            </span>
            <span
              style={{
                minWidth: 64,
                padding: '8px 6px',
                borderRadius: 14,
                textAlign: 'center',
                fontSize: 18,
                fontWeight: 800,
                background: p.estado === 'actual' ? 'var(--verde)' : p.estado === 'estimado' ? 'transparent' : 'var(--menta)',
                color: p.estado === 'actual' ? '#fff' : p.estado === 'estimado' ? 'var(--carbon)' : 'var(--verde)',
                border: p.estado === 'estimado' ? '2px dashed var(--borde-control)' : 'none',
                boxSizing: 'border-box',
              }}
            >
              {p.mes}
            </span>
          </li>
        ))}
      </ol>

      <section className="ps-pad-16" style={{ marginTop: 18, background: 'var(--cielo)', color: 'var(--carbon)', borderRadius: 22, padding: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
        <h2 className="ps-h2">{t('plan_tienes_semilla')}</h2>
        <div className="ps-grid-2">
          <button type="button" className="ps-pill activo" style={{ minHeight: 52 }}>
            {t('si')}
          </button>
          <Link to="/semillas" className="ps-pill" style={{ minHeight: 52, border: '2px solid var(--agua)', color: 'var(--agua)', background: '#fff', textDecoration: 'none' }}>
            {t('plan_buscar')}
          </Link>
        </div>
      </section>

      <div style={{ marginTop: 'auto', padding: '20px 16px 32px 16px', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <Link to="/hoy" className="ps-btn">
          {t('plan_guardar')}
        </Link>
        <Link to="/planificar" className="ps-btn-texto">
          {t('plan_cambiar')}
        </Link>
      </div>
    </Screen>
  )
}
