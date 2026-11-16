import { Link } from 'react-router-dom'
import { Screen } from '../components/Screen'
import { usePredio } from '../state/PredioContext'
import { GaleriaTutorial } from '../components/GaleriaTutorial'
import { useI18n } from '../i18n'

export default function Portada() {
  const { t } = useI18n()
  const { idParcela } = usePredio()   // con una parcela marcada ya se usó la app: se sigue en Hoy
  return (
    <Screen sinMenu>
      <div style={{ padding: '60px 0 0 0', display: 'flex', justifyContent: 'center' }}>
        <img src="/logo.webp" width={104} height={104} alt={t('portada_logo_alt')} />
      </div>
      <div style={{ margin: '14px 32px 0 32px', display: 'flex', flexDirection: 'column', gap: 10, alignItems: 'center', textAlign: 'center' }}>
        <h1 style={{ margin: 0, fontFamily: 'var(--font-marca)', fontWeight: 800, fontSize: 48, lineHeight: 1 }}>mogen</h1>
        <p style={{ margin: 0, fontSize: 20, fontWeight: 700, lineHeight: 1.3 }}>{t('mowege_slogan')}</p>
      </div>
      <div className="ps-pad-16">
        <GaleriaTutorial />
      </div>
      <div style={{ marginTop: 'auto', padding: '20px 32px 32px 32px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        <Link to={idParcela ? '/hoy' : '/explorar'} className="ps-btn">
          {t(idParcela ? 'continuar' : 'empezar')}
        </Link>
      </div>
    </Screen>
  )
}
