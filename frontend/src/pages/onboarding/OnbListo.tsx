import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Screen, BarraSuperior } from '../../components/Screen'
import { StepDots } from '../../components/StepDots'
import { IconoCheck, IconoSiguiente } from '../../components/icons'
import { usePredio } from '../../state/PredioContext'
import { candidatasSiembra } from '../../lib/api'
import { nombreEspecie } from '../../lib/formato'
import { useI18n } from '../../i18n'

const CANALES = [
  { clave: 'app', etiqueta: 'App' },
  { clave: 'whatsapp', etiqueta: 'WhatsApp' },
  { clave: 'sms', etiqueta: 'SMS' },
]

export default function OnbListo() {
  const { t } = useI18n()
  const { idParcela } = usePredio()
  const [activos, setActivos] = useState<Set<string>>(new Set(['app', 'whatsapp']))
  const [mejores, setMejores] = useState<string[] | null>(null)
  const [reuniendo, setReuniendo] = useState(false)

  useEffect(() => {
    if (!idParcela) return
    let vigente = true
    candidatasSiembra(idParcela)
      .then((r) => vigente && setMejores(r.candidatas.filter((c) => c.apta).slice(0, 3).map((c) => nombreEspecie(c.especie, c))))
      .catch(() => vigente && setReuniendo(true))
    return () => {
      vigente = false
    }
  }, [idParcela])

  const resumen = !idParcela
    ? { a: '/terreno/perimetro', titulo: 'Falta marcar tu parcela', detalle: 'Sin ella no hay clima ni suelo que analizar' }
    : mejores
      ? { a: '/terreno', titulo: mejores.length ? 'Lo que mejor se da' : 'Ninguna especie resultó apta', detalle: mejores.join(' · ') || 'Revisa el detalle de tu terreno' }
      : reuniendo
        ? { a: '/terreno/preparando', titulo: 'Reuniendo los datos de tu parcela', detalle: 'Toca para ver el avance' }
        : { a: '/terreno', titulo: 'Analizando tu terreno…', detalle: 'Buscando qué se da bien en tu parcela' }

  function alternar(clave: string) {
    const copia = new Set(activos)
    if (copia.has(clave)) copia.delete(clave)
    else copia.add(clave)
    setActivos(copia)
  }

  return (
    <Screen>
      <BarraSuperior volverA="/onboarding/meta" derecha={<StepDots paso={4} total={4} />} />

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

      <fieldset className="ps-pad-16" style={{ marginTop: 24, border: 'none', paddingBlock: 0 }}>
        <legend style={{ padding: '0 4px', marginBottom: 8, fontSize: 20, fontWeight: 800 }}>{t('onb_avisos_titulo')}</legend>
        <div className="ps-grid-3">
          {CANALES.map((c) => (
            <label key={c.clave} className={`ps-pill ${activos.has(c.clave) ? 'activo' : ''}`} style={{ minHeight: 56 }}>
              <input type="checkbox" checked={activos.has(c.clave)} onChange={() => alternar(c.clave)} className="visually-hidden" />
              {c.etiqueta}
            </label>
          ))}
        </div>
      </fieldset>

      <div style={{ marginTop: 'auto', padding: '20px 16px 32px 16px', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <Link to="/terreno" className="ps-btn">
          {t('onb_ver_que_sembrar')}
        </Link>
        <Link to="/hoy" className="ps-btn-texto">
          {t('onb_ir_a_hoy')}
        </Link>
      </div>
    </Screen>
  )
}
