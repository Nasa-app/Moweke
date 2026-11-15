import { useState } from 'react'
import { anularRiego, declararRiego, mensajeDeError, type Riego } from '../lib/api'
import { diasEntre, fechaCorta, numero } from '../lib/formato'
import { useI18n } from '../i18n'

type RiegoConEstimacion = Extract<Riego, { estado: 'regar_ya' | 'proximos_dias' | 'sin_necesidad' }>

const dias = (n: number) => `${n} ${n === 1 ? 'día' : 'días'}`
const haceDias = (n: number) => (n <= 0 ? 'hoy' : n === 1 ? 'ayer' : `hace ${n} días`)

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
      ? 'Conviene regar hoy'
      : r.estado === 'proximos_dias'
        ? `Riega antes del ${fechaCorta(r.fecha_limite)}`
        : 'No hace falta regar por ahora'
  const detalle =
    r.estado === 'regar_ya'
      ? `Unos ${r.lamina_mm} mm para llenar la zona de raíces.${r.ks_hoy < 1 ? ' El cultivo ya siente la falta de agua.' : ''}`
      : r.estado === 'proximos_dias'
        ? `En ${dias(r.dias_para_riego ?? 0)} el agua llega al nivel en que conviene regar (unos ${r.lamina_mm} mm).`
        : r.dias_revisados > 0
          ? `Según el pronóstico, el suelo aguanta los próximos ${dias(r.dias_revisados)}.`
          : 'Hoy el suelo tiene agua suficiente.'

  async function cambiar(accion: () => Promise<unknown>) {
    setEnviando(true)
    setError(null)
    try {
      await accion()
      onCambio()
    } catch (err) {
      setError(mensajeDeError(err, 'No pudimos anotar el riego. Revisa tu conexión e inténtalo de nuevo.'))
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
        <span className="ps-contexto">Estos días</span>
        {r.lluvia_reciente ? (
          <span style={{ fontSize: 16, fontWeight: 700 }}>
            {r.lluvia_reciente.dias_con_dato < Math.ceil(r.lluvia_reciente.dias / 2)
              ? 'Todavía sin datos de lluvia de estos días.'
              : !r.lluvia_reciente.ultima_lluvia
                ? `No llovió en los ${r.lluvia_reciente.dias} días hasta ayer.`
                : `Llovieron ${numero(r.lluvia_reciente.total_mm, 1)} mm en los ${r.lluvia_reciente.dias} días hasta ayer · la última lluvia fue ${haceDias(r.lluvia_reciente.ultima_lluvia.hace_dias)} (${numero(r.lluvia_reciente.ultima_lluvia.mm, 1)} mm).`}
          </span>
        ) : null}
        {r.humedad_suelo_nasa ? (
          <span style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
            <span className="ps-chip ps-chip-clima" style={{ flexShrink: 0 }}>NASA</span>
            <span style={{ fontSize: 16, fontWeight: 700 }}>
              {`Humedad del suelo ${haceDias(diasEntre(r.humedad_suelo_nasa.fecha, hoy))}: ${Math.round(r.humedad_suelo_nasa.zona_raices * 100)}% de lo que puede guardar`}
            </span>
          </span>
        ) : null}
        <span className="ps-nota">
          Lluvia: CR2MET y Open-Meteo, en el cuadro de unos 5 km donde está tu parcela.
          {r.humedad_suelo_nasa ? ` Humedad: NASA POWER, celda de unos ${r.humedad_suelo_nasa.resolucion_km} km con ${diasEntre(r.humedad_suelo_nasa.fecha, hoy)} días de atraso; es de la región, no de tu parcela, y no es el mismo porcentaje de arriba.` : ''}
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
        Es una estimación con el clima y el suelo de tu parcela; no mide la humedad del suelo. Si la tierra está húmeda, no riegues.
        {r.suelo_medido ? '' : ' Todavía no tenemos el dato de agua del suelo de tu parcela: usamos un valor promedio.'}
      </span>
    </section>
  )
}
