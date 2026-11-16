import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Screen, BarraSuperior } from '../../components/Screen'
import { StepDots } from '../../components/StepDots'
import { IconoCheck, IconoSiguiente } from '../../components/icons'
import { usePredio } from '../../state/PredioContext'
import { CATEGORIAS_COMIDA, candidatasSiembra, listarCultivos, type Cultivo } from '../../lib/api'
import { fechaCorta, nombreEspecie } from '../../lib/formato'
import { useI18n } from '../../i18n'

type Candidata = Awaited<ReturnType<typeof candidatasSiembra>>['candidatas'][number]

export default function OnbListo() {
  const { t } = useI18n()
  const { idParcela } = usePredio()
  const [aptas, setAptas] = useState<Candidata[] | null>(null)
  const [reuniendo, setReuniendo] = useState(false)
  const [cultivos, setCultivos] = useState<Cultivo[]>([])

  useEffect(() => {
    if (!idParcela) return
    let vigente = true
    candidatasSiembra(idParcela, { categorias: CATEGORIAS_COMIDA, limite: 3 })
      .then((r) => vigente && setAptas(r.candidatas.filter((c) => c.apta).slice(0, 3)))
      .catch(() => vigente && setReuniendo(true))
    return () => {
      vigente = false
    }
  }, [idParcela])

  // Lo que se acaba de registrar, para que se vea que quedó anotado: cada cultivo lleva a su seguimiento.
  useEffect(() => {
    if (!idParcela) return
    let vigente = true
    listarCultivos(idParcela)
      .then((r) => vigente && setCultivos(r.cultivos))
      .catch(() => vigente && setCultivos([]))
    return () => {
      vigente = false
    }
  }, [idParcela])

  // El nombre se arma al pintar, para que siga el idioma elegido.
  const mejores = aptas ? aptas.map((c) => nombreEspecie(c.especie, c)) : null
  const resumen = !idParcela
    ? { a: '/terreno/perimetro', titulo: t('onb_listo_falta_titulo'), detalle: t('onb_listo_falta_detalle') }
    : mejores
      ? { a: '/terreno', titulo: mejores.length ? t('onb_listo_mejor_titulo') : t('onb_listo_ninguna_titulo'), detalle: mejores.join(' · ') || t('onb_listo_ninguna_detalle') }
      : reuniendo
        ? { a: '/terreno/preparando', titulo: t('onb_listo_reuniendo_titulo'), detalle: t('onb_listo_reuniendo_detalle') }
        : { a: '/terreno', titulo: t('onb_listo_analizando_titulo'), detalle: t('onb_listo_analizando_detalle') }

  return (
    <Screen>
      <BarraSuperior volverA="/onboarding/meta" derecha={<StepDots paso={3} total={3} />} />

      <div style={{ margin: '24px 20px 0 20px', display: 'flex', alignItems: 'center', gap: 12 }}>
        <span aria-hidden="true" style={{ width: 52, height: 52, borderRadius: 26, background: 'var(--verde)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          <IconoCheck tamano={28} stroke="#fff" />
        </span>
        <h1 style={{ margin: 0, fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 30, lineHeight: 1.05 }}>{t('onb_listo_titulo')}</h1>
      </div>

      <Link
        to={resumen.a}
        className="ps-card"
        style={{ margin: '18px 16px 0 16px', textDecoration: 'none', color: 'var(--carbon)', display: 'flex', alignItems: 'center', gap: 10 }}
      >
        <span style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <span className="ps-contexto">{t('terreno_titulo')}</span>
          <span style={{ fontSize: 21, fontWeight: 800, lineHeight: 1.1 }}>{resumen.titulo}</span>
          <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--verde)' }}>{resumen.detalle}</span>
        </span>
        <IconoSiguiente />
      </Link>

      {cultivos.length ? (
        <section aria-labelledby="cultivos-registrados" className="ps-pad-16" style={{ margin: '14px 16px 0 16px' }}>
          <h2 id="cultivos-registrados" className="ps-h2" style={{ margin: '0 4px' }}>{t('onb_listo_cultivos')}</h2>
          <Link to="/cultivo" className="ps-card" style={{ marginTop: 8, textDecoration: 'none', color: 'var(--carbon)', display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
              {cultivos.map((c) => (
                <span key={c.id} style={{ fontSize: 17, fontWeight: 800 }}>
                  {nombreEspecie(c.especie)} <span className="ps-detalle">· {t('registro_sembrado', { fecha: fechaCorta(c.fecha_siembra) })}</span>
                </span>
              ))}
              <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--verde)' }}>{t('onb_listo_ver_seguimiento')}</span>
            </span>
            <IconoSiguiente />
          </Link>
        </section>
      ) : null}

      <div style={{ marginTop: 'auto', padding: '20px 16px 32px 16px', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <Link to="/especies" className="ps-btn">
          {t('onb_ver_que_sembrar')}
        </Link>
        <Link to="/hoy" className="ps-btn-texto">
          {t('onb_ir_a_hoy')}
        </Link>
      </div>
    </Screen>
  )
}
