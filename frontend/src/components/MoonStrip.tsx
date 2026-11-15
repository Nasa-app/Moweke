import { Link } from 'react-router-dom'
import { faseLunar } from '../lib/mock'
import { useI18n } from '../i18n'

const RELLENO: Record<string, string> = {
  nueva: 'var(--linea)',
  creciente: 'var(--ilus-sol)',
  llena: 'var(--ilus-sol)',
  menguante: 'var(--ilus-sol)',
}

function IconoFase({ tipo }: { tipo: string }) {
  return (
    <svg width={30} height={30} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="9" fill="var(--linea)" stroke="var(--precaucion-texto)" strokeWidth={1.2} />
      {tipo === 'creciente' ? <path d="M12 3a9 9 0 0 0 0 18z" fill={RELLENO.creciente} /> : null}
      {tipo === 'llena' ? <circle cx="12" cy="12" r="9" fill={RELLENO.llena} stroke="var(--precaucion-texto)" strokeWidth={1.2} /> : null}
      {tipo === 'menguante' ? <path d="M12 3a9 9 0 0 1 0 18z" fill={RELLENO.menguante} /> : null}
    </svg>
  )
}

// Franja de 4 fases lunares -- componente nuevo del handoff, "en validación con
// comunidades" (saber williche). Se marca así en toda pantalla donde aparece.
export function MoonStrip({ nota }: { nota?: string }) {
  const { t } = useI18n()
  return (
    <section aria-labelledby="luna" className="ps-card-plana" style={{ marginTop: 16, marginLeft: 16, marginRight: 16 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', padding: '0 4px' }}>
        <h2 id="luna" className="ps-h2">
          {t('hoy_fases_luna')}
        </h2>
        <Link to="/fuentes" className="ps-nota" style={{ textDecoration: 'none' }}>
          {t('hoy_saber_williche')}
        </Link>
      </div>
      <ol style={{ margin: '8px 0 0', padding: 0, listStyle: 'none', display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 4, textAlign: 'center' }}>
        {faseLunar.fases.map((fase, i) => (
          <li
            key={fase.nombre}
            aria-current={i === faseLunar.actual ? 'date' : undefined}
            style={{
              padding: '6px 2px 8px',
              borderRadius: 14,
              background: i === faseLunar.actual ? 'var(--blanco)' : undefined,
              boxShadow: i === faseLunar.actual ? '0 0 0 2px var(--verde)' : undefined,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 3,
            }}
          >
            <span style={{ fontSize: 12, fontWeight: 800, color: 'var(--verde)', lineHeight: 1, height: 12 }}>
              {i === faseLunar.actual ? 'Ahora' : ''}
            </span>
            <IconoFase tipo={fase.tipo} />
            <span style={{ fontSize: 14, fontWeight: 800 }}>{fase.nombre}</span>
            <span className="ps-nota">{fase.fecha}</span>
          </li>
        ))}
      </ol>
      <p style={{ margin: '6px 4px 0', fontSize: 15, fontWeight: 700, color: 'var(--verde-oscuro)', lineHeight: 1.3 }}>
        {nota ?? faseLunar.nota}
      </p>
    </section>
  )
}
