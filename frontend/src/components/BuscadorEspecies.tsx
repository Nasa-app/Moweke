import { useEffect, useState } from 'react'
import { buscarEspecies, declararCultivo, mensajeDeError, type EspecieBuscada } from '../lib/api'
import { aIso, nombreEspecie } from '../lib/formato'
import { useI18n } from '../i18n'

const MIN_LETRAS = 2
const ESPERA_MS = 250

// Busca una especie por su nombre (español, inglés, común o científico) y la agrega como cultivo de la parcela con su
// fecha de siembra. Las que tienen calendario por etapa se marcan; las demás se registran igual.
export function BuscadorEspecies({ idParcela, onAgregada }: { idParcela: number; onAgregada: (idCultivo: number, especie: string) => void }) {
  const { t } = useI18n()
  const [consulta, setConsulta] = useState('')
  const [resultados, setResultados] = useState<{ para: string; lista: EspecieBuscada[] } | null>(null)
  const [errorBuscar, setErrorBuscar] = useState(false)
  const [elegida, setElegida] = useState<EspecieBuscada | null>(null)
  const [hoy] = useState(() => aIso(new Date()))
  const [fecha, setFecha] = useState(hoy)
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)

  const texto = consulta.trim()
  const buscable = texto.length >= MIN_LETRAS

  useEffect(() => {
    if (!buscable) return
    let vigente = true
    const espera = setTimeout(() => {
      buscarEspecies(texto)
        .then((r) => {
          if (!vigente) return
          setErrorBuscar(false)
          setResultados({ para: texto, lista: r.especies })
        })
        .catch(() => vigente && setErrorBuscar(true))
    }, ESPERA_MS)
    return () => {
      vigente = false
      clearTimeout(espera)
    }
  }, [texto, buscable])

  const lista = buscable && resultados?.para === texto ? resultados.lista : null

  async function agregar() {
    if (!elegida) return
    setEnviando(true)
    setError(null)
    try {
      const cultivo = await declararCultivo(idParcela, { especie: elegida.especie, fecha_siembra: fecha })
      setAviso(t('buscador_agregado', { especie: nombreEspecie(elegida.especie, elegida) }))
      setElegida(null)
      setConsulta('')
      setResultados(null)
      onAgregada(cultivo.id, cultivo.especie)
    } catch (err) {
      setError(mensajeDeError(err, t('buscador_error_agregar')))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <section aria-labelledby="buscador-especies" className="ps-pad-16" style={{ marginTop: 14 }}>
      <h2 id="buscador-especies" className="ps-h2" style={{ margin: '0 4px' }}>{t('buscador_titulo')}</h2>
      <div className="ps-card" style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 10 }}>
        <input
          type="search"
          role="combobox"
          aria-expanded={lista !== null && lista.length > 0}
          aria-label={t('buscador_label')}
          placeholder={t('buscador_placeholder')}
          value={consulta}
          autoComplete="off"
          onChange={(e) => {
            setConsulta(e.target.value)
            setElegida(null)
            setAviso(null)
          }}
          style={{ width: '100%', boxSizing: 'border-box', minHeight: 48, padding: '0 14px', borderRadius: 14, border: '2px solid var(--borde-control)', background: 'var(--blanco)', color: 'var(--carbon)', font: "700 16px 'Alegreya Sans', sans-serif" }}
        />

        {aviso && !buscable ? <span className="ps-nota" role="status" style={{ fontWeight: 800, color: 'var(--verde)' }}>{aviso}</span> : null}
        {errorBuscar && buscable ? <span className="ps-nota" role="alert" style={{ color: 'var(--riesgo-texto)' }}>{t('buscador_error_buscar')}</span> : null}
        {buscable && lista === null && !errorBuscar ? <span className="ps-nota" role="status">{t('buscador_buscando')}</span> : null}
        {lista && lista.length === 0 ? <span className="ps-nota" role="status">{t('buscador_sin_resultados', { q: texto })}</span> : null}

        {lista && lista.length > 0 && !elegida ? (
          <ul role="listbox" aria-label={t('buscador_titulo')} style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 6 }}>
            {lista.map((e) => (
              <li key={e.especie} role="option" aria-selected={false}>
                <button type="button" onClick={() => { setElegida(e); setError(null) }} className="ps-card-plana" style={{ width: '100%', boxSizing: 'border-box', border: 'none', cursor: 'pointer', textAlign: 'left', minHeight: 52, display: 'flex', alignItems: 'center', gap: 8, color: 'var(--carbon)' }}>
                  <span style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
                    <b style={{ fontSize: 17, fontWeight: 800 }}>{nombreEspecie(e.especie, e)}</b>
                    {e.nombre_cientifico ? <span className="ps-nota" style={{ fontStyle: 'italic' }}>{e.nombre_cientifico}</span> : null}
                  </span>
                  <span className={`ps-chip ${e.seguimiento ? 'ps-chip-favorable' : 'ps-chip-neutro'}`}>{t(e.seguimiento ? 'buscador_con_seguimiento' : 'buscador_solo_registro')}</span>
                </button>
              </li>
            ))}
          </ul>
        ) : null}

        {elegida ? (
          <div role="group" aria-label={nombreEspecie(elegida.especie, elegida)} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <b style={{ fontSize: 19, fontWeight: 800 }}>{nombreEspecie(elegida.especie, elegida)}</b>
              {elegida.nombre_cientifico ? <span className="ps-nota" style={{ fontStyle: 'italic' }}>{elegida.nombre_cientifico}</span> : null}
            </div>
            <span className="ps-nota">{t(elegida.seguimiento ? 'buscador_nota_seguimiento' : 'buscador_nota_registro')}</span>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 16, fontWeight: 800 }}>
              {t('buscador_fecha')}
              <input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} style={{ width: '100%', minWidth: 0, boxSizing: 'border-box', minHeight: 48, padding: '0 12px', borderRadius: 14, border: '2px solid var(--borde-control)', background: 'var(--blanco)', color: 'var(--carbon)', font: "700 16px 'Alegreya Sans', sans-serif" }} />
            </label>
            {error ? <span className="ps-nota" role="alert" style={{ color: 'var(--riesgo-texto)' }}>{error}</span> : null}
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button type="button" className="ps-btn" onClick={agregar} disabled={enviando || !fecha} style={{ flex: '1 1 160px', width: 'auto', minWidth: 0, boxSizing: 'border-box' }}>
                {enviando ? t('cargando') : t('buscador_agregar')}
              </button>
              <button type="button" className="ps-btn-secundario" onClick={() => setElegida(null)} disabled={enviando} style={{ flex: '1 1 110px', width: 'auto', minWidth: 0, boxSizing: 'border-box' }}>
                {t('buscador_cancelar')}
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </section>
  )
}
