import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Screen, BarraSuperior, Titulo } from '../../components/Screen'
import { StepDots } from '../../components/StepDots'
import { usePredio } from '../../state/PredioContext'
import { declararCultivo, especiesConSeguimiento, listarCultivos, mensajeDeError, type EspecieConSeguimiento } from '../../lib/api'
import { aIso, nombreClave, nombreEspecie } from '../../lib/formato'
import { useI18n } from '../../i18n'

export default function OnbCultivos() {
  const { t, idioma } = useI18n()
  const navigate = useNavigate()
  const { idParcela, setCultivoActivo } = usePredio()
  const [especies, setEspecies] = useState<EspecieConSeguimiento[] | null>(null)
  const [seleccion, setSeleccion] = useState<Set<string>>(new Set())
  const [fechas, setFechas] = useState<Record<string, string>>({})
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hoy] = useState(() => aIso(new Date()))

  useEffect(() => {
    let vigente = true
    especiesConSeguimiento()
      .then((r) => vigente && setEspecies(r.especies))
      .catch((err) => vigente && setError(mensajeDeError(err, 'No se pudo cargar la lista de cultivos.')))
    return () => {
      vigente = false
    }
  }, [])

  function alternar(especie: string) {
    const copia = new Set(seleccion)
    if (copia.has(especie)) copia.delete(especie)
    else copia.add(especie)
    setSeleccion(copia)
  }

  async function seguir() {
    if (!idParcela) return
    setEnviando(true)
    setError(null)
    try {
      const { cultivos } = await listarCultivos(idParcela)
      let primero: { id: number; especie: string } | null = null
      for (const especie of seleccion) {
        const fecha = fechas[especie] ?? hoy
        const existente = cultivos.find((c) => c.especie === especie && c.fecha_siembra === fecha)
        const cultivo = existente ?? (await declararCultivo(idParcela, { especie, fecha_siembra: fecha }))
        primero = primero ?? cultivo
      }
      if (primero) setCultivoActivo(primero.id, primero.especie)
      navigate('/onboarding/listo')
    } catch (err) {
      setError(mensajeDeError(err, 'No se pudo guardar tu siembra. Revisa las fechas e intenta otra vez.'))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Screen>
      <BarraSuperior volverA="/onboarding/meta" derecha={<StepDots paso={4} total={4} />} />
      <Titulo sub="Estos cultivos tienen seguimiento por etapa. Los demás se eligen desde el análisis de tu terreno.">{t('onb_cultivos_titulo')}</Titulo>

      {!idParcela ? (
        <Link to="/terreno/perimetro?desde=onboarding" className="ps-card-plana" style={{ margin: '12px 16px 0 16px', textDecoration: 'none', color: 'var(--carbon)', display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ flex: 1, fontSize: 16, fontWeight: 700 }}>Primero marca tu parcela: el seguimiento usa su clima.</span>
          <span style={{ fontSize: 16, fontWeight: 800, color: 'var(--verde)' }}>{t('onb_marcar_parcela')}</span>
        </Link>
      ) : null}

      <fieldset className="ps-pad-16" style={{ margin: '14px 0 0 0', border: 'none' }}>
        <legend className="visually-hidden">Cultivos de esta temporada</legend>
        <div className="ps-grid-2">
          {(especies ?? []).map(({ especie, etapas }) => {
            const activo = seleccion.has(especie)
            return (
              <label
                key={especie}
                style={{
                  borderRadius: 20,
                  background: 'var(--blanco)',
                  boxShadow: activo ? '0 0 0 3px var(--verde)' : 'var(--sombra-1)',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 4,
                  minHeight: 100,
                  padding: '8px 10px',
                  textAlign: 'center',
                  cursor: 'pointer',
                }}
              >
                <input type="checkbox" checked={activo} onChange={() => alternar(especie)} className="visually-hidden" />
                <span style={{ fontSize: 18, fontWeight: 800, color: activo ? 'var(--verde)' : undefined }}>{nombreEspecie(especie)}</span>
                <span className="ps-nota">{etapas.map((e) => nombreClave(e).toLowerCase()).join(' · ')}</span>
              </label>
            )
          })}
          <Link
            to="/especies"
            style={{
              borderRadius: 20,
              border: '3px dashed var(--borde-control)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              minHeight: 100,
              font: "800 18px 'Alegreya Sans', sans-serif",
              color: 'var(--carbon)',
              textDecoration: 'none',
            }}
          >
            {idioma === 'en' ? 'Other' : 'Otro'}
          </Link>
        </div>
        {especies === null && !error ? <p className="ps-nota">{t('cargando')}</p> : null}
      </fieldset>

      {seleccion.size ? (
        <>
          <h2 className="ps-h2" style={{ margin: '18px 20px 0 20px' }}>
            {t('onb_cuando')}
          </h2>
          <div className="ps-pad-16" style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {Array.from(seleccion).map((especie) => (
              <label key={especie} className="ps-card-plana" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{ flex: 1, fontSize: 16, fontWeight: 800 }}>{nombreEspecie(especie)}</span>
                <input
                  type="date"
                  aria-label={`Fecha de siembra de ${nombreEspecie(especie)}`}
                  value={fechas[especie] ?? hoy}
                  onChange={(e) => setFechas((previas) => ({ ...previas, [especie]: e.target.value }))}
                  style={{ minHeight: 48, padding: '0 12px', borderRadius: 14, border: '2px solid var(--borde-control)', background: 'var(--blanco)', color: 'var(--carbon)', font: "700 16px 'Alegreya Sans', sans-serif" }}
                />
              </label>
            ))}
          </div>
          <p className="ps-pad ps-nota" style={{ margin: '8px 0 0 0' }}>
            Puede ser una siembra ya hecha (hasta un año atrás) o una planeada (hasta seis meses adelante).
          </p>
        </>
      ) : null}

      {error ? (
        <p className="ps-pad ps-nota" role="alert" style={{ margin: '12px 0 0 0', color: 'var(--riesgo-texto)' }}>
          {error}
        </p>
      ) : null}

      <div style={{ marginTop: 'auto', padding: '20px 16px 32px 16px' }}>
        <button type="button" onClick={seguir} disabled={enviando || seleccion.size === 0 || !idParcela} className="ps-btn">
          {enviando ? t('cargando') : t('seguir')}
        </button>
      </div>
    </Screen>
  )
}
