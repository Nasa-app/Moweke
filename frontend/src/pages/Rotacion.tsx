import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Screen } from '../components/Screen'
import { Cargando } from '../components/Cargando'
import { CompatRing } from '../components/CompatRing'
import { usePredio } from '../state/PredioContext'
import { ApiError, listarCultivos, planRotacion, type Cultivo, type EstrategiaRotacion, type PlanRotacion } from '../lib/api'
import { aPorcentaje, fechaCorta, nombreEspecie } from '../lib/formato'
import { useI18n } from '../i18n'

const OPCIONES_MAX = 3

// Qué sembrar después, a partir de lo que ya hay en la parcela: el cultivo actual es el último sembrado. Sin parcela se
// pide marcarla; sin cultivos, agregarlos. Las opciones salen del planificador de rotación del servidor, que respeta los
// intervalos entre cultivos y que las solanáceas no vayan una tras otra.
function Secuencia({ especies }: { especies: string[] }) {
  return (
    <span style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 4 }}>
      {especies.map((e, i) => (
        <span key={`${e}-${i}`} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span className="ps-chip ps-chip-neutro">{nombreEspecie(e)}</span>
          {i < especies.length - 1 ? <span aria-hidden="true" style={{ color: 'var(--texto-tenue)' }}>→</span> : null}
        </span>
      ))}
    </span>
  )
}

function Avisos({ estrategia }: { estrategia: EstrategiaRotacion }) {
  const { t } = useI18n()
  if (!estrategia.advertencias.length) return null
  return (
    <details>
      <summary className="ps-nota" style={{ cursor: 'pointer', fontWeight: 800, minHeight: 32, display: 'flex', alignItems: 'center' }}>{t('plan_avisos', { n: estrategia.advertencias.length })}</summary>
      <ul style={{ margin: '4px 0 0 0', paddingLeft: 18 }}>
        {estrategia.advertencias.map((a) => (
          <li key={a} className="ps-nota">{a}</li>
        ))}
      </ul>
    </details>
  )
}

export default function Rotacion() {
  const { t } = useI18n()
  const { idParcela } = usePredio()
  const [cultivos, setCultivos] = useState<Cultivo[] | null>(null)
  const [plan, setPlan] = useState<{ idParcela: number; datos: PlanRotacion } | null>(null)
  const [fallo, setFallo] = useState<'clima' | 'error' | null>(null)

  useEffect(() => {
    if (!idParcela) return
    let vigente = true
    listarCultivos(idParcela)
      .then((r) => vigente && setCultivos([...r.cultivos].sort((a, b) => a.fecha_siembra.localeCompare(b.fecha_siembra))))
      .catch(() => vigente && setCultivos([]))
    return () => {
      vigente = false
    }
  }, [idParcela])

  const hayCultivos = (cultivos?.length ?? 0) > 0
  useEffect(() => {
    if (!idParcela || !hayCultivos) return
    let vigente = true
    planRotacion(idParcela)
      .then((datos) => vigente && setPlan({ idParcela, datos }))
      .catch((err) => vigente && setFallo(err instanceof ApiError && err.status === 409 ? 'clima' : 'error'))
    return () => {
      vigente = false
    }
  }, [idParcela, hayCultivos])

  const actual = cultivos && cultivos.length ? cultivos[cultivos.length - 1] : null
  const antes = cultivos ? cultivos.slice(-4, -1) : []
  const datos = plan && plan.idParcela === idParcela ? plan.datos : null
  const rotaciones = (datos?.estrategias ?? []).filter((e) => e.tipo === 'rotacion' && e.cumple_reglas)
  const mejor = rotaciones[0] ?? null
  const otras = [...rotaciones.slice(1), ...(datos?.estrategias ?? []).filter((e) => e.tipo === 'base')].slice(0, OPCIONES_MAX)

  return (
    <Screen>
      <div style={{ padding: '48px 20px 0 20px', display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12 }}>
        <h1 style={{ margin: 0, fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 30, lineHeight: 1 }}>{t('planificar_titulo')}</h1>
        {idParcela ? <span className="ps-contexto">{t('rotacion_segun_parcela')}</span> : null}
      </div>

      {!idParcela ? (
        <section className="ps-pad-16" style={{ marginTop: 16 }}>
          <div className="ps-card" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <h2 className="ps-h2" style={{ margin: 0 }}>{t('plan_sin_parcela_titulo')}</h2>
            <p className="ps-cuerpo" style={{ margin: 0 }}>{t('plan_sin_parcela_texto')}</p>
            <Link to="/terreno/perimetro" className="ps-btn">{t('plan_sin_parcela_boton')}</Link>
          </div>
        </section>
      ) : cultivos === null ? (
        <div className="ps-pad-16" style={{ marginTop: 16 }}><Cargando texto={t('cargando')} /></div>
      ) : !actual ? (
        <section className="ps-pad-16" style={{ marginTop: 16 }}>
          <div className="ps-card" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <h2 className="ps-h2" style={{ margin: 0 }}>{t('plan_sin_cultivos_titulo')}</h2>
            <p className="ps-cuerpo" style={{ margin: 0 }}>{t('plan_sin_cultivos_texto')}</p>
            <Link to="/cultivo" className="ps-btn">{t('plan_sin_cultivos_boton')}</Link>
            <Link to="/historial" className="ps-btn-secundario" style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{t('plan_sin_cultivos_antes')}</Link>
          </div>
        </section>
      ) : (
        <>
          <section aria-labelledby="plan-actual" className="ps-pad-16" style={{ marginTop: 16 }}>
            <h2 id="plan-actual" className="ps-h2" style={{ margin: '0 4px' }}>{t('plan_actual')}</h2>
            <Link to="/cultivo" className="ps-card" style={{ marginTop: 10, textDecoration: 'none', color: 'var(--carbon)', display: 'flex', flexDirection: 'column', gap: 6 }}>
              <b style={{ fontSize: 22, fontWeight: 800 }}>{nombreEspecie(actual.especie)}</b>
              <span className="ps-detalle">{t('plan_sembrado_el', { fecha: fechaCorta(actual.fecha_siembra) })}</span>
              {antes.length ? (
                <span className="ps-nota">{t('plan_antes')}: {antes.map((c) => `${nombreEspecie(c.especie)} (${c.fecha_siembra.slice(0, 4)})`).join(' · ')}</span>
              ) : null}
            </Link>
          </section>

          <section aria-labelledby="plan-despues" className="ps-pad-16" style={{ marginTop: 16 }}>
            <h2 id="plan-despues" className="ps-h2" style={{ margin: '0 4px' }}>{t('plan_despues_titulo', { actual: nombreEspecie(actual.especie).toLowerCase() })}</h2>
            <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 10 }}>
              {!datos && !fallo ? <Cargando texto={t('plan_calculando')} detalle={t('especies_buscando_detalle')} /> : null}
              {fallo === 'clima' ? (
                <Link to="/terreno/preparando" className="ps-card-plana" style={{ textDecoration: 'none', color: 'var(--carbon)', fontSize: 16, fontWeight: 700 }}>{t('rotacion_reuniendo_clima')} <b style={{ color: 'var(--verde)' }}>{t('inicio_ver_avance')}</b></Link>
              ) : null}
              {fallo === 'error' ? <p className="ps-nota" role="alert" style={{ margin: 0, color: 'var(--riesgo-texto)' }}>{t('plan_error')}</p> : null}
              {datos && !mejor ? <p className="ps-cuerpo" style={{ margin: 0 }}>{t('plan_sin_opciones')}</p> : null}

              {mejor ? (
                <article className="ps-card" style={{ boxShadow: '0 0 0 3px var(--verde), var(--sombra-1)', display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                    <span className="ps-chip ps-chip-favorable">{t('plan_recomendada')}</span>
                    {mejor.puntaje !== null ? <CompatRing porcentaje={aPorcentaje(mejor.puntaje)} /> : null}
                  </div>
                  <span className="ps-contexto">{t('plan_proximo')}</span>
                  <b style={{ fontSize: 24, fontWeight: 800, lineHeight: 1.1 }}>{nombreEspecie(mejor.secuencia[0])}</b>
                  {mejor.secuencia.length > 1 ? (
                    <>
                      <span className="ps-contexto">{t('plan_luego')}</span>
                      <Secuencia especies={mejor.secuencia.slice(1)} />
                    </>
                  ) : null}
                  <span className="ps-nota">{t('plan_cumple')} · {t('plan_temporadas', { n: mejor.temporadas })}</span>
                  <Avisos estrategia={mejor} />
                  <Link to={`/especies/analisis?especie=${encodeURIComponent(mejor.secuencia[0])}`} className="ps-btn" style={{ marginTop: 4 }}>
                    {t('planificar_ver')} {nombreEspecie(mejor.secuencia[0])}
                  </Link>
                </article>
              ) : null}

              {otras.length ? <h3 className="ps-contexto" style={{ margin: '6px 4px 0 4px' }}>{t('plan_otras')}</h3> : null}
              {otras.map((e) => (
                <article key={e.secuencia.join('>') + e.tipo} className="ps-card-plana" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                    <b style={{ fontSize: 17, fontWeight: 800 }}>{e.tipo === 'base' ? t('plan_repetir', { especie: nombreEspecie(e.secuencia[0]) }) : nombreEspecie(e.secuencia[0])}</b>
                    {e.puntaje !== null ? <b style={{ fontSize: 17, fontWeight: 800, color: 'var(--verde)' }}>{t('plan_puntaje', { n: aPorcentaje(e.puntaje) })}</b> : null}
                  </div>
                  <Secuencia especies={e.secuencia} />
                  <span className="ps-nota" style={{ color: e.cumple_reglas ? undefined : 'var(--riesgo-texto)', fontWeight: e.cumple_reglas ? undefined : 800 }}>{e.cumple_reglas ? t('plan_cumple') : t('plan_no_cumple')} · {t('plan_temporadas', { n: e.temporadas })}</span>
                  <Avisos estrategia={e} />
                </article>
              ))}
              {datos ? <p className="ps-nota" style={{ margin: '4px 4px 0 4px' }}>{t('plan_nota')}</p> : null}
            </div>
          </section>
        </>
      )}

      <div className="ps-pad-16" style={{ margin: '14px 16px 12px 16px', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div className="ps-grid-2">
          <Link to="/especies" className="ps-card" style={{ textDecoration: 'none', color: 'var(--carbon)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, fontSize: 16, fontWeight: 800, minHeight: 56 }}>
            {t('planificar_especies')}
          </Link>
          <Link to="/historial" className="ps-card" style={{ textDecoration: 'none', color: 'var(--carbon)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, fontSize: 16, fontWeight: 800, minHeight: 56 }}>
            {t('planificar_historial')}
          </Link>
        </div>
      </div>
    </Screen>
  )
}
