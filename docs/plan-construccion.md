# mogen — Plan de construcción (estado real y fases restantes)

Reemplaza en vigencia al plan original de puesta en marcha del MVP (Fases 0-11). Esa estructura sigue siendo la referencia de qué se quería construir; este documento es honesto sobre qué de eso existe de verdad hoy, qué se desvió del plan original (y por qué), y qué falta en concreto para llegar a un sistema que un agricultor real use desde un teléfono.

**Principio que no cambia**: nada se declara "listo" sin haber corrido contra datos/infra reales — Postgres real en Railway, APIs externas reales, nunca un mock presentado como si fuera el resultado final. Cada ítem de este plan dice si está verificado, a medias, o sin empezar.

---

## 1. Resumen ejecutivo

Se construyó mucho más de lo que el plan original cubría en materia de **fuentes de datos** (8 fuentes reales conectadas, no las 2 originales de POWER+AppEEARS) y de **motor de idoneidad** (simulación real por fase, no el chequeo genérico planeado) — pero casi nada de la **capa de producto** (Flujos 1/3/6/7 como endpoints reales, panel de administración, vista del agricultor) existe todavía. El proyecto hoy es: un conjunto de motores biofísicos sólidos y verificados, una base de datos de especies real y poblada, y un backend de ingesta de datos real — sin ninguna interfaz, sin onboarding real, sin reporte de campo, sin notificaciones, sin scheduler automático.

La métrica honesta: de los 7 Flujos del diseño conceptual, **0 están implementados como endpoints públicos reales**. Los 14 endpoints que sí existen son todos `/api/admin/.../ingesta/*` o `/idoneidad` — herramientas de verificación para que un humano (no un agricultor) dispare una fuente de datos y vea el resultado. Son el cimiento de Flujo 2, no Flujo 2 mismo.

---

## 2. Inventario real

### 2.1 Infraestructura y auth — ✅ verificado

- Postgres+PostGIS real en Railway, schema completo (32+ tablas/vistas) corrido sin error.
- Auth real: registro/login por teléfono (agricultor) o email (admin), JWT, middleware de autorización. Usuario y admin de prueba creados (autorizados explícitamente antes de crearse).

### 2.2 Motores biofísicos — ✅ verificado, sin diccionarios hardcodeados

| Motor | Archivo | Estado |
|---|---|---|
| Fenológico (GDD, fotoperiodo, vernalización, confianza) | `services/pheno_engine.py` | ✅ Corrido contra datos reales |
| Estrés/daño por fase (helada/calor/sequía/anegamiento/tizón/ceniza) | `services/motor_estres.py` | ✅ Corrido; bug real de tizón corregido (no se evaluaba); mitigación por manejo (fungicida) real |
| Rotación (secuencias, puntaje, plan B) | `services/motor_rotacion.py` | ✅ Corrido contra el catálogo real — **nunca conectado a un endpoint público** |
| Catálogo de especies (construye todo desde datos, no código) | `services/catalogo_especies.py` | ✅ `calcular_idoneidad()` real con simulación por fase, variedad real soportada |

### 2.3 Fuentes de datos — ✅ 8 verificadas, ver detalle en `modelo-conceptual-phenoshield.md` §4.4

NASA POWER, CR2MET, Explorador Solar, CLSoilMaps, SoilGrids, AppEEARS (HLS/SMAP/ECOSTRESS/Landsat), Copernicus/Sentinel Hub, NASA FIRMS. Todas con cliente real en `services/cliente_*.py`, todas probadas contra el predio real de Quemchi.

**GAEZ nunca se implementó** — el plan original lo asumía para los escenarios climáticos moderado/extremo de Flujo 5; se reemplazó en la práctica por CR2MET/Sentinel/SoilGrids/CLSoilMaps, pero ninguno de esos cubre el rol específico de "escenario climático futuro" que tenía GAEZ. **Decisión pendiente, no tomada todavía** — ver §4.

### 2.4 Catálogo de especies — ✅ poblado

- 3 especies curadas a mano (papa/ajo_chilote/haba — INIA/CIREN) + pradera (perenne).
- 2068 especies de FAO EcoCrop (`perfil_generico` — solo idoneidad de sitio, sin fenología ni rotación).
- `caracteristica_variedad_aportada` (aporte de agricultores): tabla existe, **cero filas reales todavía** — ningún flujo real la escribe.

### 2.5 Endpoints reales — 14, todos admin/ingesta

```
POST /api/auth/registro | login | login-admin        -- Fase 2, real
GET  /api/auth/yo

POST /api/admin/parcelas/{id}/ingesta/solar          -- Explorador Solar
POST /api/admin/parcelas/{id}/ingesta/suelo          -- CLSoilMaps
POST /api/admin/parcelas/{id}/ingesta/suelo_quimico  -- SoilGrids
POST /api/admin/parcelas/{id}/ingesta/cr2met         -- CR2MET
POST /api/admin/parcelas/{id}/ingesta/copernicus     -- Sentinel-1/2
POST /api/admin/parcelas/{id}/ingesta/appeears       -- HLS/SMAP/ECOSTRESS/Landsat
POST /api/admin/parcelas/{id}/ingesta/incendios      -- FIRMS
GET  /api/admin/parcelas/{id}/idoneidad              -- catalogo_especies.calcular_idoneidad()
GET  /api/admin/copernicus/sentinel{1,2}/disponibilidad
```

**No existe ningún endpoint de `/api/parcelas` (crear), `/api/cultivos` (crear/fenología), `/api/observaciones`, `/api/alertas`, `/api/notificaciones`, `/api/parcelas/{id}/rotacion/comparar`.** El único predio real en la base (`id=2`, Quemchi) se creó con SQL directo, no por API — y su polígono es un cuadrado inventado de 4ha alrededor del punto que dio el usuario, no un deslinde real (ver hallazgo del 14-nov).

### 2.6 Lo que la base de datos tiene y nadie usa todavía

- `job_extraccion`: existe desde el schema inicial, pensada para rastrear el estado de cada extracción asíncrona. **Ningún endpoint real la escribe** — las 7 ingestas actuales van directo a `cache_consulta_grilla`, sin registro de job. El manejo de reintento/falla que describe Flujo 2 no existe.
- `predio_cultivos`, `fenologia_observada`, `manejo_predio` (salvo el fixture de mitigación probado una vez con datos sintéticos), `alerta_busqueda_variedad`, `respuesta_alerta`, `notificacion_pendiente`: todas vacías, sin código que las use.

---

## 3. Fases restantes — reordenadas por lo que realmente falta

### Fase A — Cerrar el loop de ingesta real (antes de construir más arriba)

1. **`job_extraccion` real**: cada endpoint de `/ingesta/*` debe escribir una fila al empezar y actualizarla al terminar/fallar — hoy no hay forma de saber desde la base si una ingesta falló o cuándo fue la última vez que corrió para un predio.
2. **Scheduler real (Flujo 2)**: hoy cada fuente se dispara a mano por HTTP. Falta el worker/cron que recorra predios activos y llame las 7 ingestas solo, con el manejo de reintento que ya se encontró necesario en vivo (AppEEARS se congestionó 40+ minutos en esta sesión — un cron necesita backoff real, no reintento ciego).
3. **Resolución geométrica real**: 6 de 8 fuentes usan el centroide del predio, no su polígono — para CR2MET/SMAP/Explorador Solar tiene sentido (resolución nativa mucho más gruesa que cualquier predio), pero para CLSoilMaps/SoilGrids/ECOSTRESS/Landsat (más finos que un predio típico) se está perdiendo la variación real dentro del predio. Decidir cuáles vale la pena pasar a promedio zonal sobre el polígono, como ya se hizo con Sentinel-1/2.

### Fase B — Flujo 1/1b real (onboarding)

1. `POST /api/parcelas` — real, con geometría real del agricultor (GPS + hectáreas declaradas, como ya describe el modelo conceptual), no un fixture hecho a mano.
2. `POST /api/parcelas/{id}/cultivos` — confirma qué sembrar.
3. `GET /api/parcelas/{id}/candidatas_siembra` — Flujo 1b, `calcular_idoneidad()` en modo candidatas (ya existe la función real, falta el endpoint y el filtro "especies candidatas para esta zona" en vez de recibir la lista a mano).

### Fase C — Flujo 4 y Flujo 5 como endpoints públicos

1. `GET /api/cultivos/{id}/fenologia` — expone `pheno_engine` real (ya probado, nunca expuesto).
2. `GET /api/parcelas/{id}/rotacion/comparar` — expone `motor_rotacion.buscar()` real.
3. **Decisión pendiente real**: con qué se arman los tres escenarios (sin_cambios/moderado/extremo) ahora que GAEZ no se implementó. Candidato más directo con lo que ya existe: `sin_cambios` = climatología real de CR2MET; `moderado`/`extremo` sin fuente real todavía — construirlos a mano (perturbación sintética sobre CR2MET) sería otro `placeholder_sin_validar`, no un dato real. Esto necesita una conversación explícita antes de implementar, no una decisión de código.

### Fase D — Flujo 3 (reporte de campo) y Flujo 6/7 (alertas y notificaciones)

Ninguno de los tres tiene código todavía. `POST /api/observaciones` es lo que más desbloquea (reancla el calendario con dato real de campo — la pieza central del modelo conceptual, "el dato de campo no es opcional").

### Fase E — Admin panel y capa visual del agricultor

Sin empezar. El admin panel reemplazaría los 14 endpoints HTTP crudos por vistas Jinja2 reales — alto valor ahora que hay 8 fuentes y 2071 especies que alguien tiene que poder revisar sin usar `curl`.

### Fase F — E2E real

Bloqueada hasta que existan B y C — hoy no se puede probar el ciclo completo (registro → siembra → fenología → rotación → observación) porque la mitad de esos pasos no son API todavía.

---

## 4. Decisiones pendientes (no técnicas, necesitan una conversación)

1. **Escenarios climáticos sin GAEZ** (Fase C) — qué fuente real reemplaza el rol de "proyección futura" que tenía GAEZ en el plan original.
2. **Siembras múltiples al año**: `rasgos_rotacion_especie` solo soporta una fecha de siembra por especie — documentado como hueco real en la extensión de Copernicus, sin resolver.
3. **Multi-cropping / rotación con sub-ciclos**: relacionado al punto anterior, mismo hueco.
4. **Geometría real de los predios**: no hay ningún predio con deslinde real todavía, todo lo probado usa polígonos inventados.
5. **Cuenta de servicio vs. cuenta personal para AppEEARS/Copernicus/FIRMS**: las credenciales reales hoy están atadas a la cuenta personal del usuario — antes de producción, decidir si pasan a cuentas de servicio dedicadas.
