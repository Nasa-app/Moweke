// Cliente del API real de Mogewe (ver ../../main.py). Cubre auth, parcelas (predio, mapa
// por celdas, clima diario, especies candidatas), cultivos y fenología. Lo que todavía no
// tiene endpoint (reportes, observaciones, rotación comparada, red de semillas) usa datos
// de ejemplo desde lib/mock.ts, marcados como tal en la UI.

const BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000'

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
  if (!(error instanceof ApiError)) return 'No se pudo conectar con el servidor. Revisa tu conexión.'
  const detalle = error.detail
  if (typeof detalle === 'string') return detalle
  if (detalle && typeof detalle === 'object' && 'mensaje' in detalle) {
    return String((detalle as { mensaje: unknown }).mensaje)
  }
  return porDefecto
}

function tokenActual(): string | null {
  return localStorage.getItem('mowege_token')
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
  const token = tokenActual()
  const res = await fetch(url.toString(), {
    method: opciones.method ?? 'GET',
    headers: {
      ...(opciones.body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: opciones.body ? JSON.stringify(opciones.body) : undefined,
  })
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

function conMemoria<T>(clave: string, pedir: () => Promise<T>, fresco = false): Promise<T> {
  const guardada = memoria.get(clave)
  if (!fresco && guardada && Date.now() - guardada.momento < VIGENCIA_MS) return guardada.consulta as Promise<T>
  const consulta = pedir()
  memoria.set(clave, { momento: Date.now(), consulta })
  consulta.catch(() => {
    if (memoria.get(clave)?.consulta === consulta) memoria.delete(clave)
  })
  return consulta
}

export function olvidarLecturas(): void {
  memoria.clear()
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
  incendios_cercanos: { radio_km: number; revisado: [string, string] | null; dias_con_focos: DiaConFocos[] }
  curva_satelital: { viable: boolean | null; ventanas_con_pasada_pct?: number | null }
}

export type CapaMapa = 'ndvi' | 'altitud' | 'pendiente'

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
  capa: CapaMapa
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
  fuente: string | null
  horizonte: 'observado' | 'pronostico'
}

export interface ClimaPredio {
  id_parcela: number
  hoy: string
  dias: DiaClima[]
  estado_ingesta: EstadoIngesta
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

export type Factor = 'temperatura' | 'humedad' | 'helada' | 'ph' | 'radiacion'

export interface Candidata {
  especie: string
  nombre_cientifico: string | null
  nombres_comunes: string | null
  categorias: string[]
  apta: boolean | null
  puntaje: number | null
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
  ph: number | null
  agua_disponible_suelo_mm: number | null
}

export interface CandidatasSiembra {
  parcela: number
  hectareas: number
  estado_ingesta: EstadoIngesta
  datos_sitio: DatosSitio
  especies_evaluadas: number
  especies_aptas: number
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

export interface Fenologia {
  id_cultivo: number
  id_parcela: number
  especie: string
  variedad_local: string | null
  siembra: string
  hoy: string
  horizontes: { observado_hasta: string | null; pronostico_hasta: string | null; estimado_hasta: string | null }
  etapas: { etapa: string; fecha: string | null; horizonte: Horizonte | null }[]
  fase_actual: string | null
  fases: FaseCultivo[]
  estado: string
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

export function loginAgricultor(datos: { telefono: string; password: string }) {
  return peticion<{ access_token: string }>('/api/auth/login', { method: 'POST', body: datos })
}

export function quienSoy() {
  return peticion<Usuario>('/api/auth/yo')
}

// ---------------------------------------------------------------- parcelas
export function crearParcela(perimetro: Poligono) {
  olvidarLecturas()
  return peticion<Parcela>('/api/parcelas', { method: 'POST', body: { perimetro } })
}

export function listarParcelas() {
  return peticion<{ parcelas: ParcelaResumen[] }>('/api/parcelas')
}

// `fresco`: salta la memoria (para seguir el avance de la ingesta).
export function verParcela(idParcela: number, fresco = false) {
  return conMemoria(`parcela/${idParcela}`, () => peticion<ParcelaDetalle>(`/api/parcelas/${idParcela}`), fresco)
}

export function mapaParcela(idParcela: number, capa: CapaMapa) {
  return peticion<MapaPredio>(`/api/parcelas/${idParcela}/mapa`, { query: { capa } })
}

export function climaParcela(idParcela: number, diasAtras = 30) {
  return conMemoria(`clima/${idParcela}/${diasAtras}`, () =>
    peticion<ClimaPredio>(`/api/parcelas/${idParcela}/clima`, { query: { dias_atras: diasAtras } }),
  )
}

export function reintentarIngesta(idParcela: number) {
  olvidarLecturas()
  return peticion<{ fuentes_encoladas: string[]; estado_ingesta: EstadoIngesta }>(
    `/api/parcelas/${idParcela}/ingesta`,
    { method: 'POST' },
  )
}

export function candidatasSiembra(idParcela: number) {
  return conMemoria(`candidatas/${idParcela}`, () =>
    peticion<CandidatasSiembra>(`/api/parcelas/${idParcela}/candidatas_siembra`, {
      query: { limite: 200, incluir_no_aptas: true },
    }),
  )
}

// ---------------------------------------------------------------- cultivos
export function especiesConSeguimiento() {
  return conMemoria('especies', () => peticion<{ especies: EspecieConSeguimiento[] }>('/api/especies/con_seguimiento'))
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

export { BASE_URL }
