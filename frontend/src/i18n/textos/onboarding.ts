export const textos: Record<string, { es: string; en: string }> = {
  // portada
  portada_logo_alt: {
    es: 'Logo de mogen: una planta con raíces entre el sol y la lluvia',
    en: 'mogen logo: a plant with roots between the sun and the rain',
  },

  // explorar
  explorar_humedad: { es: 'Humedad', en: 'Humidity' },
  explorar_lluvia: { es: 'Lluvia', en: 'Rain' },
  explorar_viento: { es: 'Viento', en: 'Wind' },
  explorar_hoy_fecha: { es: 'Hoy · {fecha}', en: 'Today · {fecha}' },
  explorar_nov_heladas: { es: 'Heladas', en: 'Frost' },
  explorar_helada_dia: { es: 'Posible el {dia}', en: 'Possible on {dia}' },
  explorar_helada_ninguna: { es: 'Sin heladas esta semana', en: 'No frost this week' },
  explorar_pronostico: { es: 'Pronóstico', en: 'Forecast' },
  explorar_sin_datos: { es: 'No pudimos traer el tiempo de {comuna}. Prueba de nuevo en un rato.', en: 'We could not get the weather for {comuna}. Try again in a while.' },
  explorar_alertas_titulo: { es: 'Alertas de tu predio', en: 'Alerts for your plot' },
  explorar_alertas_ver: { es: 'Ver todas', en: 'See all' },
  explorar_alertas_ninguna: { es: 'Sin cambios fuertes de clima hasta el {fecha}.', en: 'No strong weather changes until {fecha}.' },
  explorar_alertas_sin_datos: { es: 'Todavía no hay clima de tu predio para avisarte.', en: 'There is no weather for your plot yet to warn you.' },
  explorar_alertas_fallo: { es: 'No pudimos revisar el clima de tu predio.', en: 'We could not check the weather for your plot.' },
  alerta_clima_helada: { es: 'Helada', en: 'Frost' },
  alerta_clima_calor: { es: 'Calor fuerte', en: 'Strong heat' },
  alerta_clima_lluvia_fuerte: { es: 'Lluvia fuerte', en: 'Heavy rain' },
  alerta_clima_calentamiento_brusco: { es: 'Sube la temperatura de golpe', en: 'Sudden warm-up' },
  alerta_clima_enfriamiento_brusco: { es: 'Baja la temperatura de golpe', en: 'Sudden cool-down' },
  alerta_clima_helada_fuerte: { es: 'Helada fuerte', en: 'Hard frost' },
  alerta_clima_valor_temp: { es: '{valor}°', en: '{valor}°' },
  alerta_clima_valor_salto: { es: '{valor}° de un día al otro', en: '{valor}° from one day to the next' },
  alerta_clima_valor_lluvia: { es: '{valor} mm en un día', en: '{valor} mm in one day' },
  explorar_fuente_1: { es: 'Pronóstico de modelo, no medición:', en: 'Model forecast, not a measurement:' },

  // onboarding: datos
  onb_datos_titulo: { es: '¿Dónde está tu predio?', en: 'Where is your plot?' },
  onb_datos_sub: {
    es: 'Elige tu comuna. Después marcarás tu predio sobre el mapa, tocando cada esquina.',
    en: 'Choose your municipality. Then you will mark your plot on the map by tapping each corner.',
  },
  onb_datos_sigue_titulo: { es: 'Lo que sigue: marcar tu predio', en: 'Next: mark your plot' },
  onb_datos_sigue_texto: {
    es: 'Verás el mapa de {comuna}. Acércalo hasta tu predio y toca cada esquina para dibujar su contorno. Toma un par de minutos.',
    en: 'You will see the map of {comuna}. Zoom in to your plot and tap each corner to draw its outline. It takes a couple of minutes.',
  },

  // onboarding: qué sembraste antes
  onb_antes_esta: { es: 'Esta temporada', en: 'This season' },
  onb_antes_pasado: { es: 'Año pasado', en: 'Last year' },
  onb_antes_hace2: { es: 'Hace 2 años', en: '2 years ago' },
  onb_antes_papa: { es: 'Papa', en: 'Potato' },
  onb_antes_ajo: { es: 'Ajo', en: 'Garlic' },
  onb_antes_haba: { es: 'Haba', en: 'Fava bean' },
  onb_antes_avena: { es: 'Avena', en: 'Oats' },
  onb_antes_nada: { es: 'Nada', en: 'Nothing' },
  onb_antes_otro: { es: 'Otro', en: 'Other' },
  onb_antes_parcela: { es: 'Sobre tu predio (opcional)', en: 'About your plot (optional)' },
  onb_antes_sector: { es: 'Sector o localidad', en: 'Area or village' },
  onb_antes_sector_ejemplo: { es: 'Por ejemplo, Aucar', en: 'For example, Aucar' },
  onb_terreno_plano: { es: 'Plano', en: 'Flat' },
  onb_terreno_ladera: { es: 'Ladera', en: 'Hillside' },
  onb_terreno_alto: { es: 'Alto', en: 'High ground' },

  // onboarding: cultivos
  onb_cultivos_sub: {
    es: 'De estos cultivos te avisamos etapa por etapa. Para los demás, mira qué conviene sembrar en el análisis de tu terreno.',
    en: 'We alert you stage by stage for these crops. For the others, see what suits your land in the land analysis.',
  },
  onb_cultivos_primero_parcela: {
    es: 'Primero marca tu predio: el seguimiento usa su clima.',
    en: 'First mark your plot: the tracking uses its weather.',
  },
  onb_cultivos_leyenda: { es: 'Cultivos de esta temporada', en: "This season's crops" },
  onb_cultivos_otro: { es: 'Otro', en: 'Other' },
  onb_cultivos_fecha_siembra: { es: 'Fecha de siembra de {especie}', en: 'Planting date for {especie}' },
  onb_cultivos_fecha_nota: {
    es: 'Puede ser una siembra ya hecha (hasta un año atrás) o una planeada (hasta seis meses adelante).',
    en: 'It can be something already planted (up to a year ago) or planned (up to six months ahead).',
  },
  onb_cultivos_error_lista: {
    es: 'No pudimos cargar la lista de cultivos. Revisa tu conexión e inténtalo de nuevo.',
    en: 'We could not load the list of crops. Check your connection and try again.',
  },
  onb_cultivos_error_guardar: {
    es: 'No se pudo guardar tu siembra. Revisa las fechas e intenta otra vez.',
    en: 'We could not save your planting. Check the dates and try again.',
  },

  // onboarding: listo
  onb_listo_falta_titulo: { es: 'Falta marcar tu predio', en: 'Your plot is not marked yet' },
  onb_listo_falta_detalle: { es: 'Sin ella no hay clima ni suelo que analizar', en: 'Without it there is no weather or soil to analyse' },
  onb_listo_mejor_titulo: { es: 'Lo que mejor se da', en: 'What grows best' },
  onb_listo_ninguna_titulo: { es: 'Ninguna especie resultó apta', en: 'No species turned out suitable' },
  onb_listo_ninguna_detalle: { es: 'Revisa el detalle de tu terreno', en: 'Check the details of your land' },
  onb_listo_reuniendo_titulo: { es: 'Reuniendo los datos de tu predio', en: "Gathering your plot's data" },
  onb_listo_reuniendo_detalle: { es: 'Toca para ver el avance', en: 'Tap to see the progress' },
  onb_listo_analizando_titulo: { es: 'Analizando tu terreno…', en: 'Analysing your land…' },
  onb_listo_analizando_detalle: { es: 'Buscando qué se da bien en tu predio', en: 'Looking for what grows well on your plot' },

  // perímetro
  perimetro_sub_comuna: {
    es: 'El mapa muestra {comuna}. Acércalo hasta tu predio y toca cada esquina para dibujar su contorno. Puedes arrastrar una esquina para corregirla.',
    en: 'The map shows {comuna}. Zoom in to your plot and tap each corner to draw its outline. You can drag a corner to fix it.',
  },
  perimetro_sub: {
    es: 'Mueve el mapa hasta tu predio y toca cada esquina. Puedes arrastrar una esquina para corregirla.',
    en: 'Move the map to your plot and tap each corner. You can drag a corner to fix it.',
  },
  perimetro_sin_gps: {
    es: 'Este dispositivo no entrega ubicación. Mueve el mapa hasta tu predio.',
    en: "This device can't give us your location. Move the map to your plot.",
  },
  perimetro_gps_fallo: {
    es: 'No se pudo obtener tu ubicación. Mueve el mapa hasta tu predio.',
    en: "We couldn't get your location. Move the map to your plot.",
  },
  perimetro_error_guardar: {
    es: 'No se pudo guardar el predio. Revisa las esquinas que marcaste e intenta otra vez.',
    en: 'We could not save the plot. Check the corners you marked and try again.',
  },
  perimetro_esquina_una: { es: '1 esquina', en: '1 corner' },
  perimetro_esquinas: { es: '{n} esquinas', en: '{n} corners' },
  perimetro_borrar: { es: 'Borrar', en: 'Clear' },
  perimetro_medida: {
    es: 'Mueve las esquinas: el predio debe medir entre {min} y {max} hectáreas.',
    en: 'Move the corners: the plot must be between {min} and {max} hectares.',
  },

  // reportar
  reportar_fase_brote: { es: 'Brote', en: 'Sprout' },
  reportar_fase_hojas: { es: 'Hojas', en: 'Leaves' },
  reportar_fase_flor: { es: 'Flor', en: 'Flower' },
  reportar_fase_fruto: { es: 'Fruto o raíz', en: 'Fruit or root' },
  reportar_fase_amarilla: { es: 'Amarilla', en: 'Yellowing' },
  reportar_fase_cosecha: { es: 'Cosecha', en: 'Harvest' },
  reportar_sin_cultivo_titulo: { es: 'Todavía no tienes un cultivo', en: "You don't have a crop yet" },
  reportar_sin_cultivo_sub: {
    es: 'Para contarnos cómo va, primero dinos qué sembraste.',
    en: 'To tell us how it is going, first tell us what you planted.',
  },
  reportar_agregar_siembra: { es: 'Agregar qué sembraste', en: 'Add what you planted' },
  reportar_titulo_especie: { es: '¿Cómo está tu {especie}?', en: 'How is your {especie} doing?' },
  reportar_leyenda: { es: 'Elige la foto que más se parece', en: 'Choose the picture that looks most like yours' },

  // observación
  observacion_hoy_por_defecto: {
    es: 'Hoy por defecto. Cámbiala si lo viste otro día.',
    en: 'Today by default. Change it if you saw it on another day.',
  },
  observacion_color_verde: { es: 'Verde', en: 'Green' },
  observacion_color_amarillo: { es: 'Amarillo', en: 'Yellow' },
  observacion_color_seco: { es: 'Seco', en: 'Dry' },
  observacion_senal_una: { es: '{n} señal', en: '{n} sign' },
  observacion_senales: { es: '{n} señales', en: '{n} signs' },

  // confirmación
  confirmacion_en_telefono: { es: 'Tu reporte quedó guardado en tu teléfono y se enviará solo.', en: 'Your report is saved on your phone and will be sent automatically.' },
  confirmacion_corregir: { es: 'Corregir el reporte', en: 'Correct the report' },
  confirmacion_senal: { es: 'Tu aviso ayuda a confirmar lo que se ve en la zona.', en: 'Your notice helps confirm what is seen in the area.' },
  confirmacion_senal_detalle: { es: 'Ya está registrado en tu zona', en: 'It is now recorded for your area' },
  confirmacion_enviado: { es: 'Enviado', en: 'Sent' },
  confirmacion_enviado_detalle: { es: 'Ya está en el registro de tu cultivo', en: 'It is now in your crop record' },
  confirmacion_guardado: { es: 'Guardado', en: 'Saved' },
  confirmacion_en_cola: { es: 'En tu cola, se sube cuando haya señal', en: 'In your queue, it uploads when there is signal' },

  // ruta privada
  ruta_privada_titulo: { es: 'No pudimos conectar', en: "We couldn't connect" },
  ruta_privada_sub: { es: 'Revisa tu conexión e inténtalo de nuevo.', en: 'Check your connection and try again.' },
}
