import { Link } from 'react-router-dom'
import { Screen, BarraSuperior, Titulo } from '../components/Screen'
import { historialTemporadas } from '../lib/mock'
import { useI18n } from '../i18n'

export default function Historial() {
  const { t } = useI18n()
  return (
    <Screen>
      <BarraSuperior volverA="/planificar" derecha={<span className="ps-contexto">Quemchi</span>} />
      <Titulo>{t('historial_titulo')}</Titulo>

      <section aria-labelledby="aviso-familia" className="ps-pad-16" style={{ marginTop: 16, padding: 14, borderRadius: 22, background: 'var(--precaucion-fondo)', display: 'flex', gap: 12, alignItems: 'center' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <h2 id="aviso-familia" style={{ margin: 0, fontSize: 19, fontWeight: 800, color: 'var(--precaucion-texto)' }}>
            Papa 2 de 3 años
          </h2>
          <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--precaucion-texto)' }}>Más tizón y plagas del suelo</span>
        </div>
      </section>

      <ol aria-label="Temporadas" className="ps-pad-16" style={{ marginTop: 16, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {historialTemporadas.map((h) => (
          <li key={h.anio} className="ps-card" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ width: 52, height: 52, borderRadius: 26, background: 'var(--hundido)', flexShrink: 0 }} aria-hidden="true" />
            <span style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: 20, fontWeight: 800 }}>{h.especie}</span>
              <span className="ps-chip ps-chip-neutro" style={{ alignSelf: 'flex-start' }}>
                {h.familia}
              </span>
            </span>
            <span style={{ fontSize: 18, fontWeight: 800, color: 'var(--texto-tenue)' }}>{h.anio}</span>
          </li>
        ))}
      </ol>

      <button type="button" className="ps-pad-16" style={{ marginTop: 12, minHeight: 56, borderRadius: 22, border: '3px dashed var(--borde-control)', background: 'transparent', color: 'var(--carbon)', font: "800 17px 'Alegreya Sans', sans-serif", cursor: 'pointer' }}>
        {t('historial_agregar_temporada')}
      </button>

      <div style={{ marginTop: 'auto', padding: '20px 16px 32px 16px' }}>
        <Link to="/terreno" className="ps-btn">
          {t('historial_que_siembro')}
        </Link>
      </div>
    </Screen>
  )
}
