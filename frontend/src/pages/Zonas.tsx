import { useEffect, useMemo, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { Screen, BarraSuperior, Titulo } from '../components/Screen'
import { MapaCeldas } from '../components/Mapa'
import { mapaParcela, mensajeDeError, verParcela, type CapaMapa, type CeldaMapa, type MapaPredio, type Poligono } from '../lib/api'
import { fechaCorta, numero } from '../lib/formato'
import { usePredio } from '../state/PredioContext'
import { useI18n } from '../i18n'
import { tr } from '../i18n/dictionary'

// Cada capa de GET /api/parcelas/{id}/mapa: cómo se nombra, con qué colores (los de
// tokens.css) y entre qué valores se reparte la escala. El verdor y la pendiente usan una
// escala fija, para que un color signifique lo mismo en cualquier parcela; la altura, la
// del propio predio, porque lo que importa es qué parte queda más alta.
const CAPAS: Record<CapaMapa, {
  colores: string[]
  dominio: (resumen: { minimo: number; maximo: number }) => [number, number]
  formato: (valor: number) => string
}> = {
  ndvi: {
    colores: ['#d9cbb0', '#d9a85b', '#829e30', '#3f611c'],
    dominio: () => [0.1, 0.9],
    formato: (v) => numero(v, 2),
  },
  altitud: {
    colores: ['#eef4d9', '#d9a85b', '#8e4b2c'],
    dominio: (r) => [r.minimo, Math.max(r.maximo, r.minimo + 1)],
    formato: (v) => `${numero(v)} m`,
  },
  pendiente: {
    colores: ['#617f26', '#d9a85b', '#a9542f'],
    dominio: () => [0, 30],
    formato: (v) => `${numero(v, 1)} %`,
  },
  hand: {
    colores: ['#2f6f9f', '#9cc3d8', '#eef4d9'],
    dominio: () => [0, 10],
    formato: (v) => `${numero(v, 1)} m`,
  },
}
const ORDEN: CapaMapa[] = ['ndvi', 'altitud', 'pendiente', 'hand']
const SEGUNDOS_ENTRE_CONSULTAS = 5

function mezclar(desde: string, hasta: string, t: number): string {
  const canal = (hex: string, i: number) => parseInt(hex.slice(1 + i * 2, 3 + i * 2), 16)
  return `rgb(${[0, 1, 2].map((i) => Math.round(canal(desde, i) + (canal(hasta, i) - canal(desde, i)) * t)).join(', ')})`
}

function colorEnEscala(colores: string[], [minimo, maximo]: [number, number], valor: number): string {
  const posicion = Math.min(1, Math.max(0, (valor - minimo) / (maximo - minimo))) * (colores.length - 1)
  const tramo = Math.min(colores.length - 2, Math.floor(posicion))
  return mezclar(colores[tramo], colores[tramo + 1], posicion - tramo)
}

export default function Zonas() {
  const { t } = useI18n()
  const { idParcela } = usePredio()
  const [capa, setCapa] = useState<CapaMapa>('ndvi')
  const [perimetro, setPerimetro] = useState<Poligono | null>(null)
  const [mapa, setMapa] = useState<MapaPredio | null>(null)
  const [elegida, setElegida] = useState<CeldaMapa | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!idParcela) return
    verParcela(idParcela)
      .then((p) => setPerimetro(p.perimetro))
      .catch((err) => setError(mensajeDeError(err, tr('zonas_error_parcela'))))
  }, [idParcela])

  const enCurso = mapa?.capa === capa && ['pendiente', 'en_proceso'].includes(mapa.estado_ingesta.estado)

  useEffect(() => {
    if (!idParcela) return
    let vigente = true
    let reloj: ReturnType<typeof setTimeout> | undefined
    const consultar = () =>
      mapaParcela(idParcela, capa)
        .then((m) => {
          if (vigente) {
            setMapa(m)
            setError(null)
          }
        })
        .catch((err) => {
          if (vigente) setError(mensajeDeError(err, tr('zonas_error_mapa')))
        })
        .finally(() => {
          if (vigente && enCurso) reloj = setTimeout(consultar, SEGUNDOS_ENTRE_CONSULTAS * 1000)
        })
    consultar()
    return () => {
      vigente = false
      clearTimeout(reloj)
    }
  }, [idParcela, capa, enCurso])

  const config = CAPAS[capa]
  const actual = mapa?.capa === capa ? mapa : null
  const dominio = useMemo<[number, number] | null>(
    () => (actual?.resumen ? CAPAS[actual.capa].dominio(actual.resumen) : null),
    [actual],
  )
  const colorDe = useMemo(
    () => (valor: number) => (dominio ? colorEnEscala(CAPAS[capa].colores, dominio, valor) : '#ffffff'),
    [capa, dominio],
  )
  const celdas = useMemo(() => actual?.features ?? [], [actual])

  if (!idParcela) return <Navigate to="/terreno/perimetro" replace />

  function cambiarCapa(nueva: CapaMapa) {
    setCapa(nueva)
    setElegida(null)
  }

  const sinDatos = actual !== null && actual.celdas_con_dato === 0
  const estadoCapa = actual?.estado_ingesta.estado
  const aviso = !actual
    ? t('cargando')
    : !sinDatos
      ? null
      : enCurso
        ? t('zonas_reuniendo')
        : estadoCapa === 'sin_configurar'
          ? t('zonas_no_disponible')
          : estadoCapa === 'error'
            ? t('zonas_error_reintento')
            : capa === 'ndvi'
              ? t('zonas_nubes')
              : t('zonas_sin_datos_mapa')

  return (
    <Screen>
      <BarraSuperior volverA="/terreno" derecha={actual ? <span className="ps-contexto">{numero(actual.hectareas, 2)} ha</span> : undefined} />
      <Titulo>{t('zonas_titulo')}</Titulo>

      <div className="ps-pad-16" style={{ marginTop: 14 }}>
        <div role="tablist" aria-label={t('zonas_capa_aria')} style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 4, padding: 4, borderRadius: 30, background: 'var(--hundido)' }}>
          {ORDEN.map((clave) => (
            <button key={clave} type="button" role="tab" aria-selected={capa === clave} onClick={() => cambiarCapa(clave)} className={`ps-pill ${capa === clave ? 'activo' : ''}`} style={{ borderRadius: 26, minHeight: 48 }}>
              {t(`zonas_capa_${clave}`)}
            </button>
          ))}
        </div>
      </div>

      <div className="ps-pad-16" style={{ marginTop: 12 }}>
        {perimetro ? (
          <MapaCeldas
            perimetro={perimetro}
            celdas={celdas}
            colorDe={colorDe}
            elegida={elegida ? `${elegida.properties.i},${elegida.properties.j}` : null}
            onElegir={setElegida}
          />
        ) : (
          <div className="ps-mapa" aria-hidden="true" />
        )}
      </div>

      {aviso ? (
        <p className="ps-pad ps-cuerpo" role="status" style={{ margin: '10px 0 0 0' }}>
          {aviso}
        </p>
      ) : null}
      {error ? (
        <p className="ps-pad ps-nota" role="alert" style={{ margin: '10px 0 0 0', color: 'var(--riesgo-texto)' }}>
          {error}
        </p>
      ) : null}

      {actual?.resumen && dominio ? (
        <section aria-label={t('zonas_leyenda_aria')} className="ps-pad-16" style={{ marginTop: 12 }}>
          <div className="ps-card-plana" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div aria-hidden="true" style={{ height: 14, borderRadius: 7, background: `linear-gradient(to right, ${config.colores.join(', ')})` }} />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 14, fontWeight: 700 }}>
              <span>
                {t(`zonas_bajo_${capa}`)} · {config.formato(dominio[0])}
              </span>
              <span>
                {t(`zonas_alto_${capa}`)} · {config.formato(dominio[1])}
              </span>
            </div>
            <dl style={{ margin: 0, display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 8, textAlign: 'center' }}>
              {([['zonas_minimo', actual.resumen.minimo], ['zonas_mitad', actual.resumen.mediana], ['zonas_maximo', actual.resumen.maximo]] as const).map(([etiqueta, valor]) => (
                <div key={etiqueta} style={{ display: 'flex', flexDirection: 'column-reverse' }}>
                  <dt className="ps-nota">{t(etiqueta)}</dt>
                  <dd style={{ margin: 0, fontSize: 20, fontWeight: 800 }}>{config.formato(valor)}</dd>
                </div>
              ))}
            </dl>
            <Link to="/fuentes" className="ps-nota" style={{ textDecoration: 'none' }}>
              {t('zonas_fuente_detalle', { fuente: actual.fuente, m: actual.resolucion_de_la_fuente_m })}
              {capa === 'ndvi'
                ? actual.fecha_comun
                  ? ` · ${t('zonas_imagen_del', { fecha: fechaCorta(actual.fecha_comun) })}`
                  : ` · ${t('zonas_cada_cuadro')}`
                : capa === 'hand'
                  ? ` · ${t('zonas_altura_cauce')}`
                  : ` · ${t('zonas_incluye_arboles')}`}
              {` · ${t('zonas_cuadros_con_dato', { n: actual.celdas_con_dato, total: actual.celdas })}`}
            </Link>
          </div>
        </section>
      ) : null}

      <section aria-live="polite" className="ps-pad-16" style={{ marginTop: 12 }}>
        <div className="ps-card" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {elegida ? (
            <>
              <span aria-hidden="true" style={{ width: 36, height: 36, borderRadius: 10, flexShrink: 0, border: '2px solid var(--linea)', background: elegida.properties.valor === null ? 'var(--hundido)' : colorDe(elegida.properties.valor) }} />
              <span style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                <span style={{ fontSize: 20, fontWeight: 800, lineHeight: 1.1 }}>
                  {elegida.properties.valor === null ? t('zonas_sin_dato') : `${t(`zonas_capa_${capa}`)}: ${config.formato(elegida.properties.valor)}`}
                </span>
                <span className="ps-detalle">
                  {elegida.properties.fecha ? `${t('zonas_imagen_del_cap', { fecha: fechaCorta(elegida.properties.fecha) })} · ` : ''}
                  {t('zonas_fraccion_dentro', { n: numero(elegida.properties.fraccion_dentro * 100) })}
                </span>
              </span>
            </>
          ) : (
            <span className="ps-cuerpo">{t('zonas_toca_cuadro')}</span>
          )}
        </div>
      </section>

      <div style={{ marginTop: 'auto', padding: '16px 16px 32px 16px' }}>
        <Link to="/especies" className="ps-btn">
          {t('onb_ver_que_sembrar')}
        </Link>
      </div>
    </Screen>
  )
}
