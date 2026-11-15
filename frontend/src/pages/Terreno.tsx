import { useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { Screen, Titulo } from '../components/Screen'
import { BottomNav } from '../components/BottomNav'
import { EscenaTerreno } from '../components/EscenaTerreno'
import { MiniPerimetro } from '../components/MiniPerimetro'
import { SelectorParcelas } from '../components/SelectorParcelas'
import { Chip } from '../components/Chip'
import { SourceLink } from '../components/SourceLink'
import { PreguntaSuelo } from '../components/PreguntaSuelo'
import { IconoIncendio, IconoSiguiente, IconoUbicacion } from '../components/icons'
import { usePredio } from '../state/PredioContext'
import {
  ApiError, candidatasSiembra, guardarSuelo, mensajeDeError, verParcela,
  type DatosSitio, type ParcelaDetalle, type SueloDeclarado,
} from '../lib/api'
import { PREGUNTAS_SUELO } from '../lib/suelo'
import { comunaDeParcela, leerBorrador } from '../lib/comunas'
import { fechaCorta, nombreMes, numero } from '../lib/formato'
import { useI18n } from '../i18n'

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
  const [sinClima, setSinClima] = useState(false)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!idParcela) return
    let vigente = true
    // Al cambiar de parcela no se deja a la vista lo de la anterior mientras llega lo nuevo.
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
        setSuelo(p.suelo)
      }),
      candidatasSiembra(idParcela, { limite: 1 })
        .then((r) => vigente && setSitio(r.datos_sitio))
        .catch((err) => {
          if (err instanceof ApiError && err.status === 409) {
            if (vigente) setSinClima(true)
          } else throw err
        }),
    ])
      .catch((err) => vigente && setError(mensajeDeError(err, 'No pudimos cargar tu terreno. Revisa tu conexión e inténtalo de nuevo.')))
      .finally(() => vigente && setCargando(false))
    return () => {
      vigente = false
    }
  }, [idParcela])

  if (!idParcela) return <Navigate to="/terreno/perimetro" replace />

  function elegirSuelo(campo: keyof SueloDeclarado, valor: string | null) {
    if (!idParcela || !suelo) return
    const anterior = suelo
    setErrorSuelo(null)
    setSuelo({ ...suelo, [campo]: valor })
    guardarSuelo(idParcela, { [campo]: valor })
      .then((r) => setSuelo(r.suelo))
      .catch((err) => {
        setSuelo(anterior)
        setErrorSuelo(mensajeDeError(err, 'No pudimos guardar tu respuesta. Revisa tu conexión e inténtalo de nuevo.'))
      })
  }

  const predio = leerBorrador()
  const comuna = comunaDeParcela(idParcela)
  const subtitulo = parcela
    ? [predio.sector && comuna ? `${predio.sector}, ${comuna}` : comuna ?? (predio.sector || null),
        `${numero(parcela.hectareas, 2)} ha`,
        parcela.altitud_msnm !== null ? `${numero(parcela.altitud_msnm)} msnm` : null,
        parcela.ecorregion?.nombre].filter(Boolean).join(' · ')
    : undefined

  const masFrio = extremo(sitio?.temperatura_media_mensual ?? null, Math.min)
  const masCalido = extremo(sitio?.temperatura_media_mensual ?? null, Math.max)
  const helada = extremo(sitio?.temperatura_minima_mas_baja_mensual ?? null, Math.min)
  const sol = sitio?.ghi_mensual_kwh_m2_dia
  const solMedio = sol && sol.length ? sol.reduce((a, b) => a + b, 0) / sol.length : null
  const periodo = sitio ? `${fechaCorta(sitio.periodo_clima[0])} a ${fechaCorta(sitio.periodo_clima[1])}` : null
  const incendios = parcela?.incendios_cercanos
  const diasConFocos = incendios?.dias_con_focos ?? []
  const focoMasCercano = diasConFocos.reduce<number | null>(
    (menor, d) => (d.distancia_min_km !== null && (menor === null || d.distancia_min_km < menor) ? d.distancia_min_km : menor),
    null,
  )
  const pasadas = parcela?.curva_satelital.ventanas_con_pasada_pct

  return (
    <Screen>
      <div className="ps-topbar" style={{ paddingBottom: 0 }} />
      <Titulo sub={subtitulo}>{t('terreno_titulo')}</Titulo>
      <SelectorParcelas />

      <Link to="/terreno/zonas" className="ps-card" style={{ margin: '12px 16px 0 16px', textDecoration: 'none', color: 'var(--carbon)', display: 'flex', alignItems: 'center', gap: 12 }}>
        <span aria-hidden="true" style={{ width: 52, height: 52, borderRadius: 14, background: 'var(--menta)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          {parcela ? <MiniPerimetro perimetro={parcela.perimetro} /> : <IconoUbicacion stroke="var(--verde)" />}
        </span>
        <span style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <span style={{ fontSize: 18, fontWeight: 800, lineHeight: 1.1 }}>{t('terreno_zonas_sembrar')}</span>
          <span className="ps-detalle">{parcela ? `${numero(parcela.hectareas, 2)} ha marcadas · ` : ''}Qué tan verde, alta e inclinada está cada parte</span>
        </span>
        <IconoSiguiente stroke="var(--verde)" />
      </Link>
      <Link to="/terreno/parcelas" className="ps-btn-texto" style={{ margin: '4px 20px 0 20px', justifyContent: 'flex-start', fontSize: 15 }}>
        {t('terreno_mis_parcelas')}
      </Link>

      <div className="ps-pad-16" style={{ margin: '8px 16px 0 16px' }}>
        <EscenaTerreno etiqueta="Ilustración de un predio con casa, árboles y un paño de tierra labrada" />
      </div>

      {sinClima ? (
        <Link to="/terreno/preparando" className="ps-card-plana" style={{ margin: '8px 16px 0 16px', textDecoration: 'none', color: 'var(--carbon)', display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ flex: 1, fontSize: 16, fontWeight: 700 }}>Todavía se está reuniendo el clima de tu parcela.</span>
          <span style={{ fontSize: 16, fontWeight: 800, color: 'var(--verde)' }}>Ver avance</span>
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
          <SourceLink>Satélites de NASA (FIRMS)</SourceLink>
        </div>
        <div style={{ marginTop: 8, padding: '12px 14px', borderRadius: 16, background: 'var(--blanco)', display: 'flex', alignItems: 'center', gap: 12 }}>
          <IconoIncendio stroke={diasConFocos.length ? 'var(--riesgo-texto)' : 'var(--favorable-texto)'} />
          <span style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontSize: 17, fontWeight: 800, lineHeight: 1.15 }}>Focos de calor a menos de {numero(incendios?.radio_km ?? 10)} km</span>
            <span className="ps-detalle">
              {!incendios
                ? t('cargando')
                : !incendios.revisado
                  ? 'Todavía sin revisar'
                  : diasConFocos.length
                    ? `El más cercano a ${numero(focoMasCercano, 1)} km · último el ${fechaCorta(diasConFocos[diasConFocos.length - 1].fecha)}`
                    : `Revisado del ${fechaCorta(incendios.revisado[0])} al ${fechaCorta(incendios.revisado[1])}`}
            </span>
          </span>
          {incendios?.revisado ? (
            <Chip tono={diasConFocos.length ? 'riesgo' : 'favorable'}>
              {diasConFocos.length ? `${diasConFocos.length} ${diasConFocos.length === 1 ? 'día' : 'días'}` : 'Sin focos'}
            </Chip>
          ) : null}
        </div>
        <p className="ps-nota" style={{ margin: '8px 4px 0 4px' }}>
          Todavía no avisamos de deslizamientos ni inundaciones. Para eso, sigue los avisos de SENAPRED.
        </p>
      </section>

      <section aria-labelledby="medido" className="ps-pad-16" style={{ marginTop: 16 }}>
        <h2 id="medido" style={{ padding: '0 4px 8px 4px', margin: 0, fontSize: 14, fontWeight: 800, letterSpacing: '.04em', textTransform: 'uppercase', color: 'var(--texto-tenue)' }}>
          {t('terreno_medido')}
        </h2>
        <div className="ps-grid-2">
          <div className="ps-card" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span className="ps-contexto">Temperatura</span>
            <span style={{ fontSize: 22, fontWeight: 800, lineHeight: 1.05 }}>
              {masFrio && masCalido ? `${numero(masFrio.valor, 1)}° a ${numero(masCalido.valor, 1)}°` : '—'}
            </span>
            <span style={{ fontSize: 15, fontWeight: 700 }}>
              {masFrio && masCalido ? `De ${nombreMes(masFrio.mes)} (el más frío) a ${nombreMes(masCalido.mes)} (el más cálido)` : 'Sin dato todavía'}
            </span>
            <SourceLink>CR2MET{periodo ? ` · ${periodo}` : ''}</SourceLink>
          </div>
          <div className="ps-card" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span className="ps-contexto">Lluvia del año</span>
            <span style={{ fontSize: 22, fontWeight: 800, lineHeight: 1.05 }}>{sitio?.lluvia_anual_mm != null ? `${numero(sitio.lluvia_anual_mm)} mm` : '—'}</span>
            <span style={{ fontSize: 15, fontWeight: 700 }}>
              {helada ? `Noche más fría: ${numero(helada.valor, 1)}° en ${nombreMes(helada.mes)}` : 'Sin dato todavía'}
            </span>
            <SourceLink>CR2MET{periodo ? ` · ${periodo}` : ''}</SourceLink>
          </div>
          <div className="ps-card" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span className="ps-contexto">Suelo</span>
            <span style={{ fontSize: 22, fontWeight: 800 }}>{sitio?.ph != null ? `pH ${numero(sitio.ph, 1)} · ${sitio.ph < 6.5 ? 'ácido' : sitio.ph <= 7.5 ? 'neutro' : 'alcalino'}` : '—'}</span>
            <span style={{ fontSize: 15, fontWeight: 700 }}>
              {sitio?.agua_disponible_suelo_mm != null ? `Guarda ${numero(sitio.agua_disponible_suelo_mm)} litros de agua por m²` : 'Agua del suelo sin dato'}
            </span>
            <SourceLink>SoilGrids · CLSoilMaps</SourceLink>
          </div>
          <div className="ps-card" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span className="ps-contexto">Sol que llega cada día</span>
            <span style={{ fontSize: 22, fontWeight: 800 }}>{solMedio !== null ? `${numero(solMedio, 1)} h de sol pleno` : '—'}</span>
            <span style={{ fontSize: 15, fontWeight: 700 }}>
              {pasadas != null ? `El satélite ve tu parcela sin nubes el ${numero(pasadas)}% de las veces` : 'Promedio del año'}
            </span>
            <SourceLink>{sitio?.fuente_radiacion ?? 'Radiación solar'} · Sentinel-2 (Copernicus)</SourceLink>
          </div>
        </div>
        {sitio && sitio.altitud_m != null && Math.abs(sitio.correccion_temperatura_c) >= 0.3 ? (
          <p className="ps-nota" style={{ margin: '8px 4px 0 4px' }}>
            La temperatura está ajustada a la altura de tu parcela ({numero(sitio.altitud_m)} m): es {numero(Math.abs(sitio.correccion_temperatura_c), 1)}° {sitio.correccion_temperatura_c > 0 ? 'más cálida' : 'más fría'} que el promedio de su zona de 5 km.
          </p>
        ) : null}
        {cargando ? <p className="ps-nota" style={{ marginTop: 8 }}>{t('cargando')}</p> : null}
      </section>

      {suelo ? (
        <section aria-labelledby="suelo" className="ps-pad-16" style={{ marginTop: 16 }}>
          <h2 id="suelo" style={{ padding: '0 4px 8px 4px', margin: 0, fontSize: 14, fontWeight: 800, letterSpacing: '.04em', textTransform: 'uppercase', color: 'var(--texto-tenue)' }}>
            Cuéntanos de tu suelo
          </h2>
          <div className="ps-card" style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            <p className="ps-cuerpo" style={{ margin: 0 }}>
              Esto no se ve desde el satélite. Responde lo que sepas: mejora la lista de qué sembrar. Toca una respuesta otra vez para quitarla.
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

      <BottomNav />
    </Screen>
  )
}
