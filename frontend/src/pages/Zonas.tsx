import { useEffect, useMemo, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { Screen, BarraSuperior, Titulo } from '../components/Screen'
import { MapaCeldas } from '../components/Mapa'
import { mapaParcela, mensajeDeError, verParcela, type CapaMapa, type CeldaMapa, type MapaPredio, type Poligono } from '../lib/api'
import { fechaCorta, numero } from '../lib/formato'
import { usePredio } from '../state/PredioContext'
import { useI18n } from '../i18n'

// Cada capa de GET /api/parcelas/{id}/mapa: cómo se nombra, con qué colores (los de
// tokens.css) y entre qué valores se reparte la escala. El verdor y la pendiente usan una
// escala fija, para que un color signifique lo mismo en cualquier parcela; la altura, la
// del propio predio, porque lo que importa es qué parte queda más alta.
const CAPAS: Record<CapaMapa, {
  nombre: string
  colores: string[]
  dominio: (resumen: { minimo: number; maximo: number }) => [number, number]
  formato: (valor: number) => string
  bajo: string
  alto: string
}> = {
  ndvi: {
    nombre: 'Verdor',
    colores: ['#d9cbb0', '#d9a85b', '#829e30', '#3f611c'],
    dominio: () => [0.1, 0.9],
    formato: (v) => numero(v, 2),
    bajo: 'Suelo o pasto seco',
    alto: 'Vegetación vigorosa',
  },
  altitud: {
    nombre: 'Altura',
    colores: ['#eef4d9', '#d9a85b', '#8e4b2c'],
    dominio: (r) => [r.minimo, Math.max(r.maximo, r.minimo + 1)],
    formato: (v) => `${numero(v)} m`,
    bajo: 'Más bajo',
    alto: 'Más alto',
  },
  pendiente: {
    nombre: 'Pendiente',
    colores: ['#617f26', '#d9a85b', '#a9542f'],
    dominio: () => [0, 30],
    formato: (v) => `${numero(v, 1)} %`,
    bajo: 'Plano',
    alto: 'Muy inclinado',
  },
}
const ORDEN: CapaMapa[] = ['ndvi', 'altitud', 'pendiente']
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
      .catch((err) => setError(mensajeDeError(err, 'No pudimos cargar tu parcela. Revisa tu conexión e inténtalo de nuevo.')))
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
          if (vigente) setError(mensajeDeError(err, 'No pudimos cargar el mapa. Revisa tu conexión e inténtalo de nuevo.'))
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
        ? 'Estamos reuniendo estos datos. El mapa se completa solo cuando estén listos.'
        : estadoCapa === 'sin_configurar'
          ? 'Este mapa todavía no está disponible.'
          : estadoCapa === 'error'
            ? 'No pudimos cargar este mapa. Volvemos a intentarlo en unos minutos.'
            : capa === 'ndvi'
              ? 'Hubo muchas nubes en los últimos meses y el satélite no pudo ver tu parcela. Vuelve a mirar en unos días.'
              : 'No hay datos de este mapa para tu parcela.'

  return (
    <Screen>
      <BarraSuperior volverA="/terreno" derecha={actual ? <span className="ps-contexto">{numero(actual.hectareas, 2)} ha</span> : undefined} />
      <Titulo>{t('zonas_titulo')}</Titulo>

      <div className="ps-pad-16" style={{ marginTop: 14 }}>
        <div role="tablist" aria-label="Capa del mapa" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 4, padding: 4, borderRadius: 30, background: 'var(--hundido)' }}>
          {ORDEN.map((clave) => (
            <button key={clave} type="button" role="tab" aria-selected={capa === clave} onClick={() => cambiarCapa(clave)} className={`ps-pill ${capa === clave ? 'activo' : ''}`} style={{ borderRadius: 26, minHeight: 48 }}>
              {CAPAS[clave].nombre}
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
        <section aria-label="Leyenda" className="ps-pad-16" style={{ marginTop: 12 }}>
          <div className="ps-card-plana" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div aria-hidden="true" style={{ height: 14, borderRadius: 7, background: `linear-gradient(to right, ${config.colores.join(', ')})` }} />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 14, fontWeight: 700 }}>
              <span>
                {config.bajo} · {config.formato(dominio[0])}
              </span>
              <span>
                {config.alto} · {config.formato(dominio[1])}
              </span>
            </div>
            <dl style={{ margin: 0, display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 8, textAlign: 'center' }}>
              {([['Mínimo', actual.resumen.minimo], ['Mitad', actual.resumen.mediana], ['Máximo', actual.resumen.maximo]] as const).map(([etiqueta, valor]) => (
                <div key={etiqueta} style={{ display: 'flex', flexDirection: 'column-reverse' }}>
                  <dt className="ps-nota">{etiqueta}</dt>
                  <dd style={{ margin: 0, fontSize: 20, fontWeight: 800 }}>{config.formato(valor)}</dd>
                </div>
              ))}
            </dl>
            <Link to="/fuentes" className="ps-nota" style={{ textDecoration: 'none' }}>
              {actual.fuente} · detalle de {actual.resolucion_de_la_fuente_m} m
              {capa === 'ndvi'
                ? actual.fecha_comun
                  ? ` · imagen del ${fechaCorta(actual.fecha_comun)}`
                  : ' · cada cuadro con su última foto sin nubes'
                : ' · incluye árboles y construcciones'}
              {` · ${actual.celdas_con_dato} de ${actual.celdas} cuadros con dato`}
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
                  {elegida.properties.valor === null ? 'Sin dato' : `${config.nombre}: ${config.formato(elegida.properties.valor)}`}
                </span>
                <span className="ps-detalle">
                  {elegida.properties.fecha ? `Imagen del ${fechaCorta(elegida.properties.fecha)} · ` : ''}
                  {numero(elegida.properties.fraccion_dentro * 100)}% del cuadro dentro de tu parcela
                </span>
              </span>
            </>
          ) : (
            <span className="ps-cuerpo">Toca un cuadro del mapa para ver su valor.</span>
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
