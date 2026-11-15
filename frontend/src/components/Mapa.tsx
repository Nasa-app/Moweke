import { useEffect, useRef, useState } from 'react'
import type { RefObject } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { CeldaMapa, Poligono } from '../lib/api'
import type { Punto } from '../lib/geometria'
import { guardar, leer } from '../state/storage'

type Base = 'satelite' | 'mapa'

// Satélite: Esri World Imagery. Uso gratuito solo para desarrollo y uso no comercial,
// con atribución visible: antes de publicar la app hay que revisar la licencia.
// Mapa: OpenStreetMap. Sus servidores son de mejor esfuerzo y no admiten precargar zonas
// ni uso sin conexión; la atribución tiene que verse siempre sobre el mapa.
// Cada tesela se pide por la zona que se mira: la ubicación aproximada de la parcela sale
// del dispositivo hacia ese servicio.
const BASES: Record<Base, { url: string; opciones: L.TileLayerOptions }> = {
  satelite: {
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    opciones: { attribution: 'Imagen: Esri, Maxar, Earthstar Geographics', maxNativeZoom: 18, maxZoom: 20 },
  },
  mapa: {
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    opciones: {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',
      maxNativeZoom: 19,
      maxZoom: 20,
    },
  },
}

// Sobre el satélite las líneas van blancas; sobre el mapa claro, oscuras.
const colorLinea = (base: Base) => (base === 'mapa' ? '#2b2823' : '#ffffff')

function crearMapa(contenedor: HTMLElement): L.Map {
  const mapa = L.map(contenedor, { zoomControl: true })
  mapa.attributionControl.setPrefix(false)
  return mapa
}

function useBase(): [Base, (nueva: Base) => void] {
  const [base, setBase] = useState<Base>(() => (leer<string>('mapa_base', 'satelite') === 'mapa' ? 'mapa' : 'satelite'))
  return [
    base,
    (nueva) => {
      setBase(nueva)
      guardar('mapa_base', nueva)
    },
  ]
}

// Pone la capa de fondo elegida y la cambia cuando cambia `base`. Va después del efecto
// que crea el mapa.
function useCapaBase(mapa: RefObject<L.Map | null>, base: Base) {
  const capa = useRef<L.TileLayer | null>(null)
  useEffect(() => {
    if (!mapa.current) return
    capa.current?.remove()
    capa.current = L.tileLayer(BASES[base].url, BASES[base].opciones).addTo(mapa.current)
    capa.current.bringToBack()
  }, [mapa, base])
}

function SelectorBase({ base, onCambio }: { base: Base; onCambio: (nueva: Base) => void }) {
  return (
    <div
      role="group"
      aria-label="Tipo de mapa"
      style={{ position: 'absolute', top: 10, right: 10, zIndex: 2, display: 'flex', gap: 4, padding: 4, borderRadius: 16, background: 'rgba(255,255,255,.94)', boxShadow: 'var(--sombra-1)' }}
    >
      {(['satelite', 'mapa'] as const).map((opcion) => (
        <button
          key={opcion}
          type="button"
          aria-pressed={base === opcion}
          onClick={() => onCambio(opcion)}
          style={{ minHeight: 44, padding: '0 14px', borderRadius: 12, border: 'none', cursor: 'pointer', fontFamily: 'inherit', fontSize: 15, fontWeight: 800, background: base === opcion ? 'var(--verde)' : 'transparent', color: base === opcion ? 'var(--sobre-verde)' : 'var(--carbon)' }}
        >
          {opcion === 'mapa' ? 'Mapa' : 'Satélite'}
        </button>
      ))}
    </div>
  )
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
  const [base, cambiarBase] = useBase()

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

  useCapaBase(mapa, base)

  useEffect(() => {
    mapa.current?.setView(centro, 17)
  }, [centro])

  useEffect(() => {
    actuales.current = esquinas
    const grupo = capa.current
    if (!grupo) return
    grupo.clearLayers()
    if (esquinas.length >= 2) {
      L.polygon(esquinas, { color: colorLinea(base), weight: 3, fillColor: colorLinea(base), fillOpacity: 0.2, interactive: false }).addTo(grupo)
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
  }, [esquinas, base])

  return (
    <div style={{ position: 'relative' }}>
      <div ref={contenedor} className="ps-mapa" role="application" aria-label="Mapa para marcar las esquinas de tu parcela" />
      <SelectorBase base={base} onCambio={cambiarBase} />
    </div>
  )
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
  const [base, cambiarBase] = useBase()

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

  useCapaBase(mapa, base)

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
          ? { color: colorLinea(base), weight: marcada ? 3 : 1, fillColor: '#33302c', fillOpacity: 0.35, dashArray: '4 4' }
          : { color: colorLinea(base), weight: marcada ? 4 : 1, fillColor: colorDe(p.valor), fillOpacity: 0.78 }
      },
      onEachFeature: (entidad, figura) => {
        figura.on('click', () => alElegir.current(entidad as unknown as CeldaMapa))
      },
    }).addTo(grupo)
    L.geoJSON(perimetro as GeoJSON.Polygon, { style: { color: colorLinea(base), weight: 3, fill: false }, interactive: false }).addTo(grupo)
  }, [celdas, colorDe, elegida, perimetro, base])

  return (
    <div style={{ position: 'relative' }}>
      <div ref={contenedor} className="ps-mapa" role="application" aria-label="Mapa de tu parcela dividida en cuadros" />
      <SelectorBase base={base} onCambio={cambiarBase} />
    </div>
  )
}
