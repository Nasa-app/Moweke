// Fases de la luna calculadas con el mes sinódico medio (29,53 días) desde una luna nueva conocida
// (6 ene 2000, 18:14 UTC). Es una aproximación: la hora real de cada fase puede diferir hasta
// ~14 horas, así que la fecha puede correrse un día. Sin red ni datos externos.
import { tr } from '../i18n/dictionary'

const MES_SINODICO_DIAS = 29.530588853
const LUNA_NUEVA_REFERENCIA_MS = Date.UTC(2000, 0, 6, 18, 14)
const DIA_MS = 86_400_000

export type TipoFase = 'nueva' | 'creciente' | 'llena' | 'menguante'

export interface FaseLunar {
  tipo: TipoFase
  nombre: string
  fechaIso: string
}

const TIPOS: TipoFase[] = ['nueva', 'creciente', 'llena', 'menguante']

function aIsoLocal(ms: number): string {
  const f = new Date(ms)
  return `${f.getFullYear()}-${String(f.getMonth() + 1).padStart(2, '0')}-${String(f.getDate()).padStart(2, '0')}`
}

// Las cuatro fases del ciclo actual, de luna nueva a cuarto menguante. "Ahora" es la creciente mientras la
// luna sube (de nueva a llena) y la menguante mientras baja (de llena a nueva): son las dos que importan para
// sembrar, igual que en la referencia de diseño.
export function fasesLunares(hoy: Date = new Date()): { fases: FaseLunar[]; actual: number } {
  const cuarto = MES_SINODICO_DIAS / 4
  const dias = (hoy.getTime() - LUNA_NUEVA_REFERENCIA_MS) / DIA_MS
  const ciclo = Math.floor(dias / MES_SINODICO_DIAS)
  const fases = [0, 1, 2, 3].map((i) => {
    const tipo = TIPOS[i]
    return { tipo, nombre: tr(`luna_fase_${tipo}`), fechaIso: aIsoLocal(LUNA_NUEVA_REFERENCIA_MS + (ciclo * 4 + i) * cuarto * DIA_MS) }
  })
  const edad = dias - ciclo * MES_SINODICO_DIAS
  return { fases, actual: edad < MES_SINODICO_DIAS / 2 ? 1 : 3 }
}

// Solo lo que el saber de las comunidades dice de creciente y menguante (ya estaba en la app); de
// nueva y llena no hay texto con fuente, así que no se inventa.
// Se lee al usarse (getters) para que siga el idioma vigente.
export const NOTA_FASE: Partial<Record<TipoFase, string>> = {
  get creciente() {
    return tr('luna_nota_creciente')
  },
  get menguante() {
    return tr('luna_nota_menguante')
  },
}
