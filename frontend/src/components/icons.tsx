// Iconos de línea compartidos entre pantallas (1.6-2px, extremos redondeados, sin
// relleno, currentColor) -- ver design-system/README.md "Iconografía".
import type { SVGProps } from 'react'

type Props = SVGProps<SVGSVGElement> & { tamano?: number }

function base({ tamano = 22, ...resto }: Props) {
  return { width: tamano, height: tamano, viewBox: '0 0 24 24', fill: 'none', 'aria-hidden': true, ...resto }
}

export function IconoVolver(props: Props) {
  return (
    <svg {...base(props)} stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M15 5l-7 7 7 7" />
    </svg>
  )
}

export function IconoSiguiente(props: Props) {
  return (
    <svg {...base(props)} stroke="currentColor" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 5l7 7-7 7" />
    </svg>
  )
}

export function IconoMas(props: Props) {
  return (
    <svg {...base(props)} stroke="currentColor" strokeWidth={2.4} strokeLinecap="round">
      <path d="M12 5v14M5 12h14" />
    </svg>
  )
}

export function IconoCheck(props: Props) {
  return (
    <svg {...base(props)} stroke="currentColor" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12l5 5 9-10" />
    </svg>
  )
}

export function IconoHoy(props: Props) {
  return (
    <svg {...base(props)} stroke="currentColor" strokeWidth={1.8} strokeLinecap="round">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  )
}

export function IconoCultivos(props: Props) {
  return (
    <svg {...base(props)} stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 21V11" />
      <path d="M12 13c-5 0-7-4-7-8 4 0 7 3 7 8z" />
      <path d="M12 11c0-4 3-7 7-7 0 4-2 7-7 7z" />
    </svg>
  )
}

export function IconoReportar(props: Props) {
  return (
    <svg {...base(props)} stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 8h3l2-3h6l2 3h3v11H4z" />
      <circle cx="12" cy="13" r="3.5" />
    </svg>
  )
}

export function IconoPlanificar(props: Props) {
  return (
    <svg {...base(props)} stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="5" width="16" height="15" rx="3" />
      <path d="M4 10h16M9 3v4M15 3v4" />
    </svg>
  )
}

export function IconoTerreno(props: Props) {
  return (
    <svg {...base(props)} stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3.5l8.5 4.7-8.5 4.8-8.5-4.8z" />
      <path d="M3.5 12.2l8.5 4.8 8.5-4.8" />
      <path d="M3.5 16.2l8.5 4.8 8.5-4.8" />
    </svg>
  )
}

export function IconoPerfil(props: Props) {
  return (
    <svg {...base(props)} stroke="currentColor" strokeWidth={2} strokeLinecap="round">
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21c1-4 4-6 8-6s7 2 8 6" />
    </svg>
  )
}

export function IconoHelada(props: Props) {
  return (
    <svg {...base(props)} stroke="currentColor" strokeWidth={2} strokeLinecap="round">
      <path d="M12 3v18M4.5 7.5l15 9M4.5 16.5l15-9" />
    </svg>
  )
}

export function IconoLluvia(props: Props) {
  return (
    <svg {...base(props)} stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M7 14a4 4 0 1 1 .9-7.9A5 5 0 0 1 17.5 7 3.5 3.5 0 0 1 17 14z" />
      <path d="M8 17l-1 3M12 17l-1 3M16 17l-1 3" />
    </svg>
  )
}

export function IconoCalor(props: Props) {
  return (
    <svg {...base(props)} stroke="currentColor" strokeWidth={2} strokeLinecap="round">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  )
}

export function IconoInfo(props: Props) {
  return (
    <svg {...base(props)} stroke="currentColor" strokeWidth={2} strokeLinecap="round">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v6M12 7.5v.5" />
    </svg>
  )
}

export function IconoCandado(props: Props) {
  return (
    <svg {...base(props)} stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
      <rect x="5" y="11" width="14" height="10" rx="2" />
      <path d="M8 11V8a4 4 0 0 1 8 0v3" />
    </svg>
  )
}

export function IconoLupa(props: Props) {
  return (
    <svg {...base(props)} stroke="currentColor" strokeWidth={2} strokeLinecap="round">
      <circle cx="11" cy="11" r="6" />
      <path d="M16 16l5 5" />
    </svg>
  )
}

export function IconoDeslizamiento(props: Props) {
  return (
    <svg {...base(props)} stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 20L21 8v12z" />
      <path d="M8 12l2-2M12 9l2-2" />
      <circle cx="15" cy="15" r="1.4" />
      <circle cx="11" cy="17" r="1.4" />
    </svg>
  )
}

export function IconoInundacion(props: Props) {
  return (
    <svg {...base(props)} stroke="currentColor" strokeWidth={2} strokeLinecap="round">
      <path d="M3 9c3-2 6-2 9 0s6 2 9 0M3 14c3-2 6-2 9 0s6 2 9 0M3 19c3-2 6-2 9 0s6 2 9 0" />
    </svg>
  )
}

export function IconoIncendio(props: Props) {
  return (
    <svg {...base(props)} stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 21c-4 0-7-3-7-7 0-4 4-6 4-10 3 2 4 4 4 6 1-1 2-2 2-4 3 2 4 5 4 8 0 4-3 7-7 7z" />
    </svg>
  )
}

export function IconoTelefono(props: Props) {
  return (
    <svg {...base(props)} stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 4h4l2 5-3 2a11 11 0 0 0 5 5l2-3 5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2" />
    </svg>
  )
}

export function IconoCampana(props: Props) {
  return (
    <svg {...base(props)} stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15z" />
      <path d="M10 20a2 2 0 0 0 4 0" />
    </svg>
  )
}

export function IconoUbicacion(props: Props) {
  return (
    <svg {...base(props)} stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 21c-4-5-7-8.5-7-12a7 7 0 0 1 14 0c0 3.5-3 7-7 12z" />
      <circle cx="12" cy="9" r="2.5" />
    </svg>
  )
}

export function IconoReloj(props: Props) {
  return (
    <svg {...base(props)} stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 12a8 8 0 1 0 2.3-5.6" />
      <path d="M4 4v4h4M12 8v4l3 2" />
    </svg>
  )
}

export function IconoFoto(props: Props) {
  return (
    <svg {...base(props)} stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 8h3l2-3h6l2 3h3v11H4z" />
      <circle cx="12" cy="13" r="3.5" />
    </svg>
  )
}

export function IconoAudio(props: Props) {
  return (
    <svg {...base(props)} stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
    </svg>
  )
}

// Estado del cielo (Hoy). Mismo trazo que el resto: línea de 2 px, sin relleno, currentColor.
const NUBE = 'M7 18a4 4 0 1 1 .9-7.9A5 5 0 0 1 17.5 11 3.5 3.5 0 0 1 17 18z'

export function IconoSol(props: Props) {
  return IconoHoy(props)
}

export function IconoParcialmenteNublado(props: Props) {
  return (
    <svg {...base(props)} stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 3v1.5M3 8h1.5M4.6 4.6l1 1M12 4.6l-1 1" />
      <path d="M7.2 11.2a3.3 3.3 0 1 1 5.1-3.6" />
      <path d={'M9 20a3.5 3.5 0 1 1 .8-6.9A4.5 4.5 0 0 1 18.5 14 3 3 0 0 1 18 20z'} />
    </svg>
  )
}

export function IconoNublado(props: Props) {
  return (
    <svg {...base(props)} stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d={NUBE} />
    </svg>
  )
}

export function IconoNiebla(props: Props) {
  return (
    <svg {...base(props)} stroke="currentColor" strokeWidth={2} strokeLinecap="round">
      <path d="M4 9h16M6 13h12M4 17h16" />
    </svg>
  )
}

export function IconoNieve(props: Props) {
  return (
    <svg {...base(props)} stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M7 13a4 4 0 1 1 .9-7.9A5 5 0 0 1 17.5 6 3.5 3.5 0 0 1 17 13z" />
      <path d="M8 17v.01M12 17v.01M16 17v.01M10 20.5v.01M14 20.5v.01" />
    </svg>
  )
}

export function IconoTormenta(props: Props) {
  return (
    <svg {...base(props)} stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M7 13a4 4 0 1 1 .9-7.9A5 5 0 0 1 17.5 6 3.5 3.5 0 0 1 17 13z" />
      <path d="M12.5 13l-2.5 4h3l-2 4" />
    </svg>
  )
}

export function IconoSequia(props: Props) {
  return (
    <svg {...base(props)} stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3c3 4 5.5 6.6 5.5 10a5.5 5.5 0 0 1-11 0C6.5 9.6 9 7 12 3z" />
      <path d="M4 4l16 16" />
    </svg>
  )
}
