import { Link } from 'react-router-dom'
import { Screen, BarraSuperior, Titulo } from '../components/Screen'
import { IconoUbicacion } from '../components/icons'
import { CLASE_ORIGEN, FUENTES, type Origen } from '../lib/fuentes'
import { useI18n } from '../i18n'

const CLAVE_ORIGEN: Record<Origen, string> = {
  NASA: 'origen_nasa',
  Copernicus: 'origen_copernicus',
  Chile: 'origen_chile',
  'Otras fuentes': 'origen_otras',
  Comunidad: 'origen_comunidad',
}

export default function Fuentes() {
  const { t } = useI18n()
  return (
    <Screen>
      <BarraSuperior volverA="/cultivo" />
      <Titulo>{t('fuentes_titulo')}</Titulo>

      <div className="ps-pad-16" style={{ marginTop: 18, display: 'flex', flexDirection: 'column', gap: 12 }}>
        {FUENTES.map((f) => (
          <article key={f.titulo} className="ps-card" style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {f.origenes.map((o) => (
                <span key={o} className={`ps-chip ${CLASE_ORIGEN[o]}`}>{t(CLAVE_ORIGEN[o])}</span>
              ))}
            </span>
            <h2 style={{ margin: 0, fontWeight: 800, fontSize: 20 }}>{f.titulo}</h2>
            <span style={{ fontSize: 16, fontWeight: 700 }}>{f.detalle}</span>
            <span className="ps-nota">{f.nota}</span>
          </article>
        ))}
        <article className="ps-card" style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <h2 style={{ margin: 0, fontWeight: 800, fontSize: 20 }}>{t('fuentes_tus_parcelas')}</h2>
          <span style={{ fontSize: 16, fontWeight: 700 }}>{t('fuentes_lo_que_marcas')}</span>
          <span className="ps-nota">{t('fuentes_se_guarda')}</span>
        </article>
      </div>

      <section className="ps-pad-16" style={{ marginTop: 20, background: 'var(--menta)', color: 'var(--carbon)', borderRadius: 22, padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
        <h2 className="ps-h2">{t('fuentes_que_tan_seguro')}</h2>
        <div role="img" aria-label={t('fuentes_confianza_aria')} style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 6 }}>
          {[1, 1, 1, 0].map((activo, i) => (
            <span key={i} style={{ height: 12, borderRadius: 6, background: activo ? 'var(--verde)' : '#fff' }} />
          ))}
        </div>
        <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--verde)' }}>{t('fuentes_basado_comuna')}</span>
        <span className="ps-nota">{t('fuentes_sube_a_4')}</span>
      </section>

      <Link to="/terreno/perimetro" className="ps-pad-16 ps-btn-secundario" style={{ margin: '16px 16px 32px 16px', gap: 8, textDecoration: 'none' }}>
        <IconoUbicacion />
        {t('fuentes_mas_precision')}
      </Link>
    </Screen>
  )
}
