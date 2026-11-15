// Cómo se muestran al agricultor los nombres y fechas que el API entrega como claves
// (ajo_chilote, emergencia->tuberizacion, 2026-11-14).
import type { CategoriaClima, Escenario, SerieClimatica } from './api'

const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
const MESES_CORTOS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
const DIAS_CORTOS = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb']

const PALABRAS: Record<string, string> = {
  emergencia: 'Brote',
  tuberizacion: 'Formación de papas',
  bulbificacion: 'Formación del bulbo',
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
  altitud: 'Altura',
  textura: 'Tipo de suelo',
  drenaje: 'Drenaje',
  salinidad: 'Sal en el suelo',
  profundidad: 'Profundidad del suelo',
  fertilidad: 'Fertilidad',
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
export const NOMBRE_ESCENARIO: Record<Escenario, string> = {
  observado: 'Como hasta ahora',
  moderado: 'Más calor',
  fuerte: 'Mucho más calor',
}

const grados = (v: number) => v.toLocaleString('es-CL', { minimumFractionDigits: 1, maximumFractionDigits: 1, signDisplay: 'exceptZero' })

// Qué clima a futuro se está suponiendo, dicho en simple.
export function textoEscenario(escenario: Escenario, serie: SerieClimatica | null): string {
  if (escenario === 'moderado') return 'Suponemos que la temperatura sube 0,3 °C por década hasta 2040. Es un supuesto, no un pronóstico.'
  if (escenario === 'fuerte') return 'Suponemos que la temperatura sube 0,6 °C por década hasta 2040. Es un supuesto, no un pronóstico.'
  if (!serie) return 'Seguimos la tendencia que ha tenido el clima de tu parcela.'
  const observada = serie.temp_c_por_decada_observada
  return observada > 0
    ? `En ${serie.anios} años, la temperatura de tu parcela subió ${grados(observada)} °C por década. Seguimos esa tendencia hasta ${serie.horizonte}.`
    : `En ${serie.anios} años, la temperatura de tu parcela no ha subido (${grados(observada)} °C por década). No suponemos que baje: sin calentamiento, casi nada cambia hacia ${serie.horizonte}.`
}

export const TEXTO_CATEGORIA_CLIMA: Record<CategoriaClima, { chip: string; detalle: string }> = {
  tradicional: { chip: 'Se da bien hace años', detalle: 'Con el clima de los últimos años y el que viene, esta especie se mantiene.' },
  emergente: { chip: 'Nueva para tu zona', detalle: 'Antes le costaba, y con el clima que viene le iría cada vez mejor.' },
  en_riesgo: { chip: 'Cada vez menos apta', detalle: 'Hasta ahora se daba, y con el clima que viene le iría peor.' },
}

export function aPorcentaje(fraccion: number | null | undefined): number {
  return Math.round((fraccion ?? 0) * 100)
}

const DATOS_FALTANTES: Record<string, string> = {
  temperatura: 'la temperatura',
  helada: 'las heladas',
  lluvia: 'la lluvia',
  ph: 'la acidez del suelo (pH)',
  radiacion: 'el sol',
  agua_suelo: 'el agua que guarda el suelo',
}

// Aviso para cuando el servidor no pudo medir algo de la parcela: sin ese dato, ese factor no
// descarta nada y la lista puede traer especies que la parcela no tolera.
export function textoDatosFaltantes(claves: string[] | undefined): string | null {
  if (!claves?.length) return null
  const nombres = claves.map((c) => DATOS_FALTANTES[c] ?? c)
  const lista = nombres.length > 1 ? `${nombres.slice(0, -1).join(', ')} y ${nombres[nombres.length - 1]}` : nombres[0]
  return `No pudimos medir ${lista} de tu parcela. La lista puede incluir especies que no se den bien aquí.`
}

// Las preguntas sobre el suelo que el agricultor todavia no responde. Sin ellas la lista no las toma en cuenta.
export function textoSueloSinDeclarar(claves: string[] | undefined): string | null {
  if (!claves?.length) return null
  const nombres = claves.map((c) => PALABRAS[c] ?? c).map((n) => n.toLowerCase())
  const lista = nombres.length > 1 ? `${nombres.slice(0, -1).join(', ')} y ${nombres[nombres.length - 1]}` : nombres[0]
  return `Cuéntanos de tu suelo (${lista}) para afinar la lista.`
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
