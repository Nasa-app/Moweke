import { Link } from 'react-router-dom'

// Toda cifra debe poder mostrar su fuente y la fecha del dato (regla no negociable del
// handoff). Enlaza siempre a Fuentes.
export function SourceLink({ children }: { children: React.ReactNode }) {
  return (
    <Link to="/fuentes" className="ps-nota" style={{ textDecoration: 'none' }}>
      {children}
    </Link>
  )
}
