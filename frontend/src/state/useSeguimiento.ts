import { useEffect, useState } from 'react'
import { fenologiaCultivo, listarCultivos, mensajeDeError, type Cultivo, type Fenologia } from '../lib/api'
import { usePredio } from './PredioContext'

// Los cultivos de la parcela activa y el seguimiento por etapa del cultivo activo, para
// las pantallas que hablan del mismo cultivo (Hoy, Cultivos, Alertas). `aviso` trae el
// motivo cuando no hay seguimiento: especie sin perfil fenológico o clima todavía sin llegar.
export function useSeguimiento() {
  const { idParcela, idCultivoActivo, setCultivoActivo } = usePredio()
  const [cultivos, setCultivos] = useState<Cultivo[] | null>(null)
  const [seguimiento, setSeguimiento] = useState<{ idCultivo: number; fenologia: Fenologia | null; aviso: string | null } | null>(null)

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
      .then((fenologia) => vigente && setSeguimiento({ idCultivo: idCultivoActivo, fenologia, aviso: null }))
      .catch((err) => {
        if (vigente) {
          setSeguimiento({ idCultivo: idCultivoActivo, fenologia: null, aviso: mensajeDeError(err, 'No se pudo cargar el seguimiento.') })
        }
      })
    return () => {
      vigente = false
    }
  }, [idCultivoActivo])

  const activo = cultivos?.find((c) => c.id === idCultivoActivo) ?? null
  const delActivo = seguimiento && seguimiento.idCultivo === idCultivoActivo ? seguimiento : null
  return {
    idParcela,
    cultivos,
    activo,
    fenologia: delActivo?.fenologia ?? null,
    aviso: delActivo?.aviso ?? null,
    cargando: (idParcela !== null && cultivos === null) || (activo !== null && delActivo === null),
    setCultivoActivo,
  }
}
