# mogen — Arquitectura por flujos

Base: el modelo conceptual en `modelo-conceptual-phenoshield.md`. Este documento traduce ese modelo a flujos de sistema para construcción.

**Decisión de ingesta**: DAACs directos (AppEEARS / `earthaccess` / REST propio de cada fuente), no Google Earth Engine. El backend siempre tiene internet; el teléfono del agricultor nunca llama directo a ninguna fuente externa, solo sincroniza con nuestro backend (offline-first, sin cambios por esta decisión).

**Estado real vs. lo que describe este documento**: los Flujos 1-7 de abajo son el diseño objetivo. Lo que existe hoy en `main.py` son 14 endpoints bajo `/api/admin/parcelas/{id}/ingesta/*` e `idoneidad` — **síncronos, disparados a mano, no el Flujo 2 (job nocturno/cron) ni la API pública de Flujo 1/3/4/5/6/7**. Cada fuente real (CR2MET, Explorador Solar, CLSoilMaps, SoilGrids, AppEEARS, Copernicus, FIRMS) tiene su propio endpoint de ingesta que un admin llama por predio, escribe a `cache_consulta_grilla`, y devuelve el resultado en la misma respuesta HTTP. Esto fue deliberado para poder verificar cada fuente contra datos reales antes de construir el scheduler/worker de Flujo 2 — ver `docs/plan-construccion.md` para el detalle de qué falta para llegar de esto a los Flujos reales.

---

## Flujo 1 — Onboarding de usuario, predio y primer cultivo

**Trigger**: registro nuevo.

**Pasos**:
1. Captura geometría del predio (el terreno, estable a través de temporadas).
2. `asignar_bioma_tipo(geometria)` — point-in-polygon contra WWF Terrestrial Ecoregions. Local, síncrono.
3. `calcular_utm_zone(geometria)` — síncrono.
4. Consulta a POWER (REST, sin login) — clima actual, síncrono, responde en segundos.
5. `verificar_grilla_activa(utm_zone, bioma_tipo)`.
   - Si existe: el predio se asocia a la grilla existente. Fin del flujo.
   - Si no existe: crear `perfil_climatico_regional`, encolar `extraccion_historica` (job AppEEARS, asíncrono).
6. Mostrar `estado_confianza` inicial al usuario (`sin_referencia` si región nueva, con mensaje explícito de que el histórico se está construyendo).
7. Captura de geometría práctica: GPS da el punto (funciona sin señal de datos); el agricultor declara hectáreas; el sistema genera un polígono aproximado centrado en el punto con esa área. Suficiente para capas gruesas (centroide) y razonable para finas mientras no haya algo mejor — caminar el perímetro real queda como mejora futura, no requisito de entrada.
8. Si el predio no tiene ningún ciclo de cultivo todavía → Flujo 1b antes de cerrar el registro.

**Componentes**: API de registro, servicio de ecorregiones, cliente POWER REST, cola de jobs AppEEARS.

**Output**: usuario + predio creados, `bioma_tipo` asignado (o pendiente de confirmación si ambiguo), estado de confianza inicial, primer ciclo de cultivo decidido vía Flujo 1b.

---

## Flujo 1b — Planificación de primera siembra

**Trigger**: predio registrado (Flujo 1), sin ningún `predio_cultivos` todavía.

**Pasos**:
1. El agricultor indica qué especies está considerando, o el sistema sugiere candidatas típicas de la región.
2. `rotation_engine` corre en **modo candidatas**, no modo secuencia: compara cada especie directo contra `calcular_idoneidad` (humedad, luz, suelo del punto) y GAEZ. No hay componente de rotación porque no existe historial de qué se sembró antes en ese predio.
3. Cada especie se marca con su `nivel_madurez_especie` real — la primera siembra no tiene menos honestidad sobre vacíos de información que las siguientes.
4. El agricultor confirma qué sembrar → se crea la fila en `predio_cultivos` → de ahí en adelante entra al ciclo normal (Flujo 3/4).

**Componentes**: `rotation_engine` (modo candidatas), acceso a `requisitos_especie`/`rasgos_rotacion_especie`, GAEZ.

**Output**: primer `predio_cultivos` creado sobre el predio.

---

## Flujo 2 — Ingesta de datos NASA (job nocturno)

**Trigger**: cron nocturno.

**Pasos**:
1. Iterar sobre regiones activas (no una región fija).
2. Por región: actualizar `cache_consulta_grilla` por predio (POWER, SMAP, IMERG, HLS, ECOSTRESS, VNP13A1 según disponibilidad; capas regionales opcionales si el país de la región las tiene) y `cache_consulta_regional` por perfil climático (GRACE y cualquier señal que no varía entre predios de la misma región).
3. Marcar cobertura por entrada: `completa` | `parcial_nubes` | `sin_dato`.
4. Revisar jobs AppEEARS pendientes del Flujo 1; al completar, poblar el baseline histórico de esa región y subir su `estado_confianza`.

**Componentes**: scheduler/worker, clientes `earthaccess`/AppEEARS/POWER REST, almacén de grilla.

**Output**: grilla actualizada por región activa. Regiones nuevas pueden subir de escalón de confianza cuando su job histórico completa.

---

## Flujo 3 — Reporte de campo (ground truth)

**Trigger**: agricultor envía observación (voz, foto, texto).

**Pasos**:
1. Transcribir si es voz.
2. Estructurar y clasificar en tres caminos distintos:
   - Fase BBCH o evento de manejo → atado a un ciclo de cultivo (`id_cultivo`) → `fenologia_observada` o `manejo_predio`.
   - Bioindicador (Ulmo, zarapito) → atado al usuario y su zona, no a un cultivo → `bioindicador_observado`.
   - Característica de variedad (ciclo, tolerancia, resistencia) → atado al usuario y a la variedad → `caracteristica_variedad_aportada`. Se dispara como pregunta opcional cuando el agricultor siembra una variedad sin perfil todavía — no bloquea el flujo si no responde.
3. Recalcular `calendario_predio` — ancla GDD a esta confirmación, no a la siembra original.
4. Actualizar `sesgo_comuna_dias` / `sesgo_parcela_dias` si corresponde.
5. Chequear umbral de materialidad (cruce de semáforo, o cambio de ventana mayor al margen mínimo).
6. Si hay cambio material: generar respuesta (ventana recalculada, comparación vs. comuna, alertas específicas) → `notificacion_pendiente`.
7. Si `severidad == rojo` y `fase_decision == pre_siembra`: encolar `alerta_busqueda_variedad` (Flujo 6).

**Componentes**: servicio de ingestión, transcriptor de voz, `pheno_engine` (Flujo 4), servicio de notificación.

**Output**: calendario actualizado, respuesta al agricultor (o silencio si no hay cambio material), posible alerta de red.

---

## Flujo 4 — Motor fenológico (`pheno_engine`)

**Trigger**: llamado desde Flujo 3, Flujo 5, o consulta directa.

**Pasos**:
1. Cruzar GDD acumulado (desde última etapa confirmada) + curva EVI/HLS (`detect_curve_anomaly`) + ground truth de campo.
2. Aplicar ajuste de fotoperiodo si la transición es BBCH65→BBCH97.
3. Ejecutar dispatcher según `bioma_tipo`:
   - `andino_altura` → `get_climate_anomaly_shift_power`
   - `corredor_seco` → `get_rain_onset_shift`
   - `amazonico` → `get_forest_loss_shift_nasa`
   - `templado_costero` → `get_calibrated_calendar_shift`
4. Aplicar `fase_decision` (pre/post siembra) para definir el tipo de salida posible.
5. Aplicar jerarquía de confianza (`calibrado_predio` → `calibrado_comunal` → `referencia_local` → `sin_referencia`).
6. Calcular `alertas_especificas`: `riesgo_helada_tardia`, `riesgo_tizon` (vía RH2M/POWER), `ventana_polinizador` (solo haba), `posible_confusion_manejo`.

**Componentes**: servicio `pheno_engine`, acceso a grilla (Flujo 2), acceso a `umbral_fenologico_config`.

**Output**: contrato unificado — `dias_desfase`, `fuente_señal`, `severidad`, `tipo_salida`, `alertas_especificas`, `preparar_proxima_temporada`.

---

## Flujo 5 — Comparación de rotación (`rotation_engine`)

**Trigger**: agricultor pide evaluar qué sembrar, típicamente tras confirmar cosecha (BBCH97) de un cultivo.

**Pasos**:
1. Generar todas las secuencias candidatas de 3-5 temporadas entre los cultivos viables del predio (`buscar()`), incluida la pradera/barbecho como opción explícita (`perenne=True` en `PERFIL` — "dejar descansar" es una estrategia real, no solo las otras dos quedaron sin esa opción hasta ahora).
2. Descartar por reglas duras: `cumple_intervalo()` (temporadas mínimas antes de repetir un cultivo — reemplaza el booleano `ruptura_ciclo_patogeno` por un número configurable por especie, `extra_intervalo` lo alarga si hay inóculo/enfermedad declarada en `manejo_predio`) y barbecho máximo (`MAX_BARBECHO`).
3. Por cultivo de cada secuencia: llamar al Flujo 4 para obtener sus ventanas (siembra, BBCH09, BBCH65, BBCH97), y a `evaluar_cultivos()`/`evaluar()` de `motor_estres.py` para la pérdida esperada por fase y tipo de peligro (helada/calor/sequía/anegamiento/lluvia en cosecha/**ceniza** — relevante en Chile por actividad volcánica, se reporta como evento externo, no viene de ningún dato climático).
4. Calcular `calcular_idoneidad` (humedad vía `balance_agua`, luz, suelo) por cultivo contra condiciones del sitio, usando capas de grilla + capas regionales si existen.
5. Puntuar cada secuencia con 5 criterios (`puntuar()`): riesgo, peor año (robustez, no solo promedio), diversidad, precedente (bonifica leguminosa antes de cultivo exigente, penaliza repetir familia botánica), y **cobertura** (fracción de días con cultivo vivo vs. suelo desnudo — reemplaza a `dias_suelo_desnudo_estimado` como criterio positivo de puntaje, no solo como alerta de erosión).
6. Una secuencia vale lo que vale en su **peor escenario** evaluado (clima actual vs. más cálido/seco, por ejemplo), no el promedio — así no se recomienda algo que falla justo en el año malo.
7. Chequear `nivel_madurez_especie` por cultivo; si es nuevo, iniciar bootstrap.
8. Ordenar las estrategias según `prioridades_agricultor` (pendiente: los 5 criterios de `puntuar()` no se descomponen todavía por tipo de peligro — `prioridad_agua` no puede pesar solo el riesgo de sequía por separado del de helada dentro de "riesgo" sin esa descomposición; queda como limitación conocida, no resuelta).

**Componentes**: `motor_rotacion.py` (genera y puntúa secuencias), `motor_estres.py` (pérdida por fase/peligro, balance de agua, plan B), llamadas internas a `pheno_engine`, acceso a grilla, acceso a `requisitos_especie`/`rasgos_rotacion_especie`.

**Output**: top N secuencias con puntaje y los 5 criterios desglosados, `vacios_informacion` explícitos (incluye qué cultivos de la secuencia no tienen reglas de daño todavía — ver advertencia en `motor_estres.py` sobre no confundir "sin modelo" con "sin riesgo").

---

## Flujo 6 — Red de alertas de variedad

**Trigger**: `preparar_proxima_temporada == true` (automático desde Flujo 3/4) o solicitud manual.

**Pasos**:
1. Crear `alerta_busqueda_variedad`: especie, características requeridas, unidad administrativa local — nunca geometría exacta ni `id_parcela_solicitante` expuesto.
2. Notificar a usuarios dentro de la misma unidad administrativa o radio de 30km (`ST_DWithin`), mostrando solo la vista pública (`vista_publica_alerta`).
3. Recibir `respuesta_alerta`; notificar al solicitante.
4. Si la variedad ofrecida es nueva en el sistema: bootstrap de `nivel_madurez_especie` desde `sin_perfil` a `perfil_generico` con la información informal de quien responde.
5. Cerrar la alerta cuando el solicitante la marca resuelta, o tras vencimiento sin respuesta.

**Componentes**: servicio de alertas, filtro espacial de visibilidad, servicio de notificación.

**Output**: alerta publicada y, eventualmente, resuelta o cerrada por vencimiento.

---

## Flujo 7 — Retorno al usuario

**Trigger**: cualquier salida de los Flujos 3, 4, 5 o 6 marcada como cambio material.

**Pasos**:
1. Verificar que el cambio supera el umbral de materialidad (ya evaluado en Flujo 3, reutilizado aquí para Flujos 4-6).
2. Componer el mensaje en el mismo canal de entrada del usuario (voz si reportó por voz, texto si reportó por texto).
3. Enviar.

**Componentes**: servicio de notificación, lógica de materialidad compartida con Flujo 3.

---

## Endpoints por flujo

**Flujo 1 — Onboarding**
```
POST /api/usuarios
POST /api/parcelas                          -- dispara asignar_bioma_tipo, calculo UTM, POWER síncrono, verificar_grilla_activa
GET  /api/parcelas/{id}/candidatas_siembra  -- Flujo 1b: rotation_engine en modo candidatas, sin secuencia previa
POST /api/parcelas/{id}/cultivos            -- confirma qué sembrar (especie, variedad, fecha_siembra)
GET  /api/parcelas/{id}/estado_confianza
```

**Flujo 2 — Ingesta nocturna** (interno, no público salvo panel de administración)
```
POST /api/admin/ingesta/ejecutar            -- trigger manual para debug
GET  /api/admin/regiones/{id}/estado_grilla
```

**Flujo 3 — Reporte de campo**
```
POST /api/observaciones                     -- body: array de {id_cultivo, tipo: bbch|manejo, contenido, fecha_cliente}
                                                 acepta batch, porque el teléfono puede llegar con varias observaciones
                                                 acumuladas mientras estuvo sin señal
POST /api/bioindicadores                    -- body: array de {id_usuario, tipo, fecha_observada, fecha_cliente}
                                                 separado de /observaciones porque no está atado a un cultivo
POST /api/variedades/caracteristicas        -- body: {especie, variedad_local, id_usuario_aportante, caracteristicas, ciclo_dias_estimado, descripcion_libre}
                                                 opcional, no bloqueante; se promueve a requisitos_especie/rasgos_rotacion_especie
                                                 solo cuando varios aportes independientes coinciden
GET  /api/cultivos/{id}/calendario
```

**Flujo 4 — `pheno_engine`** (llamado internamente por Flujo 3 y 5; expuesto también para consulta directa)
```
GET  /api/cultivos/{id}/fenologia           -- contrato completo: dias_desfase, severidad, tipo_salida, alertas_especificas
```

**Flujo 5 — `rotation_engine`** (sobre `services/motor_rotacion.py`, que a su vez usa `services/motor_estres.py`)
```
POST /api/parcelas/{id}/prioridades
GET  /api/parcelas/{id}/rotacion/comparar      -- corre buscar(): genera y puntua secuencias de 3-5
                                                   temporadas, devuelve top N con 5 criterios
                                                   (riesgo, peor_año, diversidad, precedente, cobertura)
GET  /api/cultivos/{id}/matriz_estres          -- vulnerabilidad del cultivo por fase x tipo de peligro
                                                   (helada/calor/sequía/anegamiento/lluvia_cosecha/ceniza)
GET  /api/parcelas/{id}/rotacion/plan_b        -- para la secuencia elegida, qué cultivo alcanza a
                                                   madurar si uno se pierde a mitad de ciclo
```

**Flujo 6 — Red de alertas**
```
POST  /api/alertas
GET   /api/alertas?unidad_administrativa_local=X   -- vista pública (vista_publica_alerta), sin FK expuesta
POST  /api/alertas/{id}/respuestas
PATCH /api/alertas/{id}                     -- cerrar / marcar resuelta
```

**Flujo 7 — Retorno al usuario** (lo que el teléfono pide en cada ráfaga de sincronización)
```
GET  /api/parcelas/{id}/notificaciones      -- lee notificacion_pendiente donde entregada=false, marca entregada=true al responder
```

## Dependencias entre flujos

```
Flujo 1 (onboarding) → Flujo 1b si el predio no tiene cultivo todavía → crea el primer predio_cultivos
Flujo 1 (onboarding) → habilita Flujo 2 (región queda activa)
Flujo 2 (ingesta nocturna) → alimenta Flujo 4 (grilla disponible)
Flujo 3 (reporte de campo) → llama a Flujo 4, puede disparar Flujo 6, siempre pasa por Flujo 7
Flujo 4 (pheno_engine) → es llamado por Flujo 3 y Flujo 5, nunca al revés
Flujo 5 (rotation_engine) → llama a Flujo 4 repetidamente (una vez por cultivo de cada secuencia)
Flujo 6 (alertas) → puede modificar el catálogo de especies que consume Flujo 5
```

---

## Secretos y configuración

**El secreto correcto para AppEEARS en producción es usuario/clave de una cuenta de servicio de Earthdata, no un token de usuario.** Un "user token" de EDL es para uso personal — hasta 2 activos a la vez, pensado para que una persona lo copie y lo use, no para que un job nocturno desatendido corra indefinidamente sin que nadie lo renueve. Con usuario/clave, `services/cliente_appeears.iniciar_sesion()` genera un token de AppEEARS nuevo cada vez que corre el job (válido 48h) — se regenera solo, nadie tiene que intervenir cada dos días.

**Dónde vive ese usuario/clave**: en el almacén de variables de entorno/secretos de la plataforma de hosting (cifrado, separado del código), nunca en el repo ni en ningún archivo que se despliega. El proceso del backend lo lee en runtime vía variable de entorno. Mismo patrón para las credenciales de Postgres y cualquier otra API con login.

**Credenciales reales en uso hoy** (todas leídas vía `os.environ` en `main.py`, ninguna en el repo):
- `EARTHDATA_USUARIO`/`EARTHDATA_CLAVE` — AppEEARS. Tiene que ser el **username real de Earthdata, no el email** (con email el backend de AppEEARS se cuelga sin responder en vez de dar 401 — bug real encontrado, no documentado por NASA).
- `COPERNICUS_CLIENT_ID`/`COPERNICUS_CLIENT_SECRET` — Sentinel Hub (Copernicus Data Space). Es un "OAuth client" creado en el perfil de la cuenta, no el usuario/clave de login de la cuenta misma. Token de 1800s, se renueva solo en cada llamada.
- `FIRMS_MAP_KEY` — NASA FIRMS. Clave de un solo valor, gratuita, pedida por email (sin contraseña asociada).
- `JWT_SECRET_KEY` — firma de los tokens de sesión de la API (`services/auth.py`).
- `DATABASE_URL` — la inyecta Railway automáticamente para el servicio Postgres.

**Desarrollo local es distinto, y no se confunde con esto**: un archivo local (`.env`, o un archivo de un solo secreto como `~/.earthdata_token`) sirve para que alguien pruebe código en su máquina — cubierto por `.gitignore`, nunca llega al repo ni se despliega. Es una conveniencia de desarrollo, no el diseño de producción.

**Si el secreto falla o expira**: el job nocturno falla explícito y queda registrado (`job_extraccion.estado = 'error'`), no reintenta en silencio ni sigue corriendo con una credencial vencida sin aviso — mismo principio de `pheno_engine.ClimaIncompleto` (fallar explícito en vez de corromper en silencio), aplicado ahora a fallas de autenticación, no solo a huecos de clima.

---

## Cómo actúan los datos en la aplicación

Hay dos corrientes de datos distintas, y el diseño entero depende de que ninguna de las dos se trate como "la verdad" por sí sola — se calibran una a la otra. Esta sección traza qué pasa con cada una desde que entra hasta que produce algo que el agricultor ve.

### Corriente 1 — dato satelital/climático (NASA y fuentes regionales)

**Entrada**: Flujo 2, job nocturno (diseño objetivo) — hoy, los 7 endpoints reales de `/ingesta/*` listados arriba. Nunca entra por pedido directo del agricultor — su teléfono no tiene ni necesita saber que existen SMAP, POWER, CR2MET, HLS, Sentinel, SoilGrids, CLSoilMaps o FIRMS.

**Transformación, paso a paso**:
1. Llega como gránulo crudo o respuesta de API (`job_extraccion`, con `proveedor`/`producto`/`estado` — asíncrono porque AppEEARS puede tardar horas, no se puede hacer esperar a nadie).
2. Se reduce a un valor por predio o por región, con su ficha de procedencia (`cache_consulta_grilla` o `cache_consulta_regional` — resolución nativa, versión del producto, cobertura de nubes). El dato crudo (el gránulo global) no se guarda; solo el valor ya extraído para los puntos que importan.
3. Ese valor nunca llega al agricultor como número. Se consume dentro de un cálculo: GDD diario (`pheno_engine.tiempo_termico_diario`), balance de agua (`motor_estres.balance_agua`), curva de anomalía (`detect_curve_anomaly`), idoneidad de sitio (`calcular_idoneidad`). El agricultor no ve "SMAP dice 0.22 m³/m³" — ve "tu suelo tiene humedad normal para esta etapa" o nada, si no hay nada que decir.
4. Si el dato no llegó (nubes, job todavía pendiente), el cálculo lo sabe (`cobertura: parcial_nubes | sin_dato`) y responde con menos confianza, nunca con un valor inventado para rellenar el hueco.

**Dónde se detiene**: en el motor que lo consume. Ningún dato satelital crudo sale del backend hacia el teléfono — lo que sale es siempre una salida ya interpretada (Flujo 7).

### Corriente 2 — dato del usuario (ground truth)

**Entrada**: Flujo 3, reporte de campo (voz/foto/texto), clasificado en cuatro caminos que van a lugares distintos y hacen cosas distintas:

| Reporte | Tabla | Qué hace con él el sistema |
|---|---|---|
| Fase BBCH confirmada | `fenologia_observada` | Reancla el reloj de GDD a esa fecha real (`actualizar_calendario_con_confirmacion` — no sigue acumulando desde la siembra original). Si hay suficiente historial, recalibra `delta_microclima` o el `umbral_fenologico_config` de esa especie/comuna (`ajustar_variedad`). |
| Evento de manejo | `manejo_predio` | Se cruza contra cualquier desfase detectado antes de atribuirlo al clima (`posible_confusion_manejo`). Si declara inóculo/enfermedad, alarga `intervalo` en `motor_rotacion.cumple_intervalo` (`extra_intervalo`). Si es `fungicida`/`pesticida` y la regla de daño vigente lo declara `mitigado_por`, reduce esa pérdida en `motor_estres.evaluar()` (parámetro `manejo`) — hoy solo tizón de papa tiene esa conexión; `fertilizacion`/`riego`/`drenaje`/`aporque` quedan registrados pero no mitigan ninguna regla (no existe todavía un riesgo de estrés nutricional con umbral propio al cual conectarlos). |
| Bioindicador (Ulmo, zarapito) | `bioindicador_observado` | No cambia el calendario de ningún cultivo directamente — informa la ventana de siembra (`ventana_siembra_recomendada`, fase pre-siembra) o el desfase continuo de la rama `templado_costero` del dispatcher. |
| Característica de variedad | `caracteristica_variedad_aportada` | No se usa sola. Se acumula; cuando varios aportes independientes coinciden, promueve `requisitos_especie`/`rasgos_rotacion_especie` de esa variedad, subiendo su `nivel_madurez_especie`. |

**Por qué un solo reporte no mueve nada grande**: cada uno de estos caminos tiene su propio umbral de acumulación antes de recalibrar algo que afecta a más de un predio (ver jerarquía de confianza y madurez de especie en el modelo conceptual). Un reporte aislado reancla *su propio* calendario; no cambia el umbral que usan los demás hasta que hay suficiente coincidencia.

### Dónde confluyen las dos corrientes

`services/catalogo_especies.py` es el punto de unión real, no solo conceptual. Construye el `Cultivo` simulable y el perfil de rotación mezclando lo que entró por fuentes externas una vez (GAEZ, INIA, CIREN, cargado a `requisitos_especie`/`umbral_fenologico_config`) con lo que se acumula de agricultores con el tiempo (`caracteristica_variedad_aportada` agregada). La jerarquía de madurez (`nivel_madurez`) es, literalmente, una etiqueta de qué corriente sostiene esa especie en este momento — y de cuál de las dos hay que seguir pidiendo más antes de confiar en el calendario que produce.

### Qué le llega de vuelta al agricultor, y qué no

Nunca un dato crudo de ninguna corriente. Siempre una de las salidas ya empaquetadas por `pheno_engine`/`motor_rotacion` (`calendario_ajustado`, `sugerencia_variedad`, `mitigacion_manejo`, comparación de rotación, alerta de variedad), con su estado de confianza explícito, y solo cuando cruza el umbral de materialidad (Flujo 7) — nunca por cada actualización silenciosa de la grilla nocturna.

**Privacidad en el único punto donde el dato de un usuario puede llegar a otro**: las alertas de variedad (Flujo 6). `vista_publica_alerta`/`vista_publica_respuesta` son los únicos lugares donde la corriente de un usuario se cruza con la de otro — y ahí nunca pasa la geometría exacta ni la FK hacia `parcela`/`usuarios`, solo especie, características buscadas y unidad administrativa local.
