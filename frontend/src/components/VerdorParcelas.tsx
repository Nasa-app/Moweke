import { useEffect, useMemo, useState } from 'react'
import { listarParcelas, mapaParcela, type CeldaMapa, type MapaPredio, type ParcelaResumen } from '../lib/api'
import { COLORES_NDVI, DOMINIO_NDVI, colorEnEscala } from '../lib/escalas'
import { fechaCorta, numero } from '../lib/formato'
import { useI18n } from '../i18n'

const SEGUNDOS_ENTRE_CONSULTAS = 5

type Anillo = [number, number][]

// Los anillos exteriores de una celda (la grilla puede traer Polygon o MultiPolygon).
function anillosDe(celda: CeldaMapa): Anillo[] {
  const { type, coordinates } = celda.geometry as { type: string; coordinates: unknown }
  if (type === 'Polygon') return [(coordinates as Anillo[])[0]]
  if (type === 'MultiPolygon') return (coordinates as Anillo[][]).map((poligono) => poligono[0])
  return []
}

// El predio dibujado celda por celda con el NDVI de la imagen de NASA HLS. El este-oeste se acorta con la latitud.
function Imagen({ mapa }: { mapa: MapaPredio }) {
  const { t } = useI18n()
  const dibujo = useMemo(() => {
    const celdas = mapa.features.map((c) => ({ celda: c, anillos: anillosDe(c) })).filter((c) => c.anillos.length)
    const puntos = celdas.flatMap((c) => c.anillos.flat())
    if (!puntos.length) return null
    const k = Math.cos((puntos.reduce((s, p) => s + p[1], 0) / puntos.length) * (Math.PI / 180))
    const x0 = Math.min(...puntos.map((p) => p[0] * k))
    const y0 = Math.min(...puntos.map((p) => -p[1]))
    const ancho = Math.max(...puntos.map((p) => p[0] * k)) - x0 || 1
    const alto = Math.max(...puntos.map((p) => -p[1])) - y0 || 1
    const escala = 200 / Math.max(ancho, alto)
    const aTexto = (anillo: Anillo) => anillo.map((p) => `${((p[0] * k - x0) * escala).toFixed(1)},${((-p[1] - y0) * escala).toFixed(1)}`).join(' ')
    return { ancho: ancho * escala, alto: alto * escala, celdas: celdas.map((c) => ({ i: c.celda.properties.i, j: c.celda.properties.j, valor: c.celda.properties.valor, formas: c.anillos.map(aTexto) })) }
  }, [mapa])
  if (!dibujo) return null
  return (
    <svg viewBox={`0 0 ${dibujo.ancho.toFixed(1)} ${dibujo.alto.toFixed(1)}`} role="img" aria-label={t('hoy_verdor_imagen_aria')} style={{ width: '100%', maxHeight: 240, display: 'block', borderRadius: 14, background: 'var(--hundido)' }}>
      {dibujo.celdas.map((c) =>
        c.formas.map((puntos, n) => (
          <polygon key={`${c.i},${c.j},${n}`} points={puntos} fill={c.valor === null ? 'var(--hundido)' : colorEnEscala(COLORES_NDVI, DOMINIO_NDVI, c.valor)} stroke="#fff" strokeWidth={0.6} strokeOpacity={0.5} />
        )),
      )}
    </svg>
  )
}

function TarjetaVerdor({ parcela, numeroDeParcela }: { parcela: ParcelaResumen; numeroDeParcela: number }) {
  const { t } = useI18n()
  const [mapa, setMapa] = useState<MapaPredio | null>(null)
  const [falla, setFalla] = useState(false)
  const estado = mapa?.estado_ingesta.estado
  const enCurso = estado === 'pendiente' || estado === 'en_proceso'

  useEffect(() => {
    let vigente = true
    let reloj: ReturnType<typeof setTimeout> | undefined
    const consultar = () =>
      mapaParcela(parcela.id, 'ndvi_hls')
        .then((m) => {
          if (!vigente) return
          setMapa(m)
          setFalla(false)
          if (['pendiente', 'en_proceso'].includes(m.estado_ingesta.estado)) reloj = setTimeout(consultar, SEGUNDOS_ENTRE_CONSULTAS * 1000)
        })
        .catch(() => vigente && setFalla(true))
    consultar()
    return () => {
      vigente = false
      clearTimeout(reloj)
    }
  }, [parcela.id])

  const conImagen = mapa !== null && mapa.celdas_con_dato > 0
  const sinImagen = mapa === null ? null : estado === 'sin_configurar' ? t('hoy_verdor_sin_token') : enCurso ? t('hoy_verdor_cargando') : t('hoy_verdor_sin_imagen')

  return (
    <article className="ps-card" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 8 }}>
        <h3 style={{ margin: 0, fontWeight: 800, fontSize: 19 }}>{t('selector_parcela_n', { n: numeroDeParcela, ha: numero(parcela.hectareas, 2) })}</h3>
        {conImagen && mapa.fecha_comun ? <span className="ps-detalle">{t('hoy_verdor_fecha', { fecha: fechaCorta(mapa.fecha_comun) })}</span> : null}
      </div>
      {conImagen ? (
        <>
          <Imagen mapa={mapa} />
          <div aria-hidden="true" style={{ height: 12, borderRadius: 6, background: `linear-gradient(to right, ${COLORES_NDVI.join(', ')})` }} />
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }} className="ps-detalle">
            <span>{t('zonas_bajo_ndvi')}</span>
            <span>{t('zonas_alto_ndvi')}</span>
          </div>
          <span className="ps-nota">{t('hoy_verdor_fuente')}</span>
        </>
      ) : (
        <p className="ps-nota" style={{ margin: 0 }}>{falla ? t('hoy_verdor_error') : (sinImagen ?? t('cargando'))}</p>
      )}
    </article>
  )
}

// Una imagen de verdor (NASA HLS, 30 m) por cada predio del usuario.
export function VerdorParcelas() {
  const { t } = useI18n()
  const [parcelas, setParcelas] = useState<ParcelaResumen[]>([])

  useEffect(() => {
    let vigente = true
    listarParcelas()
      .then((r) => vigente && setParcelas(r.parcelas))
      .catch(() => vigente && setParcelas([]))
    return () => {
      vigente = false
    }
  }, [])

  if (!parcelas.length) return null
  return (
    <section aria-labelledby="verdor-parcelas" style={{ marginTop: 18 }}>
      <h2 id="verdor-parcelas" className="ps-h2" style={{ margin: '0 20px' }}>{t('hoy_verdor_titulo')}</h2>
      <div className="ps-pad-16" style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 10 }}>
        {parcelas.map((p, i) => (
          <TarjetaVerdor key={p.id} parcela={p} numeroDeParcela={i + 1} />
        ))}
      </div>
    </section>
  )
}
