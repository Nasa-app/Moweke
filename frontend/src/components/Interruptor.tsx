// Un sí o un no: más claro que dos botones iguales cuando la pregunta es "¿tienes esto?". La fila entera es el
// botón (zona de toque grande) y `descripcion` dice qué cambia con cada respuesta.
export function Interruptor({ activo, onCambio, etiqueta, descripcion }: {
  activo: boolean
  onCambio: (activo: boolean) => void
  etiqueta: string
  descripcion: string
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={activo}
      onClick={() => onCambio(!activo)}
      style={{ display: 'flex', alignItems: 'center', gap: 12, width: '100%', minHeight: 64, padding: '10px 14px', border: 'none', borderRadius: 16, background: 'var(--blanco)', boxShadow: 'var(--sombra-1)', textAlign: 'left', cursor: 'pointer', color: 'var(--carbon)', font: 'inherit' }}
    >
      <span style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
        <span style={{ fontSize: 18, fontWeight: 800, lineHeight: 1.15 }}>{etiqueta}</span>
        <span className="ps-nota">{descripcion}</span>
      </span>
      <span aria-hidden="true" style={{ position: 'relative', flex: 'none', width: 54, height: 32, borderRadius: 16, background: activo ? 'var(--verde)' : 'var(--borde-control)', transition: 'background 0.15s' }}>
        <span style={{ position: 'absolute', top: 3, left: activo ? 25 : 3, width: 26, height: 26, borderRadius: 13, background: '#fff', boxShadow: '0 1px 3px rgba(0,0,0,0.3)', transition: 'left 0.15s' }} />
      </span>
    </button>
  )
}
