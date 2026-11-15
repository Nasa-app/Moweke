import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Screen, BarraSuperior, Titulo } from '../components/Screen'
import { Chip, type TonoChip } from '../components/Chip'
import { IconoIncendio } from '../components/icons'
import { useSeguimiento } from '../state/useSeguimiento'
import { verParcela, type EventoDano, type Horizonte, type ParcelaDetalle } from '../lib/api'
import { fechaCorta, nombreClave, nombreEfecto, nombreEspecie, nombreFase, nombreHorizonte, numero } from '../lib/formato'
import { useI18n } from '../i18n'

const TONO: Record<Horizonte, TonoChip> = { observado: 'riesgo', pronostico: 'precaucion', estimado: 'neutro' }
const ORDEN: Horizonte[] = ['pronostico', 'observado', 'estimado']
const TITULO: Record<Horizonte, string> = {
  pronostico: 'Viene en el pronóstico',
  observado: 'Ya ocurrió',
  estimado: 'Si el año viene como el pasado',
}

function TarjetaEvento({ evento }: { evento: EventoDano }) {
  const unDia = evento.primer_dia === evento.ultimo_dia
  return (
    <article className="ps-card" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}>
        <h3 style={{ margin: 0, fontWeight: 800, fontSize: 21 }}>{nombreClave(evento.peligro)}</h3>
        <Chip tono={TONO[evento.horizonte]}>{nombreHorizonte(evento.horizonte)}</Chip>
      </div>
      <span style={{ fontSize: 16, fontWeight: 700 }}>{nombreEfecto(evento.efecto)}</span>
      <span className="ps-detalle">
        {unDia ? `El ${fechaCorta(evento.primer_dia)}` : `Del ${fechaCorta(evento.primer_dia)} al ${fechaCorta(evento.ultimo_dia)}`} · {nombreFase(evento.fase).toLowerCase()}
      </span>
    </article>
  )
}

export default function Alertas() {
  const { t } = useI18n()
  const { idParcela, activo, fenologia, aviso, cargando } = useSeguimiento()
  const [parcela, setParcela] = useState<ParcelaDetalle | null>(null)

  useEffect(() => {
    if (!idParcela) return
    let vigente = true
    verParcela(idParcela)
      .then((p) => vigente && setParcela(p))
      .catch(() => vigente && setParcela(null))
    return () => {
      vigente = false
    }
  }, [idParcela])

  const incendios = parcela?.incendios_cercanos
  const focos = [...(incendios?.dias_con_focos ?? [])].reverse()
  const eventos = (fenologia?.fases ?? []).flatMap((f) => f.eventos)

  return (
    <Screen>
      <BarraSuperior volverA="/hoy" />
      <Titulo>{t('alertas_titulo')}</Titulo>

      <h2 style={{ margin: '18px 20px 0 20px', fontSize: 20, fontWeight: 800 }}>{t('alertas_emergencias')}</h2>
      <div className="ps-pad-16" style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 10 }}>
        {focos.length ? (
          focos.slice(0, 5).map((dia) => (
            <article key={dia.fecha} className="ps-card" style={{ boxShadow: '0 0 0 3px var(--riesgo-texto), var(--sombra-1)', display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}>
                <h3 style={{ margin: 0, fontWeight: 800, fontSize: 21 }}>Foco de calor</h3>
                <Chip tono="riesgo">{fechaCorta(dia.fecha)}</Chip>
              </div>
              <span style={{ fontSize: 16, fontWeight: 700 }}>
                {dia.focos} {dia.focos === 1 ? 'detección' : 'detecciones'}
                {dia.distancia_min_km !== null ? ` · la más cercana a ${numero(dia.distancia_min_km, 1)} km` : ''}
              </span>
              <span className="ps-nota">Visto por satélite (NASA FIRMS). No es una alerta oficial: si SENAPRED avisa, sigue esa indicación.</span>
              <a href="tel:132" style={{ minHeight: 48, borderRadius: 14, border: '2px solid var(--riesgo-texto)', color: 'var(--riesgo-texto)', textDecoration: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, fontWeight: 800 }}>
                Bomberos 132
              </a>
            </article>
          ))
        ) : (
          <div className="ps-card-plana" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <IconoIncendio stroke="var(--favorable-texto)" />
            <span style={{ flex: 1, fontSize: 16, fontWeight: 700 }}>
              {!idParcela
                ? 'Marca tu parcela para revisar focos de calor cerca.'
                : !incendios
                  ? t('cargando')
                  : incendios.revisado
                    ? `Sin focos de calor a menos de ${numero(incendios.radio_km)} km entre el ${fechaCorta(incendios.revisado[0])} y el ${fechaCorta(incendios.revisado[1])}.`
                    : 'Los focos de calor todavía no se revisan para esta parcela.'}
            </span>
          </div>
        )}
      </div>

      <h2 style={{ margin: '22px 20px 0 20px', fontSize: 20, fontWeight: 800 }}>
        {t('alertas_cultivo')}
        {activo ? ` · ${nombreEspecie(activo.especie)}` : ''}
      </h2>
      <div className="ps-pad-16" style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 10 }}>
        {cargando ? <p className="ps-nota" style={{ margin: 0 }}>{t('cargando')}</p> : null}
        {!activo && !cargando ? (
          <p className="ps-cuerpo" style={{ margin: 0 }}>
            Sin cultivos en seguimiento. <Link to="/onboarding/cultivos">Agrega qué sembraste</Link>.
          </p>
        ) : null}
        {aviso ? <p className="ps-cuerpo" style={{ margin: 0 }}>{aviso}</p> : null}
        {fenologia && eventos.length === 0 ? (
          <div className="ps-card-plana" style={{ fontSize: 16, fontWeight: 700 }}>
            Sin daños por clima para este cultivo, ni ocurridos ni en el pronóstico hasta el {fechaCorta(fenologia.horizontes.pronostico_hasta)}.
          </div>
        ) : null}
        {ORDEN.map((horizonte) => {
          const delHorizonte = eventos.filter((e) => e.horizonte === horizonte)
          if (!delHorizonte.length) return null
          return (
            <section key={horizonte} aria-label={TITULO[horizonte]} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <h3 className="ps-contexto" style={{ margin: '4px 4px 0 4px' }}>{TITULO[horizonte]}</h3>
              {delHorizonte.map((evento) => (
                <TarjetaEvento key={`${evento.fase}-${evento.peligro}-${evento.efecto}-${evento.primer_dia}`} evento={evento} />
              ))}
            </section>
          )
        })}
      </div>

      <p className="ps-pad ps-nota" style={{ margin: 'auto 0 0 0', padding: '20px 20px 32px 20px' }}>
        Los umbrales de daño de cada etapa son de referencia y todavía no están validados en terreno. El cálculo supone cultivo sin riego.
      </p>
    </Screen>
  )
}
