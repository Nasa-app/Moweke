// Cliente del API real de mogen (ver ../../main.py). Cubre auth, parcelas (predio, mapa
// por celdas, clima diario, especies candidatas), cultivos, fenología y el tiempo por comuna.
import { borrar, guardar, leer } from '../state/storage'
import { leerToken } from './sesionToken'
import { guardarLocal, leerLocal } from './cacheLocal'
import { esViejo, registrarFresco, registrarViejo } from './frescura'
import type { NombresCatalogo } from './nombres'
import { tr } from '../i18n/dictionary'

// Una consulta que tarda más que esto se da por perdida: mejor un aviso claro que una pantalla esperando sin fin.
const TIEMPO_MAX_MS = 90_000

const BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000'

// El teléfono no tiene conexión: se avisa al instante, sin esperar el tope de tiempo.
export class ErrorSinRed extends Error {
  constructor() {
    super('sin conexión')
  }
}

export class ApiError extends Error {
  status: number
  detail: unknown
  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : JSON.stringify(detail))
    this.status = status
    this.detail = detail
  }
}

// Texto para mostrar al agricultor a partir de un error del API. FastAPI responde
// `detail` como texto, como objeto {mensaje, ...} o como lista de errores de validación.
export function mensajeDeError(error: unknown, porDefecto: string): string {
  if (!(error instanceof ApiError)) return tr('api_sin_conexion')
  const detalle = error.detail
  if (typeof detalle === 'string') return delServidor(detalle)
  if (detalle && typeof detalle === 'object' && 'mensaje' in detalle) {
    return delServidor(String((detalle as { mensaje: unknown }).mensaje))
  }
  return porDefecto
}

// Los mensajes fijos del servidor llegan en español: los que la gente puede ver se traducen aquí por su texto exacto.
const MENSAJES_SERVIDOR: Record<string, string> = {
  'Demasiados intentos. Espera unos minutos e intenta otra vez.': 'servidor_demasiados_intentos',
  'Base de datos no disponible': 'servidor_sin_base',
  'Parcela no existe': 'servidor_parcela_no_existe',
  'El punto queda fuera de la cobertura actual (Chile continental)': 'servidor_fuera_cobertura',
  'El perímetro se cruza a sí mismo; dibújalo de nuevo sin cruzar líneas': 'servidor_perimetro_cruzado',
  'La especie no está en el catálogo': 'servidor_especie_no_catalogo',
  'Cultivo no existe': 'servidor_cultivo_no_existe',
  'El cultivo no tiene fecha de siembra': 'servidor_cultivo_sin_fecha',
  'Todavía no hay clima diario del predio desde la fecha de siembra': 'servidor_sin_clima',
  'Esta especie todavía no tiene seguimiento por etapa: solo se evalúa si el sitio le sirve': 'servidor_sin_seguimiento',
  'Indicador no existe': 'servidor_indicador_no_existe',
}

function delServidor(texto: string): string {
  const clave = MENSAJES_SERVIDOR[texto]
  return clave ? tr(clave) : texto
}

async function peticion<T>(
  ruta: string,
  opciones: { method?: string; body?: unknown; query?: Record<string, string | number | boolean | undefined> } = {},
): Promise<T> {
  const url = new URL(BASE_URL + ruta)
  if (opciones.query) {
    for (const [clave, valor] of Object.entries(opciones.query)) {
      if (valor !== undefined) url.searchParams.set(clave, String(valor))
    }
  }
  const token = leerToken()
  const metodo = opciones.method ?? 'GET'
  const pedir = () =>
    fetch(url.toString(), {
      method: metodo,
      headers: {
        ...(opciones.body ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: opciones.body ? JSON.stringify(opciones.body) : undefined,
      signal: AbortSignal.timeout(TIEMPO_MAX_MS),
    })
  if (metodo === 'GET' && typeof navigator !== 'undefined' && navigator.onLine === false) throw new ErrorSinRed()
  // Una lectura que se corta en el camino (el móvil cambia de red, el servidor reinicia) se repite una vez: leer
  // dos veces no cambia nada. Una escritura no se repite, podría anotarse dos veces.
  let res: Response
  try {
    res = await pedir()
  } catch (error) {
    if (metodo !== 'GET') throw error
    await new Promise((resolver) => setTimeout(resolver, 1500))
    res = await pedir()
  }
  if (!res.ok) {
    let detail: unknown = null
    try {
      detail = await res.json()
    } catch {
      detail = await res.text().catch(() => null)
    }
    throw new ApiError(res.status, (detail as { detail?: unknown })?.detail ?? detail)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

// Memoria corta de lecturas: varias pantallas piden lo mismo (la parcela, el seguimiento
// del cultivo, el ranking) y cada consulta tarda segundos. Una lectura repetida dentro de
// la vigencia comparte la misma promesa; cualquier escritura la vacía.
const VIGENCIA_MS = 10 * 60 * 1000
const memoria = new Map<string, { momento: number; consulta: Promise<unknown> }>()

// Una lectura que llega se guarda en el teléfono. Si la siguiente falla porque no hay conexión (o el servidor está
// caído), se devuelve lo último guardado y se anota que es viejo. Si el servidor responde con un error (409, 404,
// 401...), se respeta: ese error es la respuesta, no se tapa con un dato anterior.
async function conRespaldo<T>(clave: string, pedir: () => Promise<T>): Promise<T> {
  try {
    const valor = await pedir()
    registrarFresco(clave)
    void guardarLocal(clave, valor)
    return valor
  } catch (err) {
    if (err instanceof ApiError && err.status < 500) throw err
    const guardado = await leerLocal<T>(clave)
    if (!guardado) throw err
    registrarViejo(clave, guardado.momento)
    return guardado.valor
  }
}

function conMemoria<T>(clave: string, pedir: () => Promise<T>, fresco = false): Promise<T> {
  const guardada = memoria.get(clave)
  if (!fresco && guardada && Date.now() - guardada.momento < VIGENCIA_MS) return guardada.consulta as Promise<T>
  const consulta = conRespaldo(clave, pedir)
  memoria.set(clave, { momento: Date.now(), consulta })
  // Un dato viejo (de cuando no había conexión) no se queda en la memoria: la próxima vez se vuelve a pedir.
  consulta.then(() => {
    if (esViejo(clave) && memoria.get(clave)?.consulta === consulta) memoria.delete(clave)
  }, () => undefined)
  consulta.catch(() => {
    if (memoria.get(clave)?.consulta === consulta) memoria.delete(clave)
  })
  return consulta
}

export function olvidarLecturas(): void {
  memoria.clear()
}

// Lo medido del sitio (clima normal, radiación, pH) cambia con la ingesta mensual y con lo que el agricultor declara
// del suelo: queda en el dispositivo y se vuelve a pedir pasado este tiempo, o antes si algo lo invalida.
const VIGENCIA_SITIO_MS = 24 * 60 * 60 * 1000
const claveSitio = (idParcela: number) => `sitio_${idParcela}`

export function olvidarSitio(idParcela: number): void {
  borrar(claveSitio(idParcela))
  memoria.delete(`sitio/${idParcela}`)
}

// ---------------------------------------------------------------- tipos
export interface Usuario {
  id: number
  nombre: string
  rol: 'agricultor' | 'admin'
}

export type EstadoFuente =
  | 'pendiente'
  | 'en_proceso'
  | 'completo'
  | 'error'
  | 'sin_iniciar'
  | 'interrumpida'
  | 'vencida'
  | 'sin_configurar'
  | 'no_aplica'

export interface EstadoDeFuente {
  estado: EstadoFuente
  detalle: 'sin_cobertura' | null
  reintentable: boolean
  con_error: boolean
}

export type EstadoIngesta = Record<string, EstadoDeFuente>

export interface Poligono {
  type: 'Polygon'
  coordinates: number[][][]
}

export interface ParcelaResumen {
  id: number
  altitud_msnm: number | null
  lat: number
  lon: number
  hectareas: number
  perimetro: Poligono
}

export interface Parcela extends ParcelaResumen {
  perimetro: Poligono
  origen_perimetro: 'dibujado' | 'cuadrado_aproximado' | string
  lado_celda_m: number | null
  ecorregion: { nombre: string; bioma: string | null } | null
  estado_ingesta: EstadoIngesta
}

export interface DiaConFocos {
  fecha: string
  focos: number
  distancia_min_km: number | null
  frp_max_mw: number | null
}

export interface ParcelaDetalle extends Parcela {
  suelo: SueloDeclarado
  incendios_cercanos: { radio_km: number; revisado: [string, string] | null; dias_con_focos: DiaConFocos[] }
  curva_satelital: { viable: boolean | null; ventanas_con_pasada_pct?: number | null }
  cercania_cauce: CercaniaCauce
}

export interface CercaniaCauce {
  clase: 'muy_cerca' | 'cerca' | 'lejos' | null
  celdas_con_dato: number
  umbrales_m: [number, number]
  parte_muy_cerca?: number
  parte_cerca?: number
  hand_minimo_m?: number
  hand_mediano_m?: number
}

export type CapaMapa = 'ndvi' | 'altitud' | 'pendiente' | 'hand'
// Capas que el API sirve pero la pantalla de Zonas no ofrece: la imagen de verdor de NASA HLS (30 m) que ve Hoy.
export type CapaServida = CapaMapa | 'ndvi_hls'

export interface CeldaMapa {
  type: 'Feature'
  geometry: { type: string; coordinates: unknown }
  properties: {
    i: number
    j: number
    fraccion_dentro: number
    valor: number | null
    fecha: string | null
    dias_de_antiguedad: number | null
    visible: number | null
  }
}

export interface MapaPredio {
  type: 'FeatureCollection'
  features: CeldaMapa[]
  capa: CapaServida
  unidad: string
  fuente: string
  resolucion_de_la_fuente_m: number
  fecha_comun: string | null
  celdas: number
  celdas_con_dato: number
  resumen: { minimo: number; maximo: number; mediana: number } | null
  origen_perimetro: string
  lado_celda_m: number | null
  hectareas: number
  estado_ingesta: EstadoDeFuente
}

export interface DiaClima {
  fecha: string
  tmin: number | null
  tmax: number | null
  lluvia_mm: number | null
  humedad_relativa: number | null
  // Código de tiempo del día (WMO, de Open-Meteo); null donde el modelo no lo trae (días viejos).
  codigo_tiempo: number | null
  fuente: string | null
  horizonte: 'observado' | 'pronostico'
}

export interface ClimaPredio {
  id_parcela: number
  hoy: string
  dias: DiaClima[]
  estado_ingesta: EstadoIngesta
}

export interface ZonaComuna {
  nombre: string
  lat: number
  lon: number
}

// El tiempo de ahora en una comuna (pronóstico de modelo de Open-Meteo, no medición).
export interface ClimaZona {
  hoy: string
  temperatura_c: number
  humedad_relativa: number
  viento_kmh: number
  codigo_tiempo: number | null
  lluvia_hoy_mm: number | null
  // Primer día de los próximos 7 con mínima de 0 °C o menos; null si no hay.
  primera_helada: string | null
}

export type TipoAlertaClima = 'helada' | 'calor' | 'lluvia_fuerte' | 'calentamiento_brusco' | 'enfriamiento_brusco'

// Un cambio fuerte de clima que viene para el predio (no depende del cultivo). `valor` es el extremo del tramo:
// °C para helada, calor y saltos (el salto lleva signo), mm para lluvia fuerte.
export interface AlertaClima {
  tipo: TipoAlertaClima
  primer_dia: string
  ultimo_dia: string
  valor: number
  horizonte: 'observado' | 'pronostico'
  fuerte: boolean
}

export interface AlertasClima {
  id_parcela: number
  hoy: string
  hay_datos: boolean
  // Último día revisado (fin del pronóstico); solo viene cuando hay datos.
  hasta?: string
  alertas: AlertaClima[]
}

export interface Cultivo {
  id: number
  especie: string
  variedad_local: string | null
  fecha_siembra: string
}

export interface CultivoDeclarado extends Cultivo {
  id_parcela: number
  nivel_madurez: string
  fenologia_disponible: boolean
  etapas: string[]
}

export type Factor =
  | 'temperatura' | 'humedad' | 'helada' | 'ph' | 'radiacion' | 'altitud' | 'textura'
  | 'drenaje' | 'salinidad' | 'profundidad' | 'fertilidad'

// Lo que el agricultor responde sobre su suelo; null = sin responder. No se puede medir desde el satélite.
export interface SueloDeclarado {
  drenaje: 'poorly' | 'well' | 'excessive' | null
  salinidad: 'low' | 'medium' | 'high' | null
  profundidad: 'very_shallow' | 'shallow' | 'medium' | 'deep' | null
  fertilidad: 'low' | 'moderate' | 'high' | null
}

export type CategoriaClima = 'tradicional' | 'emergente' | 'en_riesgo'
export type Escenario = 'observado' | 'moderado' | 'fuerte'

// Compatibilidad de una especie en un periodo: la de un año típico (la mediana) y la de un año difícil (el peor decil).
export interface PeriodoClima {
  tipico: number | null
  dificil: number | null
}

export interface ClimaEspecie {
  historico: PeriodoClima
  reciente: PeriodoClima
  proyectado: PeriodoClima
  categoria: CategoriaClima | null
  cambio_tipico_hasta_horizonte: number
}

export interface SerieClimatica {
  anios: number
  primer_anio: number
  ultimo_anio: number
  periodo_historico: [number, number]
  periodo_reciente: [number, number]
  horizonte: number
  temp_c_por_decada_observada: number
  temp_c_por_decada_usada: number
  lluvia_pct_por_decada_observada: number
  escenario: 'observado' | 'supuesto'
}

// Una variedad, subespecie o cultivar de la misma especie, tal como la distingue EcoCrop, con su compatibilidad.
export interface VariedadEcocrop {
  nombre_cientifico: string
  rango: 'variedad' | 'subespecie' | 'forma' | 'cultivar' | null
  nombre: string | null
  puntaje: number | null
  apta: boolean | null
  mejor: boolean
}

export interface Candidata {
  especie: string
  // Solo si la especie tiene variedades: todas, de la que más conviene a la que menos, y cuál es la mejor
  // (null si la mejor es la especie sin variedad).
  variedades?: VariedadEcocrop[]
  variedad_recomendada?: { rango: NonNullable<VariedadEcocrop['rango']>; nombre: string } | null
  nombre_cientifico: string | null
  nombres_comunes: string | null
  nombre_es: string | null
  nombre_en: string | null
  categorias: string[]
  apta: boolean | null
  marginal?: boolean
  puntaje: number | null
  puntaje_ano_dificil?: number
  clima?: ClimaEspecie
  puntaje_simulacion?: number | null
  puntaje_ecocrop?: number | null
  correcciones?: { tipo: string; ph_sitio?: number; ph_minimo?: number; fertilidad_sitio?: string; fertilidad_requerida?: string }[]
  factores: Partial<Record<Factor, number>>
  factor_limitante?: Factor | null
  mes_inicio_temporada?: number | null
  duracion_temporada_meses?: number | null
  nivel_madurez: string
  metodo: string
  fuera_de_rangos_ecocrop?: boolean
  simulacion?: { apta: boolean; siembra_simulada: string; perdida_simulada?: number; estado_simulado?: string }
}

export interface DatosSitio {
  periodo_clima: [string, string]
  temperatura_media_mensual: number[] | null
  temperatura_minima_mas_baja_mensual: number[] | null
  lluvia_mensual_mm: number[] | null
  lluvia_anual_mm: number | null
  ghi_mensual_kwh_m2_dia: number[] | null
  fuente_radiacion: string | null
  ph: number | null
  agua_disponible_suelo_mm: number | null
  altitud_m: number | null
  altitud_celda_m: number | null
  correccion_temperatura_c: number
  textura: 'light' | 'medium' | 'heavy' | null
  suelo: SueloDeclarado
}

export interface SitioParcela {
  parcela: number
  datos_sitio: DatosSitio
  datos_faltantes: string[]
}

export interface CandidatasSiembra {
  parcela: number
  hectareas: number
  estado_ingesta: EstadoIngesta
  datos_sitio: DatosSitio
  especies_evaluadas: number
  especies_aptas: number
  criterio: 'multianual' | 'un_ano'
  serie_climatica: SerieClimatica | null
  escenario: Escenario
  especies_por_categoria_clima: Record<CategoriaClima, number> | null
  riego: boolean
  datos_faltantes: string[]
  suelo_sin_declarar: string[]
  candidatas: Candidata[]
}

export type Horizonte = 'observado' | 'pronostico' | 'estimado'

export interface EventoDano {
  fase: string
  peligro: string
  efecto: 'atraso' | 'parcial' | 'total' | string
  valor: number
  primer_dia: string
  ultimo_dia: string
  dias: number
  horizonte: Horizonte
}

export interface FaseCultivo {
  fase: string
  inicio: string
  fin: string | null
  estado: 'terminada' | 'en_curso' | 'futura'
  dias_por_horizonte: Partial<Record<Horizonte, number>>
  condiciones: {
    tmin_mas_baja: number
    tmax_mas_alta: number
    lluvia_mm: number
    humedad_relativa_media: number | null
    agua_suelo_minima: number
  } | null
  eventos: EventoDano[]
}

// Cuándo regar, estimado con el balance de agua del cultivo (sin medir el suelo). Solo las
// especies con parámetros de agua traen `disponible: true`.
export type EstadoRiego = 'sin_sembrar' | 'fuera_de_ciclo' | 'regar_ya' | 'proximos_dias' | 'sin_necesidad'

// Humedad del suelo de NASA POWER: la proporción (0 a 1) del máximo que el suelo puede almacenar, en una celda de
// unos 50 km. Es una referencia de la región, no una medición del predio ni el agua aprovechable del balance.
export interface HumedadSueloNasa {
  zona_raices: number
  superficie: number | null
  fecha: string
  ultimos_dias: { fecha: string; zona_raices: number }[]
  fuente: string
  resolucion_km: number
}

// Lo que llovió en el predio los últimos días (la serie diaria del propio predio), en milímetros y días.
export interface LluviaReciente {
  dias: number
  dias_con_dato: number
  total_mm: number
  ultima_lluvia: { hace_dias: number; mm: number } | null
}

export type Riego =
  | { disponible: false; motivo: string }
  | { disponible: true; estado: 'sin_sembrar' | 'fuera_de_ciclo' }
  | {
      disponible: true
      estado: 'regar_ya' | 'proximos_dias' | 'sin_necesidad'
      agua_pct: number
      umbral_pct: number
      ks_hoy: number
      capacidad_zona_raices_mm: number
      lamina_mm: number | null
      fecha_limite: string | null
      dias_para_riego: number | null
      dias_revisados: number
      ultimo_riego: string | null
      suelo_medido: boolean
      humedad_suelo_nasa?: HumedadSueloNasa
      lluvia_reciente?: LluviaReciente
    }

export interface Fenologia {
  id_cultivo: number
  id_parcela: number
  especie: string
  variedad_local: string | null
  siembra: string
  hoy: string
  horizontes: { observado_hasta: string | null; pronostico_hasta: string | null; estimado_hasta: string | null }
  // `confirmada`: la fecha es la que el agricultor reportó (brote, flor), no la simulada.
  etapas: { etapa: string; fecha: string | null; horizonte: Horizonte | null; confirmada?: boolean }[]
  fase_actual: string | null
  fases: FaseCultivo[]
  estado: string
  riego: Riego
  perdida_observada: number
  perdida_con_pronostico: number
  perdida_proyectada: number | null
  atraso_dias: number
  eventos_externos: (DiaConFocos & { tipo: string; fase: string | null })[]
  incendios_revisados: [string, string] | null
  estado_ingesta: EstadoIngesta
}

export interface EspecieConSeguimiento {
  especie: string
  etapas: string[]
  nivel_madurez: string
  siembra_mes: number | null
  siembra_dia: number | null
}

// ---------------------------------------------------------------- auth
export function registrarAgricultor(datos: {
  nombre: string
  telefono: string
  password: string
  pais?: string
  lat: number
  lon: number
}) {
  return peticion<{ access_token: string }>('/api/auth/registro', { method: 'POST', body: datos })
}

// Cuenta sin teléfono ni contraseña que la app pide sola al abrirse: no hay pantalla de registro.
// El token que devuelve es la cuenta (dura un año), por eso AuthContext lo guarda y no lo pierde.
export function crearSesionAnonima() {
  return peticion<{ access_token: string }>('/api/auth/anonimo', { method: 'POST' })
}

export function loginAgricultor(datos: { telefono: string; password: string }) {
  return peticion<{ access_token: string }>('/api/auth/login', { method: 'POST', body: datos })
}

export function renovarSesion() {
  return peticion<{ access_token: string }>('/api/auth/renovar', { method: 'POST' })
}

export function quienSoy() {
  return conRespaldo('quien_soy', () => peticion<Usuario>('/api/auth/yo'))
}

// ---------------------------------------------------------------- parcelas
export function crearParcela(perimetro: Poligono) {
  olvidarLecturas()
  return peticion<Parcela>('/api/parcelas', { method: 'POST', body: { perimetro } })
}

export function listarParcelas() {
  return conRespaldo('parcelas', () => peticion<{ parcelas: ParcelaResumen[] }>('/api/parcelas'))
}

// `fresco`: salta la memoria (para seguir el avance de la ingesta).
export function verParcela(idParcela: number, fresco = false) {
  return conMemoria(`parcela/${idParcela}`, () => peticion<ParcelaDetalle>(`/api/parcelas/${idParcela}`), fresco)
}

// Guarda solo lo que cambia; null borra la respuesta. Olvida las lecturas guardadas: la lista de especies cambia.
export function guardarSuelo(idParcela: number, cambios: Partial<SueloDeclarado>) {
  olvidarLecturas()
  olvidarSitio(idParcela)
  return peticion<{ suelo: SueloDeclarado }>(`/api/parcelas/${idParcela}/suelo`, { method: 'PUT', body: cambios })
}

export function mapaParcela(idParcela: number, capa: CapaServida) {
  return conRespaldo(`mapa/${idParcela}/${capa}`, () => peticion<MapaPredio>(`/api/parcelas/${idParcela}/mapa`, { query: { capa } }))
}

export function climaParcela(idParcela: number, diasAtras = 30) {
  return conMemoria(`clima/${idParcela}/${diasAtras}`, () =>
    peticion<ClimaPredio>(`/api/parcelas/${idParcela}/clima`, { query: { dias_atras: diasAtras } }),
  )
}

// Lo medido del sitio de la parcela (Tu terreno), sin el ranking de especies. Se guarda en el dispositivo: abrir la
// pantalla otra vez no consulta de nuevo. Un 409 (todavía sin clima) no se guarda.
export async function sitioParcela(idParcela: number, fresco = false): Promise<SitioParcela> {
  const guardado = leer<{ momento: number; valor: SitioParcela } | null>(claveSitio(idParcela), null)
  if (!fresco && guardado && Date.now() - guardado.momento < VIGENCIA_SITIO_MS) return guardado.valor
  try {
    const valor = await conMemoria(`sitio/${idParcela}`, () => peticion<SitioParcela>(`/api/parcelas/${idParcela}/sitio`), fresco)
    guardar(claveSitio(idParcela), { momento: Date.now(), valor })
    registrarFresco(claveSitio(idParcela))
    return valor
  } catch (err) {
    // Sin conexión se muestra lo guardado aunque ya haya vencido (más de 24 h), anotando desde cuándo es.
    if (!guardado || (err instanceof ApiError && err.status < 500)) throw err
    registrarViejo(claveSitio(idParcela), guardado.momento)
    return guardado.valor
  }
}

// Comunas que se pueden mirar sin predio, y su tiempo. Públicos: no piden cuenta.
export function zonas() {
  return conMemoria('zonas', () => peticion<ZonaComuna[]>('/api/zonas'))
}

export function climaZona(nombre: string) {
  return conMemoria(`zona:${nombre}`, () => peticion<ClimaZona>(`/api/zonas/${encodeURIComponent(nombre)}/clima`))
}

export function alertasClimaParcela(idParcela: number) {
  return conMemoria(`alertas_clima:${idParcela}`, () => peticion<AlertasClima>(`/api/parcelas/${idParcela}/alertas_clima`))
}

export function reintentarIngesta(idParcela: number) {
  olvidarLecturas()
  olvidarSitio(idParcela)
  return peticion<{ fuentes_encoladas: string[]; estado_ingesta: EstadoIngesta }>(
    `/api/parcelas/${idParcela}/ingesta`,
    { method: 'POST' },
  )
}

// El agricultor dice si riega: se guarda en el dispositivo y todas las pantallas lo usan.
export const leerRiego = () => leer<boolean>('riego', false)
export const guardarRiego = (riega: boolean) => guardar('riego', riega)

// Cómo sube la temperatura hasta 2040 al evaluar el futuro: lo observado en la parcela o un supuesto. Un supuesto
// NO se guarda en el dispositivo: cada pantalla arranca en 'observado' y, si se elige otro, lo pasa por la
// dirección (?escenario=) a la pantalla que sigue. Guardado, cambiaba en silencio los resultados de Análisis,
// Rotación y el registro inicial.
export const ESCENARIOS: readonly Escenario[] = ['observado', 'moderado', 'fuerte']

// Categorías de EcoCrop que el agricultor reconoce como comida.
export const CATEGORIAS_COMIDA = ['vegetables', 'roots/tubers', 'pulses (grain legumes)', 'cereals & pseudocereals'] as const

// Cada pantalla pide solo lo que muestra: el servidor filtra por categorías y recorta
// después, así el corte nunca deja afuera especies aptas de un grupo. `especie` trae solo
// esa (apta o no); `limite` en 1 sirve cuando solo importan los datos del sitio.
export function candidatasSiembra(
  idParcela: number,
  opciones: {
    categorias?: readonly string[]; limite?: number; especie?: string; riego?: boolean
    escenario?: Escenario; climaFuturo?: CategoriaClima
  } = {},
) {
  const query = {
    limite: opciones.limite ?? 20,
    incluir_no_aptas: false,
    categorias: opciones.categorias?.length ? opciones.categorias.join(',') : undefined,
    especie: opciones.especie,
    riego: opciones.riego ?? leerRiego(),
    escenario: opciones.escenario ?? 'observado',
    clima_futuro: opciones.climaFuturo,
  }
  return conMemoria(`candidatas/${idParcela}/${JSON.stringify(query)}`, () =>
    peticion<CandidatasSiembra>(`/api/parcelas/${idParcela}/candidatas_siembra`, { query }),
  )
}

// ---------------------------------------------------------------- cultivos
// Catálogo público de nombres por idioma; no usa la memoria de lecturas porque se pide una vez al abrir.
export function nombresEspecies() {
  return conRespaldo('especies_nombres', () => peticion<NombresCatalogo>('/api/especies/nombres'))
}

export function especiesConSeguimiento() {
  return conMemoria('especies', () => peticion<{ especies: EspecieConSeguimiento[] }>('/api/especies/con_seguimiento'))
}

// Una especie que devuelve el buscador. `seguimiento`: tiene calendario por etapa; si no, solo se registra.
export interface EspecieBuscada {
  especie: string
  nombre_es: string | null
  nombre_en: string | null
  nombre_cientifico: string | null
  nombres_comunes: string | null
  seguimiento: boolean
}

export function buscarEspecies(consulta: string) {
  return peticion<{ especies: EspecieBuscada[] }>('/api/especies/buscar', { query: { q: consulta, limite: 12 } })
}

export function declararCultivo(
  idParcela: number,
  datos: { especie: string; variedad_local?: string | null; fecha_siembra: string },
) {
  olvidarLecturas()
  return peticion<CultivoDeclarado>(`/api/parcelas/${idParcela}/cultivos`, { method: 'POST', body: datos })
}

export function listarCultivos(idParcela: number) {
  return conMemoria(`cultivos/${idParcela}`, () => peticion<{ cultivos: Cultivo[] }>(`/api/parcelas/${idParcela}/cultivos`))
}

export function fenologiaCultivo(idCultivo: number) {
  return conMemoria(`fenologia/${idCultivo}`, () => peticion<Fenologia>(`/api/cultivos/${idCultivo}/fenologia`))
}

// El agricultor avisa que regó (se toma como un riego completo) o deshace un aviso. Ambos
// vacían la memoria: el seguimiento se vuelve a calcular con el riego.
export type TipoLabor = 'riego' | 'fertilizacion' | 'pesticida' | 'fungicida'
export const TIPOS_LABOR: readonly TipoLabor[] = ['riego', 'fertilizacion', 'pesticida', 'fungicida']

export interface Labor {
  tipo: TipoLabor
  fecha: string
}

export interface RegistroCultivo {
  cultivo: { id: number; id_parcela: number; especie: string; variedad_local: string | null; fecha_siembra: string | null }
  labores: Labor[]
}

// El registro del cultivo: lo declarado y las labores anotadas. No usa la memoria de lecturas: se pide al abrir y
// después de cada cambio.
export function registroCultivo(idCultivo: number) {
  return conRespaldo(`labores/${idCultivo}`, () => peticion<RegistroCultivo>(`/api/cultivos/${idCultivo}/labores`))
}

// Anotar o quitar una labor cambia el seguimiento (el riego mueve el balance de agua, el fungicida el riesgo de
// tizón): se olvidan las lecturas guardadas.
export function declararLabor(idCultivo: number, tipo: TipoLabor, fecha: string) {
  olvidarLecturas()
  return peticion<{ registrado: boolean }>(`/api/cultivos/${idCultivo}/labores`, { method: 'POST', body: { tipo, fecha } })
}

export function anularLabor(idCultivo: number, tipo: TipoLabor, fecha: string) {
  olvidarLecturas()
  return peticion<{ anulado: boolean }>(`/api/cultivos/${idCultivo}/labores/anular`, { method: 'POST', body: { tipo, fecha } })
}

export type FaseReporte = 'brote' | 'hojas' | 'flor' | 'fruto' | 'amarilla' | 'cosecha'
export const FASES_REPORTE: readonly FaseReporte[] = ['brote', 'hojas', 'flor', 'fruto', 'amarilla', 'cosecha']

export interface ReporteDeCampo {
  fase: FaseReporte
  fecha: string
}

// Los reportes de campo del cultivo, del más reciente al más antiguo. No usa la memoria de lecturas.
export function reportesCultivo(idCultivo: number) {
  return conRespaldo(`reportes/${idCultivo}`, () => peticion<{ reportes: ReporteDeCampo[] }>(`/api/cultivos/${idCultivo}/reportes`))
}

// `capturado` es la hora del teléfono al reportar: el reporte puede llegar horas después, desde la cola.
export function enviarReporte(idCultivo: number, reporte: ReporteDeCampo & { capturado: string }) {
  return peticion<{ registrado: boolean }>(`/api/cultivos/${idCultivo}/reportes`, { method: 'POST', body: reporte })
}

export function declararRiego(idCultivo: number, fecha: string) {
  olvidarLecturas()
  return peticion<{ registrado: boolean }>(`/api/cultivos/${idCultivo}/riegos`, { method: 'POST', body: { fecha } })
}

export function anularRiego(idCultivo: number, fecha: string) {
  olvidarLecturas()
  return peticion<{ anulado: boolean }>(`/api/cultivos/${idCultivo}/riegos/anular`, { method: 'POST', body: { fecha } })
}

// ---------------------------------------------------------------- indicadores locales
// Conocimiento de la comunidad (aves, floración de especies) y lo que anuncia, por zona.
// Informativo y sin validar: no cambia la proyección del cultivo.
export type CategoriaIndicador = 'aves' | 'floracion'
export type SignificadoIndicador =
  | 'precipitacion_alta'
  | 'precipitacion_baja'
  | 'helada'
  | 'precipitacion_temprana'
  | 'precipitacion_tardia'
export type EstadoSenal = 'confirmada' | 'en_observacion' | 'sin_reportes'

export interface IndicadorLocal {
  id: number
  categoria: CategoriaIndicador
  nombre: string
  evento: string
  significado: SignificadoIndicador
  nota: string | null
  mes_desde: number
  mes_hasta: number
  umbral_reportes: number
  vigencia_dias: number
  zona: string
  observadores: number
  ultima_observacion: string | null
  ya_reportaste: boolean
  estado: EstadoSenal
}

export interface IndicadoresPredio {
  indicadores: IndicadorLocal[]
  resumen: Partial<Record<SignificadoIndicador, string[]>>
  validado: false
}

export function indicadoresParcela(idParcela: number, fresco = false) {
  return conMemoria(
    `indicadores/${idParcela}`,
    () => peticion<IndicadoresPredio>(`/api/parcelas/${idParcela}/indicadores`),
    fresco,
  )
}

export function reportarIndicador(idIndicador: number, fechaObservada: string) {
  olvidarLecturas()
  return peticion<{ registrada: boolean }>(`/api/indicadores/${idIndicador}/observaciones`, {
    method: 'POST',
    body: { fecha_observada: fechaObservada },
  })
}

export { BASE_URL }
