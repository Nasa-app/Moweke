import { Link } from 'react-router-dom'
import { DibujoParcela, DibujoRotacion, DibujoSembrar } from './DibujosTutorial'
import { IconoSiguiente } from './icons'
import { useI18n } from '../i18n'

// Lo que toca hacer ahora, con los dibujos y los textos del tutorial de la portada (que se ve una sola vez): sin predio,
// marcarlo; con predio y sin cultivos, ver qué sembrar; con cultivos, planificar la rotación.
export function PasosSiguientes({ tieneParcela, tieneCultivos }: { tieneParcela: boolean; tieneCultivos: boolean }) {
  const { t } = useI18n()
  const paso = !tieneParcela
    ? { clave: 'tutorial_1', a: '/terreno/perimetro', Dibujo: DibujoParcela }
    : !tieneCultivos
      ? { clave: 'tutorial_3', a: '/especies', Dibujo: DibujoSembrar }
      : { clave: 'tutorial_4', a: '/planificar', Dibujo: DibujoRotacion }
  const { Dibujo } = paso
  return (
    <section aria-labelledby="siguiente-paso" className="ps-pad-16" style={{ marginTop: 16 }}>
      <h2 id="siguiente-paso" className="ps-h2" style={{ margin: '0 4px' }}>{t('hoy_siguiente_paso')}</h2>
      <Link to={paso.a} className="ps-card" style={{ marginTop: 10, padding: 0, overflow: 'hidden', textDecoration: 'none', color: 'var(--carbon)', display: 'flex', alignItems: 'stretch' }}>
        <span aria-hidden="true" style={{ flex: '0 0 38%', minHeight: 112, display: 'block' }}>
          <Dibujo />
        </span>
        <span style={{ flex: 1, minWidth: 0, padding: '12px 12px 12px 14px', display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
            <b style={{ fontSize: 18, fontWeight: 800, lineHeight: 1.15 }}>{t(`${paso.clave}_titulo`)}</b>
            <span className="ps-detalle">{t(`${paso.clave}_texto`)}</span>
          </span>
          <IconoSiguiente stroke="var(--verde)" />
        </span>
      </Link>
    </section>
  )
}
