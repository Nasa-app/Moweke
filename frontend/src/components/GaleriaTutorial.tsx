import { useRef, useState } from 'react'
import { useI18n } from '../i18n'

// Cuatro vistas en miniatura de lo que hace la app: dibujos con los colores del diseño, sin cifras ni datos de nadie.
const LIENZO = { width: '100%', height: '100%', display: 'block' } as const

function Parcela() {
  return (
    <svg viewBox="0 0 300 150" preserveAspectRatio="xMidYMid slice" style={LIENZO} aria-hidden="true">
      <rect width="300" height="150" fill="var(--menta)" />
      <path d="M0 112 C70 96 120 126 190 108 S270 100 300 110 V150 H0Z" fill="var(--ilus-pasto)" opacity="0.55" />
      <polygon points="92,44 196,34 220,98 112,116" fill="var(--blanco)" fillOpacity="0.55" stroke="var(--verde)" strokeWidth="4" strokeLinejoin="round" strokeDasharray="10 6" />
      {[[92, 44], [196, 34], [220, 98], [112, 116]].map(([x, y]) => (
        <circle key={`${x}${y}`} cx={x} cy={y} r="7" fill="var(--verde)" stroke="var(--blanco)" strokeWidth="3" />
      ))}
    </svg>
  )
}

function Hoy() {
  return (
    <svg viewBox="0 0 300 150" preserveAspectRatio="xMidYMid slice" style={LIENZO} aria-hidden="true">
      <rect width="300" height="150" fill="var(--cielo)" />
      <circle cx="226" cy="42" r="22" fill="var(--ilus-sol)" />
      <rect x="28" y="26" width="104" height="14" rx="7" fill="var(--agua)" opacity="0.8" />
      <rect x="28" y="48" width="64" height="10" rx="5" fill="var(--agua)" opacity="0.45" />
      <path d="M0 108 C60 94 110 118 180 104 S270 96 300 104 V150 H0Z" fill="var(--ilus-hoja)" />
      <rect x="28" y="84" width="92" height="30" rx="15" fill="var(--blanco)" />
      <circle cx="46" cy="99" r="7" fill="var(--semaforo-amarillo)" />
      <rect x="60" y="95" width="46" height="8" rx="4" fill="var(--linea)" />
      <rect x="132" y="84" width="92" height="30" rx="15" fill="var(--blanco)" />
      <circle cx="150" cy="99" r="7" fill="var(--semaforo-verde)" />
      <rect x="164" y="95" width="46" height="8" rx="4" fill="var(--linea)" />
    </svg>
  )
}

function Sembrar() {
  const filas = [
    { y: 22, largo: 150, color: 'var(--semaforo-verde)' },
    { y: 62, largo: 112, color: 'var(--semaforo-verde)' },
    { y: 102, largo: 70, color: 'var(--semaforo-amarillo)' },
  ]
  return (
    <svg viewBox="0 0 300 150" preserveAspectRatio="xMidYMid slice" style={LIENZO} aria-hidden="true">
      <rect width="300" height="150" fill="var(--hundido)" />
      {filas.map((f) => (
        <g key={f.y}>
          <rect x="24" y={f.y} width="252" height="34" rx="14" fill="var(--blanco)" />
          <circle cx="46" cy={f.y + 17} r="11" fill="var(--menta)" />
          <path d={`M46 ${f.y + 23} V${f.y + 12} M46 ${f.y + 16} q-6 -1 -7 -6 q6 0 7 6 M46 ${f.y + 14} q6 -1 7 -6 q-6 0 -7 6`} stroke="var(--verde)" strokeWidth="2" fill="none" strokeLinecap="round" />
          <rect x="68" y={f.y + 10} width="64" height="7" rx="3.5" fill="var(--carbon)" opacity="0.65" />
          <rect x="68" y={f.y + 21} width={f.largo * 0.7} height="6" rx="3" fill={f.color} />
        </g>
      ))}
    </svg>
  )
}

function Rotacion() {
  const colores = ['var(--ilus-hoja)', 'var(--celeste)', 'var(--ilus-sol)', 'var(--ilus-tierra)']
  const filas = [
    [0, 1, 2, 3],
    [1, 2, 3, 0],
    [2, 3, 0, 1],
  ]
  return (
    <svg viewBox="0 0 300 150" preserveAspectRatio="xMidYMid slice" style={LIENZO} aria-hidden="true">
      <rect width="300" height="150" fill="var(--menta)" />
      {filas.map((fila, r) =>
        fila.map((c, k) => <rect key={`${r}${k}`} x={28 + k * 62} y={20 + r * 38} width="54" height="30" rx="10" fill={colores[c]} />),
      )}
    </svg>
  )
}

const PASOS = [
  { clave: 'tutorial_1', Dibujo: Parcela },
  { clave: 'tutorial_2', Dibujo: Hoy },
  { clave: 'tutorial_3', Dibujo: Sembrar },
  { clave: 'tutorial_4', Dibujo: Rotacion },
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
