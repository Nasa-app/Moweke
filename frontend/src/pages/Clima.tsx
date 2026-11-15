import { useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { Screen, BarraSuperior, Titulo } from '../components/Screen'
import { IconoCalor, IconoHelada, IconoLluvia } from '../components/icons'
import { ApiError, climaParcela, mensajeDeError, type ClimaPredio, type DiaClima } from '../lib/api'
import { diaSemana, fechaCorta, numero } from '../lib/formato'
import { usePredio } from '../state/PredioContext'
import { useI18n } from '../i18n'

const PESTANAS = ['Calor', 'Lluvia', 'Heladas'] as const
type Pestana = (typeof PESTANAS)[number]
const DIAS_ATRAS = 30
const LLUVIA_MIN_MM = 1 // bajo esto un día no se muestra como lluvioso
const ALTO = 120

const SERIE: Record<Pestana, { valor: (d: DiaClima) => number | null; color: string; leyenda: string }> = {
  Calor: { valor: (d) => d.tmax, color: 'var(--semaforo-amarillo)', leyenda: 'Temperatura más alta de cada día' },
  Lluvia: { valor: (d) => d.lluvia_mm, color: 'var(--agua)', leyenda: 'Milímetros de lluvia de cada día' },
  Heladas: { valor: (d) => d.tmin, color: 'var(--celeste)', leyenda: 'Temperatura más baja de cada día' },
}

function Grafico({ dias, pestana, hoy }: { dias: DiaClima[]; pestana: Pestana; hoy: string }) {
  const { valor, color } = SERIE[pestana]
  const valores = dias.map(valor).filter((v): v is number => v !== null)
  if (!valores.length) return null
  const minimo = Math.min(0, ...valores)
  const maximo = Math.max(1, ...valores)
  const ancho = 100 / dias.length
  const y = (v: number) => ALTO - ((v - minimo) / (maximo - minimo)) * ALTO
  const indiceHoy = dias.findIndex((d) => d.fecha >= hoy)
  return (
    <svg viewBox={`0 0 100 ${ALTO}`} preserveAspectRatio="none" role="img" aria-label={`${SERIE[pestana].leyenda}, del ${fechaCorta(dias[0].fecha)} al ${fechaCorta(dias[dias.length - 1].fecha)}`} style={{ display: 'block', width: '100%', height: ALTO }}>
      {dias.map((d, i) => {
        const v = valor(d)
        if (v === null) return null
        const helada = pestana === 'Heladas' && v <= 0
        const arriba = Math.min(y(v), y(0))
        return (
          <rect
            key={d.fecha}
            x={i * ancho + ancho * 0.15}
            y={arriba}
            width={ancho * 0.7}
            height={Math.max(0.8, Math.abs(y(v) - y(0)))}
            fill={helada ? 'var(--semaforo-rojo)' : color}
            opacity={d.horizonte === 'pronostico' ? 0.45 : 1}
          />
        )
      })}
      <line x1={0} x2={100} y1={y(0)} y2={y(0)} stroke="var(--carbon)" strokeWidth={0.4} vectorEffect="non-scaling-stroke" />
      {indiceHoy > 0 ? (
        <line x1={indiceHoy * ancho} x2={indiceHoy * ancho} y1={0} y2={ALTO} stroke="var(--carbon)" strokeWidth={1} strokeDasharray="3 3" vectorEffect="non-scaling-stroke" />
      ) : null}
    </svg>
  )
}

export default function Clima() {
  const { t } = useI18n()
  const { idParcela } = usePredio()
  const [pestana, setPestana] = useState<Pestana>('Calor')
  const [clima, setClima] = useState<ClimaPredio | null>(null)
  const [sinClima, setSinClima] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!idParcela) return
    let vigente = true
    climaParcela(idParcela, DIAS_ATRAS)
      .then((c) => vigente && setClima(c))
      .catch((err) => {
        if (!vigente) return
        if (err instanceof ApiError && err.status === 409) setSinClima(true)
        else setError(mensajeDeError(err, 'No se pudo cargar el clima.'))
      })
    return () => {
      vigente = false
    }
  }, [idParcela])

  if (!idParcela) return <Navigate to="/terreno/perimetro" replace />

  const dias = clima?.dias ?? []
  const hoy = clima?.hoy ?? ''
  const pasados = dias.filter((d) => d.fecha < hoy)
  const proximos = dias.filter((d) => d.fecha >= hoy).slice(0, 7)
  const maximas = pasados.map((d) => d.tmax).filter((v): v is number => v !== null)
  const lluvia = pasados.reduce((suma, d) => suma + (d.lluvia_mm ?? 0), 0)
  const heladas = pasados.filter((d) => d.tmin !== null && d.tmin <= 0).length

  return (
    <Screen>
      <BarraSuperior volverA="/hoy" />
      <Titulo>{t('clima_titulo')}</Titulo>

      {sinClima ? (
        <Link to="/terreno/preparando" className="ps-card-plana" style={{ margin: '12px 16px 0 16px', textDecoration: 'none', color: 'var(--carbon)', display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ flex: 1, fontSize: 16, fontWeight: 700 }}>Todavía se está reuniendo el clima de tu parcela.</span>
          <span style={{ fontSize: 16, fontWeight: 800, color: 'var(--verde)' }}>Ver avance</span>
        </Link>
      ) : null}
      {error ? (
        <p className="ps-pad ps-nota" role="alert" style={{ margin: '12px 0 0 0', color: 'var(--riesgo-texto)' }}>
          {error}
        </p>
      ) : null}
      {!clima && !sinClima && !error ? <p className="ps-pad ps-nota" style={{ margin: '12px 0 0 0' }}>{t('cargando')}</p> : null}

      {clima ? (
        <>
          <div className="ps-pad-16" style={{ marginTop: 14 }}>
            <div role="tablist" aria-label="Dato" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 6, padding: 5, borderRadius: 18, background: 'var(--cielo)' }}>
              {PESTANAS.map((p) => (
                <button
                  key={p}
                  type="button"
                  role="tab"
                  aria-selected={pestana === p}
                  onClick={() => setPestana(p)}
                  style={{ minHeight: 48, borderRadius: 14, border: 'none', background: pestana === p ? 'var(--agua)' : 'transparent', color: pestana === p ? '#fff' : 'var(--carbon)', font: `${pestana === p ? 800 : 700} 16px 'Alegreya Sans', sans-serif`, cursor: 'pointer' }}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          <div className="ps-pad-16" style={{ marginTop: 12 }}>
            <div style={{ background: 'var(--cielo)', borderRadius: 22, padding: '14px 12px', display: 'flex', flexDirection: 'column', gap: 8 }}>
              <span style={{ fontSize: 15, fontWeight: 800 }}>{SERIE[pestana].leyenda}</span>
              <Grafico dias={dias} pestana={pestana} hoy={hoy} />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, fontWeight: 700, color: 'var(--texto-tenue)' }}>
                <span>{fechaCorta(dias[0]?.fecha)}</span>
                <span>Línea: hoy · claro: modelo o pronóstico</span>
                <span>{fechaCorta(dias[dias.length - 1]?.fecha)}</span>
              </div>
            </div>
          </div>

          <div className="ps-pad-16" style={{ marginTop: 12, display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 8 }}>
            <div className="ps-card" style={{ textAlign: 'center', padding: 12 }}>
              <span style={{ display: 'block', fontSize: 22, fontWeight: 800 }}>{maximas.length ? `${numero(Math.max(...maximas), 1)}°` : '—'}</span>
              <span className="ps-nota">Día más cálido</span>
            </div>
            <div className="ps-card" style={{ textAlign: 'center', padding: 12 }}>
              <span style={{ display: 'block', fontSize: 22, fontWeight: 800 }}>{pasados.length ? `${numero(lluvia)} mm` : '—'}</span>
              <span className="ps-nota">Lluvia</span>
            </div>
            <div className="ps-card" style={{ textAlign: 'center', padding: 12 }}>
              <span style={{ display: 'block', fontSize: 22, fontWeight: 800 }}>{pasados.length ? heladas : '—'}</span>
              <span className="ps-nota">{heladas === 1 ? 'Helada' : 'Heladas'}</span>
            </div>
          </div>
          <p className="ps-pad ps-nota" style={{ margin: '6px 0 0 0' }}>
            En los últimos {pasados.length} días.
          </p>

          <section className="ps-pad-16" style={{ marginTop: 16 }}>
            <h2 className="ps-h2" style={{ margin: '0 4px 8px 4px' }}>
              {t('clima_proximos_dias')}
            </h2>
            {proximos.length ? (
              <ol style={{ margin: 0, padding: '10px 6px', listStyle: 'none', borderRadius: 20, background: '#fff', boxShadow: 'var(--sombra-1)', display: 'grid', gridTemplateColumns: `repeat(${proximos.length}, minmax(0, 1fr))` }}>
                {proximos.map((d) => {
                  const helada = d.tmin !== null && d.tmin <= 0
                  const llueve = (d.lluvia_mm ?? 0) >= LLUVIA_MIN_MM
                  const Icono = helada ? IconoHelada : llueve ? IconoLluvia : IconoCalor
                  return (
                    <li key={d.fecha} aria-label={`${fechaCorta(d.fecha)}: entre ${numero(d.tmin)} y ${numero(d.tmax)} grados${llueve ? `, ${numero(d.lluvia_mm)} mm de lluvia` : ''}${helada ? ', helada' : ''}`} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, borderRadius: 12, background: helada ? 'var(--precaucion-fondo)' : undefined, padding: '2px 0' }}>
                      <span style={{ fontSize: 14, fontWeight: helada ? 800 : 700, color: helada ? 'var(--precaucion-texto)' : 'var(--texto-tenue)' }}>{diaSemana(d.fecha)}</span>
                      <Icono tamano={20} stroke={helada ? 'var(--precaucion-texto)' : llueve ? 'var(--agua)' : 'var(--semaforo-amarillo)'} />
                      <span style={{ fontSize: 16, fontWeight: 800 }}>{numero(d.tmax)}°</span>
                      <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--texto-tenue)' }}>{numero(d.tmin)}°</span>
                    </li>
                  )
                })}
              </ol>
            ) : (
              <p className="ps-cuerpo" style={{ margin: '0 4px' }}>El pronóstico todavía no llega para esta parcela.</p>
            )}
          </section>

          <Link to="/fuentes" className="ps-pad ps-nota" style={{ margin: 'auto 0 0 0', padding: '16px 20px 32px 20px', textDecoration: 'none' }}>
            Observado: CR2MET y NASA POWER. Pronóstico: Open-Meteo, ajustado al clima medido en tu parcela. Las heladas del pronóstico suelen quedar cortas.
          </Link>
        </>
      ) : null}
    </Screen>
  )
}
