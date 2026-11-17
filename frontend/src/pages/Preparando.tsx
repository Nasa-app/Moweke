import { useEffect, useState } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { Screen, BarraSuperior, Titulo } from '../components/Screen'
import { Chip, type TonoChip } from '../components/Chip'
import { mensajeDeError, reintentarIngesta, verParcela, type EstadoIngesta, type ParcelaDetalle } from '../lib/api'
import { numero } from '../lib/formato'
import { CLASE_ORIGEN, type Origen } from '../lib/fuentes'
import { usePredio } from '../state/PredioContext'
import { useI18n } from '../i18n'
import { tr } from '../i18n/dictionary'

// Las fuentes de ingesta_predio.py agrupadas como las entiende quien mira su predio.
const GRUPOS = [
  { clave: 'clima_ano', fuentes: ['cr2met'], origenes: ['Chile'] },
  { clave: 'clima_dias', fuentes: ['power', 'open_meteo'], origenes: ['NASA', 'Otras fuentes'] },
  { clave: 'suelo', fuentes: ['soilgrids', 'clsoilmaps'], origenes: ['Otras fuentes', 'Chile'] },
  { clave: 'sol', fuentes: ['explorador_solar'], origenes: ['NASA', 'Chile'] },
  { clave: 'relieve', fuentes: ['relieve'], origenes: ['Copernicus'] },
  { clave: 'cauces', fuentes: ['inundacion'], origenes: ['NASA'] },
  { clave: 'satelite', fuentes: ['sentinel2_nubes', 'sentinel2_ndvi', 'hls_ndvi', 'sentinel2_celdas'], origenes: ['Copernicus', 'NASA'] },
  { clave: 'focos', fuentes: ['firms'], origenes: ['NASA'] },
] as const

type Avance = 'cargando' | 'listo' | 'fallo' | 'sin_cobertura' | 'no_disponible'

const ETIQUETA: Record<Avance, { texto: string; tono: TonoChip }> = {
  cargando: { texto: 'preparando_estado_cargando', tono: 'clima' },
  listo: { texto: 'preparando_estado_listo', tono: 'favorable' },
  fallo: { texto: 'preparando_estado_fallo', tono: 'riesgo' },
  sin_cobertura: { texto: 'preparando_estado_sin_cobertura', tono: 'precaucion' },
  no_disponible: { texto: 'preparando_estado_no_disponible', tono: 'neutro' },
}

const CLAVE_ORIGEN: Record<Origen, string> = {
  NASA: 'origen_nasa',
  Copernicus: 'origen_copernicus',
  Chile: 'origen_chile',
  'Otras fuentes': 'origen_otras',
  Comunidad: 'origen_comunidad',
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
          if (vigente) setError(mensajeDeError(err, tr('preparando_error_ver')))
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
  const climaConDaymet = estado ? ['completo', 'vencida'].includes(estado.daymet?.estado ?? '') && estado.daymet.detalle === null : false
  const hayFallos = avances.includes('fallo')
  const puedeReintentar = estado ? Object.values(estado).some((e) => e.reintentable) : false

  async function reintentar() {
    if (!idParcela) return
    setReintentando(true)
    try {
      const respuesta = await reintentarIngesta(idParcela)
      setParcela((previa) => (previa ? { ...previa, estado_ingesta: respuesta.estado_ingesta } : previa))
    } catch (err) {
      setError(mensajeDeError(err, tr('preparando_error_reintentar')))
    } finally {
      setReintentando(false)
    }
  }

  return (
    <Screen>
      <BarraSuperior fijo volverA={enOnboarding ? '/onboarding/predio' : '/terreno'} />
      <Titulo
        sub={
          parcela
            ? `${numero(parcela.hectareas, 2)} ha${parcela.ecorregion ? ` · ${parcela.ecorregion.nombre}` : ''}`
            : undefined
        }
      >
        {cargando ? t('preparando_titulo_cargando') : t('preparando_titulo_listo')}
      </Titulo>
      <p className="ps-pad ps-cuerpo" style={{ margin: '8px 0 0 0' }}>
        {t('preparando_intro')}
      </p>

      <ul aria-live="polite" className="ps-pad-16" style={{ margin: '14px 0 0 0', listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 8 }}>
        {GRUPOS.map((grupo, i) => {
          const avance = avances[i] ?? 'cargando'
          return (
            <li key={grupo.clave} className="ps-card" style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 14px' }}>
              <span style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                <span style={{ fontSize: 18, fontWeight: 800, lineHeight: 1.15 }}>{t(`preparando_${grupo.clave}_titulo`)}</span>
                <span className="ps-detalle">{t(`preparando_${grupo.clave}_detalle`)}</span>
                <span className="ps-nota" style={{ marginTop: 4 }}>{t('preparando_fuente', { fuente: t(`preparando_${grupo.clave}_fuente`) })}</span>
                <span style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
                  {grupo.origenes.map((o) => (
                    <span key={o} className={`ps-chip ${CLASE_ORIGEN[o]}`}>{t(CLAVE_ORIGEN[o as Origen])}</span>
                  ))}
                </span>
              </span>
              <Chip tono={ETIQUETA[avance].tono}>{t(ETIQUETA[avance].texto)}</Chip>
            </li>
          )
        })}
      </ul>

      {climaSinCobertura ? (
        <p className="ps-pad ps-nota" role={climaConDaymet ? undefined : 'alert'} style={{ margin: '12px 0 0 0', color: climaConDaymet ? undefined : 'var(--riesgo-texto)' }}>
          {t(climaConDaymet ? 'preparando_clima_daymet' : 'preparando_clima_global')}
        </p>
      ) : null}
      {hayFallos ? (
        <div className="ps-pad-16" style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 12 }}>
          <span className="ps-nota" style={{ flex: 1 }}>
            {puedeReintentar ? t('preparando_fallos_reintentar') : t('preparando_fallos_espera')}
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

      <div style={{ position: 'sticky', bottom: 'calc(84px + env(safe-area-inset-bottom, 0px))', marginTop: 'auto', padding: '14px 16px 28px 16px', background: 'var(--arena)', display: 'flex', flexDirection: 'column', gap: 6 }}>
        {climaListo || !climaSinCobertura ? (
          <Link to={enOnboarding ? '/onboarding/meta' : '/terreno'} className="ps-btn">
            {enOnboarding ? t(climaListo ? 'preparando_seguir_registro' : 'preparando_seguir_mientras') : t('preparando_ir_terreno')}
          </Link>
        ) : (
          <button type="button" disabled className="ps-btn">
            {climaSinCobertura ? t('preparando_sin_datos_lugar') : t('preparando_reuniendo_clima')}
          </button>
        )}
        <p className="ps-nota" style={{ margin: '0 0 8px 0', textAlign: 'center' }}>
          {climaListo ? (enOnboarding ? t('preparando_nota_onboarding') : t('preparando_nota_terreno')) : climaSinCobertura ? t('preparando_nota_espera') : t('preparando_nota_mientras')}
        </p>
        <Link to="/terreno/zonas" className="ps-btn-secundario" style={{ minHeight: 52, display: 'flex', alignItems: 'center', justifyContent: 'center', textDecoration: 'none' }}>
          {t('preparando_ver_mapa')}
        </Link>
        <p className="ps-nota" style={{ margin: 0, textAlign: 'center' }}>{t('preparando_mapa_nota')}</p>
        {climaSinCobertura ? (
          <Link to="/terreno/perimetro" className="ps-btn-texto">
            {t('preparando_marcar_de_nuevo')}
          </Link>
        ) : null}
      </div>
    </Screen>
  )
}
