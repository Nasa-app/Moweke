import { fechaCorta, nombreEspecie } from '../lib/formato'
import type { Cultivo } from '../lib/api'

// Elige qué cultivo se mira cuando hay más de uno. Con uno solo no hay nada que elegir y no se muestra.
// Si la misma especie está sembrada en dos fechas, la fecha las distingue.
export function SelectorCultivos({ cultivos, activo, onElegir }: {
  cultivos: Cultivo[] | null
  activo: Cultivo | null
  onElegir: (id: number, especie: string) => void
}) {
  if (!cultivos || cultivos.length < 2) return null
  const repetida = (c: Cultivo) => cultivos.filter((o) => o.especie === c.especie).length > 1
  return (
    <div role="radiogroup" aria-label="Cultivo" className="ps-pad-16" style={{ marginTop: 14, display: 'flex', gap: 6, overflowX: 'auto', paddingBottom: 4 }}>
      {cultivos.map((c) => {
        const elegido = activo?.id === c.id
        return (
          <button
            key={c.id}
            type="button"
            role="radio"
            aria-checked={elegido}
            onClick={() => onElegir(c.id, c.especie)}
            className={`ps-pill ${elegido ? 'activo' : ''}`}
            style={{ padding: '0 16px', minHeight: 44, flexShrink: 0, whiteSpace: 'nowrap' }}
          >
            {nombreEspecie(c.especie)}{repetida(c) ? ` · ${fechaCorta(c.fecha_siembra)}` : ''}
          </button>
        )
      })}
    </div>
  )
}
