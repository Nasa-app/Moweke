import { useEffect, useState } from 'react'
import type { Punto } from './geometria'
import { zonas, type ZonaComuna } from './api'
import { guardar, leer } from '../state/storage'
import { tr } from '../i18n/dictionary'

// Las comunas de Chiloé y dónde abrir el mapa para marcar la parcela vienen del API (GET /api/zonas): el punto es el
// pueblo cabecera de cada comuna, no un deslinde, y sirve para que el mapa abra cerca. La última lista recibida
// queda en el dispositivo para abrir sin esperar.
export const COMUNA_POR_DEFECTO = 'Quemchi'
// Con este zoom se ve el pueblo y sus alrededores; para marcar esquinas hay que acercarse más (Mapa.tsx).
export const ZOOM_COMUNA = 13

const CLAVE_ZONAS = 'zonas_lista'

export function comunasGuardadas(): ZonaComuna[] {
  return leer<ZonaComuna[]>(CLAVE_ZONAS, [])
}

// `pedir` en false usa solo la lista guardada y no consulta el API (quien ya tiene dónde abrir el mapa no la necesita).
export function useComunas(pedir = true): { comunas: ZonaComuna[]; cargando: boolean } {
  const [comunas, setComunas] = useState<ZonaComuna[]>(comunasGuardadas)
  const [cargando, setCargando] = useState(pedir)
  useEffect(() => {
    if (!pedir) return
    let vigente = true
    zonas()
      .then((lista) => {
        if (!vigente) return
        guardar(CLAVE_ZONAS, lista)
        setComunas(lista)
      })
      .catch(() => undefined)
      .finally(() => vigente && setCargando(false))
    return () => {
      vigente = false
    }
  }, [pedir])
  return { comunas, cargando }
}

export function centroDeComuna(comunas: ZonaComuna[], nombre: string): Punto | null {
  const zona = comunas.find((c) => c.nombre === nombre)
  return zona ? [zona.lat, zona.lon] : null
}

export const TERRENOS = ['Plano', 'Ladera', 'Alto'] as const

// El valor guardado de TERRENOS se muestra con este nombre en el idioma vigente.
export function nombreTerreno(terreno: (typeof TERRENOS)[number]): string {
  return tr(`comunas_terreno_${terreno.toLowerCase()}`)
}

// Lo que la persona va respondiendo mientras arma su parcela. Queda en este dispositivo: el servidor todavía
// no guarda comuna, sector ni terreno.
export interface BorradorPredio {
  comuna: string
  sector: string
  terreno: (typeof TERRENOS)[number] | ''
  acepto: boolean
}

const CLAVE_BORRADOR = 'onboarding_predio'

export function leerBorrador(): BorradorPredio {
  const guardado = leer<Partial<BorradorPredio>>(CLAVE_BORRADOR, {})
  return {
    comuna: typeof guardado.comuna === 'string' && guardado.comuna ? guardado.comuna : COMUNA_POR_DEFECTO,
    sector: typeof guardado.sector === 'string' ? guardado.sector : '',
    terreno: TERRENOS.find((t) => t === guardado.terreno) ?? '',
    acepto: guardado.acepto === true,
  }
}

// La comuna de cada parcela, anotada al marcarla en el registro (cuando la persona acaba de elegirla). Las
// parcelas marcadas de otra forma, o antes de este registro, quedan sin comuna: no se adivina.
export function guardarComunaDeParcela(idParcela: number, comuna: string): void {
  guardar('comunas_parcelas', { ...leer<Record<string, string>>('comunas_parcelas', {}), [String(idParcela)]: comuna })
}

export function comunaDeParcela(idParcela: number | null): string | null {
  if (idParcela === null) return null
  const comuna = leer<Record<string, string>>('comunas_parcelas', {})[String(idParcela)]
  return comuna || null
}

export function guardarBorrador(cambios: Partial<BorradorPredio>): void {
  guardar(CLAVE_BORRADOR, { ...leerBorrador(), ...cambios })
}
