import { useEffect, useState } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { Screen, BarraSuperior, Titulo } from '../components/Screen'
import { Chip, type TonoChip } from '../components/Chip'
import { mensajeDeError, reintentarIngesta, verParcela, type EstadoIngesta, type ParcelaDetalle } from '../lib/api'
import { numero } from '../lib/formato'
import { CLASE_ORIGEN } from '../lib/fuentes'
import { usePredio } from '../state/PredioContext'
import { useI18n } from '../i18n'

// Las fuentes de ingesta_predio.py agrupadas como las entiende quien mira su predio.
const GRUPOS = [
  { titulo: 'Clima del último año', detalle: 'Temperatura y lluvia de cada día', fuentes: ['cr2met'], origenes: ['Chile'], fuente: 'CR2MET, del Centro de Ciencia del Clima y la Resiliencia (Chile)' },
  { titulo: 'Clima de estos días', detalle: 'Últimos días y pronóstico', fuentes: ['power', 'open_meteo'], origenes: ['NASA', 'Otras fuentes'], fuente: 'NASA POWER (últimos días) y Open-Meteo.com (pronóstico a 16 días)' },
  { titulo: 'Suelo', detalle: 'Acidez y agua que guarda', fuentes: ['soilgrids', 'clsoilmaps'], origenes: ['Otras fuentes', 'Chile'], fuente: 'SoilGrids, de ISRIC (acidez y textura), y CLSoilMaps, de Chile (agua que guarda)' },
  { titulo: 'Sol', detalle: 'Sol de cada mes', fuentes: ['explorador_solar'], origenes: ['NASA', 'Chile'], fuente: 'NASA POWER y Explorador Solar de Chile (respaldo)' },
  { titulo: 'Relieve', detalle: 'Altura y pendiente', fuentes: ['relieve'], origenes: ['Copernicus'], fuente: 'Modelo de elevación Copernicus GLO-30' },
  { titulo: 'Satélite', detalle: 'Verdor del campo', fuentes: ['sentinel2_nubes', 'sentinel2_ndvi', 'sentinel2_celdas'], origenes: ['Copernicus'], fuente: 'Sentinel-2, de la ESA (Copernicus)' },
  { titulo: 'Focos de calor', detalle: 'Incendios cerca de tu parcela', fuentes: ['firms'], origenes: ['NASA'], fuente: 'NASA FIRMS (satélites VIIRS)' },
] as const

type Avance = 'cargando' | 'listo' | 'fallo' | 'sin_cobertura' | 'no_disponible'

const ETIQUETA: Record<Avance, { texto: string; tono: TonoChip }> = {
  cargando: { texto: 'Cargando', tono: 'clima' },
  listo: { texto: 'Listo', tono: 'favorable' },
  fallo: { texto: 'No cargó', tono: 'riesgo' },
  sin_cobertura: { texto: 'Sin datos aquí', tono: 'precaucion' },
  no_disponible: { texto: 'No disponible', tono: 'neutro' },
}

function avanceDe(estado: EstadoIngesta, fuentes: readonly string[]): Avance {
  const propios = fuentes.map((f) => estado[f]).filter(Boolean)
  if (propios.some((e) => ['pendiente', 'en_proceso', 'sin_iniciar'].includes(e.estado))) return 'cargando'
  if (propios.some((e) => e.estado === 'error' || e.estado === 'interrumpida')) return 'fallo'
  if (propios.every((e) => e.estado === 'sin_configurar' || e.estado === 'no_aplica')) return 'no_disponible'
  if (propios.some((e) => e.detalle === 'sin_cobertura')) return 'sin_cobertura'
  return 'listo'
}

const SEGUNDOS_ENTRE_CONSULTAS = 4

export default function Preparando() {
  const { t } = useI18n()
  const [params] = useSearchParams()
  const enOnboarding = params.get('desde') === 'onboarding'
  const { idParcela } = usePredio()
  const [parcela, setParcela] = useState<ParcelaDetalle | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reintentando, setReintentando] = useState(false)

  const avances = parcela ? GRUPOS.map((g) => avanceDe(parcela.estado_ingesta, g.fuentes)) : []
  const cargando = !parcela || avances.includes('cargando')

  useEffect(() => {
    if (!idParcela || !cargando) return
    let vigente = true
    let reloj: ReturnType<typeof setTimeout> | undefined
    // La consulta siguiente se agenda cuando vuelve la anterior: mientras el servidor
    // está ocupado con la ingesta, las consultas no se apilan.
    const consultar = () =>
      verParcela(idParcela, true)
        .then((p) => {
          if (vigente) {
            setParcela(p)
            setError(null)
          }
        })
        .catch((err) => {
          if (vigente) setError(mensajeDeError(err, 'No pudimos ver cómo va. Revisa tu conexión e inténtalo de nuevo.'))
        })
        .finally(() => {
          if (vigente) reloj = setTimeout(consultar, SEGUNDOS_ENTRE_CONSULTAS * 1000)
        })
    consultar()
    return () => {
      vigente = false
      clearTimeout(reloj)
    }
  }, [idParcela, cargando])

  if (!idParcela) return <Navigate to="/terreno/perimetro" replace />

  const estado = parcela?.estado_ingesta
  const climaListo = estado ? ['completo', 'vencida'].includes(estado.cr2met.estado) && estado.cr2met.detalle === null : false
  const climaSinCobertura = estado?.cr2met.detalle === 'sin_cobertura'
  const hayFallos = avances.includes('fallo')
  const puedeReintentar = estado ? Object.values(estado).some((e) => e.reintentable) : false

  async function reintentar() {
    if (!idParcela) return
    setReintentando(true)
    try {
      const respuesta = await reintentarIngesta(idParcela)
      setParcela((previa) => (previa ? { ...previa, estado_ingesta: respuesta.estado_ingesta } : previa))
    } catch (err) {
      setError(mensajeDeError(err, 'No pudimos reintentar. Prueba otra vez en unos minutos.'))
    } finally {
      setReintentando(false)
    }
  }

  return (
    <Screen>
      <BarraSuperior volverA={enOnboarding ? '/onboarding/predio' : '/terreno'} />
      <Titulo
        sub={
          parcela
            ? `${numero(parcela.hectareas, 2)} ha${parcela.ecorregion ? ` · ${parcela.ecorregion.nombre}` : ''}`
            : undefined
        }
      >
        {cargando ? 'Preparando tu parcela' : 'Tu parcela está lista'}
      </Titulo>
      <p className="ps-pad ps-cuerpo" style={{ margin: '8px 0 0 0' }}>
        Se están reuniendo los datos de tu parcela. La primera vez tarda unos minutos.
      </p>

      <ul aria-live="polite" className="ps-pad-16" style={{ margin: '14px 0 0 0', listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 8 }}>
        {GRUPOS.map((grupo, i) => {
          const avance = avances[i] ?? 'cargando'
          return (
            <li key={grupo.titulo} className="ps-card" style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 14px' }}>
              <span style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                <span style={{ fontSize: 18, fontWeight: 800, lineHeight: 1.15 }}>{grupo.titulo}</span>
                <span className="ps-detalle">{grupo.detalle}</span>
                <span className="ps-nota" style={{ marginTop: 4 }}>Fuente: {grupo.fuente}</span>
                <span style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
                  {grupo.origenes.map((o) => (
                    <span key={o} className={`ps-chip ${CLASE_ORIGEN[o]}`}>{o}</span>
                  ))}
                </span>
              </span>
              <Chip tono={ETIQUETA[avance].tono}>{ETIQUETA[avance].texto}</Chip>
            </li>
          )
        })}
      </ul>

      {climaSinCobertura ? (
        <p className="ps-pad ps-nota" role="alert" style={{ margin: '12px 0 0 0', color: 'var(--riesgo-texto)' }}>
          Por ahora solo tenemos datos del Chile continental. Marca tu parcela otra vez, dentro de esa zona.
        </p>
      ) : null}
      {hayFallos ? (
        <div className="ps-pad-16" style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 12 }}>
          <span className="ps-nota" style={{ flex: 1 }}>
            {puedeReintentar ? 'Algunos datos no se pudieron reunir. Toca Reintentar.' : 'Algunos datos no se pudieron reunir. Prueba otra vez en unos minutos.'}
          </span>
          <button type="button" onClick={reintentar} disabled={!puedeReintentar || reintentando} className="ps-btn-secundario" style={{ padding: '0 16px', minHeight: 48 }}>
            {t('reintentar')}
          </button>
        </div>
      ) : null}
      {error ? (
        <p className="ps-pad ps-nota" role="alert" style={{ margin: '12px 0 0 0', color: 'var(--riesgo-texto)' }}>
          {error}
        </p>
      ) : null}

      <div style={{ position: 'sticky', bottom: 0, marginTop: 'auto', padding: '14px 16px 28px 16px', background: 'var(--arena)', display: 'flex', flexDirection: 'column', gap: 6 }}>
        {climaListo ? (
          <Link to={enOnboarding ? '/onboarding/meta' : '/terreno'} className="ps-btn">
            {enOnboarding ? 'Seguir con el registro' : 'Ir a Tu terreno'}
          </Link>
        ) : (
          <button type="button" disabled className="ps-btn">
            {climaSinCobertura ? 'Sin datos en este lugar' : 'Reuniendo el clima…'}
          </button>
        )}
        <p className="ps-nota" style={{ margin: '0 0 8px 0', textAlign: 'center' }}>
          {climaListo ? (enOnboarding ? 'Sigue con lo que quieres hacer ahora.' : 'Aquí ves tu parcela y lo medido en ella.') : 'Podrás seguir cuando llegue el clima.'}
        </p>
        <Link to="/terreno/zonas" className="ps-btn-secundario" style={{ minHeight: 52, display: 'flex', alignItems: 'center', justifyContent: 'center', textDecoration: 'none' }}>
          Ver el mapa de mi parcela
        </Link>
        <p className="ps-nota" style={{ margin: 0, textAlign: 'center' }}>Verdor, altura y pendiente de cada parte. Es opcional.</p>
        {climaSinCobertura ? (
          <Link to="/terreno/perimetro" className="ps-btn-texto">
            Marcar la parcela de nuevo
          </Link>
        ) : null}
      </div>
    </Screen>
  )
}
