import { useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { Screen, BarraSuperior, Titulo } from '../components/Screen'
import { CompatRing } from '../components/CompatRing'
import { Chip } from '../components/Chip'
import { IconoInfo, IconoSiguiente } from '../components/icons'
import { usePredio } from '../state/PredioContext'
import {
  ApiError, CATEGORIAS_COMIDA, ESCENARIOS, candidatasSiembra, guardarEscenario, guardarRiego, leerEscenario, leerRiego,
  mensajeDeError, type Candidata, type CandidatasSiembra, type CategoriaClima, type Escenario,
} from '../lib/api'
import {
  NOMBRE_ESCENARIO, TEXTO_CATEGORIA_CLIMA, aPorcentaje, fechaCorta, nombreClave, nombreEspecie, textoDatosFaltantes,
  textoEscenario, textoSueloSinDeclarar,
} from '../lib/formato'
import { useI18n } from '../i18n'

// Grupos de las categorías de uso de EcoCrop (el campo `categorias` de cada candidata).
const GRUPOS = [
  { clave: 'comida', nombre: 'Comida', categorias: CATEGORIAS_COMIDA },
  { clave: 'frutas', nombre: 'Frutas', categorias: ['fruits & nuts'] },
  { clave: 'forraje', nombre: 'Forraje', categorias: ['forage/pasture', 'cover crop'] },
  { clave: 'todas', nombre: 'Todas', categorias: null },
] as const
const VISTAS = [
  { clave: 'todas', nombre: 'Todas' },
  { clave: 'emergente', nombre: 'Nuevas' },
  { clave: 'en_riesgo', nombre: 'En riesgo' },
] as const
type Vista = (typeof VISTAS)[number]['clave']
const NIVELES_CON_SEGUIMIENTO = ['perfil_calibrado', 'perfil_fenologico_regional']
const FILAS_MAX = 15

const porcentaje = (candidata: Candidata) => aPorcentaje(candidata.puntaje)
const textoCompatible = (c: Candidata) =>
  c.puntaje_ano_dificil === undefined
    ? `${porcentaje(c)}% compatible`
    : `${porcentaje(c)}% compatible · ${aPorcentaje(c.puntaje_ano_dificil)}% en un año difícil`

// Solo se marca lo que cambia con el clima: las que se mantienen no necesitan etiqueta.
function ChipClima({ c }: { c: Candidata }) {
  const categoria = c.clima?.categoria
  if (categoria !== 'emergente' && categoria !== 'en_riesgo') return null
  return (
    <span style={{ marginTop: 4, alignSelf: 'center' }}>
      <Chip tono={categoria === 'emergente' ? 'clima' : 'precaucion'}>{TEXTO_CATEGORIA_CLIMA[categoria].chip}</Chip>
    </span>
  )
}

export default function Especies() {
  const { t } = useI18n()
  const { idParcela } = usePredio()
  const [grupo, setGrupo] = useState<(typeof GRUPOS)[number]['clave']>('comida')
  const [riego, setRiego] = useState(leerRiego)
  const [escenario, setEscenario] = useState<Escenario>(leerEscenario)
  const [vista, setVista] = useState<Vista>('todas')
  const [resultado, setResultado] = useState<{ pedido: string; datos: CandidatasSiembra } | null>(null)
  const [sinClima, setSinClima] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const categorias = GRUPOS.find((g) => g.clave === grupo)?.categorias ?? undefined
  const pedido = `${grupo}|${riego}|${escenario}|${vista}`
  const ranking = resultado?.pedido === pedido ? resultado.datos : null

  function elegirRiego(riega: boolean) {
    guardarRiego(riega)
    setRiego(riega)
  }

  function elegirEscenario(nuevo: Escenario) {
    guardarEscenario(nuevo)
    setEscenario(nuevo)
  }

  // Se pide solo el grupo que se mira: el servidor filtra por categorías y recorta después.
  useEffect(() => {
    if (!idParcela) return
    let vigente = true
    candidatasSiembra(idParcela, { categorias, limite: 3 + FILAS_MAX, riego, escenario, climaFuturo: vista === 'todas' ? undefined : vista })
      .then((r) => vigente && setResultado({ pedido, datos: r }))
      .catch((err) => {
        if (!vigente) return
        if (err instanceof ApiError && err.status === 409) setSinClima(true)
        else setError(mensajeDeError(err, 'No pudimos calcular qué sembrar. Revisa tu conexión e inténtalo de nuevo.'))
      })
    return () => {
      vigente = false
    }
  }, [idParcela, categorias, riego, escenario, vista, pedido])

  if (!idParcela) return <Navigate to="/terreno/perimetro" replace />

  // En 'Nuevas' y 'En riesgo' el servidor ya filtró por esa categoría, y entran también las que todavía no son aptas.
  const aptas = (ranking?.candidatas ?? []).filter((c) => vista !== 'todas' || c.apta)
  const destacadas = aptas.slice(0, 3)
  const resto = aptas.slice(3, 3 + FILAS_MAX)
  const serie = ranking?.serie_climatica ?? null
  const porCategoria = ranking?.especies_por_categoria_clima ?? null
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

      <div className="ps-pad-16" style={{ marginTop: 10 }}>
        <div role="radiogroup" aria-label="Agua del cultivo" style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 4, padding: 4, borderRadius: 30, background: 'var(--hundido)' }}>
          {([[false, 'Solo lluvia'], [true, 'Con riego']] as const).map(([valor, nombre]) => (
            <button key={nombre} type="button" role="radio" aria-checked={riego === valor} onClick={() => elegirRiego(valor)} className={`ps-pill ${riego === valor ? 'activo' : ''}`} style={{ borderRadius: 26, minHeight: 48 }}>
              {nombre}
            </button>
          ))}
        </div>
        <p className="ps-nota" style={{ margin: '6px 8px 0 8px' }}>
          {riego ? 'Contamos con que repones el agua que falta. El exceso de lluvia sigue contando.' : 'Contamos solo con la lluvia. Si riegas, elige "Con riego".'}
        </p>
      </div>

      {serie ? (
        <div className="ps-pad-16" style={{ marginTop: 10 }}>
          <div role="radiogroup" aria-label="Clima a futuro" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 4, padding: 4, borderRadius: 30, background: 'var(--hundido)' }}>
            {ESCENARIOS.map((valor) => (
              <button key={valor} type="button" role="radio" aria-checked={escenario === valor} onClick={() => elegirEscenario(valor)} className={`ps-pill ${escenario === valor ? 'activo' : ''}`} style={{ borderRadius: 26, minHeight: 48 }}>
                {NOMBRE_ESCENARIO[valor]}
              </button>
            ))}
          </div>
          <p className="ps-nota" style={{ margin: '6px 8px 0 8px' }}>{textoEscenario(escenario, serie)}</p>
          <div role="radiogroup" aria-label="Qué especies ver" style={{ marginTop: 10, display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 4, padding: 4, borderRadius: 30, background: 'var(--hundido)' }}>
            {VISTAS.map((v) => (
              <button key={v.clave} type="button" role="radio" aria-checked={vista === v.clave} onClick={() => setVista(v.clave)} className={`ps-pill ${vista === v.clave ? 'activo' : ''}`} style={{ borderRadius: 26, minHeight: 48 }}>
                {v.nombre}{v.clave !== 'todas' && porCategoria ? ` (${porCategoria[v.clave as CategoriaClima]})` : ''}
              </button>
            ))}
          </div>
          <details style={{ margin: '6px 8px 0 8px' }}>
            <summary className="ps-nota" style={{ cursor: 'pointer', fontWeight: 800 }}>¿Cómo se calcula?</summary>
            <p className="ps-nota" style={{ margin: '4px 0 0 0' }}>
              Probamos cada especie con los {serie.anios} años de clima de tu parcela ({serie.primer_anio} a {serie.ultimo_anio}). “Compatible” es lo habitual; “año difícil” es lo que logra en 9 de cada 10 años. Es apta si aguanta el año difícil de los últimos 15.
            </p>
          </details>
        </div>
      ) : null}

      {ranking && textoDatosFaltantes(ranking.datos_faltantes) ? (
        <p className="ps-pad ps-nota" role="status" style={{ margin: '8px 0 0 0', color: 'var(--precaucion-texto)' }}>
          {textoDatosFaltantes(ranking.datos_faltantes)}
        </p>
      ) : null}

      {ranking && textoSueloSinDeclarar(ranking.suelo_sin_declarar) ? (
        <Link to="/terreno" className="ps-pad ps-nota" style={{ margin: '8px 0 0 0', textDecoration: 'none' }}>
          {textoSueloSinDeclarar(ranking.suelo_sin_declarar)} <b style={{ color: 'var(--verde)' }}>Responder</b>
        </Link>
      ) : null}

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
          Buscando qué se da bien en tu parcela…
        </p>
      ) : null}
      {ranking && aptas.length === 0 ? (
        <p className="ps-pad ps-cuerpo" style={{ margin: '12px 0 0 0' }}>
          {vista === 'emergente'
            ? 'Con este clima a futuro, ninguna especie de este grupo pasa a ser buena opción para tu parcela. Prueba con “Más calor”.'
            : vista === 'en_riesgo'
              ? 'Con este clima a futuro, ninguna especie de este grupo pierde terreno en tu parcela.'
              : 'Ninguna especie de este grupo resulta apta con el clima y el suelo de tu parcela.'}
        </p>
      ) : null}

      <div className="ps-pad-16" style={{ marginTop: 14, display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 8 }}>
        {destacadas.map((c, i) => (
          <Link key={c.especie} to={enlace(c)} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, textDecoration: 'none', color: 'var(--carbon)', textAlign: 'center' }}>
            <span style={{ position: 'relative', width: 80, height: 80, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <CompatRing porcentaje={porcentaje(c)} tamano={80} />
              {i === 0 && vista === 'todas' ? (
                <span style={{ position: 'absolute', top: -8, left: '50%', transform: 'translateX(-50%)', padding: '2px 9px', borderRadius: 999, background: 'var(--verde)', color: '#fff', fontSize: 13, fontWeight: 800 }}>Mejor</span>
              ) : null}
            </span>
            <span style={{ fontSize: 18, fontWeight: 800, lineHeight: 1.05 }}>{nombreEspecie(c.especie, c)}</span>
            <span style={{ display: 'flex', flexDirection: 'column', fontSize: 14, fontWeight: 700, lineHeight: 1.1, color: 'var(--texto-tenue)' }}>
              <b style={{ fontSize: 20, fontWeight: 800, color: 'var(--verde)' }}>{porcentaje(c)}%</b>
              compatible
              {c.puntaje_ano_dificil !== undefined ? <span style={{ fontSize: 13, fontWeight: 600 }}>{aPorcentaje(c.puntaje_ano_dificil)}% en un año difícil</span> : null}
              {!c.apta ? <span style={{ fontSize: 13, fontWeight: 600 }}>todavía no es apta</span> : null}
            </span>
            <ChipClima c={c} />
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
                    {textoCompatible(c)}
                    {!c.apta ? ' · todavía no es apta' : c.factor_limitante && porcentaje(c) < 100 ? ` · lo limita: ${nombreClave(c.factor_limitante).toLowerCase()}` : ''}
                  </span>
                  <ChipClima c={c} />
                </span>
                {NIVELES_CON_SEGUIMIENTO.includes(c.nivel_madurez) ? <Chip tono="acento">Con seguimiento</Chip> : null}
                <IconoSiguiente stroke="var(--texto-tenue)" />
              </Link>
            </li>
          ))}
        </ol>
      ) : null}
      {ranking && vista === 'todas' && ranking.especies_aptas > aptas.length ? (
        <p className="ps-pad ps-nota" style={{ margin: '8px 0 0 0' }}>
          Se muestran las {aptas.length} mejores de {ranking.especies_aptas}.
        </p>
      ) : null}

      <Link to="/fuentes" className="ps-btn-texto" style={{ marginTop: 'auto', padding: '16px 20px 28px 20px', gap: 6, fontSize: 15, color: 'var(--texto-tenue)', textAlign: 'center' }}>
        <IconoInfo tamano={18} />
        Calculado con la guía de la FAO (EcoCrop), el clima y el suelo de tu parcela
        {ranking ? ` · ${fechaCorta(ranking.datos_sitio.periodo_clima[0])} a ${fechaCorta(ranking.datos_sitio.periodo_clima[1])}` : ''}
      </Link>
    </Screen>
  )
}
