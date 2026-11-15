// Datos de ejemplo para las pantallas cuyo endpoint real todavía no existe: explorar la
// zona, fuentes y señales para reportar. Predio,
// mapa, clima, especies candidatas, cultivos, seguimiento y alertas ya leen el API real
// (lib/api.ts). Nada de esto se presenta como dato real.
export const FUENTE_EJEMPLO = 'Fuente: ejemplo, sin endpoint todavía'

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

export const fuentesDatos = [
  { titulo: 'Satélite', detalle: 'Qué tan verde está tu sector', nota: 'NASA · cada 2 a 3 días' },
  { titulo: 'Clima', detalle: 'Calor, lluvia y humedad', nota: 'NASA POWER y CR2MET · pronóstico de Open-Meteo.com (CC BY 4.0) · todos los días' },
  { titulo: 'Tú y tu comuna', detalle: 'Lo que ven en el campo', nota: 'Manda' },
  { titulo: 'Saber williche', detalle: 'Luna, vientos y señales para sembrar', nota: 'Comunidades williche de Chiloé · en validación' },
  { titulo: 'Incendios', detalle: 'Focos de calor cerca de tu parcela', nota: 'Satélites de NASA (FIRMS) · alertas oficiales: SENAPRED' },
]
