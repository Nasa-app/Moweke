import { useState } from 'react'
import { Screen } from '../components/Screen'
import { BottomNav } from '../components/BottomNav'
import { IconoCandado, IconoMas } from '../components/icons'
import { semillasPedidas } from '../lib/mock'
import { useI18n } from '../i18n'

// Red de alertas de variedad -- reemplaza al modelo de "guardadoras" como institución
// (ver referencias/modelo-conceptual.md §9). alerta_busqueda_variedad / respuesta_alerta
// existen en el schema pero ningún endpoint real las escribe todavía.
export default function Red() {
  const { t } = useI18n()
  const [tab, setTab] = useState<'piden' | 'mios'>('piden')

  return (
    <Screen>
      <div style={{ padding: '48px 20px 0 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <h1 style={{ margin: 0, fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 30, lineHeight: 1 }}>{t('red_titulo')}</h1>
        <span className="ps-chip ps-chip-acento">
          <IconoCandado tamano={16} />
          {t('red_anonimo')}
        </span>
      </div>

      <div role="tablist" aria-label="Pedidos" className="ps-pad-16" style={{ marginTop: 16, display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 6, padding: 5, borderRadius: 18, background: 'var(--hundido)' }}>
        <button role="tab" aria-selected={tab === 'piden'} onClick={() => setTab('piden')} className={`ps-pill ${tab === 'piden' ? 'activo' : ''}`}>
          {t('red_piden')}
        </button>
        <button role="tab" aria-selected={tab === 'mios'} onClick={() => setTab('mios')} className={`ps-pill ${tab === 'mios' ? 'activo' : ''}`}>
          {t('red_mis_pedidos')} · 1
        </button>
      </div>

      <div className="ps-grid-2 ps-pad-16" style={{ marginTop: 14 }}>
        {tab === 'piden'
          ? semillasPedidas.map((s) => (
              <article key={s.especie} className="ps-card" style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: 10 }}>
                <div style={{ height: 70, borderRadius: 12, background: 'var(--cielo)' }} aria-hidden="true" />
                <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800 }}>{s.especie}</h2>
                <span className="ps-chip ps-chip-acento" style={{ alignSelf: 'flex-start' }}>
                  {s.variedad}
                </span>
                <span className="ps-nota">
                  {s.lugar} · {s.hace}
                </span>
                <button type="button" className="ps-btn" style={{ minHeight: 46, fontSize: 16 }}>
                  {t('red_tengo')}
                </button>
              </article>
            ))
          : (
              <div className="ps-card" style={{ gridColumn: '1 / 3' }}>
                <p className="ps-cuerpo">Tu pedido de haba sigue abierto · Quemchi</p>
              </div>
            )}
        <button
          type="button"
          style={{ borderRadius: 20, border: '3px dashed var(--borde-control)', background: 'transparent', cursor: 'pointer', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 8, minHeight: 200, font: "800 18px 'Alegreya Sans', sans-serif", color: 'var(--carbon)' }}
        >
          <span style={{ width: 56, height: 56, borderRadius: 28, background: 'var(--verde)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <IconoMas tamano={28} stroke="#fff" />
          </span>
          {t('red_pedir_semilla')}
          <span className="ps-nota">Especie y variedad</span>
        </button>
      </div>

      <BottomNav />
    </Screen>
  )
}
