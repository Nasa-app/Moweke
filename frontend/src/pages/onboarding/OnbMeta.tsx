import { Link } from 'react-router-dom'
import { Screen, BarraSuperior, Titulo } from '../../components/Screen'
import { StepDots } from '../../components/StepDots'
import { IconoSiguiente } from '../../components/icons'
import { useI18n } from '../../i18n'

function Opcion({ a, titulo, sub }: { a: string; titulo: string; sub: string }) {
  return (
    <Link to={a} className="ps-card" style={{ textDecoration: 'none', color: 'var(--carbon)', display: 'flex', alignItems: 'center', gap: 10, padding: 16 }}>
      <span style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
        <span style={{ fontSize: 22, fontWeight: 800, lineHeight: 1.1 }}>{titulo}</span>
        <span className="ps-contexto">{sub}</span>
      </span>
      <span aria-hidden="true" style={{ width: 44, height: 44, borderRadius: 22, background: 'var(--verde)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
        <IconoSiguiente tamano={22} stroke="#fff" />
      </span>
    </Link>
  )
}

export default function OnbMeta() {
  const { t } = useI18n()
  return (
    <Screen>
      <BarraSuperior volverA="/onboarding/antes" derecha={<StepDots paso={3} total={4} />} />
      <Titulo>{t('onb_meta_titulo')}</Titulo>

      <div className="ps-pad-16" style={{ marginTop: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
        <Opcion a="/onboarding/cultivos" titulo={t('onb_seguir_cultivo')} sub={t('onb_seguir_cultivo_sub')} />
        <Opcion a="/onboarding/listo" titulo={t('onb_elegir_que_sembrar')} sub={t('onb_elegir_que_sembrar_sub')} />
      </div>

      <p style={{ margin: 'auto 20px 36px 20px', paddingTop: 16, textAlign: 'center', fontSize: 16, fontWeight: 700, color: 'var(--texto-tenue)' }}>
        {t('onb_cambiar_despues')}
      </p>
    </Screen>
  )
}
