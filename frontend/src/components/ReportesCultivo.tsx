import { useReportes } from '../state/useReportes'
import { fechaCorta } from '../lib/formato'
import { useI18n } from '../i18n'

// Lo que el agricultor ha reportado de este cultivo (la etapa en que lo ve), del más reciente al más antiguo. Lo que
// aún no llegó al servidor se marca "Por enviar". Está en el registro del cultivo, con o sin seguimiento por etapa.
export function ReportesCultivo({ idCultivo, calendarioAproximado = false }: { idCultivo: number; calendarioAproximado?: boolean }) {
  const { t } = useI18n()
  const { reportes, pendientes, cargando, falla } = useReportes(idCultivo)
  const filas = [
    ...pendientes.map((r) => ({ ...r, porEnviar: true })),
    ...(reportes ?? []).map((r) => ({ ...r, porEnviar: false })),
  ].sort((a, b) => b.fecha.localeCompare(a.fecha) || Number(b.porEnviar) - Number(a.porEnviar))

  return (
    <section aria-labelledby="reportes-cultivo" className="ps-pad-16" style={{ marginTop: 14 }}>
      <h2 id="reportes-cultivo" className="ps-h2" style={{ margin: '0 4px' }}>{t('reportes_titulo')}</h2>
      <div className="ps-card" style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 6 }}>
        {cargando ? <span className="ps-nota">{t('cargando')}</span> : null}
        {falla && !filas.length ? <span className="ps-nota">{t('reportes_error')}</span> : null}
        {!cargando && !falla && !filas.length ? <span className="ps-nota">{t('reportes_vacio')}</span> : null}
        {filas.length ? (
          <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 6 }}>
            {filas.map((r) => (
              <li key={`${r.fase}-${r.fecha}-${r.porEnviar}`} style={{ display: 'flex', alignItems: 'center', gap: 8, minHeight: 36 }}>
                <span style={{ flex: 1, fontSize: 16, fontWeight: 800 }}>{t(`reportar_fase_${r.fase}`)}</span>
                {r.porEnviar ? <span className="ps-chip ps-chip-precaucion">{t('reportes_por_enviar')}</span> : null}
                <span className="ps-detalle">{fechaCorta(r.fecha)}</span>
              </li>
            ))}
          </ul>
        ) : null}
        <span className="ps-nota">{t(calendarioAproximado ? 'reportes_nota_aprox' : 'reportes_nota')}</span>
      </div>
    </section>
  )
}
