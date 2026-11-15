// Cómo se dice y se dibuja el estado del cielo de un día, a partir del código de tiempo (WMO) que entrega
// Open-Meteo. Sin código (días viejos) solo se puede decir si llovió, por los milímetros del día.
import { tr } from '../i18n/dictionary'
import type { ComponentType, SVGProps } from 'react'
import {
  IconoLluvia, IconoNiebla, IconoNieve, IconoNublado, IconoParcialmenteNublado, IconoSol, IconoTormenta,
} from '../components/icons'

type Icono = ComponentType<SVGProps<SVGSVGElement> & { tamano?: number }>

export interface Cielo {
  texto: string
  Icono: Icono
}

const LLUVIA_MIN_MM = 1

export function cieloDelDia(codigo: number | null | undefined, lluviaMm: number | null | undefined): Cielo | null {
  if (codigo === null || codigo === undefined) {
    return lluviaMm !== null && lluviaMm !== undefined && lluviaMm >= LLUVIA_MIN_MM ? { texto: tr('tiempo_lluvia'), Icono: IconoLluvia } : null
  }
  if (codigo === 0 || codigo === 1) return { texto: tr('tiempo_despejado'), Icono: IconoSol }
  if (codigo === 2) return { texto: tr('tiempo_parcial'), Icono: IconoParcialmenteNublado }
  if (codigo === 3) return { texto: tr('tiempo_cubierto'), Icono: IconoNublado }
  if (codigo === 45 || codigo === 48) return { texto: tr('tiempo_niebla'), Icono: IconoNiebla }
  if (codigo >= 51 && codigo <= 57) return { texto: tr('tiempo_llovizna'), Icono: IconoLluvia }
  if ((codigo >= 61 && codigo <= 67) || (codigo >= 80 && codigo <= 82)) return { texto: codigo >= 80 ? tr('tiempo_chubascos') : tr('tiempo_lluvia'), Icono: IconoLluvia }
  if ((codigo >= 71 && codigo <= 77) || codigo === 85 || codigo === 86) return { texto: tr('tiempo_nieve'), Icono: IconoNieve }
  if (codigo >= 95) return { texto: tr('tiempo_tormenta'), Icono: IconoTormenta }
  return null
}
