import type { SueloDeclarado } from './api'
import { tr } from '../i18n/dictionary'

// Las cuatro preguntas sobre el suelo que no se pueden medir desde el satélite. Las respuestas son las
// clases de EcoCrop (database/importar_ecocrop.py), dichas con palabras de campo. Los textos se leen al
// usarse (getters) para que sigan el idioma vigente; las claves son suelo_<campo>_*.
export interface PreguntaDeSuelo {
  campo: keyof SueloDeclarado
  pregunta: string
  ayuda?: string
  opciones: { valor: string; texto: string }[]
}

const opcion = (campo: string, valor: string) => ({
  valor,
  get texto() {
    return tr(`suelo_${campo}_${valor}`)
  },
})

export const PREGUNTAS_SUELO: PreguntaDeSuelo[] = [
  {
    campo: 'drenaje',
    // Se pregunta por inundación, no por encharcamiento: un charco que se seca en pocos días se corrige con
    // zanjas o camellones y no descarta cultivos. 'poorly' es el suelo saturado más de la mitad del año.
    get pregunta() {
      return tr('suelo_drenaje_pregunta')
    },
    get ayuda() {
      return tr('suelo_drenaje_ayuda')
    },
    opciones: [opcion('drenaje', 'poorly'), opcion('drenaje', 'well'), opcion('drenaje', 'excessive')],
  },
  {
    campo: 'salinidad',
    get pregunta() {
      return tr('suelo_salinidad_pregunta')
    },
    opciones: [opcion('salinidad', 'low'), opcion('salinidad', 'medium'), opcion('salinidad', 'high')],
  },
  {
    campo: 'profundidad',
    get pregunta() {
      return tr('suelo_profundidad_pregunta')
    },
    opciones: [opcion('profundidad', 'very_shallow'), opcion('profundidad', 'shallow'), opcion('profundidad', 'medium'), opcion('profundidad', 'deep')],
  },
  {
    campo: 'fertilidad',
    get pregunta() {
      return tr('suelo_fertilidad_pregunta')
    },
    opciones: [opcion('fertilidad', 'low'), opcion('fertilidad', 'moderate'), opcion('fertilidad', 'high')],
  },
]
