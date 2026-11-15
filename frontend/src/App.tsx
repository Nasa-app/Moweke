import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { I18nProvider } from './i18n'
import { AuthProvider } from './state/AuthContext'
import { PredioProvider } from './state/PredioContext'
import { RutaPrivada } from './components/RutaPrivada'

import Portada from './pages/Portada'
import Sesion from './pages/Sesion'
import Explorar from './pages/Explorar'
import OnbDatos from './pages/onboarding/OnbDatos'
import OnbAntes from './pages/onboarding/OnbAntes'
import OnbMeta from './pages/onboarding/OnbMeta'
import OnbCultivos from './pages/onboarding/OnbCultivos'
import OnbListo from './pages/onboarding/OnbListo'
import Perfil from './pages/Perfil'
import Rotacion from './pages/Rotacion'
import Terreno from './pages/Terreno'
import Perimetro from './pages/Perimetro'
import Preparando from './pages/Preparando'
import Zonas from './pages/Zonas'
import Especies from './pages/Especies'
import Analisis from './pages/Analisis'
import Historial from './pages/Historial'
import Plan from './pages/Plan'
import Red from './pages/Red'
import Inicio from './pages/Inicio'
import Main from './pages/Main'
import Reportar from './pages/Reportar'
import Observacion from './pages/Observacion'
import Confirmacion from './pages/Confirmacion'
import Alertas from './pages/Alertas'
import Clima from './pages/Clima'
import Fuentes from './pages/Fuentes'

function App() {
  return (
    <I18nProvider>
      <AuthProvider>
        <PredioProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<Portada />} />
              <Route path="/sesion" element={<Sesion />} />
              <Route path="/explorar" element={<Explorar />} />

              <Route path="/onboarding/predio" element={<RutaPrivada><OnbDatos /></RutaPrivada>} />
              <Route path="/onboarding/antes" element={<RutaPrivada><OnbAntes /></RutaPrivada>} />
              <Route path="/onboarding/meta" element={<RutaPrivada><OnbMeta /></RutaPrivada>} />
              <Route path="/onboarding/cultivos" element={<RutaPrivada><OnbCultivos /></RutaPrivada>} />
              <Route path="/onboarding/listo" element={<RutaPrivada><OnbListo /></RutaPrivada>} />

              <Route path="/perfil" element={<RutaPrivada><Perfil /></RutaPrivada>} />

              <Route path="/planificar" element={<RutaPrivada><Rotacion /></RutaPrivada>} />
              <Route path="/terreno" element={<RutaPrivada><Terreno /></RutaPrivada>} />
              <Route path="/terreno/perimetro" element={<RutaPrivada><Perimetro /></RutaPrivada>} />
              <Route path="/terreno/preparando" element={<RutaPrivada><Preparando /></RutaPrivada>} />
              <Route path="/terreno/zonas" element={<RutaPrivada><Zonas /></RutaPrivada>} />
              <Route path="/especies" element={<RutaPrivada><Especies /></RutaPrivada>} />
              <Route path="/especies/analisis" element={<RutaPrivada><Analisis /></RutaPrivada>} />
              <Route path="/historial" element={<RutaPrivada><Historial /></RutaPrivada>} />
              <Route path="/plan" element={<RutaPrivada><Plan /></RutaPrivada>} />
              <Route path="/semillas" element={<RutaPrivada><Red /></RutaPrivada>} />

              <Route path="/hoy" element={<RutaPrivada><Inicio /></RutaPrivada>} />
              <Route path="/cultivo" element={<RutaPrivada><Main /></RutaPrivada>} />
              <Route path="/reportar" element={<RutaPrivada><Reportar /></RutaPrivada>} />
              <Route path="/reportar/observacion" element={<RutaPrivada><Observacion /></RutaPrivada>} />
              <Route path="/reportar/confirmacion" element={<RutaPrivada><Confirmacion /></RutaPrivada>} />
              <Route path="/alertas" element={<RutaPrivada><Alertas /></RutaPrivada>} />
              <Route path="/clima" element={<RutaPrivada><Clima /></RutaPrivada>} />
              <Route path="/fuentes" element={<RutaPrivada><Fuentes /></RutaPrivada>} />
            </Routes>
          </BrowserRouter>
        </PredioProvider>
      </AuthProvider>
    </I18nProvider>
  )
}

export default App
