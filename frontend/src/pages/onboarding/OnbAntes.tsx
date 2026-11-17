import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Screen, BarraSuperior, Titulo } from '../../components/Screen'
import { TERRENOS, guardarBorrador, leerBorrador } from '../../lib/comunas'
import { leer, guardar } from '../../state/storage'
import { useI18n } from '../../i18n'

// El valor ('Papa', 'Nada'...) es lo que se guarda en el dispositivo; la etiqueta es lo que se muestra.
const OPCIONES = [
  { valor: 'Papa', etiqueta: 'onb_antes_papa' },
  { valor: 'Ajo', etiqueta: 'onb_antes_ajo' },
  { valor: 'Haba', etiqueta: 'onb_antes_haba' },
  { valor: 'Avena', etiqueta: 'onb_antes_avena' },
  { valor: 'Nada', etiqueta: 'onb_antes_nada' },
  { valor: 'Otro', etiqueta: 'onb_antes_otro' },
]
const ETIQUETA_TERRENO: Record<string, string> = {
  Plano: 'onb_terreno_plano',
  Ladera: 'onb_terreno_ladera',
  Alto: 'onb_terreno_alto',
}
// Nada viene elegido de antemano: lo que no se responde queda sin responder, no como "Papa".
const TEMPORADAS = [
  { clave: 'esta', etiqueta: 'onb_antes_esta' },
  { clave: 'pasado', etiqueta: 'onb_antes_pasado' },
  { clave: 'hace2', etiqueta: 'onb_antes_hace2' },
] as const

export default function OnbAntes() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [elegido, setElegido] = useState(() => leer<Record<string, string>>('onboarding_antes', {}))

  // Sobre el predio ya marcado: opcional, y queda en este dispositivo (el servidor todavía no lo guarda).
  const [sector, setSector] = useState(() => leerBorrador().sector)
  const [terreno, setTerreno] = useState(() => leerBorrador().terreno)

  function elegir(temporada: string, valor: string) {
    const nuevo = { ...elegido, [temporada]: valor }
    setElegido(nuevo)
    guardar('onboarding_antes', nuevo)
  }

  return (
    <Screen>
      <BarraSuperior volverA="/onboarding/meta" />
      <Titulo sub={t('onb_antes_sub')}>{t('onb_antes_titulo')}</Titulo>

      {TEMPORADAS.map(({ clave, etiqueta }) => (
        <fieldset key={clave} className="ps-pad-16" style={{ marginTop: 14, border: 'none', padding: 0 }}>
          <legend style={{ padding: '0 4px', marginBottom: 8, fontSize: 18, fontWeight: 800 }}>{t(etiqueta)}</legend>
          <div className="ps-grid-3">
            {OPCIONES.map(({ valor, etiqueta: etiquetaOpcion }) => (
              <label key={valor} className={`ps-pill ${elegido[clave] === valor ? 'activo' : ''}`}>
                <input type="radio" name={`t-${clave}`} checked={elegido[clave] === valor} onChange={() => elegir(clave, valor)} className="visually-hidden" />
                {t(etiquetaOpcion)}
              </label>
            ))}
          </div>
        </fieldset>
      ))}

      <fieldset className="ps-pad-16" style={{ marginTop: 22, border: 'none', padding: 0 }}>
        <legend style={{ padding: '0 4px', marginBottom: 2, fontSize: 18, fontWeight: 800 }}>{t('onb_antes_parcela')}</legend>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
          <span style={{ fontSize: 16, fontWeight: 700, padding: '0 4px' }}>{t('onb_antes_sector')}</span>
          <input
            type="text"
            value={sector}
            maxLength={60}
            placeholder={t('onb_antes_sector_ejemplo')}
            onChange={(e) => {
              setSector(e.target.value)
              guardarBorrador({ sector: e.target.value })
            }}
            style={{ minHeight: 52, padding: '0 14px', borderRadius: 16, border: '2px solid var(--borde-control)', background: '#fff', color: 'var(--carbon)', font: "700 17px 'Alegreya Sans', sans-serif" }}
          />
        </label>
        <div role="group" aria-label={t('onb_terreno')} style={{ marginTop: 12 }}>
          <span style={{ display: 'block', fontSize: 16, fontWeight: 700, padding: '0 4px 6px' }}>{t('onb_terreno')}</span>
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
                {t(ETIQUETA_TERRENO[tp] ?? tp)}
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
