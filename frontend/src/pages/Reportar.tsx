import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Screen, BarraSuperior, Titulo } from '../components/Screen'
import { usePredio } from '../state/PredioContext'
import { encolarReporte, sincronizarCola } from '../lib/colaReportes'
import { FASES_REPORTE, type FaseReporte } from '../lib/api'
import { aIso, nombreEspecie } from '../lib/formato'
import { useI18n } from '../i18n'

// Etapas que sirven para cualquier cultivo: ninguna nombra una especie. El valor es lo que se envía; el texto que
// se muestra es la clave reportar_fase_<valor> del diccionario.

export default function Reportar() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const { idCultivoActivo, especieActiva } = usePredio()
  const [fase, setFase] = useState<FaseReporte>('hojas')
  const [enviando, setEnviando] = useState(false)

  // Se guarda en el teléfono y se intenta subir al momento: si no hay señal, queda en cola y sube después.
  async function enviar() {
    setEnviando(true)
    encolarReporte({ fecha: aIso(new Date()), idCultivo: idCultivoActivo, fase, colorHojas: null, senales: [] })
    const enCola = await sincronizarCola().catch(() => 1)
    navigate('/reportar/confirmacion', { state: { enviado: enCola === 0 } })
  }

  // Sin un cultivo declarado no hay de qué informar: no se inventa uno.
  if (!idCultivoActivo || !especieActiva) {
    return (
      <Screen>
        <BarraSuperior volverA="/cultivo" />
        <Titulo sub={t('reportar_sin_cultivo_sub')}>{t('reportar_sin_cultivo_titulo')}</Titulo>
        <div style={{ marginTop: 'auto', padding: '16px 16px 32px 16px' }}>
          <Link to="/cultivo" className="ps-btn">
            {t('reportar_agregar_siembra')}
          </Link>
        </div>
      </Screen>
    )
  }

  return (
    <Screen>
      <BarraSuperior volverA="/cultivo" />
      <Titulo>{t('reportar_titulo_especie', { especie: nombreEspecie(especieActiva).toLowerCase() })}</Titulo>

      <fieldset className="ps-pad-16" style={{ marginTop: 16, border: 'none', paddingBlock: 0 }}>
        <legend className="visually-hidden">{t('reportar_leyenda')}</legend>
        <div className="ps-grid-2">
          {FASES_REPORTE.map((f) => (
            <label
              key={f}
              style={{ position: 'relative', borderRadius: 20, background: 'var(--blanco)', boxShadow: fase === f ? '0 0 0 3px var(--verde)' : 'var(--sombra-1)', cursor: 'pointer', display: 'flex', flexDirection: 'column', minHeight: 110, justifyContent: 'center', alignItems: 'center' }}
            >
              <input type="radio" name="fase" checked={fase === f} onChange={() => setFase(f)} className="visually-hidden" />
              <span style={{ fontSize: 17, fontWeight: 800, color: fase === f ? 'var(--verde)' : undefined }}>{t(`reportar_fase_${f}`)}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <div style={{ marginTop: 'auto', padding: '16px 16px 32px 16px' }}>
        <button type="button" onClick={enviar} disabled={enviando} className="ps-btn">
          {enviando ? t('cargando') : t('enviar')}
        </button>
      </div>
    </Screen>
  )
}
