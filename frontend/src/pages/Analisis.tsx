import { useEffect, useState } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { Screen, BarraSuperior } from '../components/Screen'
import { CompatRing } from '../components/CompatRing'
import { Cargando } from '../components/Cargando'
import { Chip } from '../components/Chip'
import { SourceLink } from '../components/SourceLink'
import { usePredio } from '../state/PredioContext'
import { ESCENARIOS, candidatasSiembra, declararCultivo, mensajeDeError, type Candidata, type Factor, type PeriodoClima, type SerieClimatica } from '../lib/api'
import { NOMBRE_ESCENARIO, TEXTO_CATEGORIA_CLIMA, aIso, aPorcentaje, fechaCorta, nombreClave, nombreEspecie, nombreMes, textoDatosFaltantes, textoVariedad } from '../lib/formato'
import { useI18n } from '../i18n'
import { tr } from '../i18n/dictionary'
import { claveVariedad, variedadesConocidas } from '../lib/nombres'

const ORDEN_FACTORES: Factor[] = [
  'temperatura', 'helada', 'humedad', 'ph', 'radiacion', 'altitud', 'textura',
  'drenaje', 'salinidad', 'profundidad', 'fertilidad',
]
const NIVELES_SEGUIMIENTO = ['perfil_calibrado', 'perfil_fenologico_regional']

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
  // El supuesto de clima con que se llegó desde "Qué sembrar" (no se guarda: viene en la dirección).
  const escenario = ESCENARIOS.find((e) => e === params.get('escenario')) ?? 'observado'
  const { idParcela, setCultivoActivo } = usePredio()
  const [candidata, setCandidata] = useState<Candidata | null | undefined>(undefined)
  const [faltantes, setFaltantes] = useState<string[]>([])
  const [serie, setSerie] = useState<SerieClimatica | null>(null)
  const [variedad, setVariedad] = useState('')
  const [fechaSiembra, setFechaSiembra] = useState(() => aIso(new Date()))
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!idParcela || !clave) return
    let vigente = true
    candidatasSiembra(idParcela, { especie: clave, escenario })
      .then((r) => {
        if (!vigente) return
        setCandidata(r.candidatas.find((c) => c.especie === clave) ?? null)
        setFaltantes(r.datos_faltantes)
        setSerie(r.serie_climatica)
      })
      .catch((err) => vigente && setError(mensajeDeError(err, tr('analisis_error_cargar'))))
    return () => {
      vigente = false
    }
  }, [idParcela, clave, escenario])

  if (!idParcela) return <Navigate to="/terreno/perimetro" replace />
  if (!clave) return <Navigate to="/especies" replace />

  async function sembrar() {
    if (!idParcela || !clave) return
    setEnviando(true)
    setError(null)
    try {
      const cultivo = await declararCultivo(idParcela, {
        especie: clave,
        variedad_local: claveVariedad(clave, variedad) || null,
        fecha_siembra: fechaSiembra,
      })
      setCultivoActivo(cultivo.id, cultivo.especie)
      navigate('/cultivo')
    } catch (err) {
      setError(mensajeDeError(err, tr('analisis_error_guardar')))
    } finally {
      setEnviando(false)
    }
  }

  const nombre = candidata ? nombreEspecie(candidata.especie, candidata) : nombreEspecie(clave)
  const compat = aPorcentaje(candidata?.puntaje)
  const seguimiento = candidata && NIVELES_SEGUIMIENTO.includes(candidata.nivel_madurez) ? candidata.nivel_madurez : undefined
  const factores = candidata ? ORDEN_FACTORES.filter((f) => candidata.factores[f] !== undefined) : []

  return (
    <Screen>
      <BarraSuperior
        volverA="/especies"
        derecha={candidata ? <Chip tono={candidata.apta ? 'favorable' : candidata.marginal ? 'precaucion' : 'riesgo'}>{candidata.apta ? t('analisis_chip_apta') : candidata.marginal ? t('analisis_chip_marginal') : t('analisis_chip_no_apta')}</Chip> : undefined}
      />

      <section aria-labelledby="especie" className="ps-pad-16" style={{ marginTop: 14 }}>
        <div className="ps-card" style={{ borderRadius: 24, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <h1 id="especie" style={{ margin: 0, fontSize: 28, fontWeight: 800, lineHeight: 1.05 }}>{nombre}</h1>
          {candidata?.nombre_cientifico ? <span className="ps-contexto" style={{ fontStyle: 'italic' }}>{candidata.nombre_cientifico}</span> : null}
          {escenario !== 'observado' ? (
            <span className="ps-nota" role="status">
              {t('analisis_supuesto_clima', { escenario: NOMBRE_ESCENARIO[escenario].toLowerCase() })}
            </span>
          ) : null}
          {candidata === undefined && !error ? <Cargando texto={t('analisis_evaluando')} detalle={t('especies_buscando_detalle')} /> : null}
          {candidata === null ? <span className="ps-cuerpo">{t('analisis_no_esta')}</span> : null}
          {candidata ? (
            <div style={{ marginTop: 10, padding: '10px 12px', borderRadius: 18, background: 'var(--hundido)', display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ flexShrink: 0 }}>
                <CompatRing porcentaje={compat} tamano={72} />
              </span>
              <span style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <span style={{ fontSize: 22, fontWeight: 800, lineHeight: 1.1 }}>{t('analisis_pct_compatible', { n: compat })}</span>
                <span className="ps-detalle">
                  {candidata.factor_limitante && compat < 100 ? t('analisis_limita', { factor: nombreClave(candidata.factor_limitante).toLowerCase() }) : t('analisis_compatible')}
                </span>
                <SourceLink>
                  {candidata.metodo === 'simulacion_por_fase' ? t('analisis_metodo_fases') : t('analisis_metodo_ecocrop')}
                </SourceLink>
              </span>
            </div>
          ) : null}
        </div>
      </section>

      {candidata?.variedades?.length ? (
        <section aria-labelledby="variedades">
          <h2 id="variedades" className="ps-h2" style={{ margin: '18px 20px 0 20px' }}>
            {t('analisis_variedad_titulo')}
          </h2>
          <p className="ps-pad ps-cuerpo" style={{ margin: '6px 0 0 0' }}>
            {candidata.variedad_recomendada
              ? t('analisis_variedad_recomendada', { variedad: textoVariedad(candidata.variedad_recomendada) })
              : t('analisis_variedad_sin')}
          </p>
          <ul aria-label={t('analisis_variedades_aria')} className="ps-pad-16" style={{ margin: '10px 0 0 0', listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 8 }}>
            {candidata.variedades.map((v) => (
              <li key={v.nombre_cientifico}>
                <Link
                  to={`/especies/analisis?especie=${encodeURIComponent(v.nombre_cientifico.trim().toLowerCase().replace(/[^a-z0-9\s]/g, '').replace(/\s+/g, '_'))}`}
                  className="ps-card"
                  aria-current={v.nombre_cientifico === candidata.nombre_cientifico ? 'true' : undefined}
                  style={{ textDecoration: 'none', color: 'var(--carbon)', display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px', boxShadow: v.mejor ? '0 0 0 3px var(--verde)' : undefined }}
                >
                  <CompatRing porcentaje={aPorcentaje(v.puntaje)} tamano={44} />
                  <span style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
                    <span style={{ fontSize: 18, fontWeight: 800, lineHeight: 1.15 }}>
                      {v.rango && v.nombre ? `${v.rango[0].toUpperCase()}${v.rango.slice(1)} ${v.nombre}` : t('analisis_especie_sin_variedad')}
                    </span>
                    <span className="ps-contexto" style={{ fontStyle: 'italic' }}>{v.nombre_cientifico}</span>
                  </span>
                  {v.mejor ? <Chip tono="favorable">{t('analisis_la_que_conviene')}</Chip> : null}
                </Link>
              </li>
            ))}
          </ul>
          <p className="ps-pad ps-nota" style={{ margin: '8px 0 0 0' }}>
            {t('analisis_variedad_nota')}
          </p>
        </section>
      ) : null}

      {candidata ? (
        <>
          <h2 className="ps-h2" style={{ margin: '18px 20px 0 20px' }}>
            {t('analisis_sirve_titulo')}
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
                  <span className="ps-barra" role="img" aria-label={t('analisis_factor_aria', { factor: nombreClave(factor), n: aPorcentaje(valor) })}>
                    <span style={{ width: `${aPorcentaje(valor)}%`, background: colorDeFactor(valor) }} />
                  </span>
                  <span className="ps-detalle">{t(`analisis_factor_${factor}`)}</span>
                </li>
              )
            })}
          </ul>
          {candidata.clima && serie ? (
            <p className="ps-pad ps-nota" style={{ margin: '8px 0 0 0' }}>
              {t('analisis_nota_barras', { desde: serie.periodo_reciente[0], hasta: serie.periodo_reciente[1] })}
            </p>
          ) : null}
          {candidata.clima && serie ? <ClimaEnElTiempo clima={candidata.clima} serie={serie} apta={!!candidata.apta} /> : null}
          {candidata.metodo === 'simulacion_por_fase' ? (
            <p className="ps-pad ps-nota" style={{ margin: '8px 0 0 0' }}>
              {t('analisis_nota_menor')}
            </p>
          ) : null}
          {candidata.correcciones?.some((c) => c.tipo === 'encalado') ? (
            <p className="ps-pad ps-nota" style={{ margin: '8px 0 0 0' }}>
              {t('analisis_nota_encalado')}
            </p>
          ) : null}
          {candidata.correcciones?.some((c) => c.tipo === 'fertilizacion') ? (
            <p className="ps-pad ps-nota" style={{ margin: '8px 0 0 0' }}>
              {t('analisis_nota_fertilidad')}
            </p>
          ) : null}
          {textoDatosFaltantes(faltantes) ? (
            <p className="ps-pad ps-nota" role="status" style={{ margin: '8px 0 0 0', color: 'var(--precaucion-texto)' }}>
              {textoDatosFaltantes(faltantes)}
            </p>
          ) : null}
          {candidata.fuera_de_rangos_ecocrop ? (
            <p className="ps-pad ps-nota" style={{ margin: '8px 0 0 0' }}>
              {t('analisis_nota_fuera_rango')}
            </p>
          ) : null}

          <h2 className="ps-h2" style={{ margin: '18px 20px 0 20px' }}>
            {t('analisis_cuando')}
          </h2>
          <div className="ps-pad-16" style={{ marginTop: 10 }}>
            <div className="ps-card" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {candidata.mes_inicio_temporada && candidata.duracion_temporada_meses ? (
                <span style={{ fontSize: 18, fontWeight: 800, lineHeight: 1.2 }}>
                  {t(candidata.duracion_temporada_meses === 1 ? 'analisis_temporada_uno' : 'analisis_temporada_otros', { mes: nombreMes(candidata.mes_inicio_temporada - 1), n: candidata.duracion_temporada_meses })}
                </span>
              ) : null}
              {candidata.simulacion ? (
                <span className="ps-cuerpo">
                  {candidata.simulacion.perdida_simulada !== undefined
                    ? t('analisis_sim_perdida', { fecha: fechaCorta(candidata.simulacion.siembra_simulada), n: aPorcentaje(candidata.simulacion.perdida_simulada) })
                    : t('analisis_sim_sin_ciclo', { fecha: fechaCorta(candidata.simulacion.siembra_simulada) })}
                </span>
              ) : null}
              <span className="ps-detalle">
                {seguimiento ? `${t('analisis_seguimiento_texto')}. ${t(`analisis_seguimiento_${seguimiento}`)}` : t('analisis_sin_seguimiento')}
              </span>
            </div>
          </div>

          <h2 className="ps-h2" style={{ margin: '18px 20px 0 20px' }}>
            {t('analisis_sembraste_titulo')}
          </h2>
          <div className="ps-pad-16" style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 10 }}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: 15, fontWeight: 800 }}>{t('analisis_fecha_siembra')}</span>
              <input type="date" value={fechaSiembra} onChange={(e) => setFechaSiembra(e.target.value)} required style={campoEstilo} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: 15, fontWeight: 800 }}>
                {t('analisis_variedad')} <span className="ps-nota">({t('opcional').toLowerCase()})</span>
              </span>
              <input value={variedad} onChange={(e) => setVariedad(e.target.value)} maxLength={120} list="variedades-conocidas"
                placeholder={t('analisis_variedad_placeholder')} style={campoEstilo} />
              <datalist id="variedades-conocidas">
                {variedadesConocidas(clave).map((v) => <option key={v.clave} value={v.nombre} />)}
              </datalist>
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
          {enviando ? t('cargando') : seguimiento ? t('analisis_seguir_cultivo') : t('analisis_agregar_cultivos')}
        </button>
      </div>
    </Screen>
  )
}

function FilaPeriodo({ nombre, periodo }: { nombre: string; periodo: PeriodoClima }) {
  const { t } = useI18n()
  const tipico = aPorcentaje(periodo.tipico)
  return (
    <li className="ps-card-plana" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, padding: '12px 14px' }}>
      <span style={{ fontSize: 17, fontWeight: 800 }}>{nombre}</span>
      <span style={{ textAlign: 'right', display: 'flex', flexDirection: 'column' }}>
        <span style={{ fontSize: 17, fontWeight: 800 }} aria-label={t('analisis_periodo_aria', { n: tipico })}>{t('analisis_pct_compatible', { n: tipico })}</span>
        <span className="ps-detalle">{t('analisis_pct_dificil', { n: aPorcentaje(periodo.dificil) })}</span>
      </span>
    </li>
  )
}

// Cómo le fue y le iría a la especie en tu parcela: antes, ahora y hacia el futuro, con el mismo cálculo año por año.
function ClimaEnElTiempo({ clima, serie, apta }: { clima: NonNullable<Candidata['clima']>; serie: SerieClimatica; apta: boolean }) {
  const { t } = useI18n()
  const categoria = clima.categoria ? TEXTO_CATEGORIA_CLIMA[clima.categoria] : null
  return (
    <>
      <h2 className="ps-h2" style={{ margin: '18px 20px 0 20px' }}>
        {t('analisis_clima_titulo')}
      </h2>
      {categoria ? (
        <p className="ps-pad ps-cuerpo" style={{ margin: '8px 0 0 0' }}>
          <b>{categoria.chip}.</b> {categoria.detalle}
          {!apta && clima.categoria === 'emergente' ? ` ${t('analisis_clima_todavia_no')}` : ''}
        </p>
      ) : null}
      <ul className="ps-pad-16" style={{ margin: '10px 0 0 0', listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 8 }}>
        <FilaPeriodo nombre={t('analisis_rango_anios', { desde: serie.periodo_historico[0], hasta: serie.periodo_historico[1] })} periodo={clima.historico} />
        <FilaPeriodo nombre={t('analisis_rango_anios', { desde: serie.periodo_reciente[0], hasta: serie.periodo_reciente[1] })} periodo={clima.reciente} />
        <FilaPeriodo nombre={t('analisis_hacia', { horizonte: serie.horizonte })} periodo={clima.proyectado} />
      </ul>
      <p className="ps-pad ps-nota" style={{ margin: '8px 0 0 0' }}>
        {t('analisis_clima_nota', { horizonte: serie.horizonte })}
      </p>
    </>
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
