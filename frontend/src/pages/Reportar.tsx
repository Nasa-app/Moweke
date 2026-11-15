import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Screen, BarraSuperior, Titulo } from '../components/Screen'
import { IconoFoto, IconoAudio } from '../components/icons'
import { usePredio } from '../state/PredioContext'
import { encolarReporte } from '../lib/colaReportes'
import { useI18n } from '../i18n'

const FASES = ['Brote', 'Hojas', 'Flor', 'Papas', 'Amarilla', 'Cosecha']

export default function Reportar() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const { idCultivoActivo, especieActiva } = usePredio()
  const [fase, setFase] = useState('Hojas')

  function enviar() {
    encolarReporte({ fecha: new Date().toISOString().slice(0, 10), idCultivo: idCultivoActivo, fase, colorHojas: null, senales: [] })
    navigate('/reportar/confirmacion')
  }

  return (
    <Screen>
      <BarraSuperior volverA="/cultivo" />
      <Titulo>{especieActiva ? `¿Cómo está tu ${especieActiva}?` : t('reportar_titulo')}</Titulo>

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

      <div className="ps-pad-16" style={{ marginTop: 16, display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 8 }}>
        <button type="button" className="ps-btn-secundario" style={{ gap: 8, fontSize: 16 }}>
          <IconoFoto tamano={20} />
          {t('reportar_foto')}
        </button>
        <button type="button" className="ps-btn-secundario" style={{ gap: 8, fontSize: 16 }}>
          <IconoAudio tamano={20} />
          {t('reportar_audio')}
        </button>
        <button type="button" onClick={() => navigate('/reportar/observacion')} className="ps-btn-secundario" aria-label="Señales del campo: floración, color de hojas, aves" style={{ gap: 8, fontSize: 16 }}>
          {t('reportar_senales')}
        </button>
      </div>

      <div style={{ marginTop: 'auto', padding: '16px 16px 32px 16px' }}>
        <button type="button" onClick={enviar} className="ps-btn">
          {t('enviar')}
        </button>
      </div>
    </Screen>
  )
}
