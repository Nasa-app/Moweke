import { useI18n } from '../i18n'

export function StepDots({ paso, total }: { paso: number; total: number }) {
  const { t } = useI18n()
  return (
    <div role="progressbar" aria-label={t('stepdots_aria', { paso, total })} aria-valuemin={1} aria-valuemax={total} aria-valuenow={paso} className="ps-steps" style={{ flex: 1 }}>
      {Array.from({ length: total }, (_, i) => (
        <span key={i} className={i < paso ? 'hecho' : ''} />
      ))}
    </div>
  )
}
