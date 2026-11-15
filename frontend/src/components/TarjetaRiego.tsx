import { useState } from 'react'
import { anularRiego, declararRiego, mensajeDeError, type Riego } from '../lib/api'
import { diasEntre, fechaCorta, numero } from '../lib/formato'
import { useI18n } from '../i18n'
import { tr } from '../i18n/dictionary'

type RiegoConEstimacion = Extract<Riego, { estado: 'regar_ya' | 'proximos_dias' | 'sin_necesidad' }>

const dias = (n: number) => tr(n === 1 ? 'inicio_dia_uno' : 'inicio_dia_otros', { n })
const haceDias = (n: number) => (n <= 0 ? tr('inicio_hace_hoy') : n === 1 ? tr('inicio_hace_ayer') : tr('inicio_hace_n', { n }))

// Cuándo regar según el balance de agua del cultivo. Es una estimación con el clima y el suelo de
// la parcela, no una medición: la tarjeta lo dice y deja anotar un riego para que el cálculo parta de ahí.
export function TarjetaRiego({ riego, idCultivo, hoy, onCambio }: {
  riego: Riego
  idCultivo: number
  hoy: string
  onCambio: () => void
}) {
  const { t } = useI18n()
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!riego.disponible || !('agua_pct' in riego)) return null
  const r: RiegoConEstimacion = riego
  const regoHoy = r.ultimo_riego === hoy

  const titulo =
    r.estado === 'regar_ya'
      ? t('riego_conviene_hoy')
      : r.estado === 'proximos_dias'
        ? t('riego_antes_del', { fecha: fechaCorta(r.fecha_limite) })
        : t('riego_no_hace_falta')
  const detalle =
    r.estado === 'regar_ya'
      ? `${t('riego_detalle_ya', { mm: String(r.lamina_mm) })}${r.ks_hoy < 1 ? t('riego_detalle_ya_estres') : ''}`
      : r.estado === 'proximos_dias'
        ? t('riego_detalle_proximos', { dias: dias(r.dias_para_riego ?? 0), mm: String(r.lamina_mm) })
        : r.dias_revisados > 0
          ? t('riego_detalle_aguanta', { dias: dias(r.dias_revisados) })
          : t('riego_detalle_suficiente')

  async function cambiar(accion: () => Promise<unknown>) {
    setEnviando(true)
    setError(null)
    try {
      await accion()
      onCambio()
    } catch (err) {
      setError(mensajeDeError(err, t('riego_error_anotar')))
    } finally {
      setEnviando(false)
    }
  }

  const resaltada = r.estado !== 'sin_necesidad'
  return (
    <section
      className="ps-card"
      aria-labelledby="riego-titulo"
      style={{ margin: '14px 16px 0 16px', display: 'flex', flexDirection: 'column', gap: 8, boxShadow: resaltada ? '0 0 0 2px var(--semaforo-amarillo), var(--sombra-1)' : undefined }}
    >
      <span className="ps-contexto">{t('riego_titulo')}</span>
      <h2 id="riego-titulo" style={{ margin: 0, fontSize: 21, fontWeight: 800, lineHeight: 1.15 }}>{titulo}</h2>
      <span style={{ fontSize: 16, fontWeight: 700 }}>{detalle}</span>
      <span className="ps-detalle">
        {t('riego_agua')}: {r.agua_pct}% · {t('riego_umbral')} {r.umbral_pct}%
        {r.ultimo_riego ? ` · ${t('riego_ultimo')}: ${fechaCorta(r.ultimo_riego)}` : ''}
      </span>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span className="ps-contexto">{t('riego_estos_dias')}</span>
        {r.lluvia_reciente ? (
          <span style={{ fontSize: 16, fontWeight: 700 }}>
            {r.lluvia_reciente.dias_con_dato < Math.ceil(r.lluvia_reciente.dias / 2)
              ? t('riego_lluvia_sin_datos')
              : !r.lluvia_reciente.ultima_lluvia
                ? t('riego_no_llovio', { dias: r.lluvia_reciente.dias })
                : t('riego_llovio', { total: numero(r.lluvia_reciente.total_mm, 1), dias: r.lluvia_reciente.dias, cuando: haceDias(r.lluvia_reciente.ultima_lluvia.hace_dias), mm: numero(r.lluvia_reciente.ultima_lluvia.mm, 1) })}
          </span>
        ) : null}
        {r.humedad_suelo_nasa ? (
          <span style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
            <span className="ps-chip ps-chip-clima" style={{ flexShrink: 0 }}>NASA</span>
            <span style={{ fontSize: 16, fontWeight: 700 }}>
              {t('riego_humedad_nasa', { cuando: haceDias(diasEntre(r.humedad_suelo_nasa.fecha, hoy)), pct: Math.round(r.humedad_suelo_nasa.zona_raices * 100) })}
            </span>
          </span>
        ) : null}
        <span className="ps-nota">
          {t('riego_fuente_lluvia')}
          {r.humedad_suelo_nasa ? t('riego_fuente_humedad', { km: r.humedad_suelo_nasa.resolucion_km, n: diasEntre(r.humedad_suelo_nasa.fecha, hoy) }) : ''}
        </span>
      </div>

      {regoHoy ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 16, fontWeight: 800, color: 'var(--verde)' }}>{t('riego_anotado')}</span>
          <button type="button" className="ps-btn-texto" disabled={enviando} onClick={() => cambiar(() => anularRiego(idCultivo, hoy))}>
            {t('riego_deshacer')}
          </button>
        </div>
      ) : (
        <button type="button" className="ps-btn-secundario" style={{ minHeight: 52 }} disabled={enviando} onClick={() => cambiar(() => declararRiego(idCultivo, hoy))}>
          {t('riego_ya_regue')}
        </button>
      )}

      {error ? <p role="alert" className="ps-nota" style={{ margin: 0, color: 'var(--riesgo-texto)', fontWeight: 700 }}>{error}</p> : null}
      <span className="ps-nota">
        {t('riego_estimacion')}
        {r.suelo_medido ? '' : t('riego_suelo_promedio')}
      </span>
    </section>
  )
}
