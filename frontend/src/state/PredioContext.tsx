import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { guardar, leer } from './storage'

// Guarda qué predio y qué cultivo está mirando el agricultor ahora, para que cada
// pantalla (Hoy, Cultivo, Terreno, Reportar...) sepa de qué predio hablar sin tener que
// volver a pedirlo. Las páginas piden los datos reales (predio, cultivos, fenología) por
// su cuenta con lib/api.ts a partir de estos ids.
interface PredioContextValor {
  idParcela: number | null
  idCultivoActivo: number | null
  especieActiva: string | null
  setParcelaActiva: (id: number | null) => void
  setCultivoActivo: (id: number | null, especie?: string | null) => void
}

const PredioContext = createContext<PredioContextValor | null>(null)

export function PredioProvider({ children }: { children: ReactNode }) {
  const [idParcela, setIdParcela] = useState<number | null>(() => leer('id_parcela', null))
  const [idCultivoActivo, setIdCultivoActivo] = useState<number | null>(() => leer('id_cultivo_activo', null))
  const [especieActiva, setEspecieActiva] = useState<string | null>(() => leer('especie_activa', null))

  const setParcelaActiva = useCallback((id: number | null) => {
    setIdParcela(id)
    guardar('id_parcela', id)
  }, [])

  const setCultivoActivo = useCallback((id: number | null, especie: string | null = null) => {
    setIdCultivoActivo(id)
    guardar('id_cultivo_activo', id)
    setEspecieActiva(especie)
    guardar('especie_activa', especie)
  }, [])

  const valor = useMemo(
    () => ({ idParcela, idCultivoActivo, especieActiva, setParcelaActiva, setCultivoActivo }),
    [idParcela, idCultivoActivo, especieActiva, setParcelaActiva, setCultivoActivo],
  )

  return <PredioContext.Provider value={valor}>{children}</PredioContext.Provider>
}

export function usePredio(): PredioContextValor {
  const ctx = useContext(PredioContext)
  if (!ctx) throw new Error('usePredio debe usarse dentro de PredioProvider')
  return ctx
}
