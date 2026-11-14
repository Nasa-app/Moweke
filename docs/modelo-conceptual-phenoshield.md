# Mogewe — Modelo conceptual consolidado

Documento de referencia para la postulación a NASA Space Apps Challenge. Consolida el diseño conceptual completo trabajado hasta ahora. No es código — es la especificación sobre la cual se implementa.

---

## 1. Resumen ejecutivo

### Contexto: por qué esto es más urgente ahora, no solo "importante en general"

El CR2 (Centro de Ciencia del Clima y la Resiliencia, U. de Chile) documentó un déficit de precipitación sostenido desde 2010 en Chile central (30°-40°S) — la "megasequía". Chiloé (42-43°S) queda fuera de esa zona definida, pero no está exento de cambio: hay inviernos puntuales con déficits de 40-50% registrados entre Ñuble y Los Lagos, y los especialistas señalan que desde Los Lagos hacia el sur El Niño deja de ser el principal driver de las lluvias de invierno. Esto significa que el régimen climático de Chiloé está empezando a moverse, y la ciencia climática chilena —concentrada en entender la sequía de la zona central— todavía no tiene el mismo nivel de resolución para esa zona específica.

El problema de fondo: dos sistemas de referencia que la comunidad usa para decidir —costumbre local y baseline científico regional— están perdiendo precisión al mismo tiempo, y ninguno se actualiza con la frecuencia que el problema necesita.

### Mecanismo: recalibración cada temporada, no corrección de una vez

El sistema no asume que el dato satelital es correcto y el agricultor lo corrige, ni al revés. Cada temporada compara lo que mide el satélite contra lo que reporta la comunidad, y de ahí salen tres resultados posibles (no dos — ver sección 7.3):

1. **Ajuste de calendario** — la desviación es manejable moviendo fechas; la variedad sigue siendo viable.
2. **Sugerencia de variedad** (solo si aún no se ha sembrado) — la desviación es tan grande que ningún ajuste de fecha deja segura a la variedad actual.
3. **Mitigación de manejo** (si ya se sembró) — la variedad ya no es una variable disponible, solo el manejo del cultivo en curso.

### Por qué el dato de campo no es opcional

No hay calendario térmico ni fotoperiódico publicado para variedades Chilotanum, no hay estaciones meteorológicas confirmadas dentro de Chiloé, y la resolución satelital no resuelve el tamaño de un predio minifundista. El dato de campo no complementa un dato bueno que ya existe en otro lado — en varias partes del sistema es el único dato que existe.

---

## 2. Extrapolación regional (argumento de escalabilidad)

El mismo patrón estructural —referencias climáticas que cambian de comportamiento, no solo de magnitud— se repite en Latinoamérica con mecanismos distintos por región. La arquitectura es portable; las variables de entrada no.

| Región | Mecanismo específico | Evidencia | Variable que reemplazaría a la de Chiloé |
|---|---|---|---|
| Andes (Perú/Bolivia) | ENSO cambiando de carácter bajo calentamiento global | Orlove, Chiang & Cane (2000, *Nature*): agricultores leen visibilidad de las Pléyades como proxy de El Niño desde hace ~400 años; GFDL/NOAA documenta intensificación y asimetría de teleconexiones ENSO | Anomalía climática POWER + altitud (ver 6.2) |
| Corredor Seco centroamericano | Desplazamiento de temporada de lluvias | IPCC AR6 cap. 12: alta confianza en impacto sobre agricultura de secano; FAO ya desplegó ZARC (zonificación de riesgo climático) en 3 países | Desfase de inicio de lluvias (IMERG) |
| Amazonía | Deforestación local, no solo calentamiento global | Nature Communications (2025): ~75% de la reducción de lluvia amazónica se explica por deforestación directa; estación seca extendida >1 mes desde los 70s | Pérdida de cobertura forestal en buffer (HLS/EVI) |
| Sudeste sudamericano (pampas) | Contraejemplo: más lluvia media, pero sequías extremas más frecuentes | IPCC AR6: no es uniformemente "más seco", es más variable en ambas direcciones | — |

---

## 3. Evaluación honesta de utilidad

El sistema no reemplaza la observación directa del agricultor sobre su propio cultivo — eso lo ve mejor que cualquier sensor remoto. El valor real se concentra en tres cosas que un agricultor, por buena que sea su observación, no puede construir solo:

1. **Comparación contra el resto de la comuna** — distingue si un desfase es de su parcela específica o de toda la zona (decide si la respuesta correcta es arreglar drenaje o cambiar de variedad).
2. **Anticipación antes del síntoma** — proyecta riesgo de tizón/helada antes de que aparezca, algo que la observación del presente no puede hacer.
3. **Conexión con otros agricultores de la red para conseguir semilla alternativa** — es un problema de información/logística, no de percepción agronómica.

Lo que NO agrega valor: confirmarle al agricultor lo que él mismo reportó, o decirle el estado actual de su planta.

---

## 4. Catálogo de datos NASA — verificado, no asumido

### 4.1 Fuentes con fidelidad alta, uso directo

| Fuente | Resolución | Rol en el modelo | Nota de fidelidad |
|---|---|---|---|
| NASA POWER (temperatura, precipitación IMERG, RH2M, radiación ALLSKY_SW) | ~55-70km (meteo), 10km (precip) | GDD, riesgo de tizón, radiación para idoneidad de sitio | Bien validado para temperatura; precipitación con sesgo que varía por región |
| SMAP L4 | 9km | Anomalía regional de humedad de suelo (rol secundario desde que se incorporó RH2M) | RMSE ~0.026 m³/m³ documentado — exacto para lo que mide, proxy débil de humectación foliar |
| HLS (Harmonized Landsat-Sentinel) | 30m, revisit 1.4-3 días | Monitoreo operativo de la temporada (EVI/NDVI), buffer forestal/cobertura | Depende en parte de Sentinel-2 (ESA) para su mejor revisit — ver nota en 4.3 |
| MOD13Q1/MYD13Q1 | 250m, 16 días | Baseline histórico continuo (desde 2000) para detección de anomalía de curva | Complementa a HLS, no lo reemplaza |
| ECOSTRESS | ~70m, revisit irregular (orbita ISS) | Evapotranspiración para motor de rotación | Cobertura temporal irregular — puede haber vacíos de varios días |
| GRACE/GRACE-FO | ~300km | Tendencia regional de almacenamiento de agua (contexto, no dato de predio) | Nunca se usa como capa espacial de grilla fina |
| SRTM | 30m | Elevación y pendiente derivada (erosión, rama andina) | Estático, sin latencia |
| MCD12Q2 | 500m, anual retrospectivo | Baseline de paisaje forestal, NUNCA fenología de cultivo | Capa de control de calidad propia marcada como no confiable por LP DAAC |
| VNP13A1/VJ113A1 (VIIRS NDVI/EVI, no confundir con VNP22Q2) | 500m, 16 días | Respaldo de continuidad del baseline histórico | VNP13A1 v1 descontinuado abril 2025, usar v2. Corre en NOAA-20 (VJ113A1), no solo Suomi NPP — sin el riesgo de sunset de VNP22Q2 |

### 4.2 Descartado, con razón documentada

- **VNP22Q2** (VIIRS Land Surface Phenology): entrega de datos Suomi NPP VIIRS termina 2 nov 2026. No se adopta.
- **ONI** (NOAA): no es NASA. Reemplazado por anomalía climática calculada directo de la serie histórica de POWER.
- **Hansen Global Forest Change** (U. Maryland): no es NASA. Reemplazado por serie temporal NDVI/EVI de HLS en el buffer.
- **Sentinel-3 OLCI** (ESA): no es NASA. Reemplazado por MODIS-Aqua (OBPG) para clorofila marina; PACE (NASA, 2024) como opción más moderna a mencionar.

### 4.3 Advertencia transparente

HLS combina Landsat (NASA/USGS) con Sentinel-2 (ESA). El producto lo procesa y distribuye NASA — aceptable como "dato NASA" en el contexto de Space Apps — pero su mejor revisit depende en parte del sensor ESA. Versión purista (solo Landsat) existe, con revisit de 8-16 días en vez de 1-3.

### 4.4 Estado real de implementación — verificado en código, no solo en catálogo

Esta sección existe porque el catálogo de 4.1/10.1 describe lo que se investigó como viable; no todo lo investigado terminó implementado, y varias fuentes reales que SÍ se implementaron no estaban en el catálogo original. Lista real, por archivo:

| Fuente | Cliente real | Estado |
|---|---|---|
| NASA POWER | `services/cliente_power.py` | ✅ Verificado — incluye `radiacion` (ALLSKY_SFC_SW_DWN), agregada tras encontrar que nunca se pedía |
| CR2MET (CR2/U. de Chile) | `services/cliente_cr2met.py` | ✅ Verificado — reemplaza/complementa a POWER para clima diario de Chile, mejor calibrado localmente, ~9 días de latencia real medida |
| AppEEARS (HLS, SMAP, ECOSTRESS, Landsat nativo) | `services/cliente_appeears.py` | ✅ Verificado — login por usuario/clave real (el "user token" de EDL NO funciona federado, da 403); NDVI/NDMI/EVI/SAVI/NBR/índices minerales desde bandas HLS reales; LST de Landsat 8/9 dio vacío real para Chiloé (sin gránulos válidos, no es bug) |
| Copernicus Data Space / Sentinel Hub (Sentinel-1/2) | `services/cliente_copernicus.py` | ✅ Verificado — OAuth client_credentials real; Statistical API da NDVI/backscatter agregados sobre el polígono real de la parcela (única fuente que usa el polígono, no el centroide) |
| CLSoilMaps (agua disponible de suelo) | `services/cliente_clsoilmaps.py` | ✅ Verificado — extrae solo el archivo necesario (328MB) de un zip remoto de 10GB vía HTTP Range, sin descargar el resto |
| SoilGrids (pH, textura, carbono orgánico) | `services/cliente_soilgrids.py` | ✅ Verificado — reemplaza al rol que 10.1 le daba a CHLSOC/SoilGrids conceptualmente; API de consulta puntual real, sin descarga |
| Explorador Solar (MinEnergía Chile) | `services/cliente_solar.py` | ✅ Verificado — endpoint no documentado públicamente, encontrado inspeccionando el mapa interactivo |
| NASA FIRMS (focos de calor) | `services/cliente_firms.py` | ✅ Verificado con clave real — 0 focos reales en Chiloé (primavera), focos reales con FRP>0 confirmados en otra zona/fecha |
| FAO EcoCrop | `database/importar_ecocrop.py` | ✅ Verificado — 2068 especies reales importadas, ver 8.3 |
| **FAO GAEZ** | — | ❌ **Investigado extensamente (ver 10.1.1), nunca implementado en código.** La decisión real de este proyecto fue cubrir el rol de "escenario climático"/terreno con CR2MET + Sentinel-1/2 + SoilGrids + CLSoilMaps en su lugar, no con GAEZ. Si se retoma GAEZ, falta todo: `services/cliente_gaez.py` no existe. |
| **CHLSOC** | — | ❌ Mencionado en 10.1 como preferible a SoilGrids para Chile; nunca se implementó, se usó SoilGrids directo. |
| **WWF Terrestrial Ecoregions** | — | ❌ Solo conceptual. `ecoregion_wwf` existe en el schema pero vacía a propósito (MVP fija `bioma_tipo='templado_costero'`, ver 10.2). |
| GRACE/GRACE-FO, GEDI, GLDAS, MCD12Q2, VNP13A1 | — | ❌ Solo conceptuales, sin cliente real todavía. |

---

## 5. Grilla de análisis — referencia de consulta, no raster fusionado

**Por qué no se pre-fusiona todo**: cada fuente vive en su propia proyección nativa (HLS/SRTM en UTM, MODIS en sinusoidal, SMAP en EASE-Grid 2.0, POWER/IMERG/GRACE en lat/lon). Fusionar de antemano generaría archivos enormes que solo repiten el mismo valor grueso en miles de celdas finas.

**Definición**: referencia de coordenadas UTM 18S (zona correcta para Chiloé), celdas de 30m alineadas al tiling nativo de HLS/MGRS. Cada capa se consulta contra esa referencia en el momento de la consulta, no se pre-calcula.

**Reglas de muestreo**:
- Capas finas (HLS, SRTM — más chicas que el predio): estadística zonal real (media/mediana) sobre el polígono.
- Capas gruesas (SMAP, POWER, GRACE — más grandes que el predio): muestreo por centroide, sin promediar entre celdas vecinas.

**Binning temporal**: ventana común de 16 días (estándar de MOD13Q1). Dentro de esa ventana: POWER/SMAP se agregan a su media; IMERG se acumula; HLS toma la mejor pasada libre de nubes disponible o queda marcado vacío; MCD12Q2 constante todo el año; GRACE constante todo el mes.

**Ficha de procedencia por valor**:
```
valor_grilla = {
  valor, resolucion_nativa, version_producto,
  periodo: {inicio, fin}, cobertura: "completa"|"parcial_nubes"|"sin_dato"
}
```

---

## 6. Modelo de datos

Schema real y vigente: `database/schema.sql`. No se duplica aquí para evitar que las dos copias se desincronicen — ya pasó una vez en este proyecto.

Dos decisiones de esa versión que no estaban en el diseño original y vale la pena explicar el porqué:

- **`parcela` separada de `predio_cultivos`**: `parcela` es el terreno, estable a través de temporadas. `predio_cultivos` es un ciclo de cultivo dentro de esa parcela. El motor de rotación (sección 8) compara secuencias de cultivos sobre la misma tierra a través del tiempo — eso no se puede consultar si el terreno y el ciclo actual son la misma fila.
- **`bioindicador_observado` separada de `fenologia_observada`**: el Ulmo y el zarapito (sección 10) no pertenecen a un ciclo de cultivo, pertenecen a quien los observa y a su zona. Forzarlos a referenciar un cultivo no reflejaba el diseño.
- **`unidad_administrativa_local`** reemplaza a "comuna" en todo el schema — término genérico para que el sistema funcione fuera de Chile sin reescribir el modelo de datos (ver sección 10.1.2).

**Nota de privacidad**: ninguna vista pública (`vista_publica_alerta`, `vista_publica_respuesta`) expone la FK hacia `parcela`/`usuarios` ni la geometría exacta. Lo que ve otro agricultor de una alerta: `{especie, caracteristicas_requeridas, unidad_administrativa_local, fecha_creacion}`. El contacto real ocurre fuera del sistema.

---

## 7. Motor fenológico (`pheno_engine`)

### 7.1 El cruce de tres señales (base de todo)

Cada transición BBCH (siembra→BBCH09, BBCH09→BBCH65, BBCH65→BBCH97) se evalúa cruzando:
1. **GDD acumulado** desde la última etapa *confirmada* (no desde la siembra original) contra el umbral de `umbral_fenologico_config`.
2. **Curva óptica** (HLS/EVI actual contra histórico MOD13Q1) vía `detect_curve_anomaly(evi_actual_hls, evi_historico_mod13q1) -> dias_adelanto_curva` — señal temprana, antes de llegar a un hito discreto.
3. **Reporte de campo del agricultor** — autoritativo en caso de conflicto con las dos señales anteriores.

Al llegar a ~80% del GDD mínimo esperado se abre una "ventana expectante" donde el monitoreo óptico se activa. El fotoperiodo (`horas_luz_criticas`) se aplica como ajuste independiente, específicamente sobre la transición BBCH65→BBCH97 (floración→maduración/tuberización) — es el punto donde la ciencia agronómica real ubica el efecto de longitud del día en papa, no en todo el ciclo.

### 7.2 Dispatcher por bioma — 100% NASA

```
andino_altura      → get_climate_anomaly_shift_power(temp_anomalia_power, precip_anomalia_power, altitud_msnm)
corredor_seco       → get_rain_onset_shift(imerg_inicio_real, power_historico_unidad_administrativa)
amazonico           → get_forest_loss_shift_nasa(evi_serie_temporal_buffer_hls)
templado_costero    → get_calibrated_calendar_shift(ground_truth_bosque_mareas, mcd12q2_baseline, modis_chla_bloom)
```

Las Pléyades (Andes) y el Ulmo (Chiloé) son referencias culturales que validan el concepto — entran como ground truth opcional si alguien las reporta, nunca como dependencia obligatoria del motor.

### 7.3 Fase de decisión — tres salidas, no dos

El tipo de salida depende de si ya se sembró, no solo de la severidad del desfase:

- `fecha_hoy < fecha_siembra` → `calendario_ajustado` o `sugerencia_variedad` (la variedad todavía se puede cambiar).
- `fecha_hoy >= fecha_siembra` → solo `mitigacion_manejo` (la variedad ya no es una variable disponible); si la severidad es roja, se agrega `preparar_proxima_temporada: true`, que dispara automáticamente una `alerta_busqueda_variedad` para la siembra que viene, no para la actual.

### 7.4 Confianza — componentes continuos, no cuatro escalones fijos

Revisión tras incorporar `services/pheno_engine.py`: la jerarquía categórica original (`calibrado_predio` → `calibrado_comunal` → `referencia_local` → `sin_referencia`) queda reemplazada por `confianza()`, que toma componentes continuos (0-1) y reporta el más débil por nombre:

```python
confianza({
    "anos_indicador": 0.45,       # cuantos años de observación tiene el indicador local calibrado
    "param_variedad": 0.6,        # qué tan calibrado está el umbral GDD de esa variedad (vs. placeholder_sin_validar)
    "suelo_ingresado": 0.9,       # SoilGrids/CHLSOC/GAEZ disponible vs. sin fuente
    "acuerdo_modelos": 0.8,       # coincidencia entre señal térmica y curva EVI/HLS
})
# -> {"nivel": "A"|"B"|"C", "limitante": "anos_indicador", "valor": 0.45}
```

Esto es mejor que la versión categórica porque dice *cuál* dato es el limitante, no solo un nivel general — "A/B/C" se derivan de este cálculo, no al revés. Cada componente sigue el mismo principio de antes (revisar nivel comunal/regional antes de asumir cero información; una parcela sin historial propio no es lo mismo que toda su zona sin ningún reporte), pero expresado como un número que se puede mezclar con otros, no como una categoría cerrada.

### 7.5 Calendario dinámico

```
calendario_predio = {
  etapa_actual, 
  etapas_proyectadas: [{ etapa, ventana: {inicio, fin}, confianza }],
  delta_microclima,  -- de pheno_engine.delta_microclima: correccion de TEMPERATURA calibrada con un
                       -- indicador local (no un offset de dias — se traslada correctamente a
                       -- cualquier cultivo evaluado en la misma parcela, porque entra al calculo de GDD)
  ultima_actualizacion: {fecha, fuente}
}
```

Ventanas más anchas cuanto más lejos en el tiempo (incertidumbre compuesta). Dos disparadores de recálculo: pull nocturno de POWER (silencioso, no notifica) y reporte de ground truth (sí notifica). Umbral de materialidad: solo se avisa al agricultor si el cambio cruza un límite de semáforo o mueve la ventana más de un margen mínimo — nunca por ruido diario. Si falta un reporte de campo en una etapa, el sistema sigue proyectando con la estimación de solo-GDD, marcada `no_confirmada_por_campo`, en vez de congelarse.

### 7.6 Alertas específicas (output consolidado)

```
alertas_especificas: {
  riesgo_helada_tardia: bool,          -- GDD acelerado + ventana histórica de helada aún abierta
  riesgo_tizon: "bajo"|"medio"|"alto", -- de get_blight_risk(temp, precip, RH2M) -- RH2M, no SMAP, es el insumo principal
  ventana_polinizador: {...} | null,   -- solo si especie == "haba"
  posible_confusion_manejo: bool       -- si hay un evento en manejo_predio que podría explicar el desfase en vez del clima
}
```

---

## 8. Motor de rotación (`rotation_engine`)

Requisito central del brief NASA sobre rotación de cultivos: comparar al menos tres estrategias (incluida la actual), cada una con evidencia, beneficios, vacíos de información y riesgos que requieren revisión local.

### 8.1 Cómo consume al motor fenológico y a la grilla

Para cada cultivo de una secuencia candidata (ej. papa→haba→ajo), primero se pide a `pheno_engine` el calendario de ese cultivo (reutiliza todo lo de la sección 7). Con esas ventanas:

```
dias_suelo_desnudo = ventana_siembra[N+1].inicio - ventana_BBCH97[N].fin
confirmacion = grilla.consultar("HLS_EVI", predio, {ventana_suelo_desnudo}, "zonal_mediana")
-- si cobertura == "sin_dato": se usa solo la resta de fechas, NUNCA se asume "sin riesgo" por falta de señal

et_acumulada = grilla.consultar("ECOSTRESS_ET", predio, ventana_crecimiento[cultivo], "zonal_media")
pendiente = grilla.consultar("SRTM_pendiente", predio, periodo=null, "zonal_media")
riesgo_erosion = combinar(pendiente, dias_suelo_desnudo, intensidad_lluvia_ventana_desnuda)
```

### 8.2 Idoneidad de sitio — cultivo vs. condiciones reales, no solo demanda

```
requisitos_especie(especie)              -- rango necesario: humedad, luz, suelo
condiciones_sitio(predio, ventana)        -- disponible: SMAP, POWER_ALLSKY_SW, fotoperiodo, suelo (si hay fuente)

calcular_idoneidad(especie, predio, ventana) -> {
  match_humedad: "adecuado"|"deficit"|"exceso",
  match_luz: "adecuado"|"insuficiente",
  match_suelo: "adecuado"|"no_evaluado",   -- nunca se inventa un valor si no hay fuente
  score_idoneidad: promedio_ponderado(solo variables con match != "no_evaluado"),
  completitud_score: n_evaluadas / n_totales
}
```

Pesos por defecto (humedad > luz, ~60/40) son supuesto razonable, no calibrado — viven en `umbral_fenologico_config`, no fijos en código.

**Implementación real: `catalogo_especies.calcular_idoneidad()`, no el pseudocódigo de arriba.** Difiere del diseño conceptual en un punto importante: para una especie con `umbral_fenologico_config` (nivel `perfil_fenologico_regional`+), NO compara un promedio de temperatura del sitio contra `tb`/`tc` — corre la simulación real (`pheno_engine.simular()` + `motor_estres.evaluar()`) con la serie diaria de clima real, para que la supervivencia ante un evento dependa de EN QUÉ FASE ocurre (`regla_dano_especie.fase`), no de si el promedio cruza el umbral en algún momento. Esto se corrigió tras un bug real: papa daba "no apta" por una helada puntual que en la simulación real solo causa un atraso de 14 días, no la mata. El chequeo por promedio (pH, tmin/tmax, y ahora también `humedad_suelo_minima/maxima` contra el agua disponible real del sitio) queda como respaldo solo para especies sin datos de fase (la mayoría de EcoCrop) o cuando el rango de clima disponible no alcanza para simular un ciclo completo. Acepta `(especie, variedad_local)`, no solo el nombre de especie — aunque hoy (verificado) ninguna fila real tiene `variedad_local` poblado todavía.

### 8.3 Madurez de la especie — separa "¿calza aquí?" de "¿cuándo se siembra?"

```
"sin_perfil"                 -- no se puede evaluar nada
"perfil_generico"             -- requisitos_especie/rasgos_rotacion_especie existen (literatura general) → idoneidad de sitio sí, calendario NO
"perfil_fenologico_regional"  -- umbral_fenologico_config existe, aunque sea placeholder → calendario ancho, confianza baja
"perfil_calibrado"            -- ground truth real acumulado
```

Una especie nueva (típicamente llegada vía `alerta_busqueda_variedad`) entra en `sin_perfil`; sube a `perfil_generico` con el conocimiento informal de quien la ofrece.

**Primera fuente masiva real en `perfil_generico`: FAO EcoCrop** (`database/importar_ecocrop.py` → `database/seed_ecocrop.sql`, extensión post-MVP). 2068 especies con `tb`/`t_optima`/`tc`/`ph_suelo_min`/`ph_suelo_max` reales, más 676 con una regla de helada derivada de su `KTMP` (temperatura letal, definición propia de EcoCrop). `fuente = 'FAO_EcoCrop_opinion_experta'` — deliberadamente distinto de `'placeholder_sin_validar'` (sin fuente) y de `'INIA_ficha_tecnica'`/`'CIREN_ficha_tecnica'` (medición real): los propios mantenedores de EcoCrop advierten que son valores de opinión experta, no mediciones. Verificado cruzando contra lo ya calibrado a mano: `tb` de `solanum_tuberosum`/`allium_sativum`/`vicia_faba` coincide casi exacto con papa/ajo_chilote/haba (±1°C), pero `t_optima`/`tc` se alejan bastante (ej. ajo: 24/35 EcoCrop vs. 17.5/30 INIA) — consistente con "opinión global genérica" vs. "calibrado para Chile", confirma por qué el nivel de fuente debe quedar separado. Ninguna de estas 2068 filas toca `rasgos_rotacion_especie` (EcoCrop no tiene mes de siembra ni intervalo de rotación) — quedan en `perfil_generico`, sirven para idoneidad de sitio, no para comparación de rotación.

**Implementación real: `services/catalogo_especies.py`.** Hasta este punto `CULTIVOS`/`PERFIL`/`REGLAS` eran diccionarios escritos a mano en Python — incorporar una especie significaba que alguien programara. Este módulo construye `Cultivo` (pheno_engine), la entrada de `PERFIL` (motor_rotacion) y las reglas de daño (motor_estres) directo desde `requisitos_especie`/`umbral_fenologico_config`/`rasgos_rotacion_especie`/`regla_dano_especie`, sin tocar código. Verificado con una especie que nunca existió en ningún diccionario de Python: construida solo con filas de datos, corrió un calendario fenológico completo.

La jerarquía de madurez decide qué función se puede llamar, no solo qué etiqueta mostrar: `calcular_idoneidad()` solo necesita `requisitos_especie` (nivel `perfil_generico`); `construir_cultivo()` necesita además `umbral_fenologico_config` (nivel `perfil_fenologico_regional` o superior) y falla explícito — `EspecieSinPerfilFenologico`, no un número inventado — si falta. Una especie sin filas en `regla_dano_especie` no queda "sin riesgo": `motor_rotacion.evaluar_cultivos()` la trata igual que a la pradera, con el relleno neutro de los cultivos sí modelados.

**Aporte proactivo de características de variedad — la función de guardián sin el rol institucional.** No hace falta esperar una alerta: cualquier agricultor que siembra una variedad local puede describir sus características (ciclo, tolerancia a sequía, resistencia a tizón) vía `caracteristica_variedad_aportada`, por el mismo canal de reporte de campo (voz/foto/texto). Esto es lo que evita que una variedad local que nunca va a aparecer en GAEZ ni en una ficha de INIA se quede para siempre en `sin_perfil`.

Un solo aporte no basta — la taxonomía campesina de nombres de variedad no siempre es consistente entre predios, ni dentro de la misma comuna. `requisitos_especie`/`rasgos_rotacion_especie` se actualiza con `fuente='conocimiento_tradicional_agricultor'` solo cuando varios aportes independientes coinciden en lo esencial, mismo patrón de umbral mínimo que el resto de la jerarquía de confianza. Esto también protege contra un reporte de mala fe (exagerar la resistencia de una semilla para colocarla vía una alerta): un aporte aislado no mueve el dato por sí solo.

### 8.4 Prioridades del agricultor

```
prioridades_agricultor = { id_parcela, prioridad_agua, prioridad_ingreso, prioridad_suelo, restricciones_equipo }
```

El sistema no elige la mejor rotación — reordena las estrategias comparadas según lo que el agricultor marcó como importante.

### 8.5 Salida de la comparación — implementada en `services/motor_rotacion.py`

Esto reemplaza la descripción genérica que teníamos (`evidencia` con cuatro campos sueltos) por lo que de verdad calcula `buscar()`: genera todas las secuencias de 3-5 temporadas entre los cultivos viables de la parcela —incluyendo **pradera/barbecho como opción explícita**, no solo "sembrar algo"—, descarta las que violan una regla dura, y puntúa el resto con cinco criterios:

```
criterios = {
  riesgo,       -- 1 - pérdida media esperada (de services/motor_estres.evaluar, por fase x peligro)
  peor_ano,     -- 1 - pérdida del año más adverso (robustez, no solo promedio)
  diversidad,   -- cultivos distintos / largo de la secuencia
  precedente,   -- bonifica leguminosa antes de cultivo exigente, penaliza repetir familia botánica
  cobertura,    -- fracción de días con cultivo vivo vs. suelo desnudo (reemplaza a
                   dias_suelo_desnudo_estimado como criterio de puntaje, no solo alerta de erosión)
}
puntaje_total = suma_ponderada(criterios, PESOS)  -- PESOS default: riesgo 35%, peor_año 20%,
                                                      diversidad 15%, precedente 15%, cobertura 15%
```

Una secuencia vale lo que vale en su **peor escenario climático evaluado**, no en el promedio — evita recomendar algo que falla justo en la temporada mala. `ruptura_ciclo_patogeno` (booleano que teníamos antes) se reemplaza por `intervalo` — temporadas mínimas antes de repetir un cultivo, por especie, que se alarga si hay inóculo/enfermedad declarada en `manejo_predio` (`extra_intervalo`).

**Peligros modelados en `motor_estres.py`**, por fase del cultivo: helada, calor, sequía, anegamiento, lluvia en cosecha, y **ceniza volcánica** — relevante en Chile por actividad volcánica activa, se reporta como evento externo (no viene de ningún dato satelital que tengamos integrado), no de clima.

**Advertencia operativa real, no teórica**: un cultivo sin reglas de daño definidas en `REGLAS` no tiene "riesgo cero" — `evaluar_cultivos()` lo trata igual que a la pradera (sin modelo, relleno con el riesgo medio de los cultivos sí modelados). Esto se encontró como bug real al incorporar ajo chilote y haba, que no tenían reglas hasta corregirlo — sin el fix, habrían ganado cualquier comparación contra papa no por ser mejores, sino por no tener riesgo modelado.

`vacios_informacion` sigue incluyendo siempre el estado real de madurez de cada especie de la secuencia y la ausencia confirmada de dato de suelo público — nunca se omite para que el resultado se vea más completo de lo que es.

**Limitación conocida, no resuelta**: `prioridades_agricultor` todavía no puede pesar selectivamente "riesgo de sequía" por separado de "riesgo de helada" dentro del criterio `riesgo` — no está descompuesto por tipo de peligro. Un agricultor que marca `prioridad_agua` alta no logra, con el diseño actual, que el sistema le dé más peso específicamente al riesgo hídrico.

---

## 9. Red de alertas de variedad (sustituye a "guardadoras" como institución)

Se descartó el modelo original de banco de semillas con rol de "guardadora" designada. En su lugar: cualquier agricultor de la red puede pedir (`alerta_busqueda_variedad`) o responder (`respuesta_alerta`), scoped por unidad administrativa local o radio de 30km (`ST_DWithin`), sin inventario permanente que mantener.

**Lo que se gana**: cero fricción de catalogación previa, sin rol institucional separado, menor exposición de privacidad (no hay mapa público permanente).
**Lo que se pierde**: la narrativa específica de "guardadoras" como institución biocultural con nombre propio — se puede mencionar en la postulación que es probable que sean quienes respondan más seguido, pero ya no es una estructura de datos propia.

---

## 10. Vacíos de información — estado actualizado tras verificación de fuentes abiertas

### 10.1 Resueltos o mejorados

- **Tipo de suelo y pH**: **SoilGrids (ISRIC) — implementado y verificado** (`services/cliente_soilgrids.py`, v2.0 REST real, sin auth). pH/textura/carbono orgánico confirmados para la parcela de prueba de Chiloé (pH 5.3, franco-arenoso, 22.5% carbono orgánico — plausible para andisol volcánico). **CHLSOC nunca se implementó** — quedó como mención conceptual, se usó SoilGrids directo. `match_suelo` deja de ser `"no_evaluado"` por default cuando hay cobertura de SoilGrids para ese punto (confirmado: responde `null` explícito, no un error, en puntos fuera de cobertura — ej. océano).
- **Corrección taxonómica**: "ajo chilote" **no es Allium sativum** — es *Allium ampeloprasum* (ajo Blandino). No afecta el rol agronómico en rotación (sigue siendo familia Allium para ruptura de ciclo de solanáceas), pero cualquier búsqueda de literatura adicional debe usar el nombre correcto. Ficha INIA (vía Portal Frutícola) da datos reales: ciclo 210-230 días, T° mínima 7°C, máxima 30°C, óptima 15-20°C, suelos franco a franco-arcillosos, pH 5,6-8,0. `umbral_fenologico_config` para ajo pasa de `placeholder_sin_validar` a `fuente='INIA_ficha_tecnica'`.
- **Haba**: ficha técnica de **CIREN (Haba.pdf)** — temperatura base 5°C, óptimo 15-20°C, máximo 28°C, suma térmica 450-650 GDD desde siembra hasta cosecha (grano seco). Nota: esto NO resuelve el vacío de suelo de CIREN (es un documento de cultivo, no el sistema de datos de suelo) — son dos cosas separadas. Otros modelos (CROPGRO-faba bean, estudio de Mendoza) dan temperaturas base muy distintas (-3,8°C a 4,47°C) según método y cultivar — no hay consenso universal, la ficha de CIREN es la referencia chilena más directa disponible, no la única posible.
- **WWF Terrestrial Ecoregions**: confirmado accesible vía espejos académicos (Stanford, Columbia, NYU, MIT), basado en Olson et al. 2001. No se confirmó en la búsqueda (solo por conocimiento general, sin verificar línea por línea en el shapefile) que la ecorregión "Valdivian temperate rain forests" esté correctamente delimitada para Chiloé — hay que confirmarlo al momento de implementar, no asumirlo.

### 10.1.1 Fuentes adicionales confirmadas tras revisar el catálogo oficial del brief (cobertura global, usables en Chile)

- **FAO GAEZ (Global Agro-Ecological Zones)**: capas de aptitud agroclimática globales por cultivo, con restricciones de suelo y disponibilidad de agua. Candidato a cruce independiente para `calcular_idoneidad` en `rotation_engine`.

  **Acceso verificado**: ArcGIS Image Server en `https://gaez-services.fao.org/server/rest/services/res05/ImageServer`. Se consulta su catálogo mosaico (`/query`) filtrando por campos `crop`, `water_supply` (`Rainfed`/`Irrigation`), `input_level` (`High`/`Low`), `variable` (`Suitability index range (0–10000)`), `year` (ej. `1981-2010` con `model=CRUTS32 Historical` para el baseline, no un escenario RCP futuro). El resultado da `download_url`, un GeoTIFF global a 5 arc-minutos (4320×2160px, ~1.3MB, LZW, con soporte de range requests en S3).

  **Verificado con datos reales para Chiloé** (histórico 1981-2010, secano, insumo alto — valor 0-10000, mayor = más idóneo): White potato — Castro 5556, Ancud 3333, Quellón 5556, Quemchi 5556. Clasificación exacta de las bandas (parecen escalones de 1111.1 → 9 clases) pendiente de confirmar contra la metodología GAEZ, no inventada aquí.

  **Limitación real, no cosmética**: el catálogo de 53 cultivos de GAEZ no incluye garlic/allium ni faba bean. Para ajo chilote (*Allium ampeloprasum*) no hay ningún proxy razonable en GAEZ (lo más cercano, Onion, es otra especie del mismo género). Para haba, el proxy más cercano es **Dry pea** (*Pisum*, no *Vicia faba*) — y dio valor 0 (no idóneo) en los cuatro puntos de Chiloé probados, en todas las combinaciones de insumo/uso de suelo, verificado contra el mismo método que sí dio valores reales para papa. Es un resultado del modelo, no un error de lectura, pero no se puede extrapolar con la misma confianza a haba real por ser géneros distintos con tolerancia a humedad posiblemente distinta.

  **Insumo alto vs. bajo — decisión de modelo que esto resuelve**: papa en insumo alto da ~5556-3333 en los puntos de Chiloé; en insumo bajo cae a ~3333-1667, una diferencia grande, no marginal. El minifundio chilote es agricultura de insumo bajo (poco fertilizante, sin riego) — `rotation_engine` debe consultar GAEZ con `input_level=Low` por defecto para este contexto, no `High`.

  **Método mejorado de consulta**: en vez de descargar cada GeoTIFF y decodificarlo localmente (varias capas usan compresión que Pillow no soporta), se usa el endpoint `identify` del propio Image Server con `mosaicRule: {mosaicMethod: esriMosaicLockRaster, lockRasterIds: [objectid]}` — el servidor decodifica y devuelve solo el valor en el punto consultado. Funciona para cualquier capa del catálogo sin depender de su compresión interna.

  **Capas de suelo adicionales encontradas** (servicio separado `LR/ImageServer`, Theme "Land and Water Resources"): calidad de suelo en 7 factores desagregados (SQ1-SQ7: nutrientes, retención, condiciones de raíz, oxígeno/drenaje, salinidad, cal/yeso, laborabilidad), suelo dominante (clase HWSD), e idoneidad combinada suelo+terreno — todas consultables por punto igual que las de cultivo. Valores reales (insumo bajo): suelo dominante clase 3 en Castro/Quellón/Quemchi, clase 19 en Ancud; idoneidad de suelo 0-1 en la mayoría de los puntos, 5-6 en Ancud.

  **Pendiente, no inventado**: no se encontró la leyenda oficial que traduzca estos códigos de clase a significado agronómico (qué es "clase 3" de suelo dominante, o si "idoneidad 0" es mejor o peor que "idoneidad 5" en esta escala discreta). Está en la metodología GAEZ v4 (Fischer et al. 2021) y el glosario del portal, no verificada en esta sesión — no usar estos códigos para decisiones del modelo hasta confirmar la leyenda.
- **GLDAS** (no NLDAS — NLDAS es exclusivo de Norteamérica, GLDAS es global): asimilación satélite+estación en grilla, sub-diaria, humedad de suelo/ET/radiación. Candidato para llenar huecos de SMAP o cruzar contra POWER.
- **ERA5 (ECMWF)**: reanálisis global horario, incluye temperatura de suelo. No es NASA — mismo criterio de honestidad que Sentinel-3/Hansen GFC: usable como validación cruzada de POWER, nunca presentado como dato de la agencia.
- **GEDI**: estructura de dosel/biomasa láser. Mejor en vegetación alta — relevante no solo para la rama amazónica, también para el buffer forestal de `templado_costero` (bosque valdiviano tiene dosel sustancial), como complemento estructural a la señal óptica de HLS/EVI.

### 10.1.2 Arquitectura global: núcleo universal + capas regionales activadas por ubicación

La app no es solo para Chiloé. Las fuentes limitadas a EE.UU. (Web Soil Survey, SSURGO/STATSGO2, CDL/CropScape, PRISM, NAIP, NLCD, CoCoRaHS, USGS NWIS, USDA AMS Market News, USDA NASS QuickStats, LANDFIRE, OpenET, NLDAS) no se descartan del sistema — se activan solo si el predio cae dentro de su cobertura:

```
capas_regionales_disponibles(geometria) -> lista de fuentes aplicables
```

Núcleo universal (cualquier predio del mundo): POWER, SMAP, HLS, MOD13Q1/MCD12Q2, VNP13A1, ECOSTRESS, SRTM, GRACE, GAEZ, GEDI, GLDAS. Capas regionales: SSURGO/CDL/PRISM/etc. si `pais == EE.UU.`; ODEPA/INE/CIREN/CHLSOC si `pais == Chile`; el equivalente correspondiente para cualquier otro país, siguiendo el mismo patrón.

**Consecuencia para la jerarquía de confianza**: un predio en EE.UU. llega a `calibrado_comunal` casi de inmediato porque SSURGO da suelo real y CDL da rotación histórica real. Un predio en Chiloé no tiene ningún equivalente de esos dos, por eso el reporte del agricultor pesa tanto en este diseño. La dependencia de ground truth de campo es proporcional a cuánto dato público abierto ya existe en esa región, no un rasgo fijo del sistema.

### 10.2 Siguen sin resolver

- **Cobertura real de nubes en HLS para Chiloé**: no se encontró ninguna estadística específica para la región (los estudios más cercanos son de Amazonía/pampa brasileña y bosque tropical, no transferibles). Solo se resuelve consultando directamente el archivo Sentinel-2/Landsat para las tiles del archipiélago — es una consulta técnica puntual pendiente, no un vacío bibliográfico.
- **Umbrales del semáforo (±3/4-9/10+ días)**: siguen sin fuente — a diferencia de los GDD de ajo y haba, no se encontró ningún estándar publicado para los rangos de alerta fenológica. Permanecen como `fuente='placeholder_sin_validar'`.
- **Capa de visualización/explicación para el agricultor**: mapas interactivos, overlays, sliders de escenario, explicación de términos — pedidos explícitamente por el brief de rotación, todavía sin diseñar.
- **Asignación automática de `bioma_tipo`**: deliberadamente no resuelta. El MVP fija `templado_costero` para todo Chiloé; la clasificación automática (WWF Terrestrial Ecoregions + corrección manual) se decide solo cuando exista una segunda región real.

---

## 11. Estado del arte local — citar, no ignorar

- **PhenChile** (PUCV + CONAF): red fenológica nacional ya operando, 10 cámaras en 7 parques de Chile central, combina satélite NASA con fotografía terrestre, ya implementa un semáforo de alerta (RFD > 0.95). No cubre Chiloé ni cultivos, pero es precedente técnico real en Chile — hay que citarlo, no presentar la idea como inédita en el país.
- **iNaturalist Chile**: ciencia ciudadana de biodiversidad, administrado por el Ministerio del Medio Ambiente.
- **FAO ZARC**: ya desplegado en Guatemala/Honduras/El Salvador, ajusta fechas de siembra con zonificación de riesgo climático — precedente de la mitad "ajuste de calendario" de este proyecto, sin la capa de ground truth en tiempo real ni la salida de cambio de variedad que Mogewe sí tiene.
