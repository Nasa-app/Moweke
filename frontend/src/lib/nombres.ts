import type { Idioma } from '../i18n/dictionary'

// Nombres de especies y variedades por idioma, tal como los entrega /api/especies/nombres.
// Vive fuera de React para que lib/formato.ts los lea sin hooks; I18nProvider lo llena y
// vuelve a pintar la interfaz cuando llega el catálogo o cambia el idioma.
export interface NombresCatalogo {
  especies: Record<string, { es: string | null; en: string | null }>
  variedades: { especie: string; clave: string; es: string; en: string }[]
}

let idiomaActivo: Idioma = 'es'
let catalogo: NombresCatalogo = { especies: {}, variedades: [] }

export function fijarIdiomaNombres(idioma: Idioma): void {
  idiomaActivo = idioma
}

export function fijarCatalogoNombres(nuevo: NombresCatalogo): void {
  catalogo = nuevo
}

export function idiomaDeNombres(): Idioma {
  return idiomaActivo
}

export function nombreCatalogado(especie: string): string | null {
  return catalogo.especies[especie]?.[idiomaActivo] ?? null
}

// El nombre del idioma activo si `valor` es una variedad conocida (por clave o por cualquiera de
// sus dos nombres); si no, el texto tal como lo escribió el agricultor.
export function nombreVariedad(especie: string, valor: string): string {
  const v = valor.trim().toLowerCase()
  const conocida = catalogo.variedades.find(
    (c) => c.especie === especie && (c.clave === v || c.es.toLowerCase() === v || c.en.toLowerCase() === v),
  )
  return conocida ? conocida[idiomaActivo] : valor
}

export function variedadesConocidas(especie: string): { clave: string; nombre: string }[] {
  return catalogo.variedades.filter((c) => c.especie === especie).map((c) => ({ clave: c.clave, nombre: c[idiomaActivo] }))
}

// La clave a guardar para lo que escribió el agricultor: la de la variedad conocida si coincide, o el texto.
export function claveVariedad(especie: string, escrito: string): string {
  const v = escrito.trim().toLowerCase()
  const conocida = catalogo.variedades.find(
    (c) => c.especie === especie && (c.clave === v || c.es.toLowerCase() === v || c.en.toLowerCase() === v),
  )
  return conocida ? conocida.clave : escrito.trim()
}
