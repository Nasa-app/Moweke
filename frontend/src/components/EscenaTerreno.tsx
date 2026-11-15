import type { ReactNode } from 'react'

// Predio isométrico de Tu terreno (handoff: "el predio isométrico es el protagonista"). Es una
// ilustración fija: casa, árboles y un paño de tierra labrada. NO dibuja ningún cultivo, porque no
// sabe cuál sembró el agricultor. Los colores salen de la ilustración, no de la interfaz
// (tokens.json permite colores propios dentro de ilustraciones). Cuadrícula de 6x6 celdas.
type Pt = [number, number]
const X = (u: number, v: number): Pt => [180 + (u - v) * 26, 44 + (u + v) * 13]
const rombo = (u0: number, v0: number, u1: number, v1: number) =>
  `M${[X(u0, v0), X(u1, v0), X(u1, v1), X(u0, v1)].map((q) => q.join(' ')).join('L')}z`

function En({ u, v, escala = 1, children }: { u: number; v: number; escala?: number; children: ReactNode }) {
  const [x, y] = X(u, v)
  return <g transform={`translate(${x} ${y}) scale(${escala})`}>{children}</g>
}

const Sombra = ({ rx, ry }: { rx: number; ry: number }) => <ellipse cx="0" cy="1" rx={rx} ry={ry} fill="#33302C" opacity={0.13} />

const Arbol = ({ u, v, escala }: { u: number; v: number; escala?: number }) => (
  <En u={u} v={v} escala={escala}>
    <Sombra rx={12} ry={5} />
    <path d="M-2 0h4v-14h-4z" fill="#8E7559" />
    <circle cx="0" cy="-24" r="14" fill="#3F611C" />
    <circle cx="-4" cy="-28" r="8" fill="#829E30" />
  </En>
)

const Pino = ({ u, v, escala }: { u: number; v: number; escala?: number }) => (
  <En u={u} v={v} escala={escala}>
    <Sombra rx={10} ry={4} />
    <path d="M-1.5 0h3v-8h-3z" fill="#8E7559" />
    <path d="M0 -40L-11 -18h22z" fill="#1D4939" />
    <path d="M0 -30L-13 -6h26z" fill="#24563F" />
    <path d="M0 -30L0 -6h13z" fill="#1D4939" />
  </En>
)

const Arbusto = ({ u, v }: { u: number; v: number }) => (
  <En u={u} v={v}>
    <Sombra rx={12} ry={4} />
    <ellipse cx="-5" cy="-6" rx="8" ry="7" fill="#617F26" />
    <ellipse cx="5" cy="-7" rx="8" ry="7.5" fill="#829E30" />
  </En>
)

const Casa = ({ u, v }: { u: number; v: number }) => (
  <En u={u} v={v}>
    <ellipse cx="0" cy="0" rx="18" ry="6" fill="#33302C" opacity=".12" />
    <path d="M-16 -8L0 0V-18L-16 -26z" fill="#FFFFFF" />
    <path d="M0 0L16 -8V-26L0 -18z" fill="#E3E9D6" />
    <path d="M-19 -24L0 -15L0 -36z" fill="#8E4B2C" />
    <path d="M0 -15L19 -24L0 -36z" fill="#6E3820" />
    <path d="M5 -6l6 -3v-8l-6 3z" fill="#8E7559" />
  </En>
)

function Surcos() {
  const [u0, v0, u1, v1] = [0.5, 2.4, 3.4, 5.6]
  const lineas = []
  for (let i = 1; i < (u1 - u0) * 2; i++) {
    const u = u0 + i / 2
    const [ax, ay] = X(u, v0)
    const [bx, by] = X(u, v1)
    lineas.push(<path key={i} d={`M${ax} ${ay}L${bx} ${by}`} stroke="#7E654B" strokeWidth="1.4" opacity=".6" />)
  }
  return (
    <>
      <path d={rombo(u0, v0, u1, v1)} fill="#8C6F55" />
      {lineas}
    </>
  )
}

export function EscenaTerreno({ etiqueta }: { etiqueta: string }) {
  return (
    <svg viewBox="14 6 332 246" role="img" aria-label={etiqueta} style={{ display: 'block', width: '100%', height: 'auto' }}>
      <path d="M24 122L180 200L180 230L24 152z" fill="#A68B6B" />
      <path d="M180 200L336 122L336 152L180 230z" fill="#8E7559" />
      <path d="M24 122L180 200L180 207L24 129z" fill="#829E30" />
      <path d="M180 200L336 122L336 129L180 207z" fill="#6F8A2C" />
      <path d="M180 44L336 122L180 200L24 122z" fill="#A3B46C" />
      <Surcos />
      <Casa u={4.6} v={1} />
      <Arbol u={0.6} v={0.9} escala={0.9} />
      <Pino u={2.3} v={0.7} escala={0.9} />
      <Arbol u={5.4} v={5.3} escala={0.8} />
      <Arbusto u={4.4} v={3.9} />
    </svg>
  )
}
