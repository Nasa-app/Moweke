import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Screen, BarraSuperior, Titulo } from '../components/Screen'
import { Chip, type TonoChip } from '../components/Chip'
import { IconoIncendio } from '../components/icons'
import { useSeguimiento } from '../state/useSeguimiento'
import { alertasClimaParcela, verParcela, type AlertasClima, type EventoDano, type Horizonte, type ParcelaDetalle } from '../lib/api'
import { fechaCorta, nombreClave, nombreEfecto, nombreEspecie, nombreFase, nombreHorizonte, numero, textoAlertaClima } from '../lib/formato'
import { useI18n } from '../i18n'

const TONO: Record<Horizonte, TonoChip> = { observado: 'riesgo', pronostico: 'precaucion', estimado: 'neutro' }
const ORDEN: Horizonte[] = ['pronostico', 'observado', 'estimado']
function TarjetaEvento({ evento }: { evento: EventoDano }) {
  const { t } = useI18n()
  const unDia = evento.primer_dia === evento.ultimo_dia
  return (
    <article className="ps-card" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}>
        <h3 style={{ margin: 0, fontWeight: 800, fontSize: 21 }}>{nombreClave(evento.peligro)}</h3>
        <Chip tono={TONO[evento.horizonte]}>{nombreHorizonte(evento.horizonte)}</Chip>
      </div>
      <span style={{ fontSize: 16, fontWeight: 700 }}>{nombreEfecto(evento.efecto)}</span>
      <span className="ps-detalle">
        {unDia ? t('alertas_el_dia', { fecha: fechaCorta(evento.primer_dia) }) : t('alertas_del_al', { desde: fechaCorta(evento.primer_dia), hasta: fechaCorta(evento.ultimo_dia) })} · {nombreFase(evento.fase).toLowerCase()}
      </span>
    </article>
  )
}

export default function Alertas() {
  const { t } = useI18n()
  const { idParcela, activo, fenologia, aviso, cargando } = useSeguimiento()
  const [parcela, setParcela] = useState<ParcelaDetalle | null>(null)
  const [clima, setClima] = useState<AlertasClima | null>(null)
  const [climaFalla, setClimaFalla] = useState(false)

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

  useEffect(() => {
    if (!idParcela) return
    let vigente = true
    alertasClimaParcela(idParcela)
      .then((a) => vigente && setClima(a))
      .catch(() => vigente && setClimaFalla(true))
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
                <h3 style={{ margin: 0, fontWeight: 800, fontSize: 21 }}>{t('alertas_foco_titulo')}</h3>
                <Chip tono="riesgo">{fechaCorta(dia.fecha)}</Chip>
              </div>
              <span style={{ fontSize: 16, fontWeight: 700 }}>
                {t(dia.focos === 1 ? 'alertas_focos_uno' : 'alertas_focos_otros', { n: dia.focos })}
                {dia.distancia_min_km !== null ? t('alertas_la_mas_cercana', { km: numero(dia.distancia_min_km, 1) }) : ''}
              </span>
              <span className="ps-nota">{t('alertas_foco_nota')}</span>
              <a href="tel:132" style={{ minHeight: 48, borderRadius: 14, border: '2px solid var(--riesgo-texto)', color: 'var(--riesgo-texto)', textDecoration: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16, fontWeight: 800 }}>
                {t('inicio_bomberos')}
              </a>
            </article>
          ))
        ) : (
          <div className="ps-card-plana" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <IconoIncendio stroke="var(--favorable-texto)" />
            <span style={{ flex: 1, fontSize: 16, fontWeight: 700 }}>
              {!idParcela
                ? t('alertas_marca_parcela')
                : !incendios
                  ? t('cargando')
                  : incendios.revisado
                    ? t('alertas_sin_focos', { km: numero(incendios.radio_km), desde: fechaCorta(incendios.revisado[0]), hasta: fechaCorta(incendios.revisado[1]) })
                    : t('alertas_focos_sin_revisar')}
            </span>
          </div>
        )}
      </div>

      <h2 style={{ margin: '22px 20px 0 20px', fontSize: 20, fontWeight: 800 }}>{t('alertas_clima_titulo')}</h2>
      <div className="ps-pad-16" style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 10 }}>
        {!idParcela ? <p className="ps-nota" style={{ margin: 0 }}>{t('alertas_marca_parcela')}</p> : null}
        {clima?.alertas.map((a) => {
          const { titulo, cifra } = textoAlertaClima(a)
          return (
            <article key={`${a.tipo}-${a.primer_dia}`} className="ps-card" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}>
                <h3 style={{ margin: 0, fontWeight: 800, fontSize: 21 }}>{titulo}</h3>
                <Chip tono={a.fuerte ? 'riesgo' : 'precaucion'}>{nombreHorizonte(a.horizonte)}</Chip>
              </div>
              <span style={{ fontSize: 16, fontWeight: 700 }}>{cifra}</span>
              <span className="ps-detalle">
                {a.primer_dia === a.ultimo_dia ? t('alertas_el_dia', { fecha: fechaCorta(a.primer_dia) }) : t('alertas_del_al', { desde: fechaCorta(a.primer_dia), hasta: fechaCorta(a.ultimo_dia) })}
              </span>
            </article>
          )
        })}
        {clima?.hay_datos && clima.alertas.length === 0 ? (
          <div className="ps-card-plana" style={{ fontSize: 16, fontWeight: 700 }}>
            {t('explorar_alertas_ninguna', { fecha: fechaCorta(clima.hasta ?? clima.hoy) })}
          </div>
        ) : null}
        {clima && !clima.hay_datos ? <p className="ps-nota" style={{ margin: 0 }}>{t('explorar_alertas_sin_datos')}</p> : null}
        {climaFalla ? <p className="ps-nota" style={{ margin: 0 }}>{t('explorar_alertas_fallo')}</p> : null}
        {idParcela && !clima && !climaFalla ? <p className="ps-nota" style={{ margin: 0 }}>{t('cargando')}</p> : null}
      </div>

      <h2 style={{ margin: '22px 20px 0 20px', fontSize: 20, fontWeight: 800 }}>
        {t('alertas_cultivo')}
        {activo ? ` · ${nombreEspecie(activo.especie)}` : ''}
      </h2>
      <div className="ps-pad-16" style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 10 }}>
        {cargando ? <p className="ps-nota" style={{ margin: 0 }}>{t('cargando')}</p> : null}
        {!activo && !cargando ? (
          <p className="ps-cuerpo" style={{ margin: 0 }}>
            {t('alertas_sin_cultivos')} <Link to="/cultivo">{t('inicio_agrega_sembraste')}</Link>.
          </p>
        ) : null}
        {aviso ? <p className="ps-cuerpo" style={{ margin: 0 }}>{aviso}</p> : null}
        {fenologia && eventos.length === 0 ? (
          <div className="ps-card-plana" style={{ fontSize: 16, fontWeight: 700 }}>
            {t('alertas_sin_danos', { fecha: fechaCorta(fenologia.horizontes.pronostico_hasta) })}
          </div>
        ) : null}
        {ORDEN.map((horizonte) => {
          const delHorizonte = eventos.filter((e) => e.horizonte === horizonte)
          if (!delHorizonte.length) return null
          return (
            <section key={horizonte} aria-label={t(`alertas_horizonte_${horizonte}`)} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <h3 className="ps-contexto" style={{ margin: '4px 4px 0 4px' }}>{t(`alertas_horizonte_${horizonte}`)}</h3>
              {delHorizonte.map((evento) => (
                <TarjetaEvento key={`${evento.fase}-${evento.peligro}-${evento.efecto}-${evento.primer_dia}`} evento={evento} />
              ))}
            </section>
          )
        })}
      </div>

      <p className="ps-pad ps-nota" style={{ margin: 'auto 0 0 0', padding: '20px 20px 32px 20px' }}>
        {t('alertas_nota_final')}
      </p>
    </Screen>
  )
}
