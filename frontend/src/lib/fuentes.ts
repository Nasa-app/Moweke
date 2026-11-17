// De dónde sale cada dato que ve el agricultor. Cada fuente lleva su origen para que se vea de un vistazo qué es de
// NASA, qué es de Copernicus (programa de la Unión Europea; Sentinel-2 lo opera la ESA) y qué es de Chile. Debe
// coincidir con lo que la API realmente descarga (services/ingesta_predio.py): si se agrega una fuente, se agrega aquí.
import { tr } from '../i18n/dictionary'

export type Origen = 'NASA' | 'Copernicus' | 'Chile' | 'Otras fuentes' | 'Comunidad'

export interface FuenteDato {
  titulo: string
  detalle: string
  origenes: Origen[]
  nota: string
}

export const CLASE_ORIGEN: Record<Origen, string> = {
  NASA: 'ps-chip-clima',
  Copernicus: 'ps-chip-acento',
  Chile: 'ps-chip-favorable',
  'Otras fuentes': 'ps-chip-neutro',
  Comunidad: 'ps-chip-precaucion',
}

// Nombre del origen en el idioma vigente (NASA, Copernicus y Chile no cambian).
export function nombreOrigen(origen: Origen): string {
  if (origen === 'Otras fuentes') return tr('fuentesdato_origen_otras')
  if (origen === 'Comunidad') return tr('fuentesdato_origen_comunidad')
  return origen
}

// Titulo, detalle y nota se leen al usarse (getters) para que sigan el idioma vigente; las claves son fuentesdato_<id>_*.
const fuente = (id: string, origenes: Origen[]): FuenteDato => ({
  get titulo() {
    return tr(`fuentesdato_${id}_titulo`)
  },
  get detalle() {
    return tr(`fuentesdato_${id}_detalle`)
  },
  origenes,
  get nota() {
    return tr(`fuentesdato_${id}_nota`)
  },
})

export const FUENTES: FuenteDato[] = [
  fuente('clima', ['NASA', 'Chile']),
  fuente('daymet', ['NASA']),
  fuente('sol', ['NASA']),
  fuente('incendios', ['NASA']),
  fuente('verdor', ['Copernicus']),
  fuente('relieve', ['Copernicus']),
  fuente('cauce', ['NASA']),
  fuente('clima35', ['Copernicus']),
  fuente('pronostico', ['Otras fuentes']),
  fuente('suelo', ['Otras fuentes', 'Chile']),
  fuente('williche', ['Comunidad']),
]
