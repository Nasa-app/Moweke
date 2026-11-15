import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Screen, BarraSuperior, Titulo } from '../components/Screen'
import { IconoFoto, IconoAudio, IconoMas, IconoCheck } from '../components/icons'
import { usePredio } from '../state/PredioContext'
import { encolarReporte } from '../lib/colaReportes'
import { senalesFenologicas } from '../lib/mock'
import { useI18n } from '../i18n'

const COLORES = [
  { clave: 'verde', nombre: 'Verde', color: 'var(--verde)' },
  { clave: 'amarillo', nombre: 'Amarillo', color: 'var(--semaforo-amarillo)' },
  { clave: 'seco', nombre: 'Seco', color: 'var(--ilus-tierra)' },
]

export default function Observacion() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const { idCultivoActivo } = usePredio()
  const hoy = new Date().toISOString().slice(0, 10)
  const [fecha, setFecha] = useState(hoy)
  const [color, setColor] = useState('verde')
  const [senales, setSenales] = useState<Set<string>>(new Set(['floracion', 'aves']))

  function alternar(clave: string) {
    const copia = new Set(senales)
    if (copia.has(clave)) copia.delete(clave)
    else copia.add(clave)
    setSenales(copia)
  }

  function enviar() {
    encolarReporte({ fecha, idCultivo: idCultivoActivo, fase: null, colorHojas: color, senales: Array.from(senales) })
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
        <span className="ps-nota">Hoy por defecto. Cámbiala si lo viste otro día.</span>
      </label>

      <fieldset className="ps-pad-16" style={{ marginTop: 14, border: 'none', paddingBlock: 0 }}>
        <legend style={{ padding: '0 4px', marginBottom: 8, fontSize: 18, fontWeight: 800 }}>{t('observacion_color_hojas')}</legend>
        <div className="ps-grid-3">
          {COLORES.map((c) => (
            <label key={c.clave} style={{ minHeight: 56, borderRadius: 16, boxShadow: color === c.clave ? 'inset 0 0 0 3px var(--verde)' : 'none', background: color === c.clave ? '#fff' : 'var(--hundido)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, fontSize: 16, fontWeight: color === c.clave ? 800 : 700, cursor: 'pointer' }}>
              <input type="radio" name="color" checked={color === c.clave} onChange={() => setColor(c.clave)} className="visually-hidden" />
              <span aria-hidden="true" style={{ width: 22, height: 22, borderRadius: 11, background: c.color }} />
              {c.nombre}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="ps-pad-16" style={{ marginTop: 16, border: 'none', paddingBlock: 0 }}>
        <legend style={{ padding: '0 4px', marginBottom: 8, fontSize: 18, fontWeight: 800 }}>Señales</legend>
        <div className="ps-grid-2">
          {senalesFenologicas.map((s) => {
            const activo = senales.has(s.clave)
            return (
              <label
                key={s.clave}
                style={{ position: 'relative', borderRadius: 20, background: 'var(--blanco)', boxShadow: activo ? '0 0 0 3px var(--verde)' : 'var(--sombra-1)', cursor: 'pointer', display: 'flex', flexDirection: 'column', padding: '14px 10px', minHeight: 90 }}
              >
                <input type="checkbox" checked={activo} onChange={() => alternar(s.clave)} className="visually-hidden" />
                <span style={{ fontSize: 17, fontWeight: 800, lineHeight: 1.1, color: activo ? 'var(--verde)' : undefined }}>{s.nombre}</span>
                <span className="ps-detalle">{s.detalle}</span>
                {activo ? (
                  <span aria-hidden="true" style={{ position: 'absolute', right: 8, top: 8, width: 30, height: 30, borderRadius: 15, background: 'var(--verde)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <IconoCheck tamano={18} stroke="#fff" />
                  </span>
                ) : null}
              </label>
            )
          })}
        </div>
      </fieldset>

      <div className="ps-pad-16" style={{ marginTop: 14, display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 8 }}>
        <button type="button" className="ps-btn-secundario" style={{ gap: 6, fontSize: 15, minHeight: 52 }}>
          <IconoFoto tamano={18} />
          {t('reportar_foto')}
        </button>
        <button type="button" className="ps-btn-secundario" style={{ gap: 6, fontSize: 15, minHeight: 52 }}>
          <IconoAudio tamano={18} />
          {t('reportar_audio')}
        </button>
        <button type="button" style={{ minHeight: 52, borderRadius: 16, border: '2px dashed var(--borde-control)', background: '#fff', color: 'var(--carbon)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, font: "800 15px 'Alegreya Sans', sans-serif", cursor: 'pointer' }}>
          <IconoMas tamano={18} />
          {t('observacion_otra')}
        </button>
      </div>

      <div style={{ marginTop: 'auto', padding: '16px 16px 32px 16px' }}>
        <button type="button" onClick={enviar} className="ps-btn">
          {t('enviar')} · {senales.size} señales
        </button>
      </div>
    </Screen>
  )
}
