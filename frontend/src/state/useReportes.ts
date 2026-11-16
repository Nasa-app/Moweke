import { useEffect, useState } from 'react'
import { reportesCultivo, type ReporteDeCampo } from '../lib/api'
import { claveDeFase, pendientesDe, sincronizarCola } from '../lib/colaReportes'

// Los reportes de campo de un cultivo: los que ya están en el servidor y los que siguen en la cola del teléfono
// (se intenta subirlos al abrir). Sirve igual con o sin seguimiento por etapa.
export function useReportes(idCultivo: number | null) {
  const [guardados, setGuardados] = useState<{ idCultivo: number; reportes: ReporteDeCampo[] } | null>(null)
  const [falla, setFalla] = useState(false)

  useEffect(() => {
    if (idCultivo === null) return
    let vigente = true
    sincronizarCola()
      .catch(() => undefined)
      .then(() => reportesCultivo(idCultivo))
      .then((r) => vigente && setGuardados({ idCultivo, reportes: r.reportes }))
      .catch(() => vigente && setFalla(true))
    return () => {
      vigente = false
    }
  }, [idCultivo])

  const delCultivo = guardados && guardados.idCultivo === idCultivo ? guardados.reportes : null
  const pendientes = idCultivo === null ? [] : pendientesDe(idCultivo).flatMap((r) => {
    const fase = claveDeFase(r.fase)
    return fase ? [{ fase, fecha: r.fecha }] : []
  })
  return { reportes: delCultivo, pendientes, cargando: idCultivo !== null && delCultivo === null && !falla, falla }
}
