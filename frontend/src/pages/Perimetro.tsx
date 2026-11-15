import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Screen, BarraSuperior, Titulo } from '../components/Screen'
import { MapaDibujo } from '../components/Mapa'
import { COMUNA_POR_DEFECTO, ZOOM_COMUNA, centroDeComuna, leerBorrador } from '../lib/comunas'
import { aPoligono, hectareasDe, type Punto } from '../lib/geometria'
import { IconoUbicacion } from '../components/icons'
import { crearParcela, mensajeDeError } from '../lib/api'
import { numero } from '../lib/formato'
import { usePredio } from '../state/PredioContext'
import { guardar, leer } from '../state/storage'
import { useI18n } from '../i18n'

// Los mismos límites que valida POST /api/parcelas.
const HECTAREAS_MIN = 0.05
const HECTAREAS_MAX = 1000
// Zoom con el que se ve una parcela (se usa con la ubicación del dispositivo y con un predio ya marcado).
const ZOOM_PARCELA = 17

interface Vista {
  centro: Punto
  zoom: number
}

// Dónde abre el mapa. Al venir del registro, en la comuna que la persona acaba de elegir. Si no, donde quedó la
// última parcela, y si no hay ninguna, en la comuna elegida o en la comuna piloto.
function vistaInicial(enOnboarding: boolean): Vista {
  const comuna = centroDeComuna(leerBorrador().comuna)
  const ultima = leer<Punto | null>('mapa_centro', null)
  if (!enOnboarding && ultima) return { centro: ultima, zoom: ZOOM_PARCELA }
  return { centro: comuna ?? centroDeComuna(COMUNA_POR_DEFECTO)!, zoom: ZOOM_COMUNA }
}

export default function Perimetro() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const enOnboarding = params.get('desde') === 'onboarding'
  const { setParcelaActiva, setCultivoActivo } = usePredio()
  const [vista, setVista] = useState<Vista>(() => vistaInicial(enOnboarding))
  const comunaElegida = enOnboarding ? leerBorrador().comuna : null
  const [esquinas, setEsquinas] = useState<Punto[]>([])
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const hectareas = hectareasDe(esquinas)
  const medidaValida = hectareas >= HECTAREAS_MIN && hectareas <= HECTAREAS_MAX
  const listo = esquinas.length >= 3 && medidaValida

  function usarUbicacion() {
    if (!('geolocation' in navigator)) {
      setError('Este dispositivo no entrega ubicación. Mueve el mapa hasta tu parcela.')
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setError(null)
        setVista({ centro: [pos.coords.latitude, pos.coords.longitude], zoom: ZOOM_PARCELA })
      },
      () => setError('No se pudo obtener tu ubicación. Mueve el mapa hasta tu parcela.'),
      { timeout: 8000 },
    )
  }

  async function analizar() {
    setEnviando(true)
    setError(null)
    try {
      const parcela = await crearParcela(aPoligono(esquinas))
      guardar('mapa_centro', [parcela.lat, parcela.lon])
      setParcelaActiva(parcela.id)
      setCultivoActivo(null)
      navigate(`/terreno/preparando${enOnboarding ? '?desde=onboarding' : ''}`)
    } catch (err) {
      setError(mensajeDeError(err, 'No se pudo guardar la parcela. Revisa las esquinas que marcaste e intenta otra vez.'))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Screen>
      <BarraSuperior volverA={enOnboarding ? '/onboarding/predio' : '/terreno'} />
      <Titulo
        sub={
          comunaElegida
            ? `El mapa muestra ${comunaElegida}. Acércalo hasta tu parcela y toca cada esquina para dibujar su contorno. Puedes arrastrar una esquina para corregirla.`
            : 'Mueve el mapa hasta tu parcela y toca cada esquina. Puedes arrastrar una esquina para corregirla.'
        }
      >
        {t('perimetro_titulo')}
      </Titulo>

      <div className="ps-pad-16" style={{ marginTop: 14, position: 'relative' }}>
        <MapaDibujo centro={vista.centro} zoom={vista.zoom} esquinas={esquinas} onCambio={setEsquinas} />
        <button
          type="button"
          aria-label={t('perimetro_usar_ubicacion')}
          onClick={usarUbicacion}
          style={{ position: 'absolute', right: 28, top: 12, width: 48, height: 48, borderRadius: 24, border: 'none', background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', boxShadow: 'var(--sombra-1)' }}
        >
          <IconoUbicacion stroke="var(--agua)" />
        </button>
      </div>

      <div className="ps-pad-16" style={{ marginTop: 12, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--texto-tenue)' }}>
            {esquinas.length === 1 ? '1 esquina' : `${esquinas.length} esquinas`}
          </span>
          <span style={{ fontSize: esquinas.length >= 3 ? 24 : 17, fontWeight: 800, lineHeight: 1.2 }}>
            {esquinas.length >= 3 ? `≈ ${numero(hectareas, 2)} ha` : t('perimetro_toca_esquinas')}
          </span>
        </div>
        <span style={{ display: 'flex', gap: 8 }}>
          <button type="button" onClick={() => setEsquinas(esquinas.slice(0, -1))} disabled={esquinas.length === 0} className="ps-btn-secundario" style={{ padding: '0 14px', minHeight: 52 }}>
            {t('deshacer')}
          </button>
          <button type="button" onClick={() => setEsquinas([])} disabled={esquinas.length === 0} className="ps-btn-secundario" style={{ padding: '0 14px', minHeight: 52 }}>
            Borrar
          </button>
        </span>
      </div>

      {esquinas.length >= 3 && !medidaValida ? (
        <p className="ps-pad-16 ps-nota" role="status" style={{ margin: '8px 0 0 0' }}>
          Mueve las esquinas: la parcela debe medir entre {numero(HECTAREAS_MIN, 2)} y {numero(HECTAREAS_MAX)} hectáreas.
        </p>
      ) : null}
      {error ? (
        <p className="ps-pad-16 ps-nota" role="alert" style={{ margin: '8px 0 0 0', color: 'var(--riesgo-texto)' }}>
          {error}
        </p>
      ) : null}

      <div style={{ marginTop: 'auto', padding: '16px 16px 32px 16px' }}>
        <button type="button" onClick={analizar} disabled={enviando || !listo} className="ps-btn">
          {enviando ? t('cargando') : t('perimetro_analizar')}
        </button>
      </div>
    </Screen>
  )
}
