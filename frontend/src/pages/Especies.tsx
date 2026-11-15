import { useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { Screen, BarraSuperior, Titulo } from '../components/Screen'
import { CompatRing } from '../components/CompatRing'
import { Chip } from '../components/Chip'
import { IconoInfo, IconoSiguiente } from '../components/icons'
import { Interruptor } from '../components/Interruptor'
import { usePredio } from '../state/PredioContext'
import { borrar } from '../state/storage'
import {
  ApiError, CATEGORIAS_COMIDA, ESCENARIOS, candidatasSiembra, guardarRiego, leerRiego,
  mensajeDeError, type Candidata, type CandidatasSiembra, type CategoriaClima, type Escenario,
} from '../lib/api'
import {
  NOMBRE_ESCENARIO, TEXTO_CATEGORIA_CLIMA, aPorcentaje, fechaCorta, nombreClave, nombreEspecie, textoDatosFaltantes, textoVariedad,
  textoEscenario, textoSueloSinDeclarar,
} from '../lib/formato'
import { useI18n } from '../i18n'
import { tr } from '../i18n/dictionary'

// Grupos de las categorías de uso de EcoCrop (el campo `categorias` de cada candidata).
const GRUPOS = [
  { clave: 'comida', categorias: CATEGORIAS_COMIDA },
  { clave: 'frutas', categorias: ['fruits & nuts'] },
  { clave: 'forraje', categorias: ['forage/pasture', 'cover crop'] },
  { clave: 'todas', categorias: null },
] as const
const VISTAS = [
  { clave: 'todas' },
  { clave: 'emergente' },
  { clave: 'en_riesgo' },
] as const
type Vista = (typeof VISTAS)[number]['clave']
const NIVELES_CON_SEGUIMIENTO = ['perfil_calibrado', 'perfil_fenologico_regional']
const FILAS_MAX = 15

const porcentaje = (candidata: Candidata) => aPorcentaje(candidata.puntaje)
const textoCompatible = (c: Candidata) =>
  c.puntaje_ano_dificil === undefined
    ? tr('especies_pct_compatible', { n: porcentaje(c) })
    : `${tr('especies_pct_compatible', { n: porcentaje(c) })} · ${tr('especies_pct_dificil', { n: aPorcentaje(c.puntaje_ano_dificil) })}`

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
  // Un supuesto (clima a futuro): siempre arranca en lo observado y no se guarda en el dispositivo.
  const [escenario, setEscenario] = useState<Escenario>('observado')
  const [vista, setVista] = useState<Vista>('todas')
  const [resultado, setResultado] = useState<{ pedido: string; datos: CandidatasSiembra } | null>(null)
  const [sinClima, setSinClima] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const categorias = GRUPOS.find((g) => g.clave === grupo)?.categorias ?? undefined
  const pedido = `${grupo}|${riego}|${escenario}|${vista}`
  // Mientras llega un cálculo nuevo se sigue mostrando el anterior, atenuado: así se ve que el cambio se está aplicando.
  const ranking = resultado?.datos ?? null
  const actualizando = resultado !== null && resultado.pedido !== pedido

  function elegirRiego(riega: boolean) {
    guardarRiego(riega)
    setRiego(riega)
  }

  // Limpia lo que versiones anteriores dejaron guardado en el dispositivo.
  useEffect(() => borrar('escenario_clima'), [])

  // Se pide solo el grupo que se mira: el servidor filtra por categorías y recorta después.
  useEffect(() => {
    if (!idParcela) return
    let vigente = true
    candidatasSiembra(idParcela, { categorias, limite: 3 + FILAS_MAX, riego, escenario, climaFuturo: vista === 'todas' ? undefined : vista })
      .then((r) => vigente && setResultado({ pedido, datos: r }))
      .catch((err) => {
        if (!vigente) return
        if (err instanceof ApiError && err.status === 409) setSinClima(true)
        else setError(mensajeDeError(err, tr('especies_error_calcular')))
      })
    return () => {
      vigente = false
    }
  }, [idParcela, categorias, riego, escenario, vista, pedido])

  if (!idParcela) return <Navigate to="/terreno/perimetro" replace />

  // En 'Nuevas' y 'En riesgo' el servidor ya filtró por esa categoría, y entran también las que todavía no son aptas.
  const aptas = (ranking?.candidatas ?? []).filter((c) => vista !== 'todas' || c.apta)
  // Dos especies distintas pueden compartir nombre común (cebollín, bledo): se distinguen con su nombre científico.
  const veces = new Map<string, number>()
  for (const c of ranking?.candidatas ?? []) {
    const n = nombreEspecie(c.especie, c)
    veces.set(n, (veces.get(n) ?? 0) + 1)
  }
  const nombreDe = (c: Candidata) => {
    const n = nombreEspecie(c.especie, c)
    return (veces.get(n) ?? 0) > 1 && c.nombre_cientifico ? `${n} (${c.nombre_cientifico})` : n
  }
  const destacadas = aptas.slice(0, 3)
  const resto = aptas.slice(3, 3 + FILAS_MAX)
  const serie = ranking?.serie_climatica ?? null
  const porCategoria = ranking?.especies_por_categoria_clima ?? null
  const enlace = (c: Candidata) =>
    `/especies/analisis?especie=${encodeURIComponent(c.especie)}${escenario === 'observado' ? '' : `&escenario=${escenario}`}`

  return (
    <Screen>
      <BarraSuperior volverA="/terreno" />
      <Titulo sub={ranking ? t('especies_sub', { aptas: ranking.especies_aptas, evaluadas: ranking.especies_evaluadas }) : undefined}>
        {t('especies_titulo')}
      </Titulo>

      <div className="ps-pad-16" style={{ marginTop: 14 }}>
        <div role="radiogroup" aria-label={t('especies_tipo_aria')} style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 4, padding: 4, borderRadius: 30, background: 'var(--hundido)' }}>
          {GRUPOS.map((g) => (
            <button key={g.clave} type="button" role="radio" aria-checked={grupo === g.clave} onClick={() => setGrupo(g.clave)} className={`ps-pill ${grupo === g.clave ? 'activo' : ''}`} style={{ borderRadius: 26, minHeight: 48 }}>
              {t(`especies_grupo_${g.clave}`)}
            </button>
          ))}
        </div>
      </div>

      {/* Tres niveles. 1) Qué quiere sembrar (arriba). 2) Su situación real: ¿puede regar? Es un sí o un no, y cambia
          mucho el resultado, por eso siempre se ve. 3) Supuestos de análisis (clima a futuro y el filtro Nuevas / En
          riesgo): recogidos, y si hay uno activo se ve como etiqueta con ✕ junto a los resultados. */}
      <div className="ps-pad-16" style={{ marginTop: 12 }}>
        <Interruptor
          activo={riego}
          onCambio={elegirRiego}
          etiqueta={t('especies_puedo_regar')}
          descripcion={riego ? t('especies_riego_si') : t('especies_riego_no')}
        />
      </div>

      {serie ? (
        <details className="ps-pad-16" style={{ marginTop: 8 }}>
          <summary style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', minHeight: 44, padding: '0 4px', fontSize: 16, fontWeight: 800, color: 'var(--verde)' }}>
            {t('especies_probar_clima')}
          </summary>
          <div style={{ marginTop: 6 }}>
            <span className="ps-contexto" style={{ padding: '0 4px' }}>{t('especies_clima_futuro')}</span>
            <div role="radiogroup" aria-label={t('especies_clima_futuro')} style={{ marginTop: 4, display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 4, padding: 4, borderRadius: 30, background: 'var(--hundido)' }}>
              {ESCENARIOS.map((valor) => (
                <button key={valor} type="button" role="radio" aria-checked={escenario === valor} onClick={() => setEscenario(valor)} className={`ps-pill ${escenario === valor ? 'activo' : ''}`} style={{ borderRadius: 26, minHeight: 48 }}>
                  {NOMBRE_ESCENARIO[valor]}
                </button>
              ))}
            </div>
            <p className="ps-nota" style={{ margin: '6px 8px 0 8px' }}>{textoEscenario(escenario, serie)}</p>

            <span className="ps-contexto" style={{ display: 'block', marginTop: 12, padding: '0 4px' }}>{t('especies_que_mostrar')}</span>
            <div role="radiogroup" aria-label={t('especies_que_ver_aria')} style={{ marginTop: 4, display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 4, padding: 4, borderRadius: 30, background: 'var(--hundido)' }}>
              {VISTAS.map((v) => (
                <button key={v.clave} type="button" role="radio" aria-checked={vista === v.clave} onClick={() => setVista(v.clave)} className={`ps-pill ${vista === v.clave ? 'activo' : ''}`} style={{ borderRadius: 26, minHeight: 48 }}>
                  {t(`especies_vista_${v.clave}`)}{v.clave !== 'todas' && porCategoria ? ` (${porCategoria[v.clave as CategoriaClima]})` : ''}
                </button>
              ))}
            </div>
            <details style={{ margin: '8px 8px 0 8px' }}>
              <summary className="ps-nota" style={{ cursor: 'pointer', fontWeight: 800 }}>{t('especies_como_calcula')}</summary>
              <p className="ps-nota" style={{ margin: '4px 0 0 0' }}>
                {t('especies_calculo_detalle', { anios: serie.anios, primer: serie.primer_anio, ultimo: serie.ultimo_anio })}
              </p>
            </details>
          </div>
        </details>
      ) : null}

      {escenario !== 'observado' || vista !== 'todas' ? (
        <div className="ps-pad-16" style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>
          {escenario !== 'observado' ? (
            <button type="button" className="ps-chip ps-chip-precaucion" onClick={() => setEscenario('observado')} style={{ border: 'none', cursor: 'pointer', minHeight: 36 }} aria-label={t('especies_quitar_clima', { escenario: NOMBRE_ESCENARIO[escenario].toLowerCase() })}>
              {t('especies_chip_clima', { escenario: NOMBRE_ESCENARIO[escenario].toLowerCase() })}
            </button>
          ) : null}
          {vista !== 'todas' ? (
            <button type="button" className="ps-chip ps-chip-precaucion" onClick={() => setVista('todas')} style={{ border: 'none', cursor: 'pointer', minHeight: 36 }} aria-label={t('especies_mostrar_todas')}>
              {t('especies_chip_solo', { vista: t(`especies_vista_${vista}`).toLowerCase() })}
            </button>
          ) : null}
          <span className="ps-nota">{t('especies_supuesto_nota')}</span>
        </div>
      ) : null}

      {ranking && textoDatosFaltantes(ranking.datos_faltantes) ? (
        <p className="ps-pad ps-nota" role="status" style={{ margin: '8px 0 0 0', color: 'var(--precaucion-texto)' }}>
          {textoDatosFaltantes(ranking.datos_faltantes)}
        </p>
      ) : null}

      {ranking && textoSueloSinDeclarar(ranking.suelo_sin_declarar) ? (
        <Link to="/terreno" className="ps-pad ps-nota" style={{ margin: '8px 0 0 0', textDecoration: 'none' }}>
          {textoSueloSinDeclarar(ranking.suelo_sin_declarar)} <b style={{ color: 'var(--verde)' }}>{t('especies_responder')}</b>
        </Link>
      ) : null}

      {sinClima ? (
        <Link to="/terreno/preparando" className="ps-card-plana" style={{ margin: '12px 16px 0 16px', textDecoration: 'none', color: 'var(--carbon)', display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ flex: 1, fontSize: 16, fontWeight: 700 }}>{t('especies_reuniendo_clima')}</span>
          <span style={{ fontSize: 16, fontWeight: 800, color: 'var(--verde)' }}>{t('especies_ver_avance')}</span>
        </Link>
      ) : null}
      {error ? (
        <p className="ps-pad ps-nota" role="alert" style={{ margin: '12px 0 0 0', color: 'var(--riesgo-texto)' }}>
          {error}
        </p>
      ) : null}
      {!ranking && !sinClima && !error ? (
        <p className="ps-pad ps-cuerpo" role="status" style={{ margin: '12px 0 0 0' }}>
          {t('especies_buscando')}
        </p>
      ) : null}
      <div aria-busy={actualizando} style={{ opacity: actualizando ? 0.45 : 1, transition: 'opacity 0.15s' }}>
      {ranking && aptas.length === 0 ? (
        <p className="ps-pad ps-cuerpo" style={{ margin: '12px 0 0 0' }}>
          {vista === 'emergente'
            ? t('especies_vacio_emergente')
            : vista === 'en_riesgo'
              ? t('especies_vacio_en_riesgo')
              : t(riego ? 'especies_vacio_riego' : 'especies_vacio_secano', { n: ranking.especies_evaluadas })}
        </p>
      ) : null}

      <div className="ps-pad-16" style={{ marginTop: 14, display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 8 }}>
        {destacadas.map((c, i) => (
          <Link key={c.especie} to={enlace(c)} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, textDecoration: 'none', color: 'var(--carbon)', textAlign: 'center' }}>
            <span style={{ position: 'relative', width: 80, height: 80, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <CompatRing porcentaje={porcentaje(c)} tamano={80} />
              {i === 0 && vista === 'todas' ? (
                <span style={{ position: 'absolute', top: -8, left: '50%', transform: 'translateX(-50%)', padding: '2px 9px', borderRadius: 999, background: 'var(--verde)', color: '#fff', fontSize: 13, fontWeight: 800 }}>{t('especies_mejor')}</span>
              ) : null}
            </span>
            <span style={{ fontSize: 18, fontWeight: 800, lineHeight: 1.05 }}>{nombreDe(c)}</span>
            {c.variedad_recomendada ? <span className="ps-nota" style={{ lineHeight: 1.1 }}>{t('especies_mejor_variedad', { variedad: textoVariedad(c.variedad_recomendada) })}</span> : null}
            <span style={{ display: 'flex', flexDirection: 'column', fontSize: 14, fontWeight: 700, lineHeight: 1.1, color: 'var(--texto-tenue)' }}>
              <b style={{ fontSize: 20, fontWeight: 800, color: 'var(--verde)' }}>{porcentaje(c)}%</b>
              {t('especies_compatible')}
              {c.puntaje_ano_dificil !== undefined ? <span style={{ fontSize: 13, fontWeight: 600 }}>{t('especies_pct_dificil', { n: aPorcentaje(c.puntaje_ano_dificil) })}</span> : null}
              {!c.apta ? <span style={{ fontSize: 13, fontWeight: 600 }}>{t('especies_todavia_no_apta')}</span> : null}
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
                  <span style={{ fontSize: 18, fontWeight: 800, lineHeight: 1.15 }}>{nombreDe(c)}</span>
                  {c.variedad_recomendada ? <span className="ps-nota">{t('especies_variedad_conviene', { variedad: textoVariedad(c.variedad_recomendada) })}</span> : null}
                  <span className="ps-detalle">
                    {textoCompatible(c)}
                    {!c.apta ? ` · ${t('especies_todavia_no_apta')}` : c.factor_limitante && porcentaje(c) < 100 ? ` · ${t('especies_lo_limita', { factor: nombreClave(c.factor_limitante).toLowerCase() })}` : ''}
                  </span>
                  <ChipClima c={c} />
                </span>
                {NIVELES_CON_SEGUIMIENTO.includes(c.nivel_madurez) ? <Chip tono="acento">{t('especies_con_seguimiento')}</Chip> : null}
                <IconoSiguiente stroke="var(--texto-tenue)" />
              </Link>
            </li>
          ))}
        </ol>
      ) : null}
      {ranking && vista === 'todas' && ranking.especies_aptas > aptas.length ? (
        <p className="ps-pad ps-nota" style={{ margin: '8px 0 0 0' }}>
          {t('especies_se_muestran', { n: aptas.length, total: ranking.especies_aptas })}
        </p>
      ) : null}
      </div>

      <Link to="/fuentes" className="ps-btn-texto" style={{ marginTop: 'auto', padding: '16px 20px 28px 20px', gap: 6, fontSize: 15, color: 'var(--texto-tenue)', textAlign: 'center' }}>
        <IconoInfo tamano={18} />
        {t('especies_footer')}
        {ranking ? ` · ${t('especies_rango_fechas', { desde: fechaCorta(ranking.datos_sitio.periodo_clima[0]), hasta: fechaCorta(ranking.datos_sitio.periodo_clima[1]) })}` : ''}
      </Link>
    </Screen>
  )
}
