import { useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { Screen, BarraSuperior, Titulo } from '../components/Screen'
import { CompatRing } from '../components/CompatRing'
import { Chip } from '../components/Chip'
import { IconoInfo, IconoSiguiente } from '../components/icons'
import { usePredio } from '../state/PredioContext'
import { ApiError, candidatasSiembra, mensajeDeError, type Candidata, type CandidatasSiembra } from '../lib/api'
import { aPorcentaje, fechaCorta, nombreClave, nombreEspecie } from '../lib/formato'
import { useI18n } from '../i18n'

// Grupos de las categorías de uso de EcoCrop (el campo `categorias` de cada candidata).
const GRUPOS = [
  { clave: 'comida', nombre: 'Comida', categorias: ['vegetables', 'roots/tubers', 'pulses (grain legumes)', 'cereals & pseudocereals'] },
  { clave: 'frutas', nombre: 'Frutas', categorias: ['fruits & nuts'] },
  { clave: 'forraje', nombre: 'Forraje', categorias: ['forage/pasture', 'cover crop'] },
  { clave: 'todas', nombre: 'Todas', categorias: null },
] as const
const NIVELES_CON_SEGUIMIENTO = ['perfil_calibrado', 'perfil_fenologico_regional']
const FILAS_MAX = 15

const porcentaje = (candidata: Candidata) => aPorcentaje(candidata.puntaje)

export default function Especies() {
  const { t } = useI18n()
  const { idParcela } = usePredio()
  const [grupo, setGrupo] = useState<(typeof GRUPOS)[number]['clave']>('comida')
  const [ranking, setRanking] = useState<CandidatasSiembra | null>(null)
  const [sinClima, setSinClima] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!idParcela) return
    let vigente = true
    candidatasSiembra(idParcela)
      .then((r) => vigente && setRanking(r))
      .catch((err) => {
        if (!vigente) return
        if (err instanceof ApiError && err.status === 409) setSinClima(true)
        else setError(mensajeDeError(err, 'No se pudieron calcular las especies.'))
      })
    return () => {
      vigente = false
    }
  }, [idParcela])

  if (!idParcela) return <Navigate to="/terreno/perimetro" replace />

  const categorias = GRUPOS.find((g) => g.clave === grupo)?.categorias ?? null
  const aptas = (ranking?.candidatas ?? []).filter(
    (c) => c.apta && (!categorias || c.categorias.some((cat) => (categorias as readonly string[]).includes(cat))),
  )
  const destacadas = aptas.slice(0, 3)
  const resto = aptas.slice(3, 3 + FILAS_MAX)
  const enlace = (c: Candidata) => `/especies/analisis?especie=${encodeURIComponent(c.especie)}`

  return (
    <Screen>
      <BarraSuperior volverA="/terreno" />
      <Titulo sub={ranking ? `${ranking.especies_aptas} especies aptas de ${ranking.especies_evaluadas} evaluadas` : undefined}>
        {t('especies_titulo')}
      </Titulo>

      <div className="ps-pad-16" style={{ marginTop: 14 }}>
        <div role="radiogroup" aria-label="Tipo de cultivo" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 4, padding: 4, borderRadius: 30, background: 'var(--hundido)' }}>
          {GRUPOS.map((g) => (
            <button key={g.clave} type="button" role="radio" aria-checked={grupo === g.clave} onClick={() => setGrupo(g.clave)} className={`ps-pill ${grupo === g.clave ? 'activo' : ''}`} style={{ borderRadius: 26, minHeight: 48 }}>
              {g.nombre}
            </button>
          ))}
        </div>
      </div>

      {sinClima ? (
        <Link to="/terreno/preparando" className="ps-card-plana" style={{ margin: '12px 16px 0 16px', textDecoration: 'none', color: 'var(--carbon)', display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ flex: 1, fontSize: 16, fontWeight: 700 }}>Todavía se está reuniendo el clima de tu parcela. Sin un año de clima no se puede calcular.</span>
          <span style={{ fontSize: 16, fontWeight: 800, color: 'var(--verde)' }}>Ver avance</span>
        </Link>
      ) : null}
      {error ? (
        <p className="ps-pad ps-nota" role="alert" style={{ margin: '12px 0 0 0', color: 'var(--riesgo-texto)' }}>
          {error}
        </p>
      ) : null}
      {!ranking && !sinClima && !error ? (
        <p className="ps-pad ps-cuerpo" role="status" style={{ margin: '12px 0 0 0' }}>
          Comparando tu terreno con el catálogo de especies…
        </p>
      ) : null}
      {ranking && aptas.length === 0 ? (
        <p className="ps-pad ps-cuerpo" style={{ margin: '12px 0 0 0' }}>
          Ninguna especie de este grupo resulta apta con el clima y el suelo de tu parcela.
        </p>
      ) : null}

      <div className="ps-pad-16" style={{ marginTop: 14, display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 8 }}>
        {destacadas.map((c, i) => (
          <Link key={c.especie} to={enlace(c)} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, textDecoration: 'none', color: 'var(--carbon)', textAlign: 'center' }}>
            <span style={{ position: 'relative', width: 80, height: 80, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <CompatRing porcentaje={porcentaje(c)} tamano={80} />
              {i === 0 ? (
                <span style={{ position: 'absolute', top: -8, left: '50%', transform: 'translateX(-50%)', padding: '2px 9px', borderRadius: 999, background: 'var(--verde)', color: '#fff', fontSize: 13, fontWeight: 800 }}>Mejor</span>
              ) : null}
            </span>
            <span style={{ fontSize: 18, fontWeight: 800, lineHeight: 1.05 }}>{nombreEspecie(c.especie, c)}</span>
            <span style={{ display: 'flex', flexDirection: 'column', fontSize: 14, fontWeight: 700, lineHeight: 1.1, color: 'var(--texto-tenue)' }}>
              <b style={{ fontSize: 20, fontWeight: 800, color: 'var(--verde)' }}>{porcentaje(c)}%</b>
              compatible
            </span>
          </Link>
        ))}
      </div>

      {resto.length ? (
        <ol className="ps-pad-16" style={{ margin: '16px 0 0 0', listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 8 }}>
          {resto.map((c) => (
            <li key={c.especie}>
              <Link to={enlace(c)} className="ps-card" style={{ textDecoration: 'none', color: 'var(--carbon)', display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px' }}>
                <CompatRing porcentaje={porcentaje(c)} tamano={44} />
                <span style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
                  <span style={{ fontSize: 18, fontWeight: 800, lineHeight: 1.15 }}>{nombreEspecie(c.especie, c)}</span>
                  <span className="ps-detalle">
                    {porcentaje(c)}% compatible
                    {c.factor_limitante && porcentaje(c) < 100 ? ` · lo limita: ${nombreClave(c.factor_limitante).toLowerCase()}` : ''}
                  </span>
                </span>
                {NIVELES_CON_SEGUIMIENTO.includes(c.nivel_madurez) ? <Chip tono="acento">Con seguimiento</Chip> : null}
                <IconoSiguiente stroke="var(--texto-tenue)" />
              </Link>
            </li>
          ))}
        </ol>
      ) : null}
      {aptas.length > 3 + FILAS_MAX ? (
        <p className="ps-pad ps-nota" style={{ margin: '8px 0 0 0' }}>
          Se muestran las {3 + FILAS_MAX} mejores de {aptas.length}.
        </p>
      ) : null}

      <Link to="/fuentes" className="ps-btn-texto" style={{ marginTop: 'auto', padding: '16px 20px 28px 20px', gap: 6, fontSize: 15, color: 'var(--texto-tenue)', textAlign: 'center' }}>
        <IconoInfo tamano={18} />
        FAO EcoCrop con el clima y el suelo de tu parcela
        {ranking ? ` · ${fechaCorta(ranking.datos_sitio.periodo_clima[0])} a ${fechaCorta(ranking.datos_sitio.periodo_clima[1])}` : ''}
      </Link>
    </Screen>
  )
}
