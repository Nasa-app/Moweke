import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Screen, BarraSuperior, Titulo } from '../components/Screen'
import { Chip } from '../components/Chip'
import { MiniPerimetro } from '../components/MiniPerimetro'
import { IconoUbicacion } from '../components/icons'
import { listarParcelas, mensajeDeError, type ParcelaResumen } from '../lib/api'
import { numero } from '../lib/formato'
import { usePredio } from '../state/PredioContext'

// Las parcelas que la persona ya marcó. Una sola está activa: es la que miran Hoy, Cultivos, Terreno y Qué sembrar.
export default function Parcelas() {
  const navigate = useNavigate()
  const { idParcela, setParcelaActiva, setCultivoActivo } = usePredio()
  const [parcelas, setParcelas] = useState<ParcelaResumen[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let vigente = true
    listarParcelas()
      .then((r) => vigente && setParcelas(r.parcelas))
      .catch((err) => vigente && setError(mensajeDeError(err, 'No pudimos cargar tus parcelas. Revisa tu conexión e inténtalo de nuevo.')))
    return () => {
      vigente = false
    }
  }, [])

  function usar(id: number) {
    setParcelaActiva(id)
    setCultivoActivo(null)
    navigate('/terreno')
  }

  return (
    <Screen>
      <BarraSuperior volverA="/terreno" />
      <Titulo sub="Elige con cuál trabajar. Hoy, Cultivos, Terreno y Qué sembrar muestran la parcela activa.">Mis parcelas</Titulo>

      {parcelas === null && !error ? <p className="ps-pad ps-nota" style={{ margin: '16px 0 0 0' }}>Cargando…</p> : null}
      {error ? (
        <p className="ps-pad ps-nota" role="alert" style={{ margin: '16px 0 0 0', color: 'var(--riesgo-texto)' }}>
          {error}
        </p>
      ) : null}
      {parcelas && parcelas.length === 0 ? (
        <p className="ps-pad ps-cuerpo" style={{ margin: '16px 0 0 0' }}>Todavía no marcaste ninguna parcela.</p>
      ) : null}

      {parcelas && parcelas.length ? (
        <ul aria-label="Parcelas" style={{ margin: '16px 16px 0 16px', padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 10 }}>
          {parcelas.map((p, i) => {
            const activa = p.id === idParcela
            return (
              <li
                key={p.id}
                className="ps-card"
                aria-current={activa ? 'true' : undefined}
                style={{ display: 'flex', alignItems: 'center', gap: 14, boxShadow: activa ? '0 0 0 3px var(--verde)' : undefined }}
              >
                <span aria-hidden="true" style={{ width: 64, height: 64, borderRadius: 16, background: 'var(--menta)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <MiniPerimetro perimetro={p.perimetro} tamano={64} />
                </span>
                <span style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
                  <span style={{ fontSize: 20, fontWeight: 800, lineHeight: 1.1 }}>Parcela {i + 1}</span>
                  <span className="ps-detalle">
                    {numero(p.hectareas, 2)} ha{p.altitud_msnm !== null ? ` · ${numero(p.altitud_msnm)} msnm` : ''}
                  </span>
                  {activa ? (
                    <span style={{ alignSelf: 'flex-start' }}>
                      <Chip tono="favorable">Activa</Chip>
                    </span>
                  ) : (
                    <button type="button" onClick={() => usar(p.id)} className="ps-btn-secundario" style={{ minHeight: 44, padding: '0 16px', alignSelf: 'flex-start', marginTop: 4 }}>
                      Usar esta
                    </button>
                  )}
                </span>
              </li>
            )
          })}
        </ul>
      ) : null}

      <div style={{ marginTop: 'auto', padding: '20px 16px 32px 16px' }}>
        <Link to="/terreno/perimetro" className="ps-btn" style={{ gap: 8 }}>
          <IconoUbicacion stroke="#fff" />
          Marcar otra parcela
        </Link>
      </div>
    </Screen>
  )
}
