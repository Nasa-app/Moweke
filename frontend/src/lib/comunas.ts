import { guardar, leer } from '../state/storage'
import { tr } from '../i18n/dictionary'

export const TERRENOS = ['Plano', 'Ladera', 'Alto'] as const

// El valor guardado de TERRENOS se muestra con este nombre en el idioma vigente.
export function nombreTerreno(terreno: (typeof TERRENOS)[number]): string {
  return tr(`comunas_terreno_${terreno.toLowerCase()}`)
}

// Lo que la persona va respondiendo mientras arma su predio. Queda en este dispositivo: el servidor todavía
// no guarda sector ni terreno.
export interface BorradorPredio {
  sector: string
  terreno: (typeof TERRENOS)[number] | ''
  acepto: boolean
}

const CLAVE_BORRADOR = 'onboarding_predio'

export function leerBorrador(): BorradorPredio {
  const guardado = leer<Partial<BorradorPredio>>(CLAVE_BORRADOR, {})
  return {
    sector: typeof guardado.sector === 'string' ? guardado.sector : '',
    terreno: TERRENOS.find((t) => t === guardado.terreno) ?? '',
    acepto: guardado.acepto === true,
  }
}

// La comuna de cada predio, anotada al marcarlo en el registro (cuando la persona acaba de elegirla). Las
// predios marcados de otra forma, o antes de este registro, quedan sin comuna: no se adivina.
export function guardarComunaDeParcela(idParcela: number, comuna: string): void {
  guardar('comunas_parcelas', { ...leer<Record<string, string>>('comunas_parcelas', {}), [String(idParcela)]: comuna })
}

export function comunaDeParcela(idParcela: number | null): string | null {
  if (idParcela === null) return null
  const comuna = leer<Record<string, string>>('comunas_parcelas', {})[String(idParcela)]
  return comuna || null
}

export function guardarBorrador(cambios: Partial<BorradorPredio>): void {
  guardar(CLAVE_BORRADOR, { ...leerBorrador(), ...cambios })
}
