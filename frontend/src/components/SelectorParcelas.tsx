import { useEffect, useState } from 'react'
import { listarParcelas, type ParcelaResumen } from '../lib/api'
import { numero } from '../lib/formato'
import { usePredio } from '../state/PredioContext'
import { useI18n } from '../i18n'

// Elige con qué parcela se trabaja. Solo aparece si hay más de una: con una sola no hay nada que elegir.
// La parcela activa es la que miran Hoy, Cultivos, Tu terreno y Qué sembrar.
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

  if (parcelas.length < 2) return null

  function elegir(id: number) {
    if (id === idParcela) return
    setParcelaActiva(id)
    setCultivoActivo(null)
  }

  return (
    <div role="radiogroup" aria-label={t('selector_parcela_aria')} className="ps-pad-16" style={{ marginTop: 12, display: 'flex', gap: 6, overflowX: 'auto', paddingBottom: 4 }}>
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
  )
}
