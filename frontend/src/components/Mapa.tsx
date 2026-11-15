import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { CeldaMapa, Poligono } from '../lib/api'
import type { Punto } from '../lib/geometria'

// Imagen satelital de Esri (World Imagery). Uso gratuito solo para desarrollo y uso no
// comercial, con atribución visible: antes de publicar la app hay que revisar la licencia.
// Cada tesela se pide a Esri por la zona que se mira: la ubicación aproximada del predio
// sale del dispositivo hacia ese servicio.
const TESELAS = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
const ATRIBUCION = 'Imagen: Esri, Maxar, Earthstar Geographics'

function crearMapa(contenedor: HTMLElement): L.Map {
  const mapa = L.map(contenedor, { zoomControl: true })
  mapa.attributionControl.setPrefix(false)
  L.tileLayer(TESELAS, { attribution: ATRIBUCION, maxNativeZoom: 18, maxZoom: 20 }).addTo(mapa)
  return mapa
}

// Mapa para dibujar el perímetro: cada toque agrega una esquina; las esquinas se pueden
// arrastrar para corregirlas.
export function MapaDibujo({
  centro,
  esquinas,
  onCambio,
}: {
  centro: Punto
  esquinas: Punto[]
  onCambio: (esquinas: Punto[]) => void
}) {
  const contenedor = useRef<HTMLDivElement>(null)
  const mapa = useRef<L.Map | null>(null)
  const capa = useRef<L.LayerGroup | null>(null)
  const actuales = useRef(esquinas)
  const alCambiar = useRef(onCambio)

  useEffect(() => {
    alCambiar.current = onCambio
  }, [onCambio])

  useEffect(() => {
    if (!contenedor.current) return
    const nuevo = crearMapa(contenedor.current)
    capa.current = L.layerGroup().addTo(nuevo)
    nuevo.on('click', (evento: L.LeafletMouseEvent) => {
      alCambiar.current([...actuales.current, [evento.latlng.lat, evento.latlng.lng]])
    })
    mapa.current = nuevo
    return () => {
      nuevo.remove()
      mapa.current = null
      capa.current = null
    }
  }, [])

  useEffect(() => {
    mapa.current?.setView(centro, 17)
  }, [centro])

  useEffect(() => {
    actuales.current = esquinas
    const grupo = capa.current
    if (!grupo) return
    grupo.clearLayers()
    if (esquinas.length >= 2) {
      L.polygon(esquinas, { color: '#ffffff', weight: 3, fillColor: '#ffffff', fillOpacity: 0.2, interactive: false }).addTo(grupo)
    }
    esquinas.forEach((punto, indice) => {
      const marcador = L.marker(punto, {
        draggable: true,
        icon: L.divIcon({ className: 'ps-esquina', html: String(indice + 1), iconSize: [32, 32], iconAnchor: [16, 16] }),
      })
      marcador.on('dragend', () => {
        const { lat, lng } = marcador.getLatLng()
        alCambiar.current(actuales.current.map((otro, j) => (j === indice ? [lat, lng] : otro)))
      })
      marcador.addTo(grupo)
    })
  }, [esquinas])

  return <div ref={contenedor} className="ps-mapa" role="application" aria-label="Mapa satelital para marcar las esquinas de tu parcela" />
}

// Mapa del predio por celdas: el perímetro y, dentro, cada celda pintada según su valor.
export function MapaCeldas({
  perimetro,
  celdas,
  colorDe,
  elegida,
  onElegir,
}: {
  perimetro: Poligono
  celdas: CeldaMapa[]
  colorDe: (valor: number) => string
  elegida: string | null
  onElegir: (celda: CeldaMapa) => void
}) {
  const contenedor = useRef<HTMLDivElement>(null)
  const mapa = useRef<L.Map | null>(null)
  const capa = useRef<L.LayerGroup | null>(null)
  const alElegir = useRef(onElegir)

  useEffect(() => {
    alElegir.current = onElegir
  }, [onElegir])

  useEffect(() => {
    if (!contenedor.current) return
    const nuevo = crearMapa(contenedor.current)
    capa.current = L.layerGroup().addTo(nuevo)
    mapa.current = nuevo
    return () => {
      nuevo.remove()
      mapa.current = null
      capa.current = null
    }
  }, [])

  useEffect(() => {
    const contorno = L.geoJSON(perimetro as GeoJSON.Polygon)
    mapa.current?.fitBounds(contorno.getBounds(), { padding: [24, 24] })
  }, [perimetro])

  useEffect(() => {
    const grupo = capa.current
    if (!grupo) return
    grupo.clearLayers()
    L.geoJSON(celdas as unknown as GeoJSON.Feature[], {
      style: (entidad) => {
        const p = (entidad as unknown as CeldaMapa).properties
        const marcada = `${p.i},${p.j}` === elegida
        return p.valor === null
          ? { color: '#ffffff', weight: marcada ? 3 : 1, fillColor: '#33302c', fillOpacity: 0.35, dashArray: '4 4' }
          : { color: '#ffffff', weight: marcada ? 4 : 1, fillColor: colorDe(p.valor), fillOpacity: 0.78 }
      },
      onEachFeature: (entidad, figura) => {
        figura.on('click', () => alElegir.current(entidad as unknown as CeldaMapa))
      },
    }).addTo(grupo)
    L.geoJSON(perimetro as GeoJSON.Polygon, { style: { color: '#ffffff', weight: 3, fill: false }, interactive: false }).addTo(grupo)
  }, [celdas, colorDe, elegida, perimetro])

  return <div ref={contenedor} className="ps-mapa" role="application" aria-label="Mapa de tu parcela dividida en cuadros" />
}
