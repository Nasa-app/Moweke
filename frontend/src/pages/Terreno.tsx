import { useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { Screen, Titulo } from '../components/Screen'
import { MapaCeldas } from '../components/Mapa'
import { MiniPerimetro } from '../components/MiniPerimetro'
import { SelectorParcelas } from '../components/SelectorParcelas'
import { Chip } from '../components/Chip'
import { SourceLink } from '../components/SourceLink'
import { PreguntaSuelo } from '../components/PreguntaSuelo'
import { IconoIncendio, IconoSiguiente, IconoUbicacion } from '../components/icons'
import { usePredio } from '../state/PredioContext'
import {
  ApiError, guardarNombre, guardarSuelo, sitioParcela, mensajeDeError, verParcela,
  type DatosSitio, type ParcelaDetalle, type SueloDeclarado,
} from '../lib/api'
import { PREGUNTAS_SUELO } from '../lib/suelo'
import { comunaDeParcela, leerBorrador } from '../lib/comunas'
import { fechaCorta, nombreMes, numero } from '../lib/formato'
import { useI18n } from '../i18n'
import { tr } from '../i18n/dictionary'

const SIN_CELDAS: never[] = []
const SIN_COLOR = () => '#000000'
const SIN_ELEGIR = () => undefined

function extremo(serie: number[] | null, elegir: (...valores: number[]) => number): { valor: number; mes: number } | null {
  if (!serie || serie.length === 0) return null
  const valor = elegir(...serie)
  return { valor, mes: serie.indexOf(valor) }
}

export default function Terreno() {
  const { t } = useI18n()
  const { idParcela } = usePredio()
  const [parcela, setParcela] = useState<ParcelaDetalle | null>(null)
  const [sitio, setSitio] = useState<DatosSitio | null>(null)
  const [suelo, setSuelo] = useState<SueloDeclarado | null>(null)
  const [errorSuelo, setErrorSuelo] = useState<string | null>(null)
  const [nombre, setNombre] = useState('')
  const [nombreGuardado, setNombreGuardado] = useState(false)
  const [errorNombre, setErrorNombre] = useState<string | null>(null)
  const [sinClima, setSinClima] = useState(false)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!idParcela) return
    let vigente = true
    // Al cambiar de predio no se deja a la vista lo de la anterior mientras llega lo nuevo.
    setParcela(null)
    setSitio(null)
    setSuelo(null)
    setSinClima(false)
    setError(null)
    setCargando(true)
    Promise.all([
      verParcela(idParcela).then((p) => {
        if (!vigente) return
        setParcela(p)
        setNombre(p.nombre ?? '')
        setNombreGuardado(false)
        setSuelo(p.suelo)
      }),
      sitioParcela(idParcela)
        .then((r) => vigente && setSitio(r.datos_sitio))
        .catch((err) => {
          if (err instanceof ApiError && err.status === 409) {
            if (vigente) setSinClima(true)
          } else throw err
        }),
    ])
      .catch((err) => vigente && setError(mensajeDeError(err, tr('terreno_error_cargar'))))
      .finally(() => vigente && setCargando(false))
    return () => {
      vigente = false
    }
  }, [idParcela])

  if (!idParcela) return <Navigate to="/terreno/perimetro" replace />

  function enviarNombre(e: React.FormEvent) {
    e.preventDefault()
    if (!idParcela) return
    setErrorNombre(null)
    setNombreGuardado(false)
    guardarNombre(idParcela, nombre)
      .then((r) => {
        setNombre(r.nombre ?? '')
        setNombreGuardado(true)
      })
      .catch((err) => setErrorNombre(mensajeDeError(err, tr('terreno_error_guardar'))))
  }

  function elegirSuelo(campo: keyof SueloDeclarado, valor: string | null) {
    if (!idParcela || !suelo) return
    const anterior = suelo
    setErrorSuelo(null)
    setSuelo({ ...suelo, [campo]: valor })
    guardarSuelo(idParcela, { [campo]: valor })
      .then((r) => setSuelo(r.suelo))
      .catch((err) => {
        setSuelo(anterior)
        setErrorSuelo(mensajeDeError(err, tr('terreno_error_guardar')))
      })
  }

  const predio = leerBorrador()
  const comuna = comunaDeParcela(idParcela)
  const referencia = parcela ? [parcela.region, parcela.pais].filter(Boolean).join(', ') : ''
  const subtitulo = parcela
    ? [referencia || (predio.sector && comuna ? `${predio.sector}, ${comuna}` : comuna ?? (predio.sector || null)),
        t('terreno_ha', { n: numero(parcela.hectareas, 2) }),
        parcela.altitud_msnm !== null ? t('terreno_msnm', { n: numero(parcela.altitud_msnm) }) : null,
        parcela.ecorregion?.nombre].filter(Boolean).join(' · ')
    : undefined

  const masFrio = extremo(sitio?.temperatura_media_mensual ?? null, Math.min)
  const masCalido = extremo(sitio?.temperatura_media_mensual ?? null, Math.max)
  const helada = extremo(sitio?.temperatura_minima_mas_baja_mensual ?? null, Math.min)
  const sol = sitio?.ghi_mensual_kwh_m2_dia
  const solMedio = sol && sol.length ? sol.reduce((a, b) => a + b, 0) / sol.length : null
  const periodo = sitio ? t('terreno_periodo', { desde: fechaCorta(sitio.periodo_clima[0]), hasta: fechaCorta(sitio.periodo_clima[1]) }) : null
  const incendios = parcela?.incendios_cercanos
  const diasConFocos = incendios?.dias_con_focos ?? []
  const focoMasCercano = diasConFocos.reduce<number | null>(
    (menor, d) => (d.distancia_min_km !== null && (menor === null || d.distancia_min_km < menor) ? d.distancia_min_km : menor),
    null,
  )
  const pasadas = parcela?.curva_satelital.ventanas_con_pasada_pct
  const cauce = parcela?.cercania_cauce

  return (
    <Screen>
      <div className="ps-topbar" style={{ paddingBottom: 0 }} />
      <Titulo sub={subtitulo}>{t('terreno_titulo')}</Titulo>
      <SelectorParcelas />

      {parcela ? (
        <form onSubmit={enviarNombre} className="ps-pad-16" style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <label htmlFor="nombre-predio" style={{ fontSize: 16, fontWeight: 700, padding: '0 4px' }}>{t('terreno_nombre')}</label>
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              id="nombre-predio"
              type="text"
              value={nombre}
              maxLength={60}
              placeholder={t('terreno_nombre_ejemplo')}
              onChange={(e) => {
                setNombre(e.target.value)
                setNombreGuardado(false)
              }}
              style={{ flex: 1, minWidth: 0, minHeight: 52, padding: '0 14px', borderRadius: 16, border: '2px solid var(--borde-control)', background: '#fff', color: 'var(--carbon)', font: "700 17px 'Alegreya Sans', sans-serif" }}
            />
            <button type="submit" className="ps-btn-secundario" style={{ padding: '0 14px', minHeight: 52 }} disabled={nombre.trim() === (parcela.nombre ?? '')}>
              {t('terreno_nombre_guardar')}
            </button>
          </div>
          {nombreGuardado ? <span className="ps-nota" role="status" style={{ padding: '0 4px' }}>{t('terreno_nombre_guardado')}</span> : null}
          {errorNombre ? <span className="ps-nota" role="alert" style={{ padding: '0 4px', color: 'var(--riesgo-texto)' }}>{errorNombre}</span> : null}
          {referencia ? <SourceLink>{t('terreno_ubicacion_osm')}</SourceLink> : null}
        </form>
      ) : null}

      <Link to="/terreno/zonas" className="ps-card" style={{ margin: '12px 16px 0 16px', textDecoration: 'none', color: 'var(--carbon)', display: 'flex', alignItems: 'center', gap: 12 }}>
        <span aria-hidden="true" style={{ width: 52, height: 52, borderRadius: 14, background: 'var(--menta)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          {parcela ? <MiniPerimetro perimetro={parcela.perimetro} /> : <IconoUbicacion stroke="var(--verde)" />}
        </span>
        <span style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <span style={{ fontSize: 18, fontWeight: 800, lineHeight: 1.1 }}>{t('terreno_zonas_sembrar')}</span>
          <span className="ps-detalle">{parcela ? t('terreno_ha_marcadas', { n: numero(parcela.hectareas, 2) }) : ''}{t('terreno_zonas_detalle')}</span>
        </span>
        <IconoSiguiente stroke="var(--verde)" />
      </Link>
      <Link to="/terreno/parcelas" className="ps-btn-texto" style={{ margin: '4px 20px 0 20px', justifyContent: 'flex-start', fontSize: 15 }}>
        {t('terreno_mis_parcelas')}
      </Link>

      <div className="ps-pad-16" style={{ margin: '8px 16px 0 16px' }}>
        {parcela ? (
          <MapaCeldas perimetro={parcela.perimetro} celdas={SIN_CELDAS} colorDe={SIN_COLOR} elegida={null} onElegir={SIN_ELEGIR} etiqueta={t('terreno_escena_aria')} />
        ) : (
          <div className="ps-mapa" aria-hidden="true" />
        )}
      </div>

      {sinClima ? (
        <Link to="/terreno/preparando" className="ps-card-plana" style={{ margin: '8px 16px 0 16px', textDecoration: 'none', color: 'var(--carbon)', display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ flex: 1, fontSize: 16, fontWeight: 700 }}>{t('inicio_reuniendo_clima')}</span>
          <span style={{ fontSize: 16, fontWeight: 800, color: 'var(--verde)' }}>{t('inicio_ver_avance')}</span>
        </Link>
      ) : null}
      {error ? (
        <p className="ps-pad ps-nota" role="alert" style={{ margin: '8px 0 0 0', color: 'var(--riesgo-texto)' }}>
          {error}
        </p>
      ) : null}

      <section aria-labelledby="riesgos" style={{ margin: '12px 16px 0 16px', padding: 12, borderRadius: 20, background: 'var(--hundido)' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', padding: '0 4px' }}>
          <h2 id="riesgos" className="ps-h2">
            {t('terreno_riesgos')}
          </h2>
          <SourceLink>{t('terreno_fuente_firms')}</SourceLink>
        </div>
        <div style={{ marginTop: 8, padding: '12px 14px', borderRadius: 16, background: 'var(--blanco)', display: 'flex', alignItems: 'center', gap: 12 }}>
          <IconoIncendio stroke={diasConFocos.length ? 'var(--riesgo-texto)' : 'var(--favorable-texto)'} />
          <span style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontSize: 17, fontWeight: 800, lineHeight: 1.15 }}>{t('terreno_focos_radio', { km: numero(incendios?.radio_km ?? 10) })}</span>
            <span className="ps-detalle">
              {!incendios
                ? t('cargando')
                : !incendios.revisado
                  ? t('terreno_sin_revisar')
                  : diasConFocos.length
                    ? t('terreno_foco_cercano', { km: numero(focoMasCercano, 1), fecha: fechaCorta(diasConFocos[diasConFocos.length - 1].fecha) })
                    : t('terreno_revisado', { desde: fechaCorta(incendios.revisado[0]), hasta: fechaCorta(incendios.revisado[1]) })}
            </span>
          </span>
          {incendios?.revisado ? (
            <Chip tono={diasConFocos.length ? 'riesgo' : 'favorable'}>
              {diasConFocos.length ? t(diasConFocos.length === 1 ? 'inicio_dia_uno' : 'inicio_dia_otros', { n: diasConFocos.length }) : t('terreno_sin_focos')}
            </Chip>
          ) : null}
        </div>
        <div style={{ marginTop: 8, padding: '12px 14px', borderRadius: 16, background: 'var(--blanco)', display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontSize: 17, fontWeight: 800, lineHeight: 1.15 }}>{t('terreno_cauce_titulo')}</span>
            <span className="ps-detalle">
              {!cauce
                ? t('cargando')
                : cauce.clase === null
                  ? t('terreno_sin_calcular')
                  : cauce.clase === 'lejos'
                    ? t('terreno_cauce_lejos', { m: numero(cauce.umbrales_m[1]) })
                    : t('terreno_cauce_parte', { pct: numero(Math.round((cauce.clase === 'muy_cerca' ? cauce.parte_muy_cerca : cauce.parte_cerca)! * 100)), m: numero(cauce.umbrales_m[cauce.clase === 'muy_cerca' ? 0 : 1]) })}
            </span>
          </span>
          {cauce?.clase ? (
            <Chip tono={cauce.clase === 'muy_cerca' ? 'riesgo' : cauce.clase === 'cerca' ? 'precaucion' : 'favorable'}>
              {cauce.clase === 'muy_cerca' ? t('terreno_cauce_muy_cerca') : cauce.clase === 'cerca' ? t('terreno_cauce_cerca') : t('terreno_cauce_lejos_chip')}
            </Chip>
          ) : null}
        </div>
        <p className="ps-nota" style={{ margin: '8px 4px 0 4px' }}>
          {t('terreno_cauce_nota')}
        </p>
      </section>

      <section aria-labelledby="medido" className="ps-pad-16" style={{ marginTop: 16 }}>
        <h2 id="medido" style={{ padding: '0 4px 8px 4px', margin: 0, fontSize: 14, fontWeight: 800, letterSpacing: '.04em', textTransform: 'uppercase', color: 'var(--texto-tenue)' }}>
          {t('terreno_medido')}
        </h2>
        <div className="ps-grid-2">
          <div className="ps-card" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span className="ps-contexto">{t('terreno_temperatura')}</span>
            <span style={{ fontSize: 22, fontWeight: 800, lineHeight: 1.05 }}>
              {masFrio && masCalido ? t('terreno_periodo', { desde: `${numero(masFrio.valor, 1)}°`, hasta: `${numero(masCalido.valor, 1)}°` }) : '—'}
            </span>
            <span style={{ fontSize: 15, fontWeight: 700 }}>
              {masFrio && masCalido ? t('terreno_temp_rango', { frio: nombreMes(masFrio.mes), calido: nombreMes(masCalido.mes) }) : t('terreno_sin_dato')}
            </span>
            <SourceLink>CR2MET{periodo ? ` · ${periodo}` : ''}</SourceLink>
          </div>
          <div className="ps-card" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span className="ps-contexto">{t('terreno_lluvia_anio')}</span>
            <span style={{ fontSize: 22, fontWeight: 800, lineHeight: 1.05 }}>{sitio?.lluvia_anual_mm != null ? `${numero(sitio.lluvia_anual_mm)} mm` : '—'}</span>
            <span style={{ fontSize: 15, fontWeight: 700 }}>
              {helada ? t('terreno_noche_fria', { t: numero(helada.valor, 1), mes: nombreMes(helada.mes) }) : t('terreno_sin_dato')}
            </span>
            <SourceLink>CR2MET{periodo ? ` · ${periodo}` : ''}</SourceLink>
          </div>
          <div className="ps-card" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span className="ps-contexto">{t('terreno_suelo')}</span>
            <span style={{ fontSize: 22, fontWeight: 800 }}>{sitio?.ph != null ? t('terreno_ph', { n: numero(sitio.ph, 1), tipo: t(sitio.ph < 6.5 ? 'terreno_ph_acido' : sitio.ph <= 7.5 ? 'terreno_ph_neutro' : 'terreno_ph_alcalino') }) : '—'}</span>
            <span style={{ fontSize: 15, fontWeight: 700 }}>
              {sitio?.agua_disponible_suelo_mm != null
                ? t(sitio.fuente_agua_suelo === 'estimado_textura' ? 'terreno_agua_suelo_estimada' : 'terreno_agua_suelo', { n: numero(sitio.agua_disponible_suelo_mm) })
                : t('terreno_agua_suelo_sin')}
            </span>
            <SourceLink>SoilGrids · CLSoilMaps</SourceLink>
          </div>
          <div className="ps-card" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span className="ps-contexto">{t('terreno_sol_dia')}</span>
            <span style={{ fontSize: 22, fontWeight: 800 }}>{solMedio !== null ? t('terreno_sol_horas', { n: numero(solMedio, 1) }) : '—'}</span>
            <span style={{ fontSize: 15, fontWeight: 700 }}>
              {pasadas != null ? t('terreno_sol_nubes', { n: numero(pasadas) }) : t('terreno_promedio_anio')}
            </span>
            <SourceLink>{sitio?.fuente_radiacion ?? t('terreno_radiacion')} · Sentinel-2 (Copernicus)</SourceLink>
          </div>
        </div>
        {sitio && sitio.altitud_m != null && Math.abs(sitio.correccion_temperatura_c) >= 0.3 ? (
          <p className="ps-nota" style={{ margin: '8px 4px 0 4px' }}>
            {t(sitio.correccion_temperatura_c > 0 ? 'terreno_ajuste_calida' : 'terreno_ajuste_fria', { alt: numero(sitio.altitud_m), dif: numero(Math.abs(sitio.correccion_temperatura_c), 1) })}
          </p>
        ) : null}
        {sitio?.fuente_clima === 'power' ? (
          <p className="ps-nota" style={{ margin: '8px 4px 0 4px' }}>{t('terreno_clima_global')}</p>
        ) : null}
        {sitio?.fuente_clima === 'power_daymet' ? (
          <p className="ps-nota" style={{ margin: '8px 4px 0 4px' }}>{t('terreno_clima_daymet')}</p>
        ) : null}
        {cargando ? <p className="ps-nota" style={{ marginTop: 8 }}>{t('cargando')}</p> : null}
      </section>

      {suelo ? (
        <section aria-labelledby="suelo" className="ps-pad-16" style={{ marginTop: 16 }}>
          <h2 id="suelo" style={{ padding: '0 4px 8px 4px', margin: 0, fontSize: 14, fontWeight: 800, letterSpacing: '.04em', textTransform: 'uppercase', color: 'var(--texto-tenue)' }}>
            {t('terreno_suelo_titulo')}
          </h2>
          <div className="ps-card" style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            <p className="ps-cuerpo" style={{ margin: 0 }}>
              {t('terreno_suelo_intro')}
            </p>
            {PREGUNTAS_SUELO.map((p) => (
              <PreguntaSuelo key={p.campo} pregunta={p.pregunta} ayuda={p.ayuda} opciones={p.opciones} valor={suelo[p.campo]} onElegir={(v) => elegirSuelo(p.campo, v)} />
            ))}
            {errorSuelo ? (
              <p className="ps-nota" role="alert" style={{ margin: 0, color: 'var(--riesgo-texto)' }}>
                {errorSuelo}
              </p>
            ) : null}
          </div>
        </section>
      ) : null}

      <div style={{ marginTop: 'auto', padding: '16px 16px 32px 16px' }}>
        <Link to="/especies" className="ps-btn">
          {t('onb_ver_que_sembrar')}
        </Link>
      </div>
    </Screen>
  )
}
