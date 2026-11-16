import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Screen } from '../components/Screen'
import { alertasClimaParcela, climaZona, type AlertasClima, type ClimaZona } from '../lib/api'
import { COMUNA_POR_DEFECTO, useComunas } from '../lib/comunas'
import { diaSemana, fechaCorta, numero, textoAlertaClima } from '../lib/formato'
import { cieloDelDia } from '../lib/tiempo'
import { Chip } from '../components/Chip'
import { useAuth } from '../state/AuthContext'
import { usePredio } from '../state/PredioContext'
import { useI18n } from '../i18n'

// El tiempo de la comuna sin necesidad de registro: comunas y pronóstico vienen del API (/api/zonas).
export default function Explorar() {
  const { t } = useI18n()
  const { autenticado } = useAuth()
  const { idParcela } = usePredio()
  const [alertas, setAlertas] = useState<AlertasClima | null>(null)
  const [alertasFallan, setAlertasFallan] = useState(false)
  const [comuna, setComuna] = useState(COMUNA_POR_DEFECTO)
  const { comunas } = useComunas()
  const [clima, setClima] = useState<ClimaZona | null>(null)
  const [falla, setFalla] = useState(false)

  useEffect(() => {
    let vigente = true
    setClima(null)
    setFalla(false)
    climaZona(comuna)
      .then((c) => vigente && setClima(c))
      .catch(() => vigente && setFalla(true))
    return () => {
      vigente = false
    }
  }, [comuna])

  useEffect(() => {
    if (!idParcela || !autenticado) return
    let vigente = true
    alertasClimaParcela(idParcela)
      .then((a) => vigente && setAlertas(a))
      .catch(() => vigente && setAlertasFallan(true))
    return () => {
      vigente = false
    }
  }, [idParcela, autenticado])

  const cielo = clima ? cieloDelDia(clima.codigo_tiempo, clima.lluvia_hoy_mm) : null

  return (
    <Screen>
      <section aria-labelledby="zona" style={{ padding: '48px 16px 16px 16px', borderRadius: '0 0 32px 32px', background: 'var(--verde)', color: '#fff', display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
          <label style={{ minHeight: 44, padding: '0 12px 0 10px', borderRadius: 22, background: 'rgba(255,255,255,.14)', display: 'flex', alignItems: 'center', gap: 6, fontSize: 16, fontWeight: 800, cursor: 'pointer' }}>
            <span className="visually-hidden">{t('onb_comuna')}</span>
            <select value={comuna} onChange={(e) => setComuna(e.target.value)} style={{ appearance: 'none', border: 'none', background: 'transparent', color: '#fff', font: "800 16px 'Alegreya Sans', sans-serif", cursor: 'pointer' }}>
              {(comunas.some((z) => z.nombre === comuna) ? comunas : [{ nombre: comuna }, ...comunas]).map(({ nombre: c }) => (
                <option key={c} value={c} style={{ color: '#000' }}>
                  {c}
                </option>
              ))}
            </select>
          </label>
          <span style={{ fontSize: 15, fontWeight: 700, opacity: 0.9 }}>{clima ? t('explorar_hoy_fecha', { fecha: fechaCorta(clima.hoy) }) : ''}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <h1 id="zona" style={{ margin: 0, fontSize: 56, fontWeight: 800, lineHeight: 1 }}>
              {clima ? `${numero(clima.temperatura_c)}°` : '—'}
            </h1>
            <span style={{ fontSize: 17, fontWeight: 700 }}>{cielo?.texto ?? (falla ? t('explorar_sin_datos', { comuna }) : '')}</span>
          </div>
        </div>
        <dl style={{ margin: 0, padding: '10px 6px', borderRadius: 20, background: 'rgba(255,255,255,.12)', display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', textAlign: 'center' }}>
          <div style={{ display: 'flex', flexDirection: 'column-reverse', gap: 2 }}>
            <dt style={{ fontSize: 14, fontWeight: 700, opacity: 0.9 }}>{t('explorar_humedad')}</dt>
            <dd style={{ margin: 0, fontSize: 20, fontWeight: 800 }}>{clima ? `${numero(clima.humedad_relativa)}%` : '—'}</dd>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column-reverse', gap: 2, borderLeft: '1px solid rgba(255,255,255,.25)', borderRight: '1px solid rgba(255,255,255,.25)' }}>
            <dt style={{ fontSize: 14, fontWeight: 700, opacity: 0.9 }}>{t('explorar_lluvia')}</dt>
            <dd style={{ margin: 0, fontSize: 20, fontWeight: 800 }}>{clima ? `${numero(clima.lluvia_hoy_mm, 1)} mm` : '—'}</dd>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column-reverse', gap: 2 }}>
            <dt style={{ fontSize: 14, fontWeight: 700, opacity: 0.9 }}>{t('explorar_viento')}</dt>
            <dd style={{ margin: 0, fontSize: 20, fontWeight: 800 }}>{clima ? `${numero(clima.viento_kmh)} km/h` : '—'}</dd>
          </div>
        </dl>
      </section>

      <h2 className="ps-h2" style={{ margin: '20px 20px 0 20px' }}>
        {t('lo_nuevo_zona')}
      </h2>
      <div className="ps-grid-2 ps-pad-16" style={{ marginTop: 10 }}>
        {clima ? (
          <Link to="/fuentes" className="ps-card" style={{ textDecoration: 'none', color: 'var(--carbon)', display: 'flex', flexDirection: 'column', gap: 8 }}>
            <span className="ps-chip ps-chip-clima" style={{ alignSelf: 'flex-start' }}>
              {t('explorar_pronostico')}
            </span>
            <span className="ps-detalle">{t('explorar_nov_heladas')}</span>
            <b style={{ fontSize: 22, fontWeight: 800, lineHeight: 1 }}>
              {clima.primera_helada ? t('explorar_helada_dia', { dia: diaSemana(clima.primera_helada) }) : t('explorar_helada_ninguna')}
            </b>
          </Link>
        ) : null}
      </div>

      {idParcela && autenticado ? (
        <section aria-labelledby="alertas-parcela" style={{ marginTop: 20 }}>
          <div style={{ margin: '0 20px', display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8 }}>
            <h2 id="alertas-parcela" className="ps-h2" style={{ margin: 0 }}>
              {t('explorar_alertas_titulo')}
            </h2>
            <Link to="/alertas">{t('explorar_alertas_ver')}</Link>
          </div>
          <div className="ps-pad-16" style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {alertas?.alertas.map((a) => {
              const { titulo, cifra } = textoAlertaClima(a)
              return (
                <Link key={`${a.tipo}-${a.primer_dia}`} to="/alertas" className="ps-card" style={{ textDecoration: 'none', color: 'var(--carbon)', display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}>
                    <b style={{ fontSize: 19, fontWeight: 800 }}>{titulo}</b>
                    <Chip tono={a.fuerte ? 'riesgo' : 'precaucion'}>{a.primer_dia === a.ultimo_dia ? fechaCorta(a.primer_dia) : `${fechaCorta(a.primer_dia)} – ${fechaCorta(a.ultimo_dia)}`}</Chip>
                  </div>
                  <span className="ps-detalle">{cifra}</span>
                </Link>
              )
            })}
            {alertas && alertas.hay_datos && alertas.alertas.length === 0 ? (
              <div className="ps-card-plana" style={{ fontSize: 16, fontWeight: 700 }}>{t('explorar_alertas_ninguna', { fecha: fechaCorta(alertas.hasta ?? alertas.hoy) })}</div>
            ) : null}
            {alertas && !alertas.hay_datos ? <p className="ps-nota" style={{ margin: 0 }}>{t('explorar_alertas_sin_datos')}</p> : null}
            {alertasFallan ? <p className="ps-nota" style={{ margin: 0 }}>{t('explorar_alertas_fallo')}</p> : null}
            {!alertas && !alertasFallan ? <p className="ps-nota" style={{ margin: 0 }}>{t('cargando')}</p> : null}
          </div>
        </section>
      ) : null}

      {clima ? (
        <p className="ps-nota" style={{ margin: '10px 20px 0 20px' }}>
          {t('explorar_fuente_1')} <a href="https://open-meteo.com/" target="_blank" rel="noopener noreferrer">Open-Meteo.com</a> (CC BY 4.0)
        </p>
      ) : null}

      <section aria-labelledby="cta-predio" className="ps-pad-16" style={{ margin: '16px 16px 0 16px', padding: 14, borderRadius: 24, background: 'var(--menta)', display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <h2 id="cta-predio" className="ps-h2">
            {t('datos_predio')}
          </h2>
          <span className="ps-contexto">{t('analisis_terreno')}</span>
        </div>
      </section>

      <div style={{ marginTop: 'auto', padding: '18px 16px 32px 16px', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <Link to={autenticado ? '/onboarding/predio' : '/sesion'} className="ps-btn">
          {t('agregar_predio')}
        </Link>
        <Link to="/hoy" className="ps-btn-texto">
          {t('seguir_mirando')}
        </Link>
      </div>
    </Screen>
  )
}
