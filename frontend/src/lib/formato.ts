// Cómo se muestran al agricultor los nombres y fechas que el API entrega como claves
// (ajo_chilote, emergencia->tuberizacion, 2026-11-14).
import type { CategoriaClima, Escenario, SerieClimatica } from './api'
import { idiomaDeNombres, nombreCatalogado } from './nombres'
import { localeVigente, tr } from '../i18n/dictionary'

// Los textos viven en i18n/textos/lib.ts; los meses y días son claves numeradas (fmt_mes_1, fmt_dia_0).
const mes = (indice: number) => tr(`fmt_mes_${indice}`)
const mesCorto = (indice: number) => tr(`fmt_mes_corto_${indice}`)

// Claves que el API entrega (fases, amenazas, categorías de clima y suelo) y que tienen nombre en fmt_palabra_<clave>.
const CLAVES_PALABRAS = new Set([
  'emergencia', 'tuberizacion', 'bulbificacion', 'floracion', 'madurez', 'siembra', 'helada', 'calor', 'sequia',
  'anegamiento', 'tizon', 'ceniza', 'temperatura', 'humedad', 'ph', 'radiacion', 'altitud', 'textura', 'drenaje',
  'salinidad', 'profundidad', 'fertilidad',
])

const palabra = (clave: string): string | undefined => (CLAVES_PALABRAS.has(clave) ? tr(`fmt_palabra_${clave}`) : undefined)

// 'a, b y c' / 'a, b and c'
function unirLista(nombres: string[]): string {
  return nombres.length > 1 ? tr('fmt_lista_y', { inicio: nombres.slice(0, -1).join(', '), ultimo: nombres[nombres.length - 1] }) : nombres[0]
}

function capitalizar(texto: string): string {
  return texto ? texto[0].toUpperCase() + texto.slice(1) : texto
}

const RANGOS = new Set(['variedad', 'subespecie', 'forma', 'cultivar'])

// 'subespecie biflora' / 'variedad reptans': como se dice una variedad de EcoCrop a quien no es botánico.
export function textoVariedad(v: { rango: string | null; nombre: string | null }): string {
  return v.rango && v.nombre ? `${RANGOS.has(v.rango) ? tr(`fmt_rango_${v.rango}`) : v.rango} ${v.nombre}` : tr('fmt_sin_variedad')
}

export function nombreClave(clave: string): string {
  return palabra(clave) ?? capitalizar(clave.replace(/_/g, ' '))
}

// 'emergencia->tuberizacion' -> 'De brote a tuberización'
export function nombreFase(fase: string): string {
  const [desde, hasta] = fase.split('->')
  if (!hasta) return nombreClave(fase)
  return tr('fmt_fase_de_a', { desde: nombreClave(desde).toLowerCase(), hasta: nombreClave(hasta).toLowerCase() })
}

// Qué anuncia un indicador local, dicho como lo entiende el agricultor.
const SIGNIFICADOS = new Set(['precipitacion_alta', 'precipitacion_baja', 'helada', 'precipitacion_temprana', 'precipitacion_tardia'])

export function nombreSignificado(clave: string): string {
  return SIGNIFICADOS.has(clave) ? tr(`fmt_significado_${clave}`) : nombreClave(clave)
}

export function nombreCategoria(categoria: string): string {
  return categoria === 'aves' ? tr('fmt_categoria_ave') : tr('fmt_categoria_floracion')
}

// Si el mes de una fecha ISO cae en la ventana de un indicador; la ventana puede cruzar el
// fin de año (de noviembre a febrero incluye diciembre y enero). Es la misma regla que
// aplica el API al recibir el reporte.
export function mesEnVentana(fechaIso: string, desde: number, hasta: number): boolean {
  const mes = Number(fechaIso.slice(5, 7))
  return desde <= hasta ? mes >= desde && mes <= hasta : mes >= desde || mes <= hasta
}

export function ventanaEnMeses(desde: number, hasta: number): string {
  return desde === hasta ? mes(desde) : tr('fmt_ventana', { desde: mes(desde), hasta: mes(hasta) })
}

// El nombre sale, en este orden, de la candidata (nombre_es / nombre_en del idioma activo), del
// catálogo de nombres y, si ninguno lo tiene, de la clave: las curadas usan una clave en español
// (ajo_chilote) y las de EcoCrop su nombre científico, con el primer nombre común como último recurso.
export function nombreEspecie(
  especie: string,
  candidata?: { nombres_comunes: string | null; nombre_cientifico: string | null; nombre_es?: string | null; nombre_en?: string | null },
): string {
  const propio = candidata ? (idiomaDeNombres() === 'en' ? candidata.nombre_en : candidata.nombre_es) : null
  const nombre = propio || nombreCatalogado(especie)
  if (nombre) return capitalizar(nombre)
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
  return tr('fmt_fecha_corta', { dia: fecha.getDate(), mes: mesCorto(fecha.getMonth() + 1) })
}

export function diaSemana(iso: string): string {
  return tr(`fmt_dia_${aFecha(iso).getDay()}`)
}

export function nombreMes(indice: number): string {
  return mes((((indice % 12) + 12) % 12) + 1)
}

export function diasEntre(desdeIso: string, hastaIso: string): number {
  return Math.round((aFecha(hastaIso).getTime() - aFecha(desdeIso).getTime()) / 86_400_000)
}

export function numero(valor: number | null | undefined, decimales = 0): string {
  if (valor === null || valor === undefined || Number.isNaN(valor)) return '—'
  return valor.toLocaleString(localeVigente(), { minimumFractionDigits: decimales, maximumFractionDigits: decimales })
}

// Fracción de 0 a 1 (puntaje, pérdida) como porcentaje entero.
// Los textos se leen al usarse (getters) para que sigan el idioma vigente.
export const NOMBRE_ESCENARIO: Record<Escenario, string> = {
  get observado() {
    return tr('fmt_escenario_observado')
  },
  get moderado() {
    return tr('fmt_escenario_moderado')
  },
  get fuerte() {
    return tr('fmt_escenario_fuerte')
  },
}

const grados = (v: number) => v.toLocaleString(localeVigente(), { minimumFractionDigits: 1, maximumFractionDigits: 1, signDisplay: 'exceptZero' })

// Qué clima a futuro se está suponiendo, dicho en simple.
export function textoEscenario(escenario: Escenario, serie: SerieClimatica | null): string {
  if (escenario === 'moderado') return tr('fmt_texto_escenario_moderado')
  if (escenario === 'fuerte') return tr('fmt_texto_escenario_fuerte')
  if (!serie) return tr('fmt_texto_escenario_tendencia')
  const observada = serie.temp_c_por_decada_observada
  const vars = { anios: serie.anios, grados: grados(observada), horizonte: serie.horizonte }
  return observada > 0 ? tr('fmt_texto_escenario_subio', vars) : tr('fmt_texto_escenario_no_subio', vars)
}

const textoCategoria = (categoria: CategoriaClima) => ({
  get chip() {
    return tr(`fmt_categoria_clima_${categoria}_chip`)
  },
  get detalle() {
    return tr(`fmt_categoria_clima_${categoria}_detalle`)
  },
})

export const TEXTO_CATEGORIA_CLIMA: Record<CategoriaClima, { chip: string; detalle: string }> = {
  tradicional: textoCategoria('tradicional'),
  emergente: textoCategoria('emergente'),
  en_riesgo: textoCategoria('en_riesgo'),
}

export function aPorcentaje(fraccion: number | null | undefined): number {
  return Math.round((fraccion ?? 0) * 100)
}

const DATOS_FALTANTES = new Set(['temperatura', 'helada', 'lluvia', 'ph', 'radiacion', 'agua_suelo'])

// Aviso para cuando el servidor no pudo medir algo de la parcela: sin ese dato, ese factor no
// descarta nada y la lista puede traer especies que la parcela no tolera.
export function textoDatosFaltantes(claves: string[] | undefined): string | null {
  if (!claves?.length) return null
  const nombres = claves.map((c) => (DATOS_FALTANTES.has(c) ? tr(`fmt_dato_faltante_${c}`) : c))
  return tr('fmt_datos_faltantes', { lista: unirLista(nombres) })
}

// Las preguntas sobre el suelo que el agricultor todavia no responde. Sin ellas la lista no las toma en cuenta.
export function textoSueloSinDeclarar(claves: string[] | undefined): string | null {
  if (!claves?.length) return null
  const nombres = claves.map((c) => palabra(c) ?? c).map((n) => n.toLowerCase())
  return tr('fmt_suelo_sin_declarar', { lista: unirLista(nombres) })
}

const EFECTOS = new Set(['atraso', 'parcial', 'total'])

export function nombreEfecto(efecto: string): string {
  return EFECTOS.has(efecto) ? tr(`fmt_efecto_${efecto}`) : capitalizar(efecto)
}

const HORIZONTES = new Set(['observado', 'pronostico', 'estimado'])

export function nombreHorizonte(horizonte: string | null | undefined): string {
  return horizonte ? (HORIZONTES.has(horizonte) ? tr(`fmt_horizonte_${horizonte}`) : horizonte) : '—'
}

// Título y cifra de una alerta de clima del predio, en el idioma vigente. El salto lleva signo (+7° / -7°).
export function textoAlertaClima(a: { tipo: string; valor: number; fuerte: boolean }): { titulo: string; cifra: string } {
  const titulo = tr(a.fuerte ? 'alerta_clima_helada_fuerte' : `alerta_clima_${a.tipo}`)
  if (a.tipo === 'lluvia_fuerte') return { titulo, cifra: tr('alerta_clima_valor_lluvia', { valor: numero(a.valor) }) }
  if (a.tipo.endsWith('_brusco')) {
    return { titulo, cifra: tr('alerta_clima_valor_salto', { valor: `${a.valor > 0 ? '+' : ''}${numero(a.valor)}` }) }
  }
  return { titulo, cifra: tr('alerta_clima_valor_temp', { valor: numero(a.valor) }) }
}
