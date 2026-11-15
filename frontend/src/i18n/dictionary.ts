export type Idioma = 'es' | 'en'

// Diccionario de la interfaz (navegación, botones, títulos y textos compartidos).
// El dato que llega del agricultor o del satélite (nombres de especie, fechas, cifras)
// no se traduce acá: ES/EN cubre el "idioma del agricultor" que pide el handoff para el
// armazón de la app, no una traducción automática de contenido agronómico.
export const diccionario: Record<string, { es: string; en: string }> = {
  // navegación inferior
  nav_hoy: { es: 'Hoy', en: 'Today' },
  nav_cultivos: { es: 'Cultivos', en: 'Crops' },
  nav_reportar: { es: 'Reportar', en: 'Report' },
  nav_planificar: { es: 'Planificar', en: 'Plan' },
  nav_semillas: { es: 'Semillas', en: 'Seeds' },

  // acciones comunes
  volver: { es: 'Volver', en: 'Back' },
  seguir: { es: 'Seguir', en: 'Next' },
  empezar: { es: 'Empezar', en: 'Get started' },
  ya_tengo_cuenta: { es: 'Ya tengo cuenta', en: 'I already have an account' },
  guardar: { es: 'Guardar', en: 'Save' },
  enviar: { es: 'Enviar', en: 'Send' },
  cancelar: { es: 'Cancelar', en: 'Cancel' },
  deshacer: { es: 'Deshacer', en: 'Undo' },
  cerrar: { es: 'Cerrar', en: 'Close' },
  opcional: { es: 'Opcional', en: 'Optional' },
  si: { es: 'Sí', en: 'Yes' },
  no: { es: 'No', en: 'No' },
  cargando: { es: 'Cargando…', en: 'Loading…' },
  reintentar: { es: 'Reintentar', en: 'Retry' },

  // portada / sesión
  mowege_slogan: { es: 'Cuándo sembrar, cuidar y cosechar.', en: 'When to sow, tend and harvest.' },
  telefono: { es: 'Teléfono', en: 'Phone' },
  contrasena: { es: 'Contraseña', en: 'Password' },
  nombre: { es: 'Nombre', en: 'Name' },
  iniciar_sesion: { es: 'Iniciar sesión', en: 'Log in' },
  crear_cuenta: { es: 'Crear cuenta', en: 'Create account' },

  // explorar
  explorar_titulo: { es: 'Explorar tu zona', en: 'Explore your area' },
  lo_nuevo_zona: { es: 'Lo nuevo en tu zona', en: "What's new in your area" },
  datos_predio: { es: 'Datos para tu parcela', en: 'Data for your plot' },
  analisis_terreno: { es: 'Análisis del terreno y qué sembrar', en: 'Land analysis and what to plant' },
  agregar_predio: { es: 'Agregar mi parcela', en: 'Add my plot' },
  seguir_mirando: { es: 'Seguir mirando', en: 'Keep looking' },

  // onboarding
  onb_predio_titulo: { es: 'Tu parcela', en: 'Your plot' },
  onb_comuna: { es: 'Comuna', en: 'Municipality' },
  onb_sector: { es: 'Sector', en: 'Sector' },
  onb_terreno: { es: 'Terreno', en: 'Land' },
  onb_marcar_parcela: { es: 'Marcar mi parcela', en: 'Mark my plot' },
  onb_privacidad_titulo: { es: 'Privacidad', en: 'Privacy' },
  onb_acepto: { es: 'Acepto', en: 'I agree' },
  onb_leer_mas: { es: 'Leer más', en: 'Read more' },
  onb_antes_titulo: { es: '¿Qué sembraste antes?', en: 'What did you plant before?' },
  onb_antes_sub: { es: 'Así sabemos qué le conviene a tu suelo.', en: "That way we know what suits your soil." },
  onb_no_me_acuerdo: { es: 'No me acuerdo', en: "I don't remember" },
  onb_meta_titulo: { es: '¿Qué quieres hacer ahora?', en: 'What do you want to do now?' },
  onb_seguir_cultivo: { es: 'Seguir lo que sembré', en: 'Follow what I planted' },
  onb_seguir_cultivo_sub: { es: 'Avisos y fases de tu cultivo', en: 'Alerts and stages of your crop' },
  onb_elegir_que_sembrar: { es: 'Elegir qué sembrar', en: 'Choose what to plant' },
  onb_elegir_que_sembrar_sub: { es: 'Según tu terreno y el clima', en: 'Based on your land and climate' },
  onb_cambiar_despues: { es: 'Puedes cambiarlo después', en: 'You can change it later' },
  onb_cultivos_titulo: { es: '¿Qué sembraste ahora?', en: 'What are you planting now?' },
  onb_cuando: { es: '¿Cuándo?', en: 'When?' },
  onb_listo_titulo: { es: 'Tu parcela está lista', en: 'Your plot is ready' },
  onb_avisos_titulo: { es: '¿Por dónde te avisamos?', en: 'How should we notify you?' },
  onb_ver_que_sembrar: { es: 'Ver qué sembrar', en: 'See what to plant' },
  onb_ir_a_hoy: { es: 'Ir a Hoy', en: 'Go to Today' },

  // perfil
  perfil_mi_parcela: { es: 'Mi parcela', en: 'My plot' },
  perfil_anio_pasado: { es: 'Año pasado', en: 'Last year' },
  perfil_lo_que_importa: { es: 'Lo que importa', en: 'What matters' },
  perfil_avisos: { es: 'Avisos', en: 'Alerts' },
  perfil_leer_voz_alta: { es: 'Leer en voz alta', en: 'Read aloud' },
  perfil_ayuda_tecnico: { es: 'Ayuda de un técnico', en: 'Help from a technician' },
  perfil_idioma: { es: 'Idioma', en: 'Language' },
  perfil_borrar_datos: { es: 'Borrar mis datos', en: 'Delete my data' },
  perfil_privacidad: { es: 'Privacidad', en: 'Privacy' },
  perfil_cerrar_sesion: { es: 'Cerrar sesión', en: 'Log out' },

  // hoy / inicio
  hoy_mi_perfil: { es: 'Mi perfil', en: 'My profile' },
  hoy_ves_flores: { es: '¿Ves flores en la papa?', en: 'Do you see flowers on the potato?' },
  hoy_fases_luna: { es: 'Fases de la luna', en: 'Moon phases' },
  hoy_saber_williche: { es: 'Saber williche', en: 'Williche knowledge' },
  emergencia_aviso: { es: 'Aviso preventivo de Mowege', en: 'Mowege preventive notice' },
  emergencia_que_hacer: { es: 'Qué hacer', en: 'What to do' },

  // cultivo
  cultivo_titulo: { es: 'Cultivos', en: 'Crops' },
  cultivo_reportar: { es: 'Reportar', en: 'Report' },
  cultivo_fases: { es: 'Etapas', en: 'Stages' },
  cultivo_tizon: { es: 'Tizón', en: 'Blight' },
  cultivo_dias: { es: 'Días', en: 'Days' },
  cultivo_fuentes: { es: '¿De dónde salen estos datos?', en: 'Where does this data come from?' },

  // reportar / observación
  reportar_titulo: { es: '¿Cómo está tu papa?', en: 'How is your potato doing?' },
  reportar_foto: { es: 'Foto', en: 'Photo' },
  reportar_audio: { es: 'Audio', en: 'Audio' },
  reportar_senales: { es: 'Señales', en: 'Signs' },
  observacion_titulo: { es: '¿Qué ves en tu campo?', en: 'What do you see in your field?' },
  observacion_sub: { es: 'Marca lo que viste esta semana', en: 'Mark what you saw this week' },
  observacion_fecha: { es: 'Fecha de registro', en: 'Record date' },
  observacion_color_hojas: { es: 'Color de las hojas', en: 'Leaf colour' },
  observacion_otra: { es: 'Otra', en: 'Other' },
  observacion_indicadores: { es: 'Indicadores de tu zona', en: 'Indicators in your area' },
  observacion_indicadores_sub: { es: 'Marca los que viste en la fecha de arriba', en: 'Mark the ones you saw on the date above' },
  observacion_sin_indicadores: {
    es: 'Tu zona todavía no tiene indicadores definidos. Cuando la comunidad los defina, aparecerán aquí.',
    en: 'Your area has no indicators yet. Once the community defines them, they will appear here.',
  },
  observacion_fuera_de_mes: { es: 'No cuenta en este mes', en: 'Does not count this month' },
  observacion_error_envio: {
    es: 'No pudimos enviar todas las señales. Revisa tu conexión e inténtalo de nuevo.',
    en: 'We could not send all the signs. Check your connection and try again.',
  },
  riego_titulo: { es: 'Riego', en: 'Irrigation' },
  riego_agua: { es: 'Agua en la zona de raíces', en: 'Water in the root zone' },
  riego_umbral: { es: 'se riega bajo', en: 'irrigate below' },
  riego_ultimo: { es: 'último riego', en: 'last irrigation' },
  riego_ya_regue: { es: 'Ya regué hoy', en: 'I irrigated today' },
  riego_anotado: { es: 'Riego de hoy anotado', en: "Today's irrigation recorded" },
  riego_deshacer: { es: 'Deshacer', en: 'Undo' },
  senales_zona_titulo: { es: 'Señales de tu zona', en: 'Signs in your area' },
  senales_zona_origen: { es: 'Conocimiento local · no es un pronóstico', en: 'Local knowledge · not a forecast' },
  senales_zona_vio_uno: { es: 'agricultor lo vio', en: 'farmer saw it' },
  senales_zona_vio_varios: { es: 'agricultores lo vieron', en: 'farmers saw it' },
  senales_zona_en_observacion: {
    es: 'Hay señales reportadas, pero todavía no las confirman suficientes agricultores.',
    en: 'Some signs were reported, but not enough farmers confirm them yet.',
  },
  senales_zona_sin_reportes: {
    es: 'Nadie de tu zona ha reportado señales todavía.',
    en: 'Nobody in your area has reported signs yet.',
  },
  senales_zona_reportar: { es: 'Reportar lo que viste', en: 'Report what you saw' },
  confirmacion_gracias: { es: 'Gracias', en: 'Thank you' },
  confirmacion_actualizado: { es: 'Tu calendario se actualizó.', en: 'Your calendar was updated.' },
  confirmacion_volver_hoy: { es: 'Volver a Hoy', en: 'Back to Today' },

  // alertas / clima
  alertas_titulo: { es: 'Alertas', en: 'Alerts' },
  alertas_emergencias: { es: 'Emergencias', en: 'Emergencies' },
  alertas_cultivo: { es: 'Cultivo', en: 'Crop' },
  alertas_riesgo_semana: { es: 'Riesgo por semana', en: 'Risk by week' },
  alertas_avisos_celular: { es: 'Avisos al celular', en: 'Phone alerts' },
  clima_titulo: { es: 'Clima', en: 'Weather' },
  clima_proximos_dias: { es: 'Próximos días', en: 'Coming days' },

  // planificar
  planificar_titulo: { es: 'Planificar', en: 'Plan' },
  planificar_que_sembrar: { es: '¿Qué sembrar?', en: 'What to plant?' },
  planificar_rotacion: { es: 'Rotación', en: 'Rotation' },
  planificar_analizar_terreno: { es: 'Analizar mi terreno', en: 'Analyse my land' },
  planificar_especies: { es: 'Especies', en: 'Species' },
  planificar_historial: { es: 'Historial', en: 'History' },

  // terreno / perímetro / zonas
  terreno_titulo: { es: 'Tu terreno', en: 'Your land' },
  terreno_zonas_sembrar: { es: 'Mapa de tu parcela', en: 'Map of your plot' },
  terreno_cambiar_perimetro: { es: 'Marcar otra parcela', en: 'Mark another plot' },
  terreno_cambio_20_anios: { es: 'Cómo viene cambiando · 20 años', en: 'How it has been changing · 20 years' },
  terreno_medido: { es: 'Medido en tu parcela', en: 'Measured on your plot' },
  terreno_riesgos: { es: 'Riesgos en tu parcela', en: 'Risks on your plot' },
  perimetro_titulo: { es: 'Marca tu parcela', en: 'Mark your plot' },
  perimetro_paso_punto: { es: 'Ubicación', en: 'Location' },
  perimetro_paso_perimetro: { es: 'Esquinas', en: 'Corners' },
  perimetro_toca_esquinas: { es: 'Toca las esquinas de tu parcela', en: "Tap your plot's corners" },
  perimetro_usar_ubicacion: { es: 'Usar mi ubicación', en: 'Use my location' },
  perimetro_analizar: { es: 'Analizar mi parcela', en: 'Analyse my plot' },
  zonas_titulo: { es: 'Mapa de tu parcela', en: 'Map of your plot' },
  zonas_conviene: { es: 'conviene', en: 'works well' },

  // especies / análisis
  especies_titulo: { es: 'Qué sembrar', en: 'What to plant' },
  especies_si_clima_cambia: { es: 'Si el clima cambia…', en: 'If the climate changes…' },
  especies_nada: { es: 'Nada', en: 'Nothing' },
  especies_algo: { es: 'Algo', en: 'Some' },
  especies_mucho: { es: 'Mucho', en: 'A lot' },
  especies_precision: { es: 'Confianza', en: 'Confidence' },
  analisis_compatible: { es: 'Compatible con tu terreno', en: 'Compatible with your land' },
  analisis_variedad: { es: 'Variedad', en: 'Variety' },
  analisis_rendimiento: { es: 'Cuánto rinde si el clima…', en: 'Yield if the climate…' },
  analisis_sigue_igual: { es: 'Sigue igual', en: 'Stays the same' },
  analisis_cambia_algo: { es: 'Cambia algo', en: 'Changes a bit' },
  analisis_cambia_mucho: { es: 'Cambia mucho', en: 'Changes a lot' },
  analisis_sus_fases: { es: 'Sus fases', en: 'Its stages' },
  analisis_usar_plan: { es: 'Usar en mi plan', en: 'Use in my plan' },

  // historial / plan / red
  historial_titulo: { es: 'Lo que sembraste', en: 'What you planted' },
  historial_agregar_temporada: { es: 'Agregar temporada', en: 'Add season' },
  historial_que_siembro: { es: '¿Qué siembro ahora?', en: 'What should I plant now?' },
  plan_titulo: { es: 'Tu plan', en: 'Your plan' },
  plan_tienes_semilla: { es: '¿Tienes semilla?', en: 'Do you have seed?' },
  plan_buscar: { es: 'Buscar', en: 'Search' },
  plan_guardar: { es: 'Guardar plan', en: 'Save plan' },
  plan_cambiar: { es: 'Cambiar', en: 'Change' },
  red_titulo: { es: 'Semillas', en: 'Seeds' },
  red_anonimo: { es: 'Anónimo', en: 'Anonymous' },
  red_piden: { es: 'Piden', en: 'Requests' },
  red_mis_pedidos: { es: 'Mis pedidos', en: 'My requests' },
  red_tengo: { es: 'Tengo', en: 'I have it' },
  red_pedir_semilla: { es: 'Pedir semilla', en: 'Request seed' },

  // fuentes
  fuentes_titulo: { es: '¿De dónde salen los datos?', en: 'Where does the data come from?' },
  fuentes_que_tan_seguro: { es: 'Qué tan seguro es', en: 'How reliable is this' },
  fuentes_mas_precision: { es: 'Datos más exactos: marca tu parcela', en: 'More accurate data: mark your plot' },
}

export function traducir(idioma: Idioma, clave: string): string {
  const entrada = diccionario[clave]
  if (!entrada) return clave
  return entrada[idioma]
}
