import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Screen, BarraSuperior, Titulo } from '../components/Screen'
import { usePredio } from '../state/PredioContext'
import { listarCultivos } from '../lib/api'
import { comunaDeParcela } from '../lib/comunas'
import { nombreEspecie } from '../lib/formato'
import { leer } from '../state/storage'
import { useI18n } from '../i18n'

interface Temporada {
  clave: string
  anio: number
  especie: string
  detalle: string
}

// Lo que el agricultor contó en "Qué sembraste antes" (solo en este dispositivo): el año se calcula desde hoy.
const ANTES: { clave: string; atras: number }[] = [
  { clave: 'esta', atras: 0 },
  { clave: 'pasado', atras: 1 },
  { clave: 'hace2', atras: 2 },
]
const SIN_CULTIVO = new Set(['Nada', 'Otro'])

const primeraPalabra = (texto: string) => texto.toLowerCase().split(' ')[0]

// Las siembras declaradas (servidor) y las contadas de memoria, de la más reciente a la más antigua.
export default function Historial() {
  const { t } = useI18n()
  const { idParcela } = usePredio()
  const [declaradas, setDeclaradas] = useState<Temporada[] | null>(idParcela ? null : [])

  useEffect(() => {
    if (!idParcela) return
    let vigente = true
    listarCultivos(idParcela)
      .then((r) =>
        vigente &&
        setDeclaradas(
          r.cultivos.map((c) => ({
            clave: `c${c.id}`,
            anio: Number(c.fecha_siembra.slice(0, 4)),
            especie: nombreEspecie(c.especie),
            detalle: c.variedad_local ?? `Sembrado el ${c.fecha_siembra.slice(8, 10)}/${c.fecha_siembra.slice(5, 7)}`,
          })),
        ),
      )
      .catch(() => vigente && setDeclaradas([]))
    return () => {
      vigente = false
    }
  }, [idParcela])

  const anioActual = new Date().getFullYear()
  const contadas: Temporada[] = ANTES.flatMap(({ clave, atras }) => {
    const especie = leer<Record<string, string>>('onboarding_antes', {})[clave]
    return especie && !SIN_CULTIVO.has(especie) ? [{ clave: `a${clave}`, anio: anioActual - atras, especie, detalle: 'Lo contaste tú' }] : []
  }).filter((c) => !(declaradas ?? []).some((d) => d.anio === c.anio && primeraPalabra(d.especie) === primeraPalabra(c.especie)))

  const temporadas = [...(declaradas ?? []), ...contadas].sort((a, b) => b.anio - a.anio)

  // Una misma especie en dos de las últimas tres temporadas: aviso de rotación.
  const ultimas = temporadas.filter((s) => s.anio > anioActual - 3)
  const repetida = [...new Set(ultimas.map((s) => primeraPalabra(s.especie)))]
    .map((p) => ({ nombre: ultimas.find((s) => primeraPalabra(s.especie) === p)!.especie, anios: new Set(ultimas.filter((s) => primeraPalabra(s.especie) === p).map((s) => s.anio)).size }))
    .find((e) => e.anios >= 2)

  const comuna = comunaDeParcela(idParcela)

  return (
    <Screen>
      <BarraSuperior volverA="/planificar" derecha={comuna ? <span className="ps-contexto">{comuna}</span> : undefined} />
      <Titulo>{t('historial_titulo')}</Titulo>

      {repetida ? (
        <section aria-labelledby="aviso-familia" className="ps-pad-16" style={{ marginTop: 16, padding: 14, borderRadius: 22, background: 'var(--precaucion-fondo, var(--hundido))' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <h2 id="aviso-familia" style={{ margin: 0, fontSize: 19, fontWeight: 800, color: 'var(--precaucion-texto)' }}>
              {repetida.nombre} {repetida.anios} de 3 años
            </h2>
            <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--precaucion-texto)' }}>Conviene alternar: repetir la misma especie favorece las plagas del suelo</span>
          </div>
        </section>
      ) : null}

      {declaradas === null ? <p className="ps-pad ps-nota" style={{ margin: '16px 0 0 0' }}>{t('cargando')}</p> : null}
      {declaradas !== null && temporadas.length === 0 ? (
        <p className="ps-pad ps-cuerpo" style={{ margin: '16px 0 0 0' }}>Todavía no hay temporadas. Agrega lo que sembraste y lo verás aquí.</p>
      ) : null}

      {temporadas.length ? (
        <ol aria-label="Temporadas" style={{ margin: '16px 16px 0 16px', padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 8 }}>
          {temporadas.map((h) => (
            <li key={h.clave} className="ps-card" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span aria-hidden="true" style={{ width: 52, height: 52, borderRadius: 26, background: 'var(--hundido)', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22, fontWeight: 800, color: 'var(--verde)' }}>
                {h.especie[0]}
              </span>
              <span style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
                <span style={{ fontSize: 20, fontWeight: 800 }}>{h.especie}</span>
                <span className="ps-chip ps-chip-neutro" style={{ alignSelf: 'flex-start' }}>
                  {h.detalle}
                </span>
              </span>
              <span style={{ fontSize: 18, fontWeight: 800, color: 'var(--texto-tenue)' }}>{h.anio}</span>
            </li>
          ))}
        </ol>
      ) : null}

      <Link to="/onboarding/cultivos" className="ps-pad-16" style={{ margin: '12px 16px 0 16px', minHeight: 56, borderRadius: 22, border: '3px dashed var(--borde-control)', color: 'var(--carbon)', display: 'flex', alignItems: 'center', justifyContent: 'center', font: "800 18px 'Alegreya Sans', sans-serif", textDecoration: 'none' }}>
        {t('historial_agregar_temporada')}
      </Link>

      <div style={{ marginTop: 'auto', padding: '20px 16px 32px 16px' }}>
        <Link to="/especies" className="ps-btn">
          {t('historial_que_siembro')}
        </Link>
      </div>
    </Screen>
  )
}
