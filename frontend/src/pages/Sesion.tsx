import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Screen, BarraSuperior, Titulo } from '../components/Screen'
import { useAuth } from '../state/AuthContext'
import { guardar } from '../state/storage'
import { usePredio } from '../state/PredioContext'
import { listarParcelas, mensajeDeError } from '../lib/api'
import { useI18n } from '../i18n'

// No es una de las 26 pantallas del handoff, pero auth (/api/auth/registro,
// /api/auth/login) es uno de los pocos endpoints reales que ya existen (ver
// docs/plan-construccion.md §2.1) -- sin esta pantalla ninguna otra vista podría llamar
// al API real.
export default function Sesion() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const { iniciarSesion, registrarse } = useAuth()
  const { setParcelaActiva, setCultivoActivo } = usePredio()
  const [modo, setModo] = useState<'login' | 'registro'>('login')
  const [nombre, setNombre] = useState('')
  const [telefono, setTelefono] = useState('')
  const [password, setPassword] = useState('')
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function manejarEnvio(evento: FormEvent) {
    evento.preventDefault()
    setError(null)
    setCargando(true)
    try {
      if (modo === 'login') {
        await iniciarSesion(telefono, password)
      } else {
        // El registro pide un punto y todavía no se conoce el del predio (se marca
        // después, en Marca tu parcela): se manda el centro de la comuna piloto.
        await registrarse({ nombre, telefono, password, lat: -42.1581806, lon: -73.6508595 })
        guardar('ultimo_nombre', nombre)
      }
      // La parcela activa es la última del usuario que entra, no la que quedó en este
      // dispositivo de una sesión anterior.
      const { parcelas } = await listarParcelas()
      const ultima = parcelas[parcelas.length - 1]
      setParcelaActiva(ultima ? ultima.id : null)
      setCultivoActivo(null)
      navigate(ultima ? '/hoy' : '/onboarding/predio')
    } catch (err) {
      setError(mensajeDeError(err, 'Revisa los datos e intenta otra vez.'))
    } finally {
      setCargando(false)
    }
  }

  return (
    <Screen>
      <BarraSuperior volverA="/" />
      <Titulo>{modo === 'login' ? t('iniciar_sesion') : t('crear_cuenta')}</Titulo>

      <div className="ps-pad-16" style={{ marginTop: 14 }}>
        <div className="ps-grid-2" role="tablist" aria-label="Modo">
          <button type="button" role="tab" aria-selected={modo === 'login'} className={`ps-pill ${modo === 'login' ? 'activo' : ''}`} onClick={() => setModo('login')}>
            {t('iniciar_sesion')}
          </button>
          <button type="button" role="tab" aria-selected={modo === 'registro'} className={`ps-pill ${modo === 'registro' ? 'activo' : ''}`} onClick={() => setModo('registro')}>
            {t('crear_cuenta')}
          </button>
        </div>
      </div>

      <form onSubmit={manejarEnvio} className="ps-pad-16" style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
        {modo === 'registro' ? (
          <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={{ fontSize: 16, fontWeight: 800 }}>{t('nombre')}</span>
            <input
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              required
              style={campoEstilo}
              placeholder="Rosa"
            />
          </label>
        ) : null}
        <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span style={{ fontSize: 16, fontWeight: 800 }}>{t('telefono')}</span>
          <input
            type="tel"
            value={telefono}
            onChange={(e) => setTelefono(e.target.value)}
            required
            style={campoEstilo}
            placeholder="+56 9 1234 5678"
          />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span style={{ fontSize: 16, fontWeight: 800 }}>{t('contrasena')}</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={6}
            style={campoEstilo}
          />
        </label>
        {error ? (
          <p className="ps-chip ps-chip-riesgo" role="alert" style={{ alignSelf: 'flex-start' }}>
            {error}
          </p>
        ) : null}
        <button type="submit" className="ps-btn" disabled={cargando} style={{ marginTop: 8 }}>
          {cargando ? t('cargando') : modo === 'login' ? t('iniciar_sesion') : t('crear_cuenta')}
        </button>
      </form>
    </Screen>
  )
}

const campoEstilo: React.CSSProperties = {
  minHeight: 52,
  padding: '0 14px',
  borderRadius: 14,
  border: '2px solid var(--borde-control)',
  background: 'var(--blanco)',
  color: 'var(--carbon)',
  font: "700 17px 'Alegreya Sans', sans-serif",
}
