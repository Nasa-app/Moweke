import { Navigate } from 'react-router-dom'
import { RutaPrivada } from '../components/RutaPrivada'
import { usePredio } from '../state/PredioContext'

// Ya no hay pantalla de registro ni de inicio de sesión: la cuenta anónima de este dispositivo se crea sola.
// Esta ruta queda solo para los enlaces que todavía apuntan a /sesion: espera la sesión y sigue adelante
// (al inicio si ya hay predio, al registro del predio si no).
export default function Sesion() {
  const { idParcela } = usePredio()
  return (
    <RutaPrivada>
      <Navigate to={idParcela ? '/hoy' : '/onboarding/predio'} replace />
    </RutaPrivada>
  )
}
