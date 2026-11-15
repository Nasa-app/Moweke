import { IconoUbicacion } from './icons'
import type { Poligono } from '../lib/api'

// El contorno real de la parcela marcada, escalado a un recuadro (el este-oeste se acorta con la latitud).
export function MiniPerimetro({ perimetro, tamano = 52 }: { perimetro: Poligono; tamano?: number }) {
  const anillo = perimetro.coordinates[0] ?? []
  if (anillo.length < 3) return <IconoUbicacion stroke="var(--verde)" />
  const lat0 = anillo.reduce((suma, p) => suma + p[1], 0) / anillo.length
  const k = Math.cos((lat0 * Math.PI) / 180)
  const xs = anillo.map((p) => p[0] * k)
  const ys = anillo.map((p) => -p[1])
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)]
  const lado = Math.max(x1 - x0, y1 - y0) || 1
  const escala = 36 / lado
  const puntos = anillo.map((_, i) => `${((xs[i] - x0) * escala + (36 - (x1 - x0) * escala) / 2 + 8).toFixed(1)},${((ys[i] - y0) * escala + (36 - (y1 - y0) * escala) / 2 + 8).toFixed(1)}`).join(' ')
  return (
    <svg width={tamano} height={tamano} viewBox="0 0 52 52" aria-hidden="true">
      <polygon points={puntos} fill="var(--ilus-verde, #829E30)" fillOpacity={0.35} stroke="var(--verde)" strokeWidth={2} strokeLinejoin="round" />
    </svg>
  )
}
