import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { traducir, type Idioma } from './dictionary'
import { guardar, leer } from '../state/storage'
import { nombresEspecies } from '../lib/api'
import { fijarCatalogoNombres, fijarIdiomaNombres } from '../lib/nombres'

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

  // Nombres de especies y variedades por idioma: sin ellos se muestra el nombre de la clave.
  const [nombresListos, setNombresListos] = useState(false)
  useEffect(() => {
    let vigente = true
    nombresEspecies()
      .then((c) => {
        fijarCatalogoNombres(c)
        if (vigente) setNombresListos(true)
      })
      .catch(() => {})
    return () => {
      vigente = false
    }
  }, [])
  fijarIdiomaNombres(idioma)

  const t = useCallback((clave: string) => traducir(idioma, clave), [idioma])

  // nombresListos fuerza un valor nuevo cuando llega el catálogo, para que se repinten los nombres.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const valor = useMemo(() => ({ idioma, cambiarIdioma, t }), [idioma, cambiarIdioma, t, nombresListos])

  return <I18nContext.Provider value={valor}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nContextValor {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error('useI18n debe usarse dentro de I18nProvider')
  return ctx
}
