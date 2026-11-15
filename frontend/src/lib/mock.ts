// Datos de ejemplo para las pantallas cuyo endpoint real todavía no existe: explorar la
// zona, luna, historial, plan, red de semillas, fuentes y señales para reportar. Predio,
// mapa, clima, especies candidatas, cultivos, seguimiento y alertas ya leen el API real
// (lib/api.ts). Nada de esto se presenta como dato real.
export const FUENTE_EJEMPLO = 'Fuente: ejemplo, sin endpoint todavía'

export const faseLunar = {
  fases: [
    { nombre: 'Nueva', fecha: '9 nov', tipo: 'nueva' as const },
    { nombre: 'Creciente', fecha: '17 nov', tipo: 'creciente' as const },
    { nombre: 'Llena', fecha: '24 nov', tipo: 'llena' as const },
    { nombre: 'Menguante', fecha: '1 dic', tipo: 'menguante' as const },
  ],
  actual: 1,
  nota: 'Creciente: la savia sube a las hojas.',
}

export const climaZona = {
  temperatura: 12,
  descripcion: 'Nublado, lluvia en la tarde',
  humedad: 88,
  lluvia_mm: 6,
  viento_kmh: 22,
  fecha: 'Hoy · 14 nov',
}

export const novedadesZona = [
  { titulo: 'Heladas', valor: 'Posible jueves', chip: 'Nuevo' },
  { titulo: 'Temporada', valor: '+1,2° más cálida', chip: null },
  { titulo: 'Verdor del campo', valor: 'Subiendo', chip: 'Satélite' },
  { titulo: 'Papa en Quemchi', valor: 'Con hojas', chip: 'Vecinos' },
]

export const historialTemporadas = [
  { anio: 2026, especie: 'Papa', familia: 'Familia papa' },
  { anio: 2025, especie: 'Ajo chilote', familia: 'Familia ajo' },
  { anio: 2024, especie: 'Papa', familia: 'Familia papa' },
  { anio: 2023, especie: 'Haba', familia: 'Legumbre' },
]

export const planTemporada = [
  { tarea: 'Cosechar papa', detalle: 'Esta temporada', mes: 'Mar', estado: 'normal' as const },
  { tarea: 'Sembrar haba', detalle: 'Cuida el suelo', mes: 'May', estado: 'actual' as const },
  { tarea: 'Cosechar haba', detalle: 'Estimado', mes: 'Dic', estado: 'estimado' as const },
]

export const semillasPedidas = [
  { especie: 'Papa nativa', variedad: 'Michuñe azul', lugar: 'Quemchi', hace: '2 días' },
  { especie: 'Haba', variedad: 'Cualquier variedad', lugar: 'Castro', hace: '5 días' },
  { especie: 'Ajo chilote', variedad: 'Cualquier variedad', lugar: 'Queilén', hace: '1 sem.' },
]

export const fuentesDatos = [
  { titulo: 'Satélite', detalle: 'Qué tan verde está tu sector', nota: 'NASA · cada 2 a 3 días' },
  { titulo: 'Clima', detalle: 'Calor, lluvia y humedad', nota: 'NASA POWER y CR2MET · pronóstico de Open-Meteo.com (CC BY 4.0) · todos los días' },
  { titulo: 'Tú y tu comuna', detalle: 'Lo que ven en el campo', nota: 'Manda' },
  { titulo: 'Saber williche', detalle: 'Luna, vientos y señales para sembrar', nota: 'Comunidades williche de Chiloé · en validación' },
  { titulo: 'Incendios', detalle: 'Focos de calor cerca de tu parcela', nota: 'Satélites de NASA (FIRMS) · alertas oficiales: SENAPRED' },
]
