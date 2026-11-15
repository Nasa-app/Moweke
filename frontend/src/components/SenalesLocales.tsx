import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { indicadoresParcela, type IndicadoresPredio } from '../lib/api'
import { nombreCategoria, nombreSignificado, ventanaEnMeses } from '../lib/formato'
import { useI18n } from '../i18n'

// Lo que la comunidad de la zona observa (aves, floración de especies) y lo que anuncia, con
// cuántos agricultores lo respaldan. Es conocimiento local sin validar: va rotulado así y no
// cambia ninguna fecha ni riesgo calculado. Sin indicadores definidos para la zona no se dibuja.
export function SenalesLocales({ idParcela }: { idParcela: number }) {
  const { t } = useI18n()
  const [datos, setDatos] = useState<IndicadoresPredio | null>(null)

  useEffect(() => {
    let vigente = true
    indicadoresParcela(idParcela)
      .then((d) => vigente && setDatos(d))
      .catch(() => vigente && setDatos(null))
    return () => {
      vigente = false
    }
  }, [idParcela])

  if (!datos || datos.indicadores.length === 0) return null
  const confirmadas = datos.indicadores.filter((i) => i.estado === 'confirmada')
  const enObservacion = datos.indicadores.some((i) => i.estado === 'en_observacion')

  return (
    <section className="ps-card" aria-labelledby="senales-zona" style={{ margin: '14px 16px 0 16px', display: 'flex', flexDirection: 'column', gap: 8 }}>
      <span className="ps-contexto">{t('senales_zona_origen')}</span>
      <h2 id="senales-zona" style={{ margin: 0, fontSize: 19, fontWeight: 800, lineHeight: 1.15 }}>
        {t('senales_zona_titulo')}
      </h2>
      {confirmadas.length ? (
        <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 10 }}>
          {confirmadas.map((i) => (
            <li key={i.id} style={{ display: 'flex', flexDirection: 'column' }}>
              <span style={{ fontSize: 18, fontWeight: 800, lineHeight: 1.15 }}>{nombreSignificado(i.significado)}</span>
              <span className="ps-detalle">
                {nombreCategoria(i.categoria)}: {i.nombre} · {i.evento}
              </span>
              <span className="ps-detalle">
                {i.observadores} {i.observadores === 1 ? t('senales_zona_vio_uno') : t('senales_zona_vio_varios')} · {i.zona} ·{' '}
                {ventanaEnMeses(i.mes_desde, i.mes_hasta)}
              </span>
              {i.nota ? <span className="ps-detalle">{i.nota}</span> : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="ps-nota" style={{ margin: 0 }}>
          {enObservacion ? t('senales_zona_en_observacion') : t('senales_zona_sin_reportes')}
        </p>
      )}
      <Link to="/reportar/observacion" style={{ fontSize: 16, fontWeight: 800 }}>
        {t('senales_zona_reportar')}
      </Link>
    </section>
  )
}
