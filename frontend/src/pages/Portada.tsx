import { Link } from 'react-router-dom'
import { Screen } from '../components/Screen'
import { LangSwitch } from '../components/LangSwitch'
import { useI18n } from '../i18n'

export default function Portada() {
  const { t } = useI18n()
  return (
    <Screen>
      <div style={{ padding: '44px 20px 0 20px', display: 'flex', justifyContent: 'flex-end' }}>
        <LangSwitch />
      </div>
      <div style={{ padding: '32px 0 0 0', display: 'flex', justifyContent: 'center' }}>
        <svg width={160} height={160} viewBox="0 0 160 160" aria-label="Logo de Mowege: una planta con raíces entre el sol y la lluvia" role="img">
          <circle cx="80" cy="80" r="76" fill="var(--menta)" />
          <circle cx="50" cy="48" r="20" fill="var(--ilus-sol)" />
          <path d="M100 40c14 6 20 20 14 34-8-2-14-10-18-20-4 8-10 14-18 16 2-16 12-26 22-30z" fill="var(--agua)" opacity={0.25} />
          <path d="M80 130V70" stroke="var(--verde-oscuro)" strokeWidth={4} />
          <ellipse cx="60" cy="100" rx="18" ry="9" transform="rotate(-25 60 100)" fill="var(--semaforo-verde)" />
          <ellipse cx="100" cy="92" rx="18" ry="9" transform="rotate(25 100 92)" fill="var(--oliva)" />
          <ellipse cx="80" cy="66" rx="10" ry="15" fill="var(--ilus-pasto)" />
          <path d="M60 130c6-10 14-10 20-10s14 0 20 10z" fill="var(--ilus-tierra)" />
        </svg>
      </div>
      <div style={{ margin: '24px 32px 0 32px', display: 'flex', flexDirection: 'column', gap: 10, alignItems: 'center', textAlign: 'center' }}>
        <h1 style={{ margin: 0, fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 52, lineHeight: 1 }}>Mowege</h1>
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
