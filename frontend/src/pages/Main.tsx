import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Screen } from '../components/Screen'
import { Chip } from '../components/Chip'
import { IconoCheck } from '../components/icons'
import { RegistroCultivo } from '../components/RegistroCultivo'
import { ReportesCultivo } from '../components/ReportesCultivo'
import { useSeguimiento } from '../state/useSeguimiento'
import { nombreVariedad } from '../lib/nombres'
import { aIso, aPorcentaje, diasEntre, fechaCorta, nombreClave, nombreEspecie, nombreFase, nombreHorizonte, numero } from '../lib/formato'
import { useI18n } from '../i18n'

export default function Main() {
  const { t } = useI18n()
  const { idParcela, cultivos, activo, fenologia, aviso, cargando, setCultivoActivo, recargar } = useSeguimiento()

  const [hoy] = useState(() => aIso(new Date()))
  const etapas = fenologia ? [{ etapa: 'siembra', fecha: fenologia.siembra, horizonte: null }, ...fenologia.etapas] : []
  const proxima = fenologia?.etapas.find((e) => e.fecha !== null && e.fecha > hoy)
  const faseActual = fenologia?.fases.find((f) => f.estado === 'en_curso')
  const perdida = fenologia ? (fenologia.perdida_proyectada ?? fenologia.perdida_con_pronostico) : null
  const diasDesdeSiembra = activo ? diasEntre(activo.fecha_siembra, hoy) : 0
  const eventos = fenologia?.fases.flatMap((f) => f.eventos).length ?? 0

  return (
    <Screen>
      <div style={{ padding: '48px 16px 0 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <h1 style={{ margin: 0, fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 30, lineHeight: 1 }}>{t('cultivo_titulo')}</h1>
        <Link to="/especies" className="ps-btn-texto" style={{ fontSize: 16, fontWeight: 800, color: 'var(--verde)' }}>
          {t('main_agregar')}
        </Link>
      </div>

      {cultivos && cultivos.length > 0 ? (
        <div role="tablist" aria-label={t('inicio_cultivo_aria')} className="ps-pad-16" style={{ marginTop: 12, display: 'flex', gap: 6, overflowX: 'auto' }}>
          {cultivos.map((c) => (
            <button
              key={c.id}
              type="button"
              role="tab"
              aria-selected={activo?.id === c.id}
              onClick={() => setCultivoActivo(c.id, c.especie)}
              className={`ps-pill ${activo?.id === c.id ? 'activo' : ''}`}
              style={{ padding: '0 16px', minHeight: 44, flexShrink: 0 }}
            >
              {nombreEspecie(c.especie)} · {fechaCorta(c.fecha_siembra)}
            </button>
          ))}
        </div>
      ) : null}

      {!activo ? (
        <p className="ps-pad ps-cuerpo" style={{ margin: '16px 0 0 0' }}>
          {cargando ? (
            t('cargando')
          ) : !idParcela ? (
            <>
              {t('inicio_sin_parcela_titulo')}. <Link to="/terreno/perimetro">{t('inicio_sin_parcela_link')}</Link>.
            </>
          ) : (
            <>
              {t('inicio_sin_cultivos_titulo')}. <Link to="/onboarding/cultivos">{t('inicio_agrega_sembraste')}</Link>.
            </>
          )}
        </p>
      ) : (
        <>
          <div className="ps-pad-16" style={{ marginTop: 14, display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 24, fontWeight: 800 }}>{nombreEspecie(activo.especie)}</span>
            {activo.variedad_local ? <span style={{ fontSize: 16, color: 'var(--texto-tenue)' }}>{nombreVariedad(activo.especie, activo.variedad_local)}</span> : null}
            {fenologia?.fase_actual ? <Chip tono="acento">{nombreFase(fenologia.fase_actual)}</Chip> : null}
            {fenologia?.estado === 'perdido' ? <Chip tono="riesgo">{t('main_perdido')}</Chip> : null}
          </div>

          {aviso ? (
            <p className="ps-pad ps-cuerpo" role="status" style={{ margin: '10px 0 0 0' }}>
              {aviso}
            </p>
          ) : null}
          {cargando ? <p className="ps-pad ps-nota" style={{ margin: '10px 0 0 0' }}>{t('cargando')}</p> : null}

          {fenologia ? (
            <>
              <ol aria-label={t('cultivo_fases')} className="ps-pad-16" style={{ margin: '16px 0 0 0', listStyle: 'none', display: 'grid', gridTemplateColumns: `repeat(${etapas.length}, minmax(0, 1fr))`, gap: 4 }}>
                {etapas.map((etapa) => {
                  const alcanzada = etapa.fecha !== null && etapa.fecha <= hoy
                  const siguiente = etapa === proxima
                  return (
                    <li key={etapa.etapa} aria-current={siguiente ? 'step' : undefined} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, textAlign: 'center' }}>
                      <span
                        aria-hidden="true"
                        style={{
                          width: 48,
                          height: 48,
                          borderRadius: 24,
                          boxSizing: 'border-box',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          background: alcanzada ? 'var(--verde)' : siguiente ? '#fff' : 'var(--hundido)',
                          boxShadow: siguiente ? '0 0 0 3px var(--verde)' : undefined,
                          border: !alcanzada && !siguiente ? '2px dashed var(--borde-control)' : 'none',
                        }}
                      >
                        {alcanzada ? <IconoCheck tamano={22} stroke="#fff" /> : null}
                      </span>
                      <span style={{ fontSize: 14, fontWeight: 800, lineHeight: 1.1, color: alcanzada || siguiente ? 'var(--verde)' : undefined }}>{nombreClave(etapa.etapa)}</span>
                      <span className="ps-nota" style={{ lineHeight: 1.1 }}>{etapa.fecha ? fechaCorta(etapa.fecha) : t('main_sin_fecha')}</span>
                    </li>
                  )
                })}
              </ol>
              <p className="ps-pad ps-nota" style={{ margin: '8px 0 0 0' }}>
                {t('main_horizontes', { obs: fechaCorta(fenologia.horizontes.observado_hasta), pron: fechaCorta(fenologia.horizontes.pronostico_hasta) })}
              </p>

              <div className="ps-pad-16" style={{ marginTop: 14, display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 8 }}>
                <div className="ps-card" style={{ textAlign: 'center', padding: 12 }}>
                  <span style={{ display: 'block', fontSize: 21, fontWeight: 800 }}>{proxima?.fecha ? fechaCorta(proxima.fecha) : '—'}</span>
                  <span className="ps-nota">{proxima ? `${nombreClave(proxima.etapa)} · ${nombreHorizonte(proxima.horizonte).toLowerCase()}` : t('main_ciclo_completo')}</span>
                </div>
                <div className="ps-card" style={{ textAlign: 'center', padding: 12 }}>
                  <span style={{ display: 'block', fontSize: 21, fontWeight: 800 }}>{diasDesdeSiembra >= 0 ? diasDesdeSiembra : t('main_en_dias', { n: -diasDesdeSiembra })}</span>
                  <span className="ps-nota">{diasDesdeSiembra >= 0 ? t('main_dias_desde_siembra') : t('main_dias_para_sembrar')}</span>
                </div>
                <Link to="/alertas" className="ps-card" style={{ textAlign: 'center', padding: 12, textDecoration: 'none', color: 'var(--carbon)' }}>
                  <span style={{ display: 'block', fontSize: 21, fontWeight: 800 }}>{perdida !== null ? `${aPorcentaje(perdida)}%` : '—'}</span>
                  <span className="ps-nota">{eventos ? t(eventos === 1 ? 'main_perdida_avisos_uno' : 'main_perdida_avisos_otros', { n: eventos }) : t('main_perdida_estimada')}</span>
                </Link>
              </div>

              {faseActual?.condiciones ? (
                <section aria-labelledby="condiciones" className="ps-pad-16" style={{ marginTop: 14 }}>
                  <div className="ps-card-plana" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <h2 id="condiciones" className="ps-h2">
                      {t('main_en_esta_etapa', { fecha: fechaCorta(faseActual.inicio) })}
                    </h2>
                    <dl style={{ margin: 0, display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 8 }}>
                      {(
                        [
                          [t('main_noche_fria'), `${numero(faseActual.condiciones.tmin_mas_baja, 1)}°`],
                          [t('main_dia_calido'), `${numero(faseActual.condiciones.tmax_mas_alta, 1)}°`],
                          [t('main_lluvia'), `${numero(faseActual.condiciones.lluvia_mm)} mm`],
                          [t('main_humedad_aire'), faseActual.condiciones.humedad_relativa_media !== null ? `${numero(faseActual.condiciones.humedad_relativa_media)}%` : '—'],
                        ] as const
                      ).map(([etiqueta, valor]) => (
                        <div key={etiqueta} style={{ display: 'flex', flexDirection: 'column-reverse' }}>
                          <dt className="ps-nota">{etiqueta}</dt>
                          <dd style={{ margin: 0, fontSize: 20, fontWeight: 800 }}>{valor}</dd>
                        </div>
                      ))}
                    </dl>
                    <span className="ps-nota">{t('main_incluye_dias')}</span>
                  </div>
                </section>
              ) : null}
            </>
          ) : null}

          <RegistroCultivo key={activo.id} idCultivo={activo.id} onCambio={recargar} />
          <ReportesCultivo key={`r${activo.id}`} idCultivo={activo.id} />

          <div className="ps-pad-16" style={{ marginTop: 16, display: 'flex', gap: 8 }}>
            <Link to="/reportar" className="ps-btn" style={{ flex: 1 }}>
              {t('cultivo_reportar')}
            </Link>
            <Link to="/fuentes" aria-label={t('cultivo_fuentes')} className="ps-btn-secundario" style={{ width: 56, minHeight: 56, padding: 0, flex: '0 0 auto', textDecoration: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              i
            </Link>
          </div>
        </>
      )}
    </Screen>
  )
}
