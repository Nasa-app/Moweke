export type TonoChip = 'favorable' | 'precaucion' | 'riesgo' | 'acento' | 'clima' | 'neutro'

const PUNTO: Record<TonoChip, string> = {
  favorable: 'var(--favorable-texto)',
  precaucion: 'var(--semaforo-amarillo)',
  riesgo: 'var(--semaforo-rojo)',
  acento: 'var(--verde)',
  clima: 'var(--agua)',
  neutro: 'var(--texto-tenue)',
}

export function Chip({ tono, children, conPunto = true }: { tono: TonoChip; children: React.ReactNode; conPunto?: boolean }) {
  return (
    <span className={`ps-chip ps-chip-${tono}`}>
      {conPunto ? <span aria-hidden="true" className="ps-chip-dot" style={{ background: PUNTO[tono] }} /> : null}
      {children}
    </span>
  )
}
