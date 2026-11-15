import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Screen } from '../components/Screen'
import { BottomNav } from '../components/BottomNav'
import { MoonStrip } from '../components/MoonStrip'
import { EscenaTerreno } from '../components/EscenaTerreno'
import { SelectorCultivos } from '../components/SelectorCultivos'
import { SenalesLocales } from '../components/SenalesLocales'
import { TarjetaRiego } from '../components/TarjetaRiego'
import { IconoCalor, IconoCampana, IconoHelada, IconoIncendio, IconoInundacion, IconoLluvia, IconoPerfil, IconoSequia, IconoSiguiente, IconoTelefono } from '../components/icons'
import { useSeguimiento } from '../state/useSeguimiento'
import { climaParcela, verParcela, type DiaClima, type DiaConFocos, type EventoDano } from '../lib/api'
import { cieloDelDia } from '../lib/tiempo'
import { aIso, diasEntre, fechaCorta, nombreClave, nombreEfecto, nombreEspecie, nombreFase, nombreHorizonte, numero } from '../lib/formato'
import { fasesLunares } from '../lib/luna'
import { useI18n } from '../i18n'

// Un foco de calor se avisa en la portada si es de los últimos días; más viejo queda en Alertas.
const DIAS_FOCO_RECIENTE = 3

export default function Inicio() {
  const { t } = useI18n()
  const { idParcela, cultivos, activo, fenologia, aviso, cargando, recargar, setCultivoActivo } = useSeguimiento()
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
  const [diaClima, setDiaClima] = useState<DiaClima | null>(null)

  // El tiempo de hoy en el predio, de la misma serie diaria que la pantalla de Clima.
  useEffect(() => {
    if (!idParcela) return
    let vigente = true
    climaParcela(idParcela, 2)
      .then((c) => vigente && setDiaClima(c.dias.find((d) => d.fecha === c.hoy) ?? null))
      .catch(() => vigente && setDiaClima(null))
    return () => {
      vigente = false
    }
  }, [idParcela])
  const focoReciente = [...focos].reverse().find((d) => diasEntre(d.fecha, hoy) <= DIAS_FOCO_RECIENTE)
  // Lo que viene: daños que el pronóstico anuncia y todavía no terminan.
  const porVenir: EventoDano[] = (fenologia?.fases ?? [])
    .flatMap((f) => f.eventos)
    .filter((e) => e.horizonte === 'pronostico' && e.ultimo_dia >= hoy)
  // Avisos vigentes, cada uno con su ícono: un foco de calor reciente y los daños que anuncia el pronóstico.
  const ICONO_PELIGRO: Record<string, typeof IconoCampana> = {
    helada: IconoHelada, calor: IconoCalor, sequia: IconoSequia, anegamiento: IconoInundacion, tizon: IconoLluvia,
  }
  const alertas: { clave: string; nombre: string; Icono: typeof IconoCampana }[] = []
  if (focoReciente) alertas.push({ clave: 'incendio', nombre: 'Foco de calor cerca', Icono: IconoIncendio })
  for (const e of porVenir) {
    if (!alertas.some((a) => a.clave === e.peligro)) alertas.push({ clave: e.peligro, nombre: nombreClave(e.peligro), Icono: ICONO_PELIGRO[e.peligro] ?? IconoCampana })
  }
  const cielo = diaClima ? cieloDelDia(diaClima.codigo_tiempo, diaClima.lluvia_mm) : null
  const etapas = fenologia?.etapas ?? []
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
          <span style={{ fontSize: 14, fontWeight: 700, opacity: 0.95 }}>No es una alerta oficial. Si ves humo o fuego, llama a Bomberos al 132. Si SENAPRED avisa, sigue sus indicaciones.</span>
        </section>
      ) : null}

      <div style={{ position: 'relative', margin: '8px 16px 0 16px' }}>
        <EscenaTerreno conCultivo={activo !== null} etiqueta="Ilustración de tu predio con casa, árboles y tu terreno de cultivo" />
        {diaClima && (diaClima.tmax !== null || cielo) ? (
          <Link
            to="/clima"
            aria-label={`Hoy${cielo ? `: ${cielo.texto.toLowerCase()}` : ''}${diaClima.tmax !== null ? `, máxima ${numero(diaClima.tmax)} grados` : ''}${diaClima.tmin !== null ? `, mínima ${numero(diaClima.tmin)} grados` : ''}. Ver el clima`}
            style={{ position: 'absolute', top: '3%', left: '4%', minHeight: 48, padding: '4px 14px 4px 10px', borderRadius: 24, background: 'var(--blanco)', boxShadow: 'var(--sombra-1)', color: 'var(--carbon)', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 8 }}
          >
            {cielo ? <span style={{ color: 'var(--agua)', display: 'flex' }}><cielo.Icono tamano={28} /></span> : null}
            <span style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.05 }}>
              <span style={{ fontSize: 18, fontWeight: 800 }}>
                {diaClima.tmax !== null ? `${numero(diaClima.tmax)}°` : ''}
                {diaClima.tmin !== null ? <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--texto-tenue)' }}> / {numero(diaClima.tmin)}°</span> : null}
              </span>
              {cielo ? <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--texto-tenue)' }}>{cielo.texto}</span> : null}
            </span>
          </Link>
        ) : null}
        {alertas.length ? (
          <Link
            to="/alertas"
            aria-label={`Avisos vigentes: ${alertas.map((a) => a.nombre).join(', ')}. Ver detalle`}
            style={{ position: 'absolute', top: '9%', right: '4%', minHeight: 48, padding: '4px 12px', borderRadius: 24, background: 'var(--blanco)', boxShadow: 'var(--sombra-1)', color: 'var(--riesgo-texto)', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 8 }}
          >
            {alertas.slice(0, 3).map(({ clave, Icono }) => (
              <Icono key={clave} tamano={26} />
            ))}
            {alertas.length > 3 ? <span style={{ fontSize: 15, fontWeight: 800 }}>+{alertas.length - 3}</span> : null}
          </Link>
        ) : null}
        <span style={{ position: 'absolute', left: '4%', bottom: '10%', minHeight: 30, padding: '0 12px', borderRadius: 15, background: 'var(--blanco)', boxShadow: 'var(--sombra-1)', fontSize: 15, fontWeight: 800, display: 'flex', alignItems: 'center' }}>
          Luna {fasesLunares().fases[fasesLunares().actual].nombre.toLowerCase()}
        </span>
        {activo ? (
          <span style={{ position: 'absolute', left: '24%', top: '52%', minHeight: 30, padding: '0 12px', borderRadius: 15, background: 'var(--blanco)', boxShadow: 'var(--sombra-1)', fontSize: 15, fontWeight: 800, display: 'flex', alignItems: 'center' }}>
            {nombreEspecie(activo.especie)}
          </span>
        ) : null}
      </div>

      <SelectorCultivos cultivos={cultivos} activo={activo} onElegir={setCultivoActivo} />

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
            {etapas.length ? (
              <ol aria-label="Etapas del cultivo" style={{ margin: '14px 0 0', padding: 0, listStyle: 'none', display: 'grid', gridTemplateColumns: `repeat(${etapas.length}, minmax(0, 1fr))`, gap: 6 }}>
                {etapas.map((e, i) => {
                  const pasada = e.fecha !== null && e.fecha <= hoy
                  const actual = !pasada && (i === 0 || etapas[i - 1].fecha !== null && etapas[i - 1].fecha! <= hoy)
                  return (
                    <li key={e.etapa} aria-current={actual ? 'step' : undefined} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <span aria-hidden="true" style={{ height: 8, borderRadius: 4, background: pasada ? 'var(--verde)' : actual ? 'var(--menta)' : 'var(--hundido)' }} />
                      <span style={{ fontSize: 14, fontWeight: actual || pasada ? 800 : 600, color: actual ? 'var(--verde)' : 'var(--texto-tenue)', lineHeight: 1.1 }}>
                        {nombreClave(e.etapa)}
                        <span className="visually-hidden">{pasada ? ' (ya pasó)' : actual ? ' (ahora)' : ''}</span>
                      </span>
                    </li>
                  )
                })}
              </ol>
            ) : null}
            <Link to="/reportar" className="ps-btn-secundario" style={{ marginTop: 18, width: '100%', boxSizing: 'border-box', minHeight: 56, display: 'flex', alignItems: 'center', justifyContent: 'center', textDecoration: 'none' }}>
              Cuéntanos cómo va
            </Link>
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

      {activo && fenologia ? (
        <TarjetaRiego riego={fenologia.riego} idCultivo={activo.id} hoy={fenologia.hoy} onCambio={recargar} />
      ) : null}

      {idParcela ? <SenalesLocales idParcela={idParcela} /> : null}

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
