// Cómo se muestran al agricultor los nombres y fechas que el API entrega como claves
// (ajo_chilote, emergencia->tuberizacion, 2026-11-14).

const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
const MESES_CORTOS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
const DIAS_CORTOS = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb']

const PALABRAS: Record<string, string> = {
  emergencia: 'Brote',
  tuberizacion: 'Tuberización',
  bulbificacion: 'Bulbificación',
  floracion: 'Floración',
  madurez: 'Madurez',
  siembra: 'Siembra',
  helada: 'Helada',
  calor: 'Calor',
  sequia: 'Sequía',
  anegamiento: 'Exceso de agua',
  tizon: 'Tizón',
  ceniza: 'Ceniza',
  temperatura: 'Temperatura',
  humedad: 'Lluvia',
  ph: 'Acidez del suelo',
  radiacion: 'Sol',
}

function capitalizar(texto: string): string {
  return texto ? texto[0].toUpperCase() + texto.slice(1) : texto
}

export function nombreClave(clave: string): string {
  return PALABRAS[clave] ?? capitalizar(clave.replace(/_/g, ' '))
}

// 'emergencia->tuberizacion' -> 'De brote a tuberización'
export function nombreFase(fase: string): string {
  const [desde, hasta] = fase.split('->')
  if (!hasta) return nombreClave(fase)
  return `De ${nombreClave(desde).toLowerCase()} a ${nombreClave(hasta).toLowerCase()}`
}

// Las especies curadas vienen con clave propia en español (ajo_chilote). Las de EcoCrop
// usan como clave su nombre científico (chenopodium_quinoa) y traen una lista de nombres
// comunes, casi siempre en inglés: se muestra el primero y, si no hay, el científico.
export function nombreEspecie(especie: string, candidata?: { nombres_comunes: string | null; nombre_cientifico: string | null }): string {
  const cientifico = candidata?.nombre_cientifico
  const esDeEcocrop = cientifico ? cientifico.trim().toLowerCase().replace(/[^a-z0-9\s]/g, '').replace(/\s+/g, '_') === especie : false
  if (!esDeEcocrop) return capitalizar(especie.replace(/_/g, ' '))
  const comun = candidata?.nombres_comunes?.split(',')[0]?.trim()
  return comun ? capitalizar(comun) : (cientifico ?? especie)
}

// Fecha ISO (AAAA-MM-DD) como fecha local, sin el corrimiento de zona de new Date(iso).
export function aFecha(iso: string): Date {
  const [anio, mes, dia] = iso.slice(0, 10).split('-').map(Number)
  return new Date(anio, mes - 1, dia)
}

export function aIso(fecha: Date): string {
  return `${fecha.getFullYear()}-${String(fecha.getMonth() + 1).padStart(2, '0')}-${String(fecha.getDate()).padStart(2, '0')}`
}

export function fechaCorta(iso: string | null | undefined): string {
  if (!iso) return '—'
  const fecha = aFecha(iso)
  return `${fecha.getDate()} ${MESES_CORTOS[fecha.getMonth()]}`
}

export function diaSemana(iso: string): string {
  return DIAS_CORTOS[aFecha(iso).getDay()]
}

export function nombreMes(indice: number): string {
  return MESES[((indice % 12) + 12) % 12]
}

export function diasEntre(desdeIso: string, hastaIso: string): number {
  return Math.round((aFecha(hastaIso).getTime() - aFecha(desdeIso).getTime()) / 86_400_000)
}

export function numero(valor: number | null | undefined, decimales = 0): string {
  if (valor === null || valor === undefined || Number.isNaN(valor)) return '—'
  return valor.toLocaleString('es-CL', { minimumFractionDigits: decimales, maximumFractionDigits: decimales })
}

// Fracción de 0 a 1 (puntaje, pérdida) como porcentaje entero.
export function aPorcentaje(fraccion: number | null | undefined): number {
  return Math.round((fraccion ?? 0) * 100)
}

const EFECTOS: Record<string, string> = {
  atraso: 'Atrasa el cultivo',
  parcial: 'Baja la cosecha',
  total: 'Puede perderse el cultivo',
}

export function nombreEfecto(efecto: string): string {
  return EFECTOS[efecto] ?? capitalizar(efecto)
}

const HORIZONTES: Record<string, string> = {
  observado: 'Ya ocurrió',
  pronostico: 'Pronóstico',
  estimado: 'Estimado con el año pasado',
}

export function nombreHorizonte(horizonte: string | null | undefined): string {
  return horizonte ? (HORIZONTES[horizonte] ?? horizonte) : '—'
}
