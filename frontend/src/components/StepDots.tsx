export function StepDots({ paso, total }: { paso: number; total: number }) {
  return (
    <div role="progressbar" aria-label={`Paso ${paso} de ${total}`} aria-valuemin={1} aria-valuemax={total} aria-valuenow={paso} className="ps-steps" style={{ flex: 1 }}>
      {Array.from({ length: total }, (_, i) => (
        <span key={i} className={i < paso ? 'hecho' : ''} />
      ))}
    </div>
  )
}
