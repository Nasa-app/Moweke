import { useCallback, useEffect, useState } from 'react'
import { anularLabor, declararLabor, mensajeDeError, registroCultivo, TIPOS_LABOR, type Labor, type RegistroCultivo as Registro, type TipoLabor } from '../lib/api'
import { aIso, fechaCorta, nombreEspecie } from '../lib/formato'
import { nombreVariedad } from '../lib/nombres'
import { useI18n } from '../i18n'

// Lo que el agricultor declaró del cultivo (especie, variedad, siembra) y las labores que va anotando: riego,
// fertilizante, pesticida y fungicida. Cada cambio avisa a la pantalla para que vuelva a pedir el seguimiento.
// Se monta con `key` por cultivo: al cambiar de cultivo empieza limpio.
export function RegistroCultivo({ idCultivo, onCambio }: { idCultivo: number; onCambio: () => void }) {
  const { t } = useI18n()
  const [registro, setRegistro] = useState<Registro | null>(null)
  const [tipo, setTipo] = useState<TipoLabor>('riego')
  const [hoy] = useState(() => aIso(new Date()))
  const [fecha, setFecha] = useState(hoy)
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)

  const cargar = useCallback(() => {
    return registroCultivo(idCultivo)
      .then(setRegistro)
      .catch((err) => setError(mensajeDeError(err, t('registro_error_cargar'))))
  }, [idCultivo, t])

  useEffect(() => {
    cargar()
  }, [cargar])

  async function cambiar(accion: () => Promise<unknown>, avisoOk: string | null) {
    setEnviando(true)
    setError(null)
    setAviso(null)
    try {
      await accion()
      await cargar()
      onCambio()
      setAviso(avisoOk)
    } catch (err) {
      setError(mensajeDeError(err, t('registro_error')))
    } finally {
      setEnviando(false)
    }
  }

  const anotar = () => cambiar(() => declararLabor(idCultivo, tipo, fecha), t('registro_anotada', { labor: t(`labor_${tipo}`) }))
  const quitar = (l: Labor) => cambiar(() => anularLabor(idCultivo, l.tipo, l.fecha), null)

  const cultivo = registro?.cultivo
  const desde = cultivo?.fecha_siembra ?? undefined

  return (
    <section aria-labelledby="registro-cultivo" className="ps-pad-16" style={{ marginTop: 18 }}>
      <h2 id="registro-cultivo" className="ps-h2" style={{ margin: '0 4px' }}>{t('registro_titulo')}</h2>

      <div className="ps-card" style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 12 }}>
        {cultivo ? (
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <b style={{ fontSize: 19, fontWeight: 800 }}>
              {nombreEspecie(cultivo.especie)}
              {cultivo.variedad_local ? ` · ${nombreVariedad(cultivo.especie, cultivo.variedad_local)}` : ''}
            </b>
            <span className="ps-detalle">{cultivo.fecha_siembra ? t('registro_sembrado', { fecha: fechaCorta(cultivo.fecha_siembra) }) : ''}</span>
          </div>
        ) : null}

        <div role="radiogroup" aria-label={t('registro_anotar')} style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {TIPOS_LABOR.map((l) => (
            <button key={l} type="button" role="radio" aria-checked={tipo === l} onClick={() => setTipo(l)} className={`ps-pill ${tipo === l ? 'activo' : ''}`} style={{ padding: '0 14px', minHeight: 44 }}>
              {t(`labor_${l}`)}
            </button>
          ))}
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input
            type="date"
            aria-label={t('registro_fecha_aria')}
            value={fecha}
            min={desde}
            max={hoy}
            onChange={(e) => setFecha(e.target.value)}
            style={{ flex: 1, minHeight: 48, padding: '0 12px', borderRadius: 14, border: '2px solid var(--borde-control)', background: 'var(--blanco)', color: 'var(--carbon)', font: "700 16px 'Alegreya Sans', sans-serif" }}
          />
          <button type="button" className="ps-btn" onClick={anotar} disabled={enviando || !fecha} style={{ flex: '0 0 auto', padding: '0 20px' }}>
            {t('registro_guardar')}
          </button>
        </div>

        {aviso ? <span className="ps-nota" role="status">{aviso}</span> : null}
        {error ? <span className="ps-nota" role="alert" style={{ color: 'var(--riesgo-texto)' }}>{error}</span> : null}

        {registro && registro.labores.length === 0 ? <span className="ps-nota">{t('registro_vacio')}</span> : null}
        {registro && registro.labores.length ? (
          <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 6 }}>
            {registro.labores.map((l) => (
              <li key={`${l.tipo}-${l.fecha}`} style={{ display: 'flex', alignItems: 'center', gap: 8, minHeight: 44 }}>
                <span style={{ flex: 1, fontSize: 16, fontWeight: 800 }}>{t(`labor_${l.tipo}`)}</span>
                <span className="ps-detalle">{fechaCorta(l.fecha)}</span>
                <button type="button" className="ps-btn-texto" onClick={() => quitar(l)} disabled={enviando} aria-label={t('registro_quitar_aria', { labor: t(`labor_${l.tipo}`), fecha: fechaCorta(l.fecha) })}>
                  {t('registro_quitar')}
                </button>
              </li>
            ))}
          </ul>
        ) : null}
        <span className="ps-nota">{t('registro_nota')}</span>
      </div>
    </section>
  )
}
