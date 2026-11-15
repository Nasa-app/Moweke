import { useState } from 'react'
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

// Centro inicial del mapa cuando no se conoce la ubicación: Quemchi, la comuna piloto.
const CENTRO_POR_DEFECTO: Punto = [-42.1581806, -73.6508595]
// Los mismos límites que valida POST /api/parcelas.
const HECTAREAS_MIN = 0.05
const HECTAREAS_MAX = 1000

export default function Perimetro() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const enOnboarding = params.get('desde') === 'onboarding'
  const { setParcelaActiva, setCultivoActivo } = usePredio()
  const [centro, setCentro] = useState<Punto>(() => leer<Punto>('mapa_centro', CENTRO_POR_DEFECTO))
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
        setCentro([pos.coords.latitude, pos.coords.longitude])
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
      <Titulo sub="Mueve el mapa hasta tu parcela y toca cada esquina. Puedes arrastrar una esquina para corregirla.">
        {t('perimetro_titulo')}
      </Titulo>

      <div className="ps-pad-16" style={{ marginTop: 14, position: 'relative' }}>
        <MapaDibujo centro={centro} esquinas={esquinas} onCambio={setEsquinas} />
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
