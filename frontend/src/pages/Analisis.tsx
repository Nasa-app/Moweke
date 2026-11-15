import { useEffect, useState } from 'react'
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { Screen, BarraSuperior } from '../components/Screen'
import { CompatRing } from '../components/CompatRing'
import { Chip } from '../components/Chip'
import { SourceLink } from '../components/SourceLink'
import { usePredio } from '../state/PredioContext'
import { candidatasSiembra, declararCultivo, mensajeDeError, type Candidata, type Factor } from '../lib/api'
import { aIso, aPorcentaje, fechaCorta, nombreClave, nombreEspecie, nombreMes } from '../lib/formato'
import { useI18n } from '../i18n'

const ORDEN_FACTORES: Factor[] = ['temperatura', 'helada', 'humedad', 'ph', 'radiacion']
const DETALLE_FACTOR: Record<Factor, string> = {
  temperatura: 'Calor promedio de la temporada',
  helada: 'Que la noche más fría no la mate',
  humedad: 'Lluvia de la temporada, sin riego',
  ph: 'Qué tan ácido o alcalino es el suelo (pH) para ella',
  radiacion: 'Sol que recibe en la temporada',
}
const SEGUIMIENTO: Record<string, { texto: string; detalle: string }> = {
  perfil_calibrado: { texto: 'Te avisamos etapa por etapa', detalle: 'Las etapas están ajustadas con datos de la zona.' },
  perfil_fenologico_regional: { texto: 'Te avisamos etapa por etapa', detalle: 'Las etapas son de referencia: aún no se han probado en terreno.' },
}

function colorDeFactor(valor: number): string {
  if (valor >= 0.7) return 'var(--semaforo-verde)'
  if (valor >= 0.4) return 'var(--semaforo-amarillo)'
  return 'var(--semaforo-rojo)'
}

export default function Analisis() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const clave = params.get('especie')
  const { idParcela, setCultivoActivo } = usePredio()
  const [candidata, setCandidata] = useState<Candidata | null | undefined>(undefined)
  const [variedad, setVariedad] = useState('')
  const [fechaSiembra, setFechaSiembra] = useState(() => aIso(new Date()))
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!idParcela || !clave) return
    let vigente = true
    candidatasSiembra(idParcela)
      .then((r) => vigente && setCandidata(r.candidatas.find((c) => c.especie === clave) ?? null))
      .catch((err) => vigente && setError(mensajeDeError(err, 'No pudimos cargar el análisis. Revisa tu conexión e inténtalo de nuevo.')))
    return () => {
      vigente = false
    }
  }, [idParcela, clave])

  if (!idParcela) return <Navigate to="/terreno/perimetro" replace />
  if (!clave) return <Navigate to="/especies" replace />

  async function sembrar() {
    if (!idParcela || !clave) return
    setEnviando(true)
    setError(null)
    try {
      const cultivo = await declararCultivo(idParcela, {
        especie: clave,
        variedad_local: variedad.trim() || null,
        fecha_siembra: fechaSiembra,
      })
      setCultivoActivo(cultivo.id, cultivo.especie)
      navigate('/cultivo')
    } catch (err) {
      setError(mensajeDeError(err, 'No se pudo guardar la siembra. Revisa la fecha e intenta otra vez.'))
    } finally {
      setEnviando(false)
    }
  }

  const nombre = candidata ? nombreEspecie(candidata.especie, candidata) : nombreEspecie(clave)
  const compat = aPorcentaje(candidata?.puntaje)
  const seguimiento = candidata ? SEGUIMIENTO[candidata.nivel_madurez] : undefined
  const factores = candidata ? ORDEN_FACTORES.filter((f) => candidata.factores[f] !== undefined) : []

  return (
    <Screen>
      <BarraSuperior
        volverA="/especies"
        derecha={candidata ? <Chip tono={candidata.apta ? 'favorable' : 'riesgo'}>{candidata.apta ? 'Apta para tu parcela' : 'No apta para tu parcela'}</Chip> : undefined}
      />

      <section aria-labelledby="especie" className="ps-pad-16" style={{ marginTop: 14 }}>
        <div className="ps-card" style={{ borderRadius: 24, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <h1 id="especie" style={{ margin: 0, fontSize: 28, fontWeight: 800, lineHeight: 1.05 }}>{nombre}</h1>
          {candidata?.nombre_cientifico ? <span className="ps-contexto" style={{ fontStyle: 'italic' }}>{candidata.nombre_cientifico}</span> : null}
          {candidata === undefined && !error ? <span className="ps-nota">{t('cargando')}</span> : null}
          {candidata === null ? <span className="ps-cuerpo">Esta especie no está en el análisis de tu parcela.</span> : null}
          {candidata ? (
            <div style={{ marginTop: 10, padding: '10px 12px', borderRadius: 18, background: 'var(--hundido)', display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ flexShrink: 0 }}>
                <CompatRing porcentaje={compat} tamano={72} />
              </span>
              <span style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <span style={{ fontSize: 22, fontWeight: 800, lineHeight: 1.1 }}>{compat}% compatible</span>
                <span className="ps-detalle">
                  {candidata.factor_limitante && compat < 100 ? `Lo que más la limita: ${nombreClave(candidata.factor_limitante).toLowerCase()}` : t('analisis_compatible')}
                </span>
                <SourceLink>
                  {candidata.metodo === 'simulacion_por_fase' ? 'Calculado etapa por etapa con el clima de tu parcela' : 'Calculado con la guía de la FAO (EcoCrop) y el clima de tu parcela'}
                </SourceLink>
              </span>
            </div>
          ) : null}
        </div>
      </section>

      {candidata ? (
        <>
          <h2 className="ps-h2" style={{ margin: '18px 20px 0 20px' }}>
            Qué le sirve y qué no
          </h2>
          <ul className="ps-pad-16" style={{ margin: '10px 0 0 0', listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 8 }}>
            {factores.map((factor) => {
              const valor = candidata.factores[factor] ?? 0
              return (
                <li key={factor} className="ps-card-plana" style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: '12px 14px' }}>
                  <span style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8 }}>
                    <span style={{ fontSize: 17, fontWeight: 800 }}>{nombreClave(factor)}</span>
                    <span style={{ fontSize: 17, fontWeight: 800 }}>{aPorcentaje(valor)}%</span>
                  </span>
                  <span className="ps-barra" role="img" aria-label={`${nombreClave(factor)}: ${aPorcentaje(valor)} de 100`}>
                    <span style={{ width: `${aPorcentaje(valor)}%`, background: colorDeFactor(valor) }} />
                  </span>
                  <span className="ps-detalle">{DETALLE_FACTOR[factor]}</span>
                </li>
              )
            })}
          </ul>
          {candidata.metodo === 'simulacion_por_fase' ? (
            <p className="ps-pad ps-nota" style={{ margin: '8px 0 0 0' }}>
              El porcentaje de arriba sale de simular el cultivo etapa por etapa con el clima de tu parcela. Las barras muestran lo que esta especie aguanta, según la guía de la FAO.
            </p>
          ) : null}
          {candidata.fuera_de_rangos_ecocrop ? (
            <p className="ps-pad ps-nota" style={{ margin: '8px 0 0 0' }}>
              El clima de tu parcela está fuera de lo que esta especie aguanta, por eso no la recomendamos.
            </p>
          ) : null}

          <h2 className="ps-h2" style={{ margin: '18px 20px 0 20px' }}>
            Cuándo
          </h2>
          <div className="ps-pad-16" style={{ marginTop: 10 }}>
            <div className="ps-card" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {candidata.mes_inicio_temporada && candidata.duracion_temporada_meses ? (
                <span style={{ fontSize: 18, fontWeight: 800, lineHeight: 1.2 }}>
                  Mejor temporada: desde {nombreMes(candidata.mes_inicio_temporada - 1)}, unos {candidata.duracion_temporada_meses}{' '}
                  {candidata.duracion_temporada_meses === 1 ? 'mes' : 'meses'}
                </span>
              ) : null}
              {candidata.simulacion ? (
                <span className="ps-cuerpo">
                  Si la siembras el {fechaCorta(candidata.simulacion.siembra_simulada)}
                  {candidata.simulacion.perdida_simulada !== undefined
                    ? `, podrías perder cerca del ${aPorcentaje(candidata.simulacion.perdida_simulada)}% de la cosecha.`
                    : ', no alcanza a completar su ciclo con el clima que tenemos.'}
                </span>
              ) : null}
              <span className="ps-detalle">
                {seguimiento ? `${seguimiento.texto}. ${seguimiento.detalle}` : 'Todavía no seguimos sus etapas: solo vemos si tu terreno le sirve.'}
              </span>
            </div>
          </div>

          <h2 className="ps-h2" style={{ margin: '18px 20px 0 20px' }}>
            ¿La sembraste o la vas a sembrar?
          </h2>
          <div className="ps-pad-16" style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 10 }}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: 15, fontWeight: 800 }}>Fecha de siembra</span>
              <input type="date" value={fechaSiembra} onChange={(e) => setFechaSiembra(e.target.value)} required style={campoEstilo} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: 15, fontWeight: 800 }}>
                {t('analisis_variedad')} <span className="ps-nota">({t('opcional').toLowerCase()})</span>
              </span>
              <input value={variedad} onChange={(e) => setVariedad(e.target.value)} maxLength={120} placeholder="Escribe tu variedad" style={campoEstilo} />
            </label>
          </div>
        </>
      ) : null}

      {error ? (
        <p className="ps-pad ps-nota" role="alert" style={{ margin: '10px 0 0 0', color: 'var(--riesgo-texto)' }}>
          {error}
        </p>
      ) : null}

      <div style={{ marginTop: 'auto', padding: '16px 16px 32px 16px' }}>
        <button type="button" onClick={sembrar} disabled={!candidata || enviando || !fechaSiembra} className="ps-btn">
          {enviando ? t('cargando') : seguimiento ? 'Seguir este cultivo' : 'Agregar a mis cultivos'}
        </button>
      </div>
    </Screen>
  )
}

const campoEstilo: React.CSSProperties = {
  minHeight: 50,
  padding: '0 14px',
  borderRadius: 14,
  border: '2px solid var(--borde-control)',
  background: 'var(--blanco)',
  color: 'var(--carbon)',
  font: "700 17px 'Alegreya Sans', sans-serif",
}
