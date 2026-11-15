// Una pregunta con respuestas de elegir una. Tocar la respuesta marcada la quita (vuelve a "sin responder").
export function PreguntaSuelo({
  pregunta,
  ayuda,
  opciones,
  valor,
  onElegir,
}: {
  pregunta: string
  ayuda?: string
  opciones: { valor: string; texto: string }[]
  valor: string | null
  onElegir: (nuevo: string | null) => void
}) {
  return (
    <fieldset style={{ border: 'none', margin: 0, padding: 0 }}>
      <legend style={{ fontSize: 17, fontWeight: 800, padding: 0 }}>{pregunta}</legend>
      {ayuda ? <p className="ps-nota" style={{ margin: '4px 0 0 0' }}>{ayuda}</p> : null}
      <div role="radiogroup" aria-label={pregunta} style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
        {opciones.map((o) => (
          <button
            key={o.valor}
            type="button"
            role="radio"
            aria-checked={valor === o.valor}
            onClick={() => onElegir(valor === o.valor ? null : o.valor)}
            className={`ps-pill ${valor === o.valor ? 'activo' : ''}`}
            style={{ borderRadius: 18, minHeight: 48, padding: '8px 14px', justifyContent: 'flex-start', textAlign: 'left' }}
          >
            {o.texto}
          </button>
        ))}
      </div>
    </fieldset>
  )
}
