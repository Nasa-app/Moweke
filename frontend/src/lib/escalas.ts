// Escalas de color de los mapas del predio. Un color significa lo mismo en cualquier parcela cuando la escala es fija.
export const COLORES_NDVI = ['#d9cbb0', '#d9a85b', '#829e30', '#3f611c']
export const DOMINIO_NDVI: [number, number] = [0.1, 0.9]

function mezclar(desde: string, hasta: string, t: number): string {
  const canal = (hex: string, i: number) => parseInt(hex.slice(1 + i * 2, 3 + i * 2), 16)
  return `rgb(${[0, 1, 2].map((i) => Math.round(canal(desde, i) + (canal(hasta, i) - canal(desde, i)) * t)).join(', ')})`
}

export function colorEnEscala(colores: string[], [minimo, maximo]: [number, number], valor: number): string {
  const posicion = Math.min(1, Math.max(0, (valor - minimo) / (maximo - minimo))) * (colores.length - 1)
  const tramo = Math.min(colores.length - 2, Math.floor(posicion))
  return mezclar(colores[tramo], colores[tramo + 1], posicion - tramo)
}
