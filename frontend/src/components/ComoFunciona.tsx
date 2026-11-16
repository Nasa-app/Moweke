import { GaleriaTutorial } from './GaleriaTutorial'
import { useI18n } from '../i18n'

// El tutorial de la portada (que se ve una sola vez), plegado al pie de Hoy para volver a verlo cuando se quiera.
export function ComoFunciona() {
  const { t } = useI18n()
  return (
    <details className="ps-pad-16" style={{ marginTop: 14 }}>
      <summary style={{ cursor: 'pointer', minHeight: 44, display: 'flex', alignItems: 'center', padding: '0 4px', fontSize: 16, fontWeight: 800, color: 'var(--verde)' }}>
        {t('tutorial_aria')}
      </summary>
      <GaleriaTutorial />
    </details>
  )
}
