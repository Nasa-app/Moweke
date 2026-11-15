import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Screen, BarraSuperior, Titulo } from '../components/Screen'
import { usePredio } from '../state/PredioContext'
import { encolarReporte } from '../lib/colaReportes'
import { nombreEspecie } from '../lib/formato'
import { useI18n } from '../i18n'

// Etapas que sirven para cualquier cultivo: ninguna nombra una especie.
const FASES = ['Brote', 'Hojas', 'Flor', 'Fruto o raíz', 'Amarilla', 'Cosecha']

export default function Reportar() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const { idCultivoActivo, especieActiva } = usePredio()
  const [fase, setFase] = useState('Hojas')

  function enviar() {
    encolarReporte({ fecha: new Date().toISOString().slice(0, 10), idCultivo: idCultivoActivo, fase, colorHojas: null, senales: [] })
    navigate('/reportar/confirmacion')
  }

  // Sin un cultivo declarado no hay de qué informar: no se inventa uno.
  if (!idCultivoActivo || !especieActiva) {
    return (
      <Screen>
        <BarraSuperior volverA="/cultivo" />
        <Titulo sub="Para contarnos cómo va, primero dinos qué sembraste.">Todavía no tienes un cultivo</Titulo>
        <div style={{ marginTop: 'auto', padding: '16px 16px 32px 16px' }}>
          <Link to="/onboarding/cultivos" className="ps-btn">
            Agregar qué sembraste
          </Link>
        </div>
      </Screen>
    )
  }

  return (
    <Screen>
      <BarraSuperior volverA="/cultivo" />
      <Titulo>{`¿Cómo está tu ${nombreEspecie(especieActiva).toLowerCase()}?`}</Titulo>

      <fieldset className="ps-pad-16" style={{ marginTop: 16, border: 'none', paddingBlock: 0 }}>
        <legend className="visually-hidden">Elige la foto que más se parece</legend>
        <div className="ps-grid-2">
          {FASES.map((f) => (
            <label
              key={f}
              style={{ position: 'relative', borderRadius: 20, background: 'var(--blanco)', boxShadow: fase === f ? '0 0 0 3px var(--verde)' : 'var(--sombra-1)', cursor: 'pointer', display: 'flex', flexDirection: 'column', minHeight: 110, justifyContent: 'center', alignItems: 'center' }}
            >
              <input type="radio" name="fase" checked={fase === f} onChange={() => setFase(f)} className="visually-hidden" />
              <span style={{ fontSize: 17, fontWeight: 800, color: fase === f ? 'var(--verde)' : undefined }}>{f}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <div style={{ marginTop: 'auto', padding: '16px 16px 32px 16px' }}>
        <button type="button" onClick={enviar} className="ps-btn">
          {t('enviar')}
        </button>
      </div>
    </Screen>
  )
}
