// Cómo se dice y se dibuja el estado del cielo de un día, a partir del código de tiempo (WMO) que entrega
// Open-Meteo. Sin código (días viejos) solo se puede decir si llovió, por los milímetros del día.
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
    return lluviaMm !== null && lluviaMm !== undefined && lluviaMm >= LLUVIA_MIN_MM ? { texto: 'Lluvia', Icono: IconoLluvia } : null
  }
  if (codigo === 0 || codigo === 1) return { texto: 'Despejado', Icono: IconoSol }
  if (codigo === 2) return { texto: 'Parcialmente nublado', Icono: IconoParcialmenteNublado }
  if (codigo === 3) return { texto: 'Cubierto', Icono: IconoNublado }
  if (codigo === 45 || codigo === 48) return { texto: 'Niebla', Icono: IconoNiebla }
  if (codigo >= 51 && codigo <= 57) return { texto: 'Llovizna', Icono: IconoLluvia }
  if ((codigo >= 61 && codigo <= 67) || (codigo >= 80 && codigo <= 82)) return { texto: codigo >= 80 ? 'Chubascos' : 'Lluvia', Icono: IconoLluvia }
  if ((codigo >= 71 && codigo <= 77) || codigo === 85 || codigo === 86) return { texto: 'Nieve', Icono: IconoNieve }
  if (codigo >= 95) return { texto: 'Tormenta', Icono: IconoTormenta }
  return null
}
