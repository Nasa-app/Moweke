import { Component, type ErrorInfo, type ReactNode } from 'react'
import { tr } from '../i18n/dictionary'

// Si una pantalla falla al pintarse, la app no se queda en blanco: avisa y deja recargar o volver al inicio. React
// desmonta todo el árbol ante un error sin capturar, y en un teléfono una pantalla en blanco no tiene salida.
export class ErrorBoundary extends Component<{ children: ReactNode }, { fallo: boolean }> {
  state = { fallo: false }

  static getDerivedStateFromError() {
    return { fallo: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(error, info.componentStack)
  }

  render() {
    if (!this.state.fallo) return this.props.children
    return (
      <div role="alert" style={{ minHeight: '100dvh', boxSizing: 'border-box', padding: '72px 24px 24px', display: 'flex', flexDirection: 'column', gap: 12, alignItems: 'center', textAlign: 'center', background: 'var(--arena)', color: 'var(--carbon)' }}>
        <h1 style={{ margin: 0, fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 28 }}>{tr('error_pantalla_titulo')}</h1>
        <p style={{ margin: 0, fontSize: 17, fontWeight: 700 }}>{tr('error_pantalla_texto')}</p>
        <button type="button" className="ps-btn" onClick={() => window.location.reload()} style={{ maxWidth: 320 }}>
          {tr('error_pantalla_recargar')}
        </button>
        <a href="/hoy" className="ps-btn-secundario" style={{ maxWidth: 320, boxSizing: 'border-box', display: 'flex', alignItems: 'center', justifyContent: 'center', textDecoration: 'none', width: '100%' }}>
          {tr('error_pantalla_inicio')}
        </a>
      </div>
    )
  }
}
