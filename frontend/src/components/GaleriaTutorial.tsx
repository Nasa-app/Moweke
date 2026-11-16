import { useRef, useState } from 'react'
import { useI18n } from '../i18n'
import { DibujoHoy, DibujoParcela, DibujoRotacion, DibujoSembrar } from './DibujosTutorial'

const PASOS = [
  { clave: 'tutorial_1', Dibujo: DibujoParcela },
  { clave: 'tutorial_2', Dibujo: DibujoHoy },
  { clave: 'tutorial_3', Dibujo: DibujoSembrar },
  { clave: 'tutorial_4', Dibujo: DibujoRotacion },
] as const

export function GaleriaTutorial() {
  const { t } = useI18n()
  const pista = useRef<HTMLDivElement>(null)
  const [actual, setActual] = useState(0)

  function alDesplazar() {
    const el = pista.current
    if (el) setActual(Math.round(el.scrollLeft / el.clientWidth))
  }

  function ir(i: number) {
    const el = pista.current
    if (!el) return
    const sinMovimiento = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    el.scrollTo({ left: i * el.clientWidth, behavior: sinMovimiento ? 'auto' : 'smooth' })
  }

  return (
    <section aria-roledescription="carrusel" aria-label={t('tutorial_aria')} style={{ margin: '20px 0 0 0' }}>
      <div ref={pista} onScroll={alDesplazar} className="ps-galeria" tabIndex={0}>
        {PASOS.map(({ clave, Dibujo }, i) => (
          <article key={clave} className="ps-galeria-paso" aria-roledescription="diapositiva" aria-label={`${i + 1} / ${PASOS.length}`}>
            <div className="ps-galeria-vista">
              <Dibujo />
            </div>
            <h2 style={{ margin: '12px 0 0 0', fontSize: 20, fontWeight: 800, lineHeight: 1.15 }}>{t(`${clave}_titulo`)}</h2>
            <p style={{ margin: '4px 0 0 0', fontSize: 17, lineHeight: 1.3, color: 'var(--texto-tenue)', fontWeight: 600 }}>{t(`${clave}_texto`)}</p>
          </article>
        ))}
      </div>
      <div className="ps-galeria-puntos">
        {PASOS.map(({ clave }, i) => (
          <button key={clave} type="button" onClick={() => ir(i)} aria-label={`${t('tutorial_ir')} ${i + 1}`} aria-current={actual === i ? 'true' : undefined} className={actual === i ? 'activo' : ''}>
            <span />
          </button>
        ))}
      </div>
    </section>
  )
}
