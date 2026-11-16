// Aviso de que algo se está calculando: una rueda que gira, el texto y una barra. Se anuncia a los lectores de
// pantalla (role="status"). Con movimiento reducido, la rueda y la barra quedan quietas.
export function Cargando({ texto, detalle, compacto = false }: { texto: string; detalle?: string; compacto?: boolean }) {
  if (compacto) {
    return (
      <div role="status" aria-live="polite" style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <span className="ps-nota" style={{ fontWeight: 800 }}>{texto}</span>
        <span className="ps-barra" aria-hidden="true" />
      </div>
    )
  }
  return (
    <div role="status" aria-live="polite" className="ps-card-plana ps-cargando">
      <span className="ps-rueda" aria-hidden="true" />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
        <span style={{ fontSize: 17, fontWeight: 800, lineHeight: 1.2 }}>{texto}</span>
        <span className="ps-barra" aria-hidden="true" />
        {detalle ? <span className="ps-nota">{detalle}</span> : null}
      </div>
    </div>
  )
}
