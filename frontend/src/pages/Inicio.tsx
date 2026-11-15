import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Screen } from '../components/Screen'
import { BottomNav } from '../components/BottomNav'
import { MoonStrip } from '../components/MoonStrip'
import { IconoIncendio, IconoPerfil, IconoSiguiente, IconoTelefono } from '../components/icons'
import { useSeguimiento } from '../state/useSeguimiento'
import { verParcela, type DiaConFocos, type EventoDano } from '../lib/api'
import { aIso, diasEntre, fechaCorta, nombreClave, nombreEfecto, nombreEspecie, nombreFase, nombreHorizonte, numero } from '../lib/formato'
import { useI18n } from '../i18n'

// Un foco de calor se avisa en la portada si es de los últimos días; más viejo queda en Alertas.
const DIAS_FOCO_RECIENTE = 3

export default function Inicio() {
  const { t } = useI18n()
  const { idParcela, cultivos, activo, fenologia, aviso, cargando } = useSeguimiento()
  const [focos, setFocos] = useState<DiaConFocos[]>([])

  useEffect(() => {
    if (!idParcela) return
    let vigente = true
    verParcela(idParcela)
      .then((p) => vigente && setFocos(p.incendios_cercanos.dias_con_focos))
      .catch(() => vigente && setFocos([]))
    return () => {
      vigente = false
    }
  }, [idParcela])

  const [hoy] = useState(() => aIso(new Date()))
  const focoReciente = [...focos].reverse().find((d) => diasEntre(d.fecha, hoy) <= DIAS_FOCO_RECIENTE)
  // Lo que viene: daños que el pronóstico anuncia y todavía no terminan.
  const porVenir: EventoDano[] = (fenologia?.fases ?? [])
    .flatMap((f) => f.eventos)
    .filter((e) => e.horizonte === 'pronostico' && e.ultimo_dia >= hoy)
  const proxima = fenologia?.etapas.find((e) => e.fecha !== null && e.fecha > hoy)

  return (
    <Screen>
      <div style={{ padding: '48px 20px 0 20px', display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <span className="ps-contexto">
            {new Date().toLocaleDateString('es-CL', { weekday: 'long', day: 'numeric', month: 'short' })}
          </span>
          <h1 style={{ margin: 0, fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 30, lineHeight: 1.05 }}>Tu predio</h1>
        </div>
        <Link to="/perfil" aria-label={t('hoy_mi_perfil')} style={{ width: 44, height: 44, borderRadius: 22, background: 'var(--hundido)', color: 'var(--carbon)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <IconoPerfil />
        </Link>
      </div>

      {focoReciente ? (
        <section role="alert" aria-labelledby="emerg" className="ps-banner-emergencia" style={{ margin: '12px 16px 0 16px' }}>
          <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
            <IconoIncendio stroke="#fff" tamano={28} />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <span style={{ fontSize: 14, fontWeight: 700, opacity: 0.9 }}>{t('emergencia_aviso')}</span>
              <h2 id="emerg" style={{ margin: 0, fontSize: 22, fontWeight: 800, lineHeight: 1.1 }}>Foco de calor cerca de tu parcela</h2>
              <span style={{ fontSize: 16, fontWeight: 700 }}>
                {focoReciente.distancia_min_km !== null ? `A ${numero(focoReciente.distancia_min_km, 1)} km · ` : ''}
                visto por satélite el {fechaCorta(focoReciente.fecha)}
              </span>
            </div>
          </div>
          <div className="ps-grid-2">
            <Link to="/alertas" style={{ minHeight: 52, borderRadius: 16, background: '#fff', color: 'var(--riesgo-texto)', textDecoration: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, fontWeight: 800 }}>
              Ver detalle
            </Link>
            <a href="tel:132" style={{ minHeight: 52, borderRadius: 16, border: '2px solid #fff', color: '#fff', textDecoration: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, fontSize: 17, fontWeight: 800 }}>
              <IconoTelefono stroke="#fff" />
              Bomberos 132
            </a>
          </div>
          <span style={{ fontSize: 14, fontWeight: 700, opacity: 0.95 }}>No es una alerta oficial. Si SENAPRED avisa, sigue esa indicación.</span>
        </section>
      ) : null}

      <div className="ps-pad-16" style={{ marginTop: 14, textAlign: 'center' }}>
        {!idParcela ? (
          <>
            <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800, lineHeight: 1.1 }}>Todavía no marcaste tu parcela</h2>
            <p style={{ margin: '4px 0 0', fontSize: 16, fontWeight: 700, color: 'var(--texto-tenue)' }}>
              <Link to="/terreno/perimetro">Marca tu parcela</Link> para ver su clima y qué sembrar.
            </p>
          </>
        ) : activo ? (
          <>
            <h2 style={{ margin: 0, fontSize: 26, fontWeight: 800, lineHeight: 1.1 }}>
              {nombreEspecie(activo.especie)}
              {fenologia?.fase_actual ? `: ${nombreFase(fenologia.fase_actual).toLowerCase()}` : ''}
            </h2>
            <p style={{ margin: '4px 0 0', fontSize: 17, fontWeight: 700, color: 'var(--texto-tenue)' }}>
              {activo.fecha_siembra > hoy ? 'Siembra planeada para el' : 'Sembrado el'} {fechaCorta(activo.fecha_siembra)}
              {proxima?.fecha ? ` · ${nombreClave(proxima.etapa).toLowerCase()} hacia el ${fechaCorta(proxima.fecha)}` : ''}
            </p>
            {aviso ? <p className="ps-nota" style={{ margin: '6px 0 0' }}>{aviso}</p> : null}
          </>
        ) : cultivos ? (
          <>
            <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800, lineHeight: 1.1 }}>Todavía no tienes cultivos</h2>
            <p style={{ margin: '4px 0 0', fontSize: 16, fontWeight: 700, color: 'var(--texto-tenue)' }}>
              <Link to="/onboarding/cultivos">Agrega qué sembraste</Link> o mira <Link to="/especies">qué conviene sembrar</Link>.
            </p>
          </>
        ) : null}
        {cargando ? <p className="ps-nota">{t('cargando')}</p> : null}
      </div>

      {porVenir.length ? (
        <Link to="/alertas" className="ps-card" style={{ margin: '14px 16px 0 16px', textDecoration: 'none', color: 'var(--carbon)', display: 'flex', alignItems: 'center', gap: 12, boxShadow: '0 0 0 2px var(--semaforo-amarillo), var(--sombra-1)' }}>
          <span style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <span className="ps-contexto">{nombreHorizonte('pronostico')}</span>
            <span style={{ fontSize: 19, fontWeight: 800, lineHeight: 1.15 }}>
              {nombreClave(porVenir[0].peligro)} hacia el {fechaCorta(porVenir[0].primer_dia)}
            </span>
            <span className="ps-detalle">
              {nombreEfecto(porVenir[0].efecto)}
              {porVenir.length > 1 ? ` · y ${porVenir.length - 1} más` : ''}
            </span>
          </span>
          <IconoSiguiente stroke="var(--precaucion-texto)" />
        </Link>
      ) : null}

      {idParcela ? (
        <div className="ps-grid-2" style={{ margin: '14px 16px 0 16px' }}>
          <Link to="/clima" className="ps-card" style={{ textDecoration: 'none', color: 'var(--carbon)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 17, fontWeight: 800, minHeight: 56 }}>
            {t('clima_titulo')}
          </Link>
          <Link to="/alertas" className="ps-card" style={{ textDecoration: 'none', color: 'var(--carbon)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 17, fontWeight: 800, minHeight: 56 }}>
            {t('alertas_titulo')}
          </Link>
        </div>
      ) : null}

      <MoonStrip />

      <BottomNav />
    </Screen>
  )
}
