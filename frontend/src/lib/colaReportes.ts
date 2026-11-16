import { guardar, leer } from '../state/storage'
import { ApiError, enviarReporte, FASES_REPORTE, type FaseReporte } from './api'

// Reportar guarda primero en una cola local y la sube de inmediato: con señal intermitente (el caso real del
// campo) el reporte no se pierde, queda en el teléfono y se sube cuando hay conexión. Cada reporte lleva su cultivo.
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
// Las etapas se guardaban con el texto que se mostraba; hoy se envía su clave.
const CLAVE_DE_ETAPA_ANTIGUA: Record<string, FaseReporte> = {
  Brote: 'brote', Hojas: 'hojas', Flor: 'flor', 'Fruto o raíz': 'fruto', Amarilla: 'amarilla', Cosecha: 'cosecha',
}

export function encolarReporte(reporte: Omit<ReporteEncolado, 'id' | 'creado'>): ReporteEncolado {
  const completo: ReporteEncolado = { ...reporte, id: crypto.randomUUID(), creado: new Date().toISOString() }
  const cola = leer<ReporteEncolado[]>(CLAVE, [])
  guardar(CLAVE, [...cola, completo])
  return completo
}

export function leerCola(): ReporteEncolado[] {
  return leer<ReporteEncolado[]>(CLAVE, [])
}

// Lo que sigue en cola de un cultivo: aún no llegó al servidor.
export function pendientesDe(idCultivo: number): ReporteEncolado[] {
  return leerCola().filter((r) => r.idCultivo === idCultivo)
}

export function claveDeFase(fase: string | null): FaseReporte | null {
  if (fase === null) return null
  return FASES_REPORTE.find((f) => f === fase) ?? CLAVE_DE_ETAPA_ANTIGUA[fase] ?? null
}

let subiendo: Promise<number> | null = null

// Sube la cola, de a un reporte. Sale del teléfono el que llegó, o el que el servidor rechaza por inválido (un cultivo
// que ya no existe, una fecha fuera de rango: reintentarlo no lo arregla). Se queda el que falló por la conexión o
// por el servidor. Devuelve cuántos quedan en cola.
export function sincronizarCola(): Promise<number> {
  if (!subiendo) subiendo = subir().finally(() => (subiendo = null))
  return subiendo
}

async function subir(): Promise<number> {
  let cola = leerCola()
  for (const reporte of cola) {
    const fase = claveDeFase(reporte.fase)
    let quitar = fase === null || reporte.idCultivo === null
    if (!quitar) {
      try {
        await enviarReporte(reporte.idCultivo as number, { fase: fase as FaseReporte, fecha: reporte.fecha, capturado: reporte.creado })
        quitar = true
      } catch (err) {
        const rechazado = err instanceof ApiError && err.status >= 400 && err.status < 500 && ![401, 408, 429].includes(err.status)
        if (!rechazado) break   // sin conexión, servidor caído o sesión que aún no está: se reintenta después
        quitar = true
      }
    }
    if (quitar) {
      cola = leerCola().filter((r) => r.id !== reporte.id)
      guardar(CLAVE, cola)
    }
  }
  return leerCola().length
}
