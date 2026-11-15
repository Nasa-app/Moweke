import type { SueloDeclarado } from './api'

// Las cuatro preguntas sobre el suelo que no se pueden medir desde el satélite. Las respuestas son las
// clases de EcoCrop (database/importar_ecocrop.py), dichas con palabras de campo.
export interface PreguntaDeSuelo {
  campo: keyof SueloDeclarado
  pregunta: string
  ayuda?: string
  opciones: { valor: string; texto: string }[]
}

export const PREGUNTAS_SUELO: PreguntaDeSuelo[] = [
  {
    campo: 'drenaje',
    // Se pregunta por inundación, no por encharcamiento: un charco que se seca en pocos días se corrige con
    // zanjas o camellones y no descarta cultivos. 'poorly' es el suelo saturado más de la mitad del año.
    pregunta: '¿Se inunda tu terreno?',
    ayuda: 'Un charco que se seca en pocos días no cuenta: eso se arregla con zanjas o camellones.',
    opciones: [
      { valor: 'poorly', texto: 'Sí, el agua queda gran parte del año' },
      { valor: 'well', texto: 'No, el agua baja bien' },
      { valor: 'excessive', texto: 'No se inunda, pero se seca muy rápido' },
    ],
  },
  {
    campo: 'salinidad',
    pregunta: '¿Ves sal en el suelo?',
    opciones: [
      { valor: 'low', texto: 'No veo sal' },
      { valor: 'medium', texto: 'Manchas blancas en algunas partes' },
      { valor: 'high', texto: 'Costras blancas y casi nada crece' },
    ],
  },
  {
    campo: 'profundidad',
    pregunta: '¿Hasta dónde llega la pala antes de topar piedra o tosca?',
    opciones: [
      { valor: 'very_shallow', texto: 'Menos de 20 cm' },
      { valor: 'shallow', texto: 'De 20 a 50 cm' },
      { valor: 'medium', texto: 'De 50 cm a 1,5 m' },
      { valor: 'deep', texto: 'Más de 1,5 m' },
    ],
  },
  {
    campo: 'fertilidad',
    pregunta: '¿Cómo es la tierra?',
    opciones: [
      { valor: 'low', texto: 'Pobre: cuesta que crezcan las plantas' },
      { valor: 'moderate', texto: 'Regular' },
      { valor: 'high', texto: 'Rica: negra y suelta' },
    ],
  },
]
