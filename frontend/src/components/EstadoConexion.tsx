import { useEffect, useState } from 'react'
import { useConexion, useDatoViejo } from '../lib/frescura'
import { edadDelDato } from '../lib/formato'
import { useI18n } from '../i18n'

// Avisa cuando lo que se ve no es lo más reciente: sin conexión, o con conexión pero sin poder actualizar. Va sobre el
// menú inferior y se anuncia a los lectores de pantalla.
export function EstadoConexion() {
  const { t } = useI18n()
  const hayRed = useConexion()
  const desde = useDatoViejo()
  const [ahora, setAhora] = useState(() => Date.now())

  useEffect(() => {
    if (desde === null) return
    const reloj = setInterval(() => setAhora(Date.now()), 60_000)
    return () => clearInterval(reloj)
  }, [desde])

  const texto = !hayRed ? t('conexion_sin_red') : desde !== null ? t('conexion_dato_viejo', { edad: edadDelDato(desde, ahora) }) : null
  if (!texto) return null
  return (
    <div role="status" aria-live="polite" className="ps-aviso-conexion">
      {texto}
      {!hayRed && desde !== null ? ` ${t('conexion_dato_viejo', { edad: edadDelDato(desde, ahora) })}` : ''}
    </div>
  )
}
