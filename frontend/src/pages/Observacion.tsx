import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Screen, BarraSuperior, Titulo } from '../components/Screen'
import { IconoMas, IconoCheck } from '../components/icons'
import { usePredio } from '../state/PredioContext'
import { encolarReporte } from '../lib/colaReportes'
import { indicadoresParcela, mensajeDeError, reportarIndicador, type IndicadorLocal } from '../lib/api'
import { mesEnVentana, nombreCategoria, nombreSignificado, ventanaEnMeses } from '../lib/formato'
import { useI18n } from '../i18n'

const COLORES = [
  { clave: 'verde', nombre: 'observacion_color_verde', color: 'var(--verde)' },
  { clave: 'amarillo', nombre: 'observacion_color_amarillo', color: 'var(--semaforo-amarillo)' },
  { clave: 'seco', nombre: 'observacion_color_seco', color: 'var(--ilus-tierra)' },
]

export default function Observacion() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const { idParcela, idCultivoActivo } = usePredio()
  const hoy = new Date().toISOString().slice(0, 10)
  const [fecha, setFecha] = useState(hoy)
  const [color, setColor] = useState('verde')
  const [indicadores, setIndicadores] = useState<IndicadorLocal[] | null>(null)
  const [marcados, setMarcados] = useState<Set<number>>(new Set())
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)
  // Los que el servidor ya recibió: si otro reintento sigue, solo se reenvían los que faltan.
  const [enviados, setEnviados] = useState<number[]>([])

  useEffect(() => {
    if (!idParcela) return
    let vigente = true
    indicadoresParcela(idParcela, true)
      .then((d) => vigente && setIndicadores(d.indicadores))
      .catch((err) => vigente && setError(mensajeDeError(err, t('observacion_error_envio'))))
    return () => {
      vigente = false
    }
  }, [idParcela, t])

  // Solo se pueden reportar los que cuentan en el mes de la fecha elegida (el servidor lo exige).
  const elegibles = (indicadores ?? []).filter((i) => mesEnVentana(fecha, i.mes_desde, i.mes_hasta))
  const aEnviar = elegibles.filter((i) => marcados.has(i.id) && !enviados.includes(i.id))

  function alternar(id: number) {
    const copia = new Set(marcados)
    if (copia.has(id)) copia.delete(id)
    else copia.add(id)
    setMarcados(copia)
  }

  async function enviar() {
    setEnviando(true)
    setError(null)
    const resultados = await Promise.allSettled(aEnviar.map((i) => reportarIndicador(i.id, fecha)))
    const recibidos = [...enviados, ...aEnviar.filter((_, n) => resultados[n].status === 'fulfilled').map((i) => i.id)]
    setEnviados(recibidos)
    const fallo = resultados.find((r): r is PromiseRejectedResult => r.status === 'rejected')
    if (fallo) {
      setError(mensajeDeError(fallo.reason, t('observacion_error_envio')))
      setEnviando(false)
      return
    }
    encolarReporte({ fecha, idCultivo: idCultivoActivo, fase: null, colorHojas: color, senales: recibidos.map(String) })
    navigate('/reportar/confirmacion')
  }

  return (
    <Screen>
      <BarraSuperior volverA="/reportar" derecha={<span className="ps-contexto">Quemchi</span>} />
      <Titulo sub={t('observacion_sub')}>{t('observacion_titulo')}</Titulo>

      <label className="ps-pad-16" style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span style={{ fontSize: 18, fontWeight: 800 }}>{t('observacion_fecha')}</span>
        <input
          type="date"
          value={fecha}
          max={hoy}
          required
          onChange={(e) => setFecha(e.target.value)}
          style={{ minHeight: 52, padding: '0 14px', borderRadius: 16, border: '2px solid var(--borde-control)', background: '#fff', color: 'var(--carbon)', font: "800 17px 'Alegreya Sans', sans-serif" }}
        />
        <span className="ps-nota">{t('observacion_hoy_por_defecto')}</span>
      </label>

      <fieldset className="ps-pad-16" style={{ marginTop: 14, border: 'none', paddingBlock: 0 }}>
        <legend style={{ padding: '0 4px', marginBottom: 8, fontSize: 18, fontWeight: 800 }}>{t('observacion_color_hojas')}</legend>
        <div className="ps-grid-3">
          {COLORES.map((c) => (
            <label key={c.clave} style={{ minHeight: 56, borderRadius: 16, boxShadow: color === c.clave ? 'inset 0 0 0 3px var(--verde)' : 'none', background: color === c.clave ? '#fff' : 'var(--hundido)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, fontSize: 16, fontWeight: color === c.clave ? 800 : 700, cursor: 'pointer' }}>
              <input type="radio" name="color" checked={color === c.clave} onChange={() => setColor(c.clave)} className="visually-hidden" />
              <span aria-hidden="true" style={{ width: 22, height: 22, borderRadius: 11, background: c.color }} />
              {t(c.nombre)}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="ps-pad-16" style={{ marginTop: 16, border: 'none', paddingBlock: 0 }}>
        <legend style={{ padding: '0 4px', marginBottom: 2, fontSize: 18, fontWeight: 800 }}>{t('observacion_indicadores')}</legend>
        {indicadores && indicadores.length ? (
          <>
            <p className="ps-nota" style={{ margin: '0 4px 8px' }}>{t('observacion_indicadores_sub')}</p>
            <div className="ps-grid-2">
              {indicadores.map((i) => {
                const cuenta = mesEnVentana(fecha, i.mes_desde, i.mes_hasta)
                const activo = cuenta && marcados.has(i.id)
                return (
                  <label
                    key={i.id}
                    style={{ position: 'relative', borderRadius: 20, background: 'var(--blanco)', boxShadow: activo ? '0 0 0 3px var(--verde)' : 'var(--sombra-1)', cursor: cuenta ? 'pointer' : 'not-allowed', opacity: cuenta ? 1 : 0.6, display: 'flex', flexDirection: 'column', padding: '14px 10px', minHeight: 90 }}
                  >
                    <input type="checkbox" checked={activo} disabled={!cuenta} onChange={() => alternar(i.id)} className="visually-hidden" />
                    <span style={{ fontSize: 17, fontWeight: 800, lineHeight: 1.1, color: activo ? 'var(--verde)' : undefined }}>{i.nombre}</span>
                    <span className="ps-detalle">{nombreCategoria(i.categoria)} · {i.evento}</span>
                    <span className="ps-detalle">{nombreSignificado(i.significado)}</span>
                    <span className="ps-nota">{cuenta ? ventanaEnMeses(i.mes_desde, i.mes_hasta) : t('observacion_fuera_de_mes')}</span>
                    {activo ? (
                      <span aria-hidden="true" style={{ position: 'absolute', right: 8, top: 8, width: 30, height: 30, borderRadius: 15, background: 'var(--verde)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <IconoCheck tamano={18} stroke="#fff" />
                      </span>
                    ) : null}
                  </label>
                )
              })}
            </div>
          </>
        ) : indicadores ? (
          <p className="ps-nota" style={{ margin: '0 4px' }}>{t('observacion_sin_indicadores')}</p>
        ) : null}
        {error ? <p role="alert" className="ps-nota" style={{ margin: '8px 4px 0', color: 'var(--riesgo-texto)', fontWeight: 700 }}>{error}</p> : null}
      </fieldset>

      <div className="ps-pad-16" style={{ marginTop: 14, display: 'grid', gridTemplateColumns: 'minmax(0, 1fr)' }}>
        <button type="button" style={{ minHeight: 52, borderRadius: 16, border: '2px dashed var(--borde-control)', background: '#fff', color: 'var(--carbon)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, font: "800 15px 'Alegreya Sans', sans-serif", cursor: 'pointer' }}>
          <IconoMas tamano={18} />
          {t('observacion_otra')}
        </button>
      </div>

      <div style={{ marginTop: 'auto', padding: '16px 16px 32px 16px' }}>
        <button type="button" onClick={enviar} disabled={enviando} className="ps-btn">
          {t('enviar')}{aEnviar.length ? ` · ${t(aEnviar.length === 1 ? 'observacion_senal_una' : 'observacion_senales', { n: aEnviar.length })}` : ''}
        </button>
      </div>
    </Screen>
  )
}
