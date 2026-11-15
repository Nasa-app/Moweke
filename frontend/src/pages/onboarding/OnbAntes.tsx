import { useNavigate } from 'react-router-dom'
import { Screen, BarraSuperior, Titulo } from '../../components/Screen'
import { StepDots } from '../../components/StepDots'
import { leer, guardar } from '../../state/storage'
import { useI18n } from '../../i18n'

const OPCIONES = ['Papa', 'Ajo', 'Haba', 'Avena', 'Nada', 'Otro']
const TEMPORADAS = [
  { clave: 'esta', etiqueta: 'Esta temporada', porDefecto: 'Papa' },
  { clave: 'pasado', etiqueta: 'Año pasado', porDefecto: 'Ajo' },
  { clave: 'hace2', etiqueta: 'Hace 2 años', porDefecto: 'Papa' },
] as const

export default function OnbAntes() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const elegido = leer<Record<string, string>>('onboarding_antes', {
    esta: 'Papa',
    pasado: 'Ajo',
    hace2: 'Papa',
  })

  function elegir(temporada: string, valor: string) {
    guardar('onboarding_antes', { ...elegido, [temporada]: valor })
  }

  return (
    <Screen>
      <BarraSuperior volverA="/onboarding/predio" derecha={<StepDots paso={2} total={4} />} />
      <Titulo sub={t('onb_antes_sub')}>{t('onb_antes_titulo')}</Titulo>

      {TEMPORADAS.map(({ clave, etiqueta, porDefecto }) => (
        <fieldset key={clave} className="ps-pad-16" style={{ marginTop: 14, border: 'none', padding: 0 }}>
          <legend style={{ padding: '0 4px', marginBottom: 8, fontSize: 18, fontWeight: 800 }}>{etiqueta}</legend>
          <div className="ps-grid-3">
            {OPCIONES.map((op) => (
              <label key={op} className={`ps-pill ${(elegido[clave] ?? porDefecto) === op ? 'activo' : ''}`}>
                <input type="radio" name={`t-${clave}`} defaultChecked={(elegido[clave] ?? porDefecto) === op} onChange={() => elegir(clave, op)} className="visually-hidden" />
                {op}
              </label>
            ))}
          </div>
        </fieldset>
      ))}

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
