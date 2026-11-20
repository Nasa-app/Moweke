import type { Punto } from './geometria'

// Centro y zoom con que se ve cada país entero. Sirve para abrir el mapa en el país de la persona cuando no hay
// ubicación del dispositivo: el país sale de la región del idioma del navegador (es-CL → CL), sin enviar nada a ningún servicio.
const PAISES: Record<string, [number, number, number]> = {
  AR: [-38.4, -63.6, 4], BO: [-16.3, -63.6, 5], BR: [-14.2, -51.9, 4], CL: [-35.7, -71.5, 4], CO: [4.6, -74.1, 5],
  CR: [9.7, -83.8, 7], CU: [21.5, -79.5, 6], DO: [18.7, -70.2, 7], EC: [-1.8, -78.2, 6], SV: [13.8, -88.9, 8],
  GT: [15.5, -90.3, 7], HN: [14.8, -86.6, 7], MX: [23.6, -102.5, 5], NI: [12.9, -85.2, 7], PA: [8.5, -80.1, 7],
  PY: [-23.4, -58.4, 6], PE: [-9.2, -75.0, 5], PR: [18.2, -66.5, 8], UY: [-32.5, -55.8, 7], VE: [6.4, -66.6, 6],
  US: [39.8, -98.6, 4], CA: [56.1, -106.3, 3], ES: [40.4, -3.7, 6], PT: [39.4, -8.2, 6], FR: [46.6, 2.2, 6],
  DE: [51.2, 10.4, 6], IT: [41.9, 12.6, 6], GB: [54.0, -2.5, 6], IE: [53.4, -8.2, 7], NL: [52.1, 5.3, 7],
  AU: [-25.3, 133.8, 4], NZ: [-41.0, 174.0, 5], ZA: [-29.0, 25.1, 5], KE: [0.0, 37.9, 6], NG: [9.1, 8.7, 6],
  ET: [9.1, 40.5, 6], GH: [7.9, -1.0, 7], IN: [22.0, 79.0, 5], PH: [12.9, 121.8, 6], ID: [-2.5, 118.0, 4],
  VN: [14.1, 108.3, 6], TH: [15.9, 101.0, 6], CN: [35.9, 104.2, 4], JP: [36.2, 138.3, 5],
}

export function paisDelNavegador(): string | null {
  const idiomas = typeof navigator === 'undefined' ? [] : (navigator.languages?.length ? navigator.languages : [navigator.language])
  for (const idioma of idiomas) {
    try {
      const region = new Intl.Locale(idioma).region
      if (region && PAISES[region]) return region
    } catch {
      // idioma mal formado: se prueba con el siguiente
    }
  }
  return null
}

export function vistaDePais(codigo: string | null): { centro: Punto; zoom: number } | null {
  const pais = codigo ? PAISES[codigo] : undefined
  return pais ? { centro: [pais[0], pais[1]], zoom: pais[2] } : null
}
