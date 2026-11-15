import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Screen, BarraSuperior, Titulo } from '../../components/Screen'
import { StepDots } from '../../components/StepDots'
import { TERRENOS, guardarBorrador, leerBorrador } from '../../lib/comunas'
import { leer, guardar } from '../../state/storage'
import { useI18n } from '../../i18n'

const OPCIONES = ['Papa', 'Ajo', 'Haba', 'Avena', 'Nada', 'Otro']
// Nada viene elegido de antemano: lo que no se responde queda sin responder, no como "Papa".
const TEMPORADAS = [
  { clave: 'esta', etiqueta: 'Esta temporada' },
  { clave: 'pasado', etiqueta: 'Año pasado' },
  { clave: 'hace2', etiqueta: 'Hace 2 años' },
] as const

export default function OnbAntes() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const elegido = leer<Record<string, string>>('onboarding_antes', {})

  // Sobre la parcela ya marcada: opcional, y queda en este dispositivo (el servidor todavía no lo guarda).
  const [sector, setSector] = useState(() => leerBorrador().sector)
  const [terreno, setTerreno] = useState(() => leerBorrador().terreno)

  function elegir(temporada: string, valor: string) {
    guardar('onboarding_antes', { ...elegido, [temporada]: valor })
  }

  return (
    <Screen>
      <BarraSuperior volverA="/onboarding/predio" derecha={<StepDots paso={2} total={4} />} />
      <Titulo sub={t('onb_antes_sub')}>{t('onb_antes_titulo')}</Titulo>

      {TEMPORADAS.map(({ clave, etiqueta }) => (
        <fieldset key={clave} className="ps-pad-16" style={{ marginTop: 14, border: 'none', padding: 0 }}>
          <legend style={{ padding: '0 4px', marginBottom: 8, fontSize: 18, fontWeight: 800 }}>{etiqueta}</legend>
          <div className="ps-grid-3">
            {OPCIONES.map((op) => (
              <label key={op} className={`ps-pill ${elegido[clave] === op ? 'activo' : ''}`}>
                <input type="radio" name={`t-${clave}`} defaultChecked={elegido[clave] === op} onChange={() => elegir(clave, op)} className="visually-hidden" />
                {op}
              </label>
            ))}
          </div>
        </fieldset>
      ))}

      <fieldset className="ps-pad-16" style={{ marginTop: 22, border: 'none', padding: 0 }}>
        <legend style={{ padding: '0 4px', marginBottom: 2, fontSize: 18, fontWeight: 800 }}>Sobre tu parcela (opcional)</legend>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
          <span style={{ fontSize: 16, fontWeight: 700, padding: '0 4px' }}>Sector o localidad</span>
          <input
            type="text"
            value={sector}
            maxLength={60}
            placeholder="Por ejemplo, Aucar"
            onChange={(e) => {
              setSector(e.target.value)
              guardarBorrador({ sector: e.target.value })
            }}
            style={{ minHeight: 52, padding: '0 14px', borderRadius: 16, border: '2px solid var(--borde-control)', background: '#fff', color: 'var(--carbon)', font: "700 17px 'Alegreya Sans', sans-serif" }}
          />
        </label>
        <div role="group" aria-label="Terreno" style={{ marginTop: 12 }}>
          <span style={{ display: 'block', fontSize: 16, fontWeight: 700, padding: '0 4px 6px' }}>Terreno</span>
          <div className="ps-grid-3">
            {TERRENOS.map((tp) => (
              <button
                key={tp}
                type="button"
                aria-pressed={terreno === tp}
                className={`ps-pill ${terreno === tp ? 'activo' : ''}`}
                onClick={() => {
                  const nuevo = terreno === tp ? '' : tp
                  setTerreno(nuevo)
                  guardarBorrador({ terreno: nuevo })
                }}
              >
                {tp}
              </button>
            ))}
          </div>
        </div>
      </fieldset>

      <div style={{ marginTop: 'auto', padding: '20px 16px 32px 16px', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <button type="button" onClick={() => navigate('/onboarding/meta')} className="ps-btn">
          {t('seguir')}
        </button>
        <button type="button" onClick={() => navigate('/onboarding/meta')} className="ps-btn-texto">
          {t('onb_no_me_acuerdo')}
        </button>
      </div>
    </Screen>
  )
}
