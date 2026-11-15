// Barras de precisión del dato (1 a 4) -- componente nuevo del handoff. Las fórmulas de
// % de compatibilidad y de precisión no están definidas todavía (ver CLAUDE.md del
// handoff, "Pendientes conocidos" #1): este componente solo dibuja el nivel que se le
// pase, no lo calcula.
const ETIQUETAS = ['Baja', 'Media', 'Buena', 'Alta']

export function PrecisionBars({ nivel, fecha }: { nivel: 1 | 2 | 3 | 4; fecha?: string }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
      <svg width={22} height={18} viewBox="0 0 22 18" aria-hidden="true">
        {[0, 1, 2, 3].map((i) => (
          <rect
            key={i}
            x={i * 6}
            y={14 - i * 4}
            width={4}
            height={4 + i * 4}
            rx={2}
            fill={i < nivel ? 'var(--verde)' : 'var(--linea)'}
          />
        ))}
      </svg>
      <span>
        <b style={{ fontWeight: 800 }}>Precisión {ETIQUETAS[nivel - 1].toLowerCase()}</b>
        {fecha ? <span className="ps-nota"> · datos al {fecha}</span> : null}
      </span>
    </span>
  )
}
