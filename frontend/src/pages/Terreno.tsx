import { useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { Screen, BarraSuperior, Titulo } from '../components/Screen'
import { MoonStrip } from '../components/MoonStrip'
import { Chip } from '../components/Chip'
import { SourceLink } from '../components/SourceLink'
import { IconoIncendio, IconoSiguiente, IconoUbicacion } from '../components/icons'
import { usePredio } from '../state/PredioContext'
import { ApiError, candidatasSiembra, mensajeDeError, verParcela, type DatosSitio, type ParcelaDetalle } from '../lib/api'
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
  const [sinClima, setSinClima] = useState(false)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!idParcela) return
    let vigente = true
    Promise.all([
      verParcela(idParcela).then((p) => vigente && setParcela(p)),
      candidatasSiembra(idParcela)
        .then((r) => vigente && setSitio(r.datos_sitio))
        .catch((err) => {
          if (err instanceof ApiError && err.status === 409) {
            if (vigente) setSinClima(true)
          } else throw err
        }),
    ])
      .catch((err) => vigente && setError(mensajeDeError(err, 'No se pudo cargar tu terreno.')))
      .finally(() => vigente && setCargando(false))
    return () => {
      vigente = false
    }
  }, [idParcela])

  if (!idParcela) return <Navigate to="/terreno/perimetro" replace />

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
      <BarraSuperior volverA="/planificar" />
      <Titulo
        sub={
          parcela
            ? [`${numero(parcela.hectareas, 2)} ha`, parcela.altitud_msnm !== null ? `${numero(parcela.altitud_msnm)} msnm` : null, parcela.ecorregion?.nombre]
                .filter(Boolean)
                .join(' · ')
            : undefined
        }
      >
        {t('terreno_titulo')}
      </Titulo>

      <Link to="/terreno/zonas" className="ps-card" style={{ margin: '12px 16px 0 16px', textDecoration: 'none', color: 'var(--carbon)', display: 'flex', alignItems: 'center', gap: 12 }}>
        <span aria-hidden="true" style={{ width: 40, height: 40, borderRadius: 12, background: 'var(--menta)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          <IconoUbicacion stroke="var(--verde)" />
        </span>
        <span style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <span style={{ fontSize: 18, fontWeight: 800, lineHeight: 1.1 }}>{t('terreno_zonas_sembrar')}</span>
          <span className="ps-detalle">Verdor, altura y pendiente por celda</span>
        </span>
        <IconoSiguiente stroke="var(--verde)" />
      </Link>
      <Link to="/terreno/perimetro" className="ps-btn-texto" style={{ margin: '4px 20px 0 20px', justifyContent: 'flex-start', fontSize: 15 }}>
        {t('terreno_cambiar_perimetro')}
      </Link>

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
          <SourceLink>NASA FIRMS</SourceLink>
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
          Deslizamiento e inundación todavía no tienen una fuente conectada.
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
              {masFrio && masCalido ? `Media de ${nombreMes(masFrio.mes)} y de ${nombreMes(masCalido.mes)}` : 'Sin dato todavía'}
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
            <span style={{ fontSize: 22, fontWeight: 800 }}>{sitio?.ph != null ? `pH ${numero(sitio.ph, 1)}` : '—'}</span>
            <span style={{ fontSize: 15, fontWeight: 700 }}>
              {sitio?.agua_disponible_suelo_mm != null ? `Guarda ${numero(sitio.agua_disponible_suelo_mm)} mm de agua` : 'Agua del suelo sin dato'}
            </span>
            <SourceLink>SoilGrids · CLSoilMaps</SourceLink>
          </div>
          <div className="ps-card" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span className="ps-contexto">Sol y satélite</span>
            <span style={{ fontSize: 22, fontWeight: 800 }}>{solMedio !== null ? `${numero(solMedio, 1)} kWh/m²` : '—'}</span>
            <span style={{ fontSize: 15, fontWeight: 700 }}>
              {pasadas != null ? `Cielo despejado para el satélite: ${numero(pasadas)}% de las veces` : 'Radiación media por día'}
            </span>
            <SourceLink>Explorador Solar · Sentinel-2</SourceLink>
          </div>
        </div>
        {cargando ? <p className="ps-nota" style={{ marginTop: 8 }}>{t('cargando')}</p> : null}
      </section>

      <MoonStrip />

      <div style={{ marginTop: 'auto', padding: '16px 16px 32px 16px' }}>
        <Link to="/especies" className="ps-btn">
          {t('onb_ver_que_sembrar')}
        </Link>
      </div>
    </Screen>
  )
}
