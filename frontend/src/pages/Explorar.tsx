import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Screen } from '../components/Screen'
import { climaZona, novedadesZona } from '../lib/mock'
import { useAuth } from '../state/AuthContext'
import { useI18n } from '../i18n'

const COMUNAS = ['Quemchi', 'Chonchi', 'Castro', 'Ancud', 'Dalcahue', 'Quellón']

// Datos de la comuna sin registro (ver CLAUDE.md handoff, "Navegación") -- no hay
// endpoint público de clima/novedades por comuna todavía, así que esta pantalla entera
// usa lib/mock.ts.
export default function Explorar() {
  const { t } = useI18n()
  const { autenticado } = useAuth()
  const [comuna, setComuna] = useState('Quemchi')

  return (
    <Screen>
      <section aria-labelledby="zona" style={{ padding: '48px 16px 16px 16px', borderRadius: '0 0 32px 32px', background: 'var(--verde)', color: '#fff', display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
          <label style={{ minHeight: 44, padding: '0 12px 0 10px', borderRadius: 22, background: 'rgba(255,255,255,.14)', display: 'flex', alignItems: 'center', gap: 6, fontSize: 16, fontWeight: 800, cursor: 'pointer' }}>
            <span className="visually-hidden">Comuna</span>
            <select value={comuna} onChange={(e) => setComuna(e.target.value)} style={{ appearance: 'none', border: 'none', background: 'transparent', color: '#fff', font: "800 16px 'Alegreya Sans', sans-serif", cursor: 'pointer' }}>
              {COMUNAS.map((c) => (
                <option key={c} value={c} style={{ color: '#000' }}>
                  {c}
                </option>
              ))}
            </select>
          </label>
          <span style={{ fontSize: 15, fontWeight: 700, opacity: 0.9 }}>{climaZona.fecha}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <h1 id="zona" style={{ margin: 0, fontSize: 56, fontWeight: 800, lineHeight: 1 }}>
              {climaZona.temperatura}°
            </h1>
            <span style={{ fontSize: 17, fontWeight: 700 }}>{climaZona.descripcion}</span>
          </div>
        </div>
        <dl style={{ margin: 0, padding: '10px 6px', borderRadius: 20, background: 'rgba(255,255,255,.12)', display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', textAlign: 'center' }}>
          <div style={{ display: 'flex', flexDirection: 'column-reverse', gap: 2 }}>
            <dt style={{ fontSize: 14, fontWeight: 700, opacity: 0.9 }}>Humedad</dt>
            <dd style={{ margin: 0, fontSize: 20, fontWeight: 800 }}>{climaZona.humedad}%</dd>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column-reverse', gap: 2, borderLeft: '1px solid rgba(255,255,255,.25)', borderRight: '1px solid rgba(255,255,255,.25)' }}>
            <dt style={{ fontSize: 14, fontWeight: 700, opacity: 0.9 }}>Lluvia</dt>
            <dd style={{ margin: 0, fontSize: 20, fontWeight: 800 }}>{climaZona.lluvia_mm} mm</dd>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column-reverse', gap: 2 }}>
            <dt style={{ fontSize: 14, fontWeight: 700, opacity: 0.9 }}>Viento</dt>
            <dd style={{ margin: 0, fontSize: 20, fontWeight: 800 }}>{climaZona.viento_kmh} km/h</dd>
          </div>
        </dl>
      </section>

      <h2 className="ps-h2" style={{ margin: '20px 20px 0 20px' }}>
        {t('lo_nuevo_zona')}
      </h2>
      <div className="ps-grid-2 ps-pad-16" style={{ marginTop: 10 }}>
        {novedadesZona.map((n) => (
          <Link key={n.titulo} to="/fuentes" className="ps-card" style={{ textDecoration: 'none', color: 'var(--carbon)', display: 'flex', flexDirection: 'column', gap: 8 }}>
            {n.chip ? (
              <span className="ps-chip ps-chip-clima" style={{ alignSelf: 'flex-start' }}>
                {n.chip}
              </span>
            ) : null}
            <span className="ps-detalle">{n.titulo}</span>
            <b style={{ fontSize: 22, fontWeight: 800, lineHeight: 1 }}>{n.valor}</b>
          </Link>
        ))}
      </div>

      <section aria-labelledby="cta-predio" className="ps-pad-16" style={{ margin: '16px 16px 0 16px', padding: 14, borderRadius: 24, background: 'var(--menta)', display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <h2 id="cta-predio" className="ps-h2">
            {t('datos_predio')}
          </h2>
          <span className="ps-contexto">{t('analisis_terreno')}</span>
        </div>
      </section>

      <div style={{ marginTop: 'auto', padding: '18px 16px 32px 16px', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <Link to={autenticado ? '/onboarding/predio' : '/sesion'} className="ps-btn">
          {t('agregar_predio')}
        </Link>
        <Link to="/hoy" className="ps-btn-texto">
          {t('seguir_mirando')}
        </Link>
      </div>
    </Screen>
  )
}
