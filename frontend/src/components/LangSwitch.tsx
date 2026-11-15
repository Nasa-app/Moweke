import { useI18n } from '../i18n'

export function LangSwitch() {
  const { idioma, cambiarIdioma } = useI18n()
  return (
    <div role="radiogroup" aria-label="Idioma · Language" className="ps-lang">
      <button
        role="radio"
        aria-checked={idioma === 'es'}
        lang="es"
        aria-label="Español"
        className={idioma === 'es' ? 'activo' : ''}
        onClick={() => cambiarIdioma('es')}
      >
        ES
      </button>
      <button
        role="radio"
        aria-checked={idioma === 'en'}
        lang="en"
        aria-label="English"
        className={idioma === 'en' ? 'activo' : ''}
        onClick={() => cambiarIdioma('en')}
      >
        EN
      </button>
    </div>
  )
}
