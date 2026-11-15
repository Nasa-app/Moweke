// Anillo de compatibilidad -- componente nuevo que pide el handoff (no estaba en el
// design system original). % de 0 a 100, color según umbral del semáforo fenológico.
function colorPorPorcentaje(pct: number): string {
  if (pct >= 70) return 'var(--semaforo-verde)'
  if (pct >= 50) return 'var(--semaforo-amarillo)'
  return 'var(--semaforo-rojo)'
}

export function CompatRing({ porcentaje, tamano = 34 }: { porcentaje: number; tamano?: number }) {
  const radio = tamano / 2 - 2.5
  const circunferencia = 2 * Math.PI * radio
  const relleno = (porcentaje / 100) * circunferencia
  const color = colorPorPorcentaje(porcentaje)
  const centro = tamano / 2
  return (
    <svg width={tamano} height={tamano} viewBox={`0 0 ${tamano} ${tamano}`} role="img" aria-label={`${porcentaje}% compatible con tu terreno`}>
      <circle cx={centro} cy={centro} r={radio} fill="none" stroke="var(--linea)" strokeWidth={5} />
      <circle
        cx={centro}
        cy={centro}
        r={radio}
        fill="none"
        stroke={color}
        strokeWidth={5}
        strokeLinecap="round"
        strokeDasharray={`${relleno} ${circunferencia}`}
        transform={`rotate(-90 ${centro} ${centro})`}
      />
    </svg>
  )
}
