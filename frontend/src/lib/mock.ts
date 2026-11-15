// Datos de ejemplo para las pantallas cuyo endpoint real todavía no existe: explorar la
// zona, fuentes y señales para reportar. Predio,
// mapa, clima, especies candidatas, cultivos, seguimiento y alertas ya leen el API real
// (lib/api.ts). Nada de esto se presenta como dato real.
export const FUENTE_EJEMPLO = 'Fuente: ejemplo, sin endpoint todavía'

// Los textos de climaZona y novedadesZona son claves del diccionario (i18n/textos/onboarding.ts):
// la pantalla las traduce con t().
export const climaZona = {
  temperatura: 12,
  descripcion: 'explorar_clima_desc',
  humedad: 88,
  lluvia_mm: 6,
  viento_kmh: 22,
  fecha: 'explorar_clima_fecha',
}

export const novedadesZona = [
  { titulo: 'explorar_nov_heladas', valor: 'explorar_nov_heladas_valor', chip: 'explorar_nov_nuevo' },
  { titulo: 'explorar_nov_temporada', valor: 'explorar_nov_temporada_valor', chip: null },
  { titulo: 'explorar_nov_verdor', valor: 'explorar_nov_verdor_valor', chip: 'explorar_nov_satelite' },
  { titulo: 'explorar_nov_papa', valor: 'explorar_nov_papa_valor', chip: 'explorar_nov_vecinos' },
]

export const fuentesDatos = [
  { titulo: 'Satélite', detalle: 'Qué tan verde está tu sector', nota: 'NASA · cada 2 a 3 días' },
  { titulo: 'Clima', detalle: 'Calor, lluvia y humedad', nota: 'NASA POWER y CR2MET · pronóstico de Open-Meteo.com (CC BY 4.0) · todos los días' },
  { titulo: 'Tú y tu comuna', detalle: 'Lo que ven en el campo', nota: 'Manda' },
  { titulo: 'Saber williche', detalle: 'Luna, vientos y señales para sembrar', nota: 'Comunidades williche de Chiloé · en validación' },
  { titulo: 'Incendios', detalle: 'Focos de calor cerca de tu parcela', nota: 'Satélites de NASA (FIRMS) · alertas oficiales: SENAPRED' },
]
