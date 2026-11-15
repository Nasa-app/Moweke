import { guardar, leer } from '../state/storage'

// POST /api/observaciones no existe todavía (ver docs/plan-construccion.md, Fase D:
// "es lo que más desbloquea"). Mientras tanto, reportar guarda en una cola local --
// el gesto offline-first real que describe el handoff (Android de gama baja, señal
// intermitente): el reporte no se pierde, solo espera a que haya endpoint real.
export interface ReporteEncolado {
  id: string
  fecha: string
  idCultivo: number | null
  fase: string | null
  colorHojas: string | null
  senales: string[]
  creado: string
}

const CLAVE = 'cola_reportes'

export function encolarReporte(reporte: Omit<ReporteEncolado, 'id' | 'creado'>): ReporteEncolado {
  const completo: ReporteEncolado = { ...reporte, id: crypto.randomUUID(), creado: new Date().toISOString() }
  const cola = leer<ReporteEncolado[]>(CLAVE, [])
  guardar(CLAVE, [...cola, completo])
  return completo
}

export function leerCola(): ReporteEncolado[] {
  return leer<ReporteEncolado[]>(CLAVE, [])
}
