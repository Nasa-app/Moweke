import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { traducir, type Idioma } from './dictionary'
import { guardar, leer } from '../state/storage'

interface I18nContextValor {
  idioma: Idioma
  cambiarIdioma: (idioma: Idioma) => void
  t: (clave: string) => string
}

const I18nContext = createContext<I18nContextValor | null>(null)

export function I18nProvider({ children }: { children: ReactNode }) {
  const [idioma, setIdioma] = useState<Idioma>(() => leer('idioma', 'es'))

  const cambiarIdioma = useCallback((nuevo: Idioma) => {
    setIdioma(nuevo)
    guardar('idioma', nuevo)
  }, [])

  const t = useCallback((clave: string) => traducir(idioma, clave), [idioma])

  const valor = useMemo(() => ({ idioma, cambiarIdioma, t }), [idioma, cambiarIdioma, t])

  return <I18nContext.Provider value={valor}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nContextValor {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error('useI18n debe usarse dentro de I18nProvider')
  return ctx
}
