import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../state/AuthContext'

export function RutaPrivada({ children }: { children: ReactNode }) {
  const { autenticado, cargando } = useAuth()
  if (cargando) return null
  if (!autenticado) return <Navigate to="/sesion" replace />
  return <>{children}</>
}
