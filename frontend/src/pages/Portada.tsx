import { Link } from 'react-router-dom'
import { Screen } from '../components/Screen'
import { useI18n } from '../i18n'

export default function Portada() {
  const { t } = useI18n()
  return (
    <Screen>
      <div style={{ padding: '76px 0 0 0', display: 'flex', justifyContent: 'center' }}>
        <img src="/logo.webp" width={160} height={160} alt="Logo de mogen: una planta con raíces entre el sol y la lluvia" />

      </div>
      <div style={{ margin: '24px 32px 0 32px', display: 'flex', flexDirection: 'column', gap: 10, alignItems: 'center', textAlign: 'center' }}>
        <h1 style={{ margin: 0, fontFamily: 'var(--font-marca)', fontWeight: 800, fontSize: 52, lineHeight: 1 }}>mogen</h1>
        <p style={{ margin: 0, fontSize: 20, fontWeight: 700, lineHeight: 1.3 }}>{t('mowege_slogan')}</p>
      </div>
      <div style={{ marginTop: 'auto', padding: '24px 32px 40px 32px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        <Link to="/explorar" className="ps-btn">
          {t('empezar')}
        </Link>
        <Link to="/sesion" className="ps-btn-texto">
          {t('ya_tengo_cuenta')}
        </Link>
      </div>
    </Screen>
  )
}
