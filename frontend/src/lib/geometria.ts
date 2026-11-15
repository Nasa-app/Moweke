import type { Poligono } from './api'

export type Punto = [lat: number, lon: number]

// Superficie del polígono en hectáreas, en un plano local en metros alrededor de su
// latitud media. Es para mostrarla mientras se dibuja; la que vale es la que calcula el API.
export function hectareasDe(esquinas: Punto[]): number {
  if (esquinas.length < 3) return 0
  const latMedia = esquinas.reduce((suma, p) => suma + p[0], 0) / esquinas.length
  const mLon = 111_320 * Math.cos((latMedia * Math.PI) / 180)
  const mLat = 110_540
  let area = 0
  for (let i = 0; i < esquinas.length; i++) {
    const a = esquinas[i]
    const b = esquinas[(i + 1) % esquinas.length]
    area += a[1] * mLon * (b[0] * mLat) - b[1] * mLon * (a[0] * mLat)
  }
  return Math.abs(area / 2) / 10_000
}

export function aPoligono(esquinas: Punto[]): Poligono {
  const anillo = esquinas.map(([lat, lon]) => [Number(lon.toFixed(6)), Number(lat.toFixed(6))])
  return { type: 'Polygon', coordinates: [[...anillo, anillo[0]]] }
}
