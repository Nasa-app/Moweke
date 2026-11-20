import { useNavigate } from 'react-router-dom'
import { Screen, BarraSuperior, Titulo } from '../../components/Screen'
import { StepDots } from '../../components/StepDots'
import { IconoUbicacion } from '../../components/icons'
import { guardarBorrador, leerBorrador } from '../../lib/comunas'
import { usePredio } from '../../state/PredioContext'
import { useI18n } from '../../i18n'

const IR_AL_MAPA = '/terreno/perimetro?desde=onboarding'

// Primer paso: privacidad. El mapa abre en la ubicación del dispositivo; el sector y el tipo de terreno se
// preguntan después (paso 2), cuando el predio ya está marcado.
export default function OnbDatos() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const { idParcela } = usePredio()

  return (
    <Screen>
      <BarraSuperior volverA="/explorar" derecha={<StepDots paso={1} total={3} />} />
      <Titulo sub={t('onb_datos_sub')}>{t('onb_datos_titulo')}</Titulo>

      <section className="ps-card-plana" style={{ margin: '16px 16px 0 16px', display: 'flex', gap: 12, alignItems: 'flex-start' }}>
        <span aria-hidden="true" style={{ flex: 'none', width: 44, height: 44, borderRadius: 22, background: 'var(--verde)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <IconoUbicacion stroke="#fff" />
        </span>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <span style={{ fontSize: 18, fontWeight: 800, lineHeight: 1.2 }}>{t('onb_datos_sigue_titulo')}</span>
          <span style={{ fontSize: 16, fontWeight: 600, lineHeight: 1.35, color: 'var(--texto-tenue)' }}>
            {t('onb_datos_sigue_texto')}
          </span>
        </div>
      </section>

      <section aria-label={t('onb_privacidad_titulo')} className="ps-pad-16" style={{ margin: '18px 16px 0 16px', background: 'var(--cielo)', color: 'var(--carbon)', borderRadius: 20, padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
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

      <div style={{ position: 'sticky', bottom: 'calc(84px + env(safe-area-inset-bottom, 0px))', marginTop: 'auto', padding: '14px 16px 28px 16px', background: 'var(--arena)', display: 'flex', flexDirection: 'column', gap: 8 }}>
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
