import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { IconoMas } from './icons'
import { listarParcelas, type ParcelaResumen } from '../lib/api'
import { numero } from '../lib/formato'
import { usePredio } from '../state/PredioContext'
import { useI18n } from '../i18n'

// Elige con qué parcela se trabaja y deja marcar otra. Las parcelas van en una fila que se desliza; "Agregar" queda
// fijo a su derecha, siempre a la vista aunque haya muchas parcelas. La parcela activa es la que miran Hoy, Cultivos,
// Tu terreno y Qué sembrar.
export function SelectorParcelas() {
  const { t } = useI18n()
  const { idParcela, setParcelaActiva, setCultivoActivo } = usePredio()
  const [parcelas, setParcelas] = useState<ParcelaResumen[]>([])

  useEffect(() => {
    let vigente = true
    listarParcelas()
      .then((r) => vigente && setParcelas(r.parcelas))
      .catch(() => vigente && setParcelas([]))
    return () => {
      vigente = false
    }
  }, [])

  if (parcelas.length === 0) return null   // cargando, o sin parcelas (Terreno ya lleva a marcar la primera)

  function elegir(id: number) {
    if (id === idParcela) return
    setParcelaActiva(id)
    setCultivoActivo(null)
  }

  return (
    <div className="ps-pad-16" style={{ marginTop: 12, display: 'flex', alignItems: 'flex-start', gap: 8 }}>
    <div role="radiogroup" aria-label={t('selector_parcela_aria')} style={{ flex: 1, minWidth: 0, display: 'flex', gap: 6, overflowX: 'auto', paddingBottom: 4 }}>
      {parcelas.map((p, i) => {
        const activa = p.id === idParcela
        return (
          <button
            key={p.id}
            type="button"
            role="radio"
            aria-checked={activa}
            onClick={() => elegir(p.id)}
            className={`ps-pill ${activa ? 'activo' : ''}`}
            style={{ padding: '0 16px', minHeight: 44, flexShrink: 0, whiteSpace: 'nowrap' }}
          >
            {t('selector_parcela_n', { n: i + 1, ha: numero(p.hectareas, 2) })}
          </button>
        )
      })}
    </div>
      <Link
        to="/terreno/perimetro"
        aria-label={t('selector_parcela_agregar_aria')}
        className="ps-pill"
        style={{ flex: 'none', minHeight: 44, padding: '0 14px', gap: 6, textDecoration: 'none', background: 'transparent', border: '2px dashed var(--borde-control)', boxSizing: 'border-box', color: 'var(--verde)', fontWeight: 800 }}
      >
        <IconoMas tamano={18} />
        {t('selector_parcela_agregar')}
      </Link>
    </div>
  )
}
