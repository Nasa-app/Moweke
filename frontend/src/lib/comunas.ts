import type { Punto } from './geometria'
import { guardar, leer } from '../state/storage'
import { tr } from '../i18n/dictionary'

// Las comunas de Chiloé y dónde abrir el mapa para marcar la parcela. El punto es el pueblo cabecera de cada
// comuna (coordenadas del geocodificador de Open-Meteo, revisadas el 15-nov-2026), no un deslinde: sirve para
// que el mapa abra cerca y la persona termine de buscar su parcela acercándose. Quinchao: Achao.
export interface Comuna {
  nombre: string
  centro: Punto
}

export const COMUNAS: Comuna[] = [
  { nombre: 'Ancud', centro: [-41.8707, -73.8162] },
  { nombre: 'Castro', centro: [-42.4721, -73.7732] },
  { nombre: 'Chonchi', centro: [-42.6239, -73.775] },
  { nombre: 'Curaco de Vélez', centro: [-42.4389, -73.6012] },
  { nombre: 'Dalcahue', centro: [-42.3785, -73.6501] },
  { nombre: 'Puqueldón', centro: [-42.6, -73.6746] },
  { nombre: 'Queilén', centro: [-42.889, -73.4742] },
  { nombre: 'Quellón', centro: [-43.1182, -73.6166] },
  { nombre: 'Quemchi', centro: [-42.1439, -73.4751] },
  { nombre: 'Quinchao', centro: [-42.4709, -73.4914] },
]

export const COMUNA_POR_DEFECTO = 'Quemchi'
// Con este zoom se ve el pueblo y sus alrededores; para marcar esquinas hay que acercarse más (Mapa.tsx).
export const ZOOM_COMUNA = 13

export function centroDeComuna(nombre: string): Punto | null {
  return COMUNAS.find((c) => c.nombre === nombre)?.centro ?? null
}

export const TERRENOS = ['Plano', 'Ladera', 'Alto'] as const

// El valor guardado de TERRENOS se muestra con este nombre en el idioma vigente.
export function nombreTerreno(terreno: (typeof TERRENOS)[number]): string {
  return tr(`comunas_terreno_${terreno.toLowerCase()}`)
}

// Lo que la persona va respondiendo mientras arma su parcela. Queda en este dispositivo: el servidor todavía
// no guarda comuna, sector ni terreno.
export interface BorradorPredio {
  comuna: string
  sector: string
  terreno: (typeof TERRENOS)[number] | ''
  acepto: boolean
}

const CLAVE_BORRADOR = 'onboarding_predio'

export function leerBorrador(): BorradorPredio {
  const guardado = leer<Partial<BorradorPredio>>(CLAVE_BORRADOR, {})
  return {
    comuna: COMUNAS.some((c) => c.nombre === guardado.comuna) ? (guardado.comuna as string) : COMUNA_POR_DEFECTO,
    sector: typeof guardado.sector === 'string' ? guardado.sector : '',
    terreno: TERRENOS.find((t) => t === guardado.terreno) ?? '',
    acepto: guardado.acepto === true,
  }
}

// La comuna de cada parcela, anotada al marcarla en el registro (cuando la persona acaba de elegirla). Las
// parcelas marcadas de otra forma, o antes de este registro, quedan sin comuna: no se adivina.
export function guardarComunaDeParcela(idParcela: number, comuna: string): void {
  guardar('comunas_parcelas', { ...leer<Record<string, string>>('comunas_parcelas', {}), [String(idParcela)]: comuna })
}

export function comunaDeParcela(idParcela: number | null): string | null {
  if (idParcela === null) return null
  const comuna = leer<Record<string, string>>('comunas_parcelas', {})[String(idParcela)]
  return COMUNAS.some((c) => c.nombre === comuna) ? comuna : null
}

export function guardarBorrador(cambios: Partial<BorradorPredio>): void {
  guardar(CLAVE_BORRADOR, { ...leerBorrador(), ...cambios })
}
