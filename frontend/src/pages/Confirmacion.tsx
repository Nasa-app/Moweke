import { Link, useLocation } from 'react-router-dom'
import { Screen } from '../components/Screen'
import { IconoCheck } from '../components/icons'
import { useI18n } from '../i18n'

export default function Confirmacion() {
  const { t } = useI18n()
  const enviado = (useLocation().state as { enviado?: boolean } | null)?.enviado === true
  return (
    <Screen>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <div style={{ marginTop: 110, position: 'relative', width: 180, height: 180 }}>
          <svg width={180} height={180} viewBox="0 0 180 180" aria-hidden="true">
            <circle cx="90" cy="90" r="84" fill="var(--cielo)" />
          </svg>
          <span
            style={{
              position: 'absolute',
              right: 6,
              top: 10,
              width: 56,
              height: 56,
              borderRadius: 28,
              background: 'var(--verde)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 0 6px #fff',
            }}
          >
            <IconoCheck tamano={30} stroke="#fff" />
          </span>
        </div>

        <h1 style={{ margin: '24px 24px 0 24px', fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 32, lineHeight: 1.1, textAlign: 'center' }}>
          {t('confirmacion_gracias')}
        </h1>
        <p style={{ margin: '8px 24px 0 24px', fontSize: 18, lineHeight: 1.35, textAlign: 'center' }}>{t('confirmacion_actualizado')}</p>

        <div style={{ marginTop: 24, padding: '0 24px', alignSelf: 'stretch', display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 8 }}>
          <div className="ps-card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
            <span style={{ fontSize: 24, fontWeight: 800 }}>{t(enviado ? 'confirmacion_enviado' : 'confirmacion_guardado')}</span>
            <span className="ps-nota">{t(enviado ? 'confirmacion_enviado_detalle' : 'confirmacion_en_cola')}</span>
          </div>
        </div>

        <div style={{ marginTop: 'auto', alignSelf: 'stretch', padding: '24px 16px 32px 16px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          <Link to="/hoy" className="ps-btn">
            {t('confirmacion_volver_hoy')}
          </Link>
          <Link to="/reportar" className="ps-btn-texto">
            {t('deshacer')}
          </Link>
        </div>
      </div>
    </Screen>
  )
}
