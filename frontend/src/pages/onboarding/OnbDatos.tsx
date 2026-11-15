import { useNavigate } from 'react-router-dom'
import { Screen, BarraSuperior, Titulo } from '../../components/Screen'
import { StepDots } from '../../components/StepDots'
import { leer, guardar } from '../../state/storage'
import { usePredio } from '../../state/PredioContext'
import { useI18n } from '../../i18n'

const SECTORES = ['Centro', 'Aucar', 'Lliuco', 'Huite', 'Montemar', 'Tubildad']
const COMUNAS = ['Ancud', 'Castro', 'Chonchi', 'Curaco de Vélez', 'Dalcahue', 'Puqueldón', 'Queilén', 'Quellón', 'Quemchi', 'Quinchao']
const TERRENOS = ['Plano', 'Ladera', 'Alto'] as const

interface BorradorPredio {
  comuna: string
  sector: string
  terreno: (typeof TERRENOS)[number]
  acepto: boolean
}

export default function OnbDatos() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const { idParcela } = usePredio()
  const borrador = leer<BorradorPredio>('onboarding_predio', { comuna: 'Quemchi', sector: 'Centro', terreno: 'Ladera', acepto: false })

  function actualizar(cambios: Partial<BorradorPredio>) {
    guardar('onboarding_predio', { ...borrador, ...cambios })
  }

  function seguir() {
    navigate(idParcela ? '/onboarding/antes' : '/terreno/perimetro?desde=onboarding')
  }

  return (
    <Screen>
      <BarraSuperior volverA="/explorar" derecha={<StepDots paso={1} total={4} />} />
      <Titulo>{t('onb_predio_titulo')}</Titulo>

      <div className="ps-pad-16" style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 6 }}>
        <label htmlFor="comuna" style={{ fontSize: 16, fontWeight: 800, padding: '0 4px' }}>
          {t('onb_comuna')}
        </label>
        <select
          id="comuna"
          defaultValue={borrador.comuna}
          onChange={(e) => actualizar({ comuna: e.target.value })}
          style={{ minHeight: 56, padding: '0 14px', borderRadius: 16, border: '2px solid var(--borde-control)', background: 'var(--blanco)', font: "700 18px 'Alegreya Sans', sans-serif", color: 'var(--carbon)' }}
        >
          {COMUNAS.map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
      </div>

      <fieldset className="ps-pad-16" style={{ marginTop: 16, border: 'none', paddingBlock: 0 }}>
        <legend style={{ padding: '0 4px', marginBottom: 8, fontSize: 16, fontWeight: 800 }}>{t('onb_sector')}</legend>
        <div className="ps-grid-3">
          {SECTORES.map((s) => (
            <label key={s} className={`ps-pill ${borrador.sector === s ? 'activo' : ''}`}>
              <input type="radio" name="sector" defaultChecked={borrador.sector === s} onChange={() => actualizar({ sector: s })} className="visually-hidden" />
              {s}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="ps-pad-16" style={{ marginTop: 16, border: 'none', paddingBlock: 0 }}>
        <legend style={{ padding: '0 4px', marginBottom: 8, fontSize: 16, fontWeight: 800 }}>{t('onb_terreno')}</legend>
        <div className="ps-grid-3">
          {TERRENOS.map((tp) => (
            <label
              key={tp}
              style={{
                borderRadius: 16,
                overflow: 'hidden',
                background: 'var(--blanco)',
                boxShadow: borrador.terreno === tp ? '0 0 0 3px var(--verde)' : 'var(--sombra-1)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                cursor: 'pointer',
                padding: '10px 0',
              }}
            >
              <input type="radio" name="terreno" defaultChecked={borrador.terreno === tp} onChange={() => actualizar({ terreno: tp })} className="visually-hidden" />
              <span style={{ fontSize: 15, fontWeight: 800, color: borrador.terreno === tp ? 'var(--verde)' : undefined }}>{tp}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <button
        type="button"
        onClick={() => navigate('/terreno/perimetro?desde=onboarding')}
        className="ps-pad-16"
        style={{
          margin: '10px 16px 0 16px',
          minHeight: 48,
          borderRadius: 14,
          border: '1.5px dashed var(--borde-control)',
          background: 'transparent',
          color: 'var(--carbon)',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          fontSize: 16,
          fontWeight: 700,
          cursor: 'pointer',
        }}
      >
        <span style={{ flex: 1, textAlign: 'left' }}>{t('onb_marcar_parcela')}</span>
        <span className="ps-nota">{idParcela ? 'Ya marcada · marcar otra' : 'Sigue después de este paso'}</span>
      </button>

      <section aria-label="Privacidad" className="ps-pad-16" style={{ margin: '18px 16px 0 16px', background: 'var(--cielo)', color: 'var(--carbon)', borderRadius: 20, padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 6, textAlign: 'center', fontSize: 14, fontWeight: 700 }}>
          <span>Sin tu nombre</span>
          <span>No se vende</span>
          <span>Lo borras</span>
        </div>
        <label style={{ display: 'flex', alignItems: 'center', gap: 12, minHeight: 48, padding: '0 12px', borderRadius: 14, background: 'var(--blanco)', cursor: 'pointer' }}>
          <input type="checkbox" defaultChecked={borrador.acepto} onChange={(e) => actualizar({ acepto: e.target.checked })} style={{ width: 24, height: 24, accentColor: 'var(--verde)' }} />
          <span style={{ flex: 1, fontSize: 16, fontWeight: 800 }}>{t('onb_acepto')}</span>
        </label>
      </section>

      <div style={{ marginTop: 'auto', padding: '20px 16px 32px 16px' }}>
        <button type="button" onClick={seguir} className="ps-btn">
          {t('seguir')}
        </button>
      </div>
    </Screen>
  )
}
