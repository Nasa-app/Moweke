import { useCallback, useEffect, useState } from 'react'
import { fenologiaCultivo, listarCultivos, mensajeDeError, type Cultivo, type Fenologia } from '../lib/api'
import { usePredio } from './PredioContext'
import { tr } from '../i18n/dictionary'

// Los cultivos de la parcela activa y el seguimiento por etapa del cultivo activo, para
// las pantallas que hablan del mismo cultivo (Hoy, Cultivos, Alertas). `aviso` trae el
// motivo cuando no hay seguimiento: especie sin perfil fenológico o clima todavía sin llegar.
export function useSeguimiento() {
  const { idParcela, idCultivoActivo, setCultivoActivo } = usePredio()
  const [cultivos, setCultivos] = useState<Cultivo[] | null>(null)
  const [seguimiento, setSeguimiento] = useState<{ idCultivo: number; fenologia: Fenologia | null; error: unknown } | null>(null)
  // Subir este número vuelve a pedir el seguimiento (por ejemplo, tras anotar un riego); mientras
  // llega lo nuevo se sigue mostrando lo anterior.
  const [version, setVersion] = useState(0)
  const recargar = useCallback(() => setVersion((v) => v + 1), [])

  useEffect(() => {
    if (!idParcela) return
    let vigente = true
    listarCultivos(idParcela)
      .then((r) => {
        if (!vigente) return
        setCultivos(r.cultivos)
        if (!r.cultivos.some((c) => c.id === idCultivoActivo)) {
          const primero = r.cultivos[0]
          setCultivoActivo(primero ? primero.id : null, primero ? primero.especie : null)
        }
      })
      .catch(() => vigente && setCultivos([]))
    return () => {
      vigente = false
    }
  }, [idParcela, idCultivoActivo, setCultivoActivo])

  useEffect(() => {
    if (!idCultivoActivo) return
    let vigente = true
    fenologiaCultivo(idCultivoActivo)
      .then((fenologia) => vigente && setSeguimiento({ idCultivo: idCultivoActivo, fenologia, error: null }))
      .catch((err) => {
        if (vigente) {
          setSeguimiento({ idCultivo: idCultivoActivo, fenologia: null, error: err })
        }
      })
    return () => {
      vigente = false
    }
  }, [idCultivoActivo, version])

  const activo = cultivos?.find((c) => c.id === idCultivoActivo) ?? null
  const delActivo = seguimiento && seguimiento.idCultivo === idCultivoActivo ? seguimiento : null
  return {
    idParcela,
    cultivos,
    activo,
    fenologia: delActivo?.fenologia ?? null,
    aviso: delActivo?.error ? mensajeDeError(delActivo.error, tr('seguimiento_error')) : null,
    cargando: (idParcela !== null && cultivos === null) || (activo !== null && delActivo === null),
    setCultivoActivo,
    recargar,
  }
}
