import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Screen } from '../components/Screen'
import { CompatRing } from '../components/CompatRing'
import { usePredio } from '../state/PredioContext'
import { CATEGORIAS_COMIDA, candidatasSiembra, listarCultivos, type Cultivo } from '../lib/api'
import { aPorcentaje, nombreClave, nombreEspecie } from '../lib/formato'
import { useI18n } from '../i18n'

export default function Rotacion() {
  const { t } = useI18n()
  const { idParcela } = usePredio()
  const [especiesTerreno, setEspeciesTerreno] = useState<{ especie: string; nombre: string; compatibilidad: number; motivo: string }[]>([])
  const [elegido, setElegido] = useState<string | null>(null)
  const [siembras, setSiembras] = useState<Cultivo[]>([])
  const [aviso, setAviso] = useState<string | null>(idParcela ? 'Buscando qué se da bien en tu parcela…' : 'Marca tu parcela para ver qué conviene sembrar.')

  // Las cuatro especies de comida más compatibles con la parcela, del ranking real.
  useEffect(() => {
    if (!idParcela) return
    let vigente = true
    candidatasSiembra(idParcela, { categorias: CATEGORIAS_COMIDA, limite: 4 })
      .then((r) => {
        if (!vigente) return
        const mejores = r.candidatas
          .filter((c) => c.apta)
          .slice(0, 4)
          .map((c) => ({
            especie: c.especie,
            nombre: nombreEspecie(c.especie, c),
            compatibilidad: aPorcentaje(c.puntaje),
            motivo: c.factor_limitante && aPorcentaje(c.puntaje) < 100 ? `Lo limita: ${nombreClave(c.factor_limitante).toLowerCase()}` : 'Sin problemas',
          }))
        setEspeciesTerreno(mejores)
        setElegido(mejores[0]?.especie ?? null)
        setAviso(mejores.length ? null : 'Ninguna especie de comida resultó apta para tu parcela.')
      })
      .catch(() => vigente && setAviso('Todavía se está reuniendo el clima de tu parcela.'))
    return () => {
      vigente = false
    }
  }, [idParcela])

  // Lo que el agricultor ya declaró sembrar, de la más antigua a la más reciente (las últimas tres).
  useEffect(() => {
    if (!idParcela) return
    let vigente = true
    listarCultivos(idParcela)
      .then((r) => vigente && setSiembras([...r.cultivos].sort((a, b) => a.fecha_siembra.localeCompare(b.fecha_siembra)).slice(-3)))
      .catch(() => vigente && setSiembras([]))
    return () => {
      vigente = false
    }
  }, [idParcela])

  const nombreElegido = especiesTerreno.find((e) => e.especie === elegido)?.nombre

  return (
    <Screen>
      <div style={{ padding: '48px 20px 0 20px', display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12 }}>
        <h1 style={{ margin: 0, fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 30, lineHeight: 1 }}>{t('planificar_titulo')}</h1>
        <span className="ps-contexto">Según tu parcela</span>
      </div>

      <fieldset className="ps-pad-16" style={{ marginTop: 16, border: 'none', paddingBlock: 0 }}>
        <legend style={{ padding: '0 4px', marginBottom: 10, fontWeight: 800, fontSize: 20 }}>{t('planificar_que_sembrar')}</legend>
        <div className="ps-grid-2">
          {especiesTerreno.map((e, i) => {
            const activo = elegido === e.especie
            return (
              <label
                key={e.especie}
                style={{ position: 'relative', borderRadius: 20, background: 'var(--blanco)', boxShadow: activo ? '0 0 0 3px var(--verde)' : 'var(--sombra-1)', cursor: 'pointer', display: 'flex', flexDirection: 'column', padding: '12px 10px' }}
              >
                <input type="radio" name="cultivo" checked={activo} onChange={() => setElegido(e.especie)} className="visually-hidden" />
                {i === 0 ? (
                  <span style={{ position: 'absolute', left: 8, top: 8, fontSize: 13, fontWeight: 800, padding: '3px 8px', borderRadius: 10, background: 'var(--verde)', color: '#fff' }}>Mejor</span>
                ) : null}
                <span style={{ fontSize: 18, fontWeight: 800, marginTop: i === 0 ? 18 : 0 }}>{e.nombre}</span>
                <span role="img" aria-label={`${e.compatibilidad}% compatible con tu terreno. ${e.motivo}.`} style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
                  <CompatRing porcentaje={e.compatibilidad} />
                  <span style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.1 }}>
                    <b style={{ fontSize: 18, fontWeight: 800 }}>{e.compatibilidad}%</b>
                    <span className="ps-detalle">{e.motivo}</span>
                  </span>
                </span>
              </label>
            )
          })}
          <Link
            to="/especies"
            style={{ borderRadius: 20, border: '3px dashed var(--borde-control)', background: 'transparent', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 6, minHeight: 170, font: "800 18px 'Alegreya Sans', sans-serif", color: 'var(--carbon)', textDecoration: 'none' }}
          >
            Otro
          </Link>
        </div>
        {aviso ? <p className="ps-nota">{aviso}</p> : null}
      </fieldset>

      {siembras.length ? (
        <section className="ps-pad-16" style={{ margin: '12px 16px 0 16px', background: 'var(--menta)', color: 'var(--carbon)', borderRadius: 22, padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
          <h2 className="ps-h2">{t('planificar_lo_sembrado')}</h2>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-around' }}>
            {siembras.map((c, i) => (
              <span key={c.id} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                  <span style={{ width: 48, height: 48, borderRadius: 24, background: 'var(--blanco)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, fontWeight: 800 }}>
                    {nombreEspecie(c.especie)[0]}
                  </span>
                  <span className="ps-detalle">{nombreEspecie(c.especie)}</span>
                  <span className="ps-nota">{c.fecha_siembra.slice(0, 4)}</span>
                </span>
                {i < siembras.length - 1 ? <span aria-hidden="true" style={{ color: 'var(--texto-tenue)' }}>→</span> : null}
              </span>
            ))}
          </div>
        </section>
      ) : null}

      <div className="ps-pad-16" style={{ margin: '10px 16px 12px 16px', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <Link to={elegido ? `/especies/analisis?especie=${encodeURIComponent(elegido)}` : '/especies'} className="ps-btn">
          {nombreElegido ? `${t('planificar_ver')} ${nombreElegido}` : t('planificar_que_sembrar')}
        </Link>
        <div className="ps-grid-2">
          <Link to="/especies" className="ps-card" style={{ textDecoration: 'none', color: 'var(--carbon)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, fontSize: 16, fontWeight: 800, minHeight: 48 }}>
            {t('planificar_especies')}
          </Link>
          <Link to="/historial" className="ps-card" style={{ textDecoration: 'none', color: 'var(--carbon)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, fontSize: 16, fontWeight: 800, minHeight: 48 }}>
            {t('planificar_historial')}
          </Link>
        </div>
      </div>
    </Screen>
  )
}
