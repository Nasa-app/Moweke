import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Screen, BarraSuperior, Titulo } from '../../components/Screen'
import { StepDots } from '../../components/StepDots'
import { IconoUbicacion } from '../../components/icons'
import { COMUNAS, guardarBorrador, leerBorrador } from '../../lib/comunas'
import { usePredio } from '../../state/PredioContext'
import { useI18n } from '../../i18n'

const IR_AL_MAPA = '/terreno/perimetro?desde=onboarding'

// Primer paso: solo la comuna, para abrir el mapa cerca de la parcela. El sector y el tipo de terreno se
// preguntan después (paso 2), cuando la parcela ya está marcada.
export default function OnbDatos() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const { idParcela } = usePredio()
  const [comuna, setComuna] = useState(() => leerBorrador().comuna)

  return (
    <Screen>
      <BarraSuperior volverA="/explorar" derecha={<StepDots paso={1} total={3} />} />
      <Titulo sub="Elige tu comuna. Después marcarás tu parcela sobre el mapa, tocando cada esquina.">
        ¿Dónde está tu parcela?
      </Titulo>

      <div className="ps-pad-16" style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 6 }}>
        <label htmlFor="comuna" style={{ fontSize: 16, fontWeight: 800, padding: '0 4px' }}>
          {t('onb_comuna')}
        </label>
        <select
          id="comuna"
          value={comuna}
          onChange={(e) => {
            setComuna(e.target.value)
            guardarBorrador({ comuna: e.target.value })
          }}
          style={{ minHeight: 56, padding: '0 14px', borderRadius: 16, border: '2px solid var(--borde-control)', background: 'var(--blanco)', font: "700 18px 'Alegreya Sans', sans-serif", color: 'var(--carbon)' }}
        >
          {COMUNAS.map((c) => (
            <option key={c.nombre}>{c.nombre}</option>
          ))}
        </select>
      </div>

      <section className="ps-card-plana" style={{ margin: '16px 16px 0 16px', display: 'flex', gap: 12, alignItems: 'flex-start' }}>
        <span aria-hidden="true" style={{ flex: 'none', width: 44, height: 44, borderRadius: 22, background: 'var(--verde)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <IconoUbicacion stroke="#fff" />
        </span>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <span style={{ fontSize: 18, fontWeight: 800, lineHeight: 1.2 }}>Lo que sigue: marcar tu parcela</span>
          <span style={{ fontSize: 16, fontWeight: 600, lineHeight: 1.35, color: 'var(--texto-tenue)' }}>
            Verás el mapa de {comuna}. Acércalo hasta tu parcela y toca cada esquina para dibujar su contorno. Toma un par de minutos.
          </span>
        </div>
      </section>

      <section aria-label="Privacidad" className="ps-pad-16" style={{ margin: '18px 16px 0 16px', background: 'var(--cielo)', color: 'var(--carbon)', borderRadius: 20, padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <h2 className="ps-h2">{t('onb_priv_titulo')}</h2>
        <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 8, fontSize: 16, fontWeight: 700, lineHeight: 1.3 }}>
          <li>{t('onb_priv_nombre')}</li>
          <li>{t('onb_priv_uso')}</li>
          <li>{t('onb_priv_borrar')}</li>
        </ul>
        <label style={{ display: 'flex', alignItems: 'center', gap: 12, minHeight: 48, padding: '0 12px', borderRadius: 14, background: 'var(--blanco)', cursor: 'pointer' }}>
          <input type="checkbox" defaultChecked={leerBorrador().acepto} onChange={(e) => guardarBorrador({ acepto: e.target.checked })} style={{ width: 24, height: 24, accentColor: 'var(--verde)' }} />
          <span style={{ flex: 1, fontSize: 16, fontWeight: 800 }}>{t('onb_acepto')}</span>
        </label>
      </section>

      <div style={{ position: 'sticky', bottom: 0, marginTop: 'auto', padding: '14px 16px 28px 16px', background: 'var(--arena)', display: 'flex', flexDirection: 'column', gap: 8 }}>
        <button type="button" onClick={() => navigate(IR_AL_MAPA)} className="ps-btn" style={{ gap: 8 }}>
          <IconoUbicacion stroke="#fff" />
          {t('onb_seguir_marcar')}
        </button>
        {idParcela ? (
          <button type="button" onClick={() => navigate('/onboarding/meta')} className="ps-btn-secundario">
            {t('onb_quedarme')}
          </button>
        ) : null}
      </div>
    </Screen>
  )
}
