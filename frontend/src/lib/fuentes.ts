// De dónde sale cada dato que ve el agricultor. Cada fuente lleva su origen para que se vea de un vistazo qué es de
// NASA, qué es de Copernicus (programa de la Unión Europea; Sentinel-2 lo opera la ESA) y qué es de Chile. Debe
// coincidir con lo que la API realmente descarga (services/ingesta_predio.py): si se agrega una fuente, se agrega aquí.
export type Origen = 'NASA' | 'Copernicus' | 'Chile' | 'Otras fuentes' | 'Comunidad'

export interface FuenteDato {
  titulo: string
  detalle: string
  origenes: Origen[]
  nota: string
}

export const CLASE_ORIGEN: Record<Origen, string> = {
  NASA: 'ps-chip-clima',
  Copernicus: 'ps-chip-acento',
  Chile: 'ps-chip-favorable',
  'Otras fuentes': 'ps-chip-neutro',
  Comunidad: 'ps-chip-precaucion',
}

export const FUENTES: FuenteDato[] = [
  {
    titulo: 'Clima de los últimos días',
    detalle: 'Calor, lluvia y humedad del aire',
    origenes: ['NASA', 'Chile'],
    nota: 'NASA POWER y CR2MET (Chile) · todos los días, con unos días de atraso',
  },
  {
    titulo: 'Sol',
    detalle: 'Cuánto sol llega a tu zona en cada mes',
    origenes: ['NASA'],
    nota: 'NASA POWER · celda de unos 100 km: referencia de la región, no de tu parcela',
  },
  {
    titulo: 'Incendios',
    detalle: 'Focos de calor cerca de tu parcela',
    origenes: ['NASA'],
    nota: 'NASA FIRMS (satélites VIIRS) · alertas oficiales: SENAPRED',
  },
  {
    titulo: 'Verdor del campo',
    detalle: 'Qué tan verde está tu sector',
    origenes: ['Copernicus'],
    nota: 'Sentinel-2, de la ESA · cada 5 días, cuando el cielo deja ver el predio',
  },
  {
    titulo: 'Relieve',
    detalle: 'Altura y pendiente de tu parcela',
    origenes: ['Copernicus'],
    nota: 'Modelo de elevación Copernicus GLO-30',
  },
  {
    titulo: 'Cercanía al cauce',
    detalle: 'Qué tan alto queda tu parcela sobre el cauce más cercano',
    origenes: ['NASA'],
    nota: 'HAND de 30 m del centro de datos ASF de NASA, sobre Copernicus GLO-30 · no es un aviso de crecida',
  },
  {
    titulo: 'Clima de 35 años',
    detalle: 'Cómo ha sido el clima de tu zona, para elegir qué sembrar',
    origenes: ['Copernicus'],
    nota: 'ERA5 (Copernicus y ECMWF), entregado por Open-Meteo.com · CC BY 4.0',
  },
  {
    titulo: 'Pronóstico',
    detalle: 'Los próximos 16 días',
    origenes: ['Otras fuentes'],
    nota: 'Open-Meteo.com (CC BY 4.0) · todos los días',
  },
  {
    titulo: 'Suelo',
    detalle: 'Acidez, textura y agua que guarda',
    origenes: ['Otras fuentes', 'Chile'],
    nota: 'SoilGrids (ISRIC) y CLSoilMaps (Chile)',
  },
  {
    titulo: 'Saber williche',
    detalle: 'Luna, vientos y señales para sembrar',
    origenes: ['Comunidad'],
    nota: 'Comunidades williche de Chiloé · en validación',
  },
]
