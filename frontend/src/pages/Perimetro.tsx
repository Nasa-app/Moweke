import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Screen, BarraSuperior, Titulo } from '../components/Screen'
import { MapaDibujo } from '../components/Mapa'
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
// Zoom con el que se ve un predio (se usa con la ubicación del dispositivo y con un predio ya marcado).
const ZOOM_PARCELA = 17

interface Vista {
  centro: Punto
  zoom: number
}

// Sin ubicación todavía el mapa abre mostrando el mundo: no se supone ningún país. Con ubicación, o con un predio
// ya marcado antes, abre sobre el predio.
const VISTA_MUNDO: Vista = { centro: [20, 0], zoom: 2 }

export default function Perimetro() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const enOnboarding = params.get('desde') === 'onboarding'
  const { idParcela, setParcelaActiva, setCultivoActivo } = usePredio()
  const ultima = leer<Punto | null>('mapa_centro', null)
  const [elegida, setVista] = useState<Vista | null>(null)
  const vista = elegida ?? (ultima ? { centro: ultima, zoom: ZOOM_PARCELA } : VISTA_MUNDO)
  const [esquinas, setEsquinas] = useState<Punto[]>([])
  const [nombre, setNombre] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const hectareas = hectareasDe(esquinas)
  const medidaValida = hectareas >= HECTAREAS_MIN && hectareas <= HECTAREAS_MAX
  const listo = esquinas.length >= 3 && medidaValida

  // El mapa intenta abrir donde está la persona; si no da permiso o no hay señal, queda la vista de arriba y el botón
  // de ubicación sigue disponible.
  useEffect(() => {
    if (!('geolocation' in navigator)) return
    let vigente = true
    navigator.geolocation.getCurrentPosition(
      (pos) => vigente && setVista({ centro: [pos.coords.latitude, pos.coords.longitude], zoom: ZOOM_PARCELA }),
      () => undefined,
      { timeout: 8000, maximumAge: 300000 },
    )
    return () => {
      vigente = false
    }
  }, [])

  function usarUbicacion() {
    if (!('geolocation' in navigator)) {
      setError(t('perimetro_sin_gps'))
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setError(null)
        setVista({ centro: [pos.coords.latitude, pos.coords.longitude], zoom: ZOOM_PARCELA })
      },
      () => setError(t('perimetro_gps_fallo')),
      { timeout: 8000 },
    )
  }

  async function analizar() {
    setEnviando(true)
    setError(null)
    try {
      const parcela = await crearParcela(aPoligono(esquinas), nombre)
      guardar('mapa_centro', [parcela.lat, parcela.lon])
      setParcelaActiva(parcela.id)
      setCultivoActivo(null)
      navigate(`/terreno/preparando${enOnboarding ? '?desde=onboarding' : ''}`)
    } catch (err) {
      setError(mensajeDeError(err, t('perimetro_error_guardar')))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Screen>
      <BarraSuperior volverA={enOnboarding ? '/onboarding/predio' : idParcela ? '/terreno' : '/hoy'} />
      <Titulo sub={t('perimetro_sub')}>
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
            {esquinas.length === 1 ? t('perimetro_esquina_una') : t('perimetro_esquinas', { n: esquinas.length })}
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
            {t('perimetro_borrar')}
          </button>
        </span>
      </div>

      {esquinas.length >= 3 && !medidaValida ? (
        <p className="ps-pad-16 ps-nota" role="status" style={{ margin: '8px 0 0 0' }}>
          {t('perimetro_medida', { min: numero(HECTAREAS_MIN, 2), max: numero(HECTAREAS_MAX) })}
        </p>
      ) : null}
      {error ? (
        <p className="ps-pad-16 ps-nota" role="alert" style={{ margin: '8px 0 0 0', color: 'var(--riesgo-texto)' }}>
          {error}
        </p>
      ) : null}

      <label className="ps-pad-16" style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 12 }}>
        <span style={{ fontSize: 16, fontWeight: 700, padding: '0 4px' }}>{t('perimetro_nombre')}</span>
        <input
          type="text"
          value={nombre}
          maxLength={60}
          placeholder={t('terreno_nombre_ejemplo')}
          onChange={(e) => setNombre(e.target.value)}
          style={{ minHeight: 52, padding: '0 14px', borderRadius: 16, border: '2px solid var(--borde-control)', background: '#fff', color: 'var(--carbon)', font: "700 17px 'Alegreya Sans', sans-serif" }}
        />
      </label>

      <div style={{ marginTop: 'auto', padding: '16px 16px 32px 16px' }}>
        <button type="button" onClick={analizar} disabled={enviando || !listo} className="ps-btn">
          {enviando ? t('cargando') : t('perimetro_analizar')}
        </button>
      </div>
    </Screen>
  )
}
