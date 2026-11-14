-- Mogewe — schema de base de datos
-- Basado en docs/modelo-conceptual-phenoshield.md (sección 6) y docs/arquitectura-flujos-mogewe.md

CREATE EXTENSION IF NOT EXISTS postgis;

-- ============================================================
-- Núcleo
-- ============================================================

CREATE TABLE usuarios (
  id SERIAL PRIMARY KEY,
  nombre VARCHAR NOT NULL,
  pais VARCHAR NOT NULL,
  unidad_administrativa_local VARCHAR,
  geometria GEOMETRY(Point, 4326) NOT NULL,
  -- Fase 2 del plan de MVP: autenticación. Agricultor por teléfono, admin por email.
  telefono VARCHAR UNIQUE,
  email VARCHAR UNIQUE,
  password_hash VARCHAR,
  rol VARCHAR NOT NULL DEFAULT 'agricultor' CHECK (rol IN ('agricultor', 'admin'))
);
CREATE INDEX idx_usuarios_geometria ON usuarios USING GIST (geometria);

CREATE TABLE perfil_climatico_regional (
  id SERIAL PRIMARY KEY,
  bioma_tipo VARCHAR NOT NULL CHECK (bioma_tipo IN
    ('templado_costero', 'andino_altura', 'corredor_seco', 'amazonico')),
  utm_zone VARCHAR NOT NULL
);

CREATE TABLE ecoregion_wwf (
  id SERIAL PRIMARY KEY,
  eco_name VARCHAR NOT NULL,
  bioma_tipo VARCHAR CHECK (bioma_tipo IN
    ('templado_costero', 'andino_altura', 'corredor_seco', 'amazonico')),
  geometria GEOMETRY(MultiPolygon, 4326) NOT NULL
);
CREATE INDEX idx_ecoregion_wwf_geometria ON ecoregion_wwf USING GIST (geometria);
-- Import único desde el shapefile WWF Terrestrial Ecoregions (Olson et al. 2001).
-- bioma_tipo se llena a mano por fila tras el import, no viene en la fuente original.

-- La tierra física, estable a través de temporadas. El motor de rotación compara
-- secuencias de cultivos sobre la MISMA parcela — por eso el terreno y el ciclo
-- de cultivo actual no pueden ser la misma fila.
CREATE TABLE parcela (
  id SERIAL PRIMARY KEY,
  id_usuario INT NOT NULL REFERENCES usuarios(id),
  id_perfil_climatico INT REFERENCES perfil_climatico_regional(id),
  geometria GEOMETRY(Polygon, 4326) NOT NULL,
  altitud_msnm INT
);
CREATE INDEX idx_parcela_geometria ON parcela USING GIST (geometria);

-- Un ciclo de cultivo dentro de una parcela. Varias filas por parcela a través
-- del tiempo son la "secuencia de rotación" que compara rotation_engine.
CREATE TABLE predio_cultivos (
  id SERIAL PRIMARY KEY,
  id_parcela INT NOT NULL REFERENCES parcela(id),
  especie VARCHAR NOT NULL,
  variedad_local VARCHAR,
  fecha_siembra DATE
);
CREATE INDEX idx_predio_cultivos_parcela ON predio_cultivos (id_parcela);

CREATE TABLE fenologia_observada (
  id SERIAL PRIMARY KEY,
  id_cultivo INT NOT NULL REFERENCES predio_cultivos(id),
  fase_fenologica VARCHAR NOT NULL, -- 'BBCH09' | 'BBCH65' | 'BBCH97'
  fecha_observada DATE NOT NULL,
  registro_fotografico_url TEXT,
  fecha_reporte_cliente TIMESTAMP -- timestamp del teléfono al capturar, puede ser anterior a la sync
);

-- Bioindicadores de zona (Ulmo, zarapito): no pertenecen a un ciclo de cultivo,
-- pertenecen a quien los observa y a su zona. Separado de fenologia_observada
-- a propósito — forzarlos a tener un id_cultivo no reflejaba el diseño.
CREATE TABLE bioindicador_observado (
  id SERIAL PRIMARY KEY,
  id_usuario INT NOT NULL REFERENCES usuarios(id),
  tipo VARCHAR NOT NULL, -- 'ulmo_floracion' | 'zarapito_llegada' | libre, sin restricción rígida
  fecha_observada DATE NOT NULL,
  unidad_administrativa_local VARCHAR NOT NULL,
  fecha_reporte_cliente TIMESTAMP
);

CREATE TABLE manejo_predio (
  id SERIAL PRIMARY KEY,
  id_cultivo INT NOT NULL REFERENCES predio_cultivos(id),
  -- 'fungicida'/'pesticida' agregados para alimentar la mitigacion de regla_dano_especie
  -- (services/motor_estres.evaluar(), parametro `manejo`) -- 'fertilizacion' queda sin
  -- conectar a ningun riesgo: no existe todavia una regla de estres nutricional con
  -- umbral propio a la cual atenuar, agregar una inventada seria otro dato sin fuente.
  tipo_labor VARCHAR NOT NULL CHECK (tipo_labor IN
    ('aporque', 'fertilizacion', 'riego', 'drenaje', 'fungicida', 'pesticida')),
  fecha DATE NOT NULL
);

-- ============================================================
-- Calibración fenológica y requisitos agronómicos
-- ============================================================

CREATE TABLE umbral_fenologico_config (
  id SERIAL PRIMARY KEY,
  especie VARCHAR NOT NULL,
  variedad_local VARCHAR,
  transicion VARCHAR NOT NULL CHECK (transicion IN
    ('siembra_BBCH09', 'BBCH09_BBCH65', 'BBCH65_BBCH97')),
  gdd_minimo FLOAT NOT NULL,
  gdd_maximo FLOAT NOT NULL,
  horas_luz_criticas FLOAT,
  fuente VARCHAR NOT NULL DEFAULT 'placeholder_sin_validar',
  fecha_ultima_calibracion DATE,
  UNIQUE (especie, variedad_local, transicion)
);

CREATE TABLE requisitos_especie (
  id SERIAL PRIMARY KEY,
  especie VARCHAR NOT NULL,
  variedad_local VARCHAR,
  humedad_suelo_minima FLOAT,
  humedad_suelo_maxima FLOAT,
  horas_luz_criticas FLOAT,
  radiacion_solar_minima FLOAT,
  tipo_suelo_preferido TEXT[],
  ph_suelo_min FLOAT,
  ph_suelo_max FLOAT,
  -- Temperaturas cardinales para el reloj de GDD (services/pheno_engine.tiempo_termico_diario).
  -- Con solo esto ya se puede calcular_idoneidad() -- "nivel_generico" en la jerarquia de
  -- madurez de especie. Construir un Cultivo simulable requiere ademas umbral_fenologico_config.
  tb FLOAT,
  t_optima FLOAT,
  tc FLOAT,
  foto_critico FLOAT,
  foto_sens FLOAT,
  vern_req FLOAT,
  fuente VARCHAR NOT NULL DEFAULT 'placeholder_sin_validar',
  UNIQUE (especie, variedad_local)
);

CREATE TABLE rasgos_rotacion_especie (
  especie VARCHAR PRIMARY KEY,
  fija_nitrogeno BOOLEAN NOT NULL,
  familia_botanica VARCHAR NOT NULL,
  demanda_hidrica_relativa VARCHAR CHECK (demanda_hidrica_relativa IN ('alta', 'media', 'baja')),
  profundidad_raiz_relativa VARCHAR,
  -- Para motor_rotacion.PERFIL: exigente (demanda de nutrientes), intervalo_rotacion
  -- (temporadas minimas antes de repetir -- reemplaza al booleano ruptura_ciclo_patogeno),
  -- siembra_mes/siembra_dia (default antes de calibrar con el calendario dinamico), perenne
  -- (pradera/barbecho como opcion real de rotacion, no solo "sembrar algo").
  exigente BOOLEAN,
  intervalo_rotacion INT,
  siembra_mes INT,
  siembra_dia INT,
  perenne BOOLEAN NOT NULL DEFAULT false,
  -- Fase 1 del plan de MVP: max_ciclo (antes global en motor_rotacion.evaluar_cultivos)
  -- pasa a ser por especie, nullable, con fallback al valor global en el código si es NULL.
  -- Resuelve el bug documentado de que papa falla por corte de días, no por clima real.
  max_ciclo_dias INT
);

-- Reglas de dano por fase x peligro (services/motor_estres.Regla). Una especie sin filas
-- aqui NO tiene "riesgo cero" -- motor_rotacion.evaluar_cultivos() la trata como "no
-- modelada" (relleno neutro), nunca como libre de riesgo. Ver advertencia en ese archivo.
CREATE TABLE regla_dano_especie (
  id SERIAL PRIMARY KEY,
  especie VARCHAR NOT NULL,
  variedad_local VARCHAR,
  fase VARCHAR NOT NULL,       -- 'ini->fin' | 'cosecha' | '*'
  peligro VARCHAR NOT NULL,    -- helada | calor | sequia | anegamiento | lluvia_cosecha | ceniza | tizon
  umbral FLOAT NOT NULL,
  minimo INT NOT NULL DEFAULT 1,
  efecto VARCHAR NOT NULL CHECK (efecto IN ('parcial', 'total', 'atraso')),
  valor FLOAT NOT NULL DEFAULT 0,
  fuente VARCHAR NOT NULL DEFAULT 'placeholder_sin_validar',
  -- Mitigacion por manejo real (manejo_predio.tipo_labor) -- ver services/motor_estres.Regla.
  -- Solo tiene sentido para peligros bioticos (tizon via fungicida); NULL en el resto --
  -- ningun insumo evita una helada o una sequia, no poner mitigado_por ahi.
  mitigado_por VARCHAR,              -- tipo_labor de manejo_predio que atenua esta regla
  factor_mitigacion FLOAT NOT NULL DEFAULT 0,      -- fraccion de 'valor' que se evita
  ventana_mitigacion_dias INT NOT NULL DEFAULT 0   -- dias previos al evento que protegen
);

-- ============================================================
-- Rotación: prioridades del agricultor — pertenecen a la tierra, no al ciclo actual
-- ============================================================

CREATE TABLE prioridades_agricultor (
  id SERIAL PRIMARY KEY,
  id_parcela INT NOT NULL UNIQUE REFERENCES parcela(id),
  prioridad_agua INT CHECK (prioridad_agua BETWEEN 1 AND 5),
  prioridad_ingreso INT CHECK (prioridad_ingreso BETWEEN 1 AND 5),
  prioridad_suelo INT CHECK (prioridad_suelo BETWEEN 1 AND 5),
  restricciones_equipo TEXT[]
);

-- ============================================================
-- Red de alertas de variedad (sustituye a "guardadoras" institucionales)
-- ============================================================

CREATE TABLE alerta_busqueda_variedad (
  id SERIAL PRIMARY KEY,
  id_parcela_solicitante INT NOT NULL REFERENCES parcela(id),
  especie VARCHAR NOT NULL,
  caracteristicas_requeridas TEXT[],
  unidad_administrativa_local VARCHAR NOT NULL,
  fecha_creacion DATE NOT NULL DEFAULT CURRENT_DATE,
  estado VARCHAR NOT NULL DEFAULT 'abierta' CHECK (estado IN ('abierta', 'cerrada'))
);

CREATE TABLE respuesta_alerta (
  id SERIAL PRIMARY KEY,
  id_alerta INT NOT NULL REFERENCES alerta_busqueda_variedad(id),
  id_usuario_respondiente INT NOT NULL REFERENCES usuarios(id),
  descripcion_semilla_ofrecida TEXT NOT NULL,
  fecha_respuesta DATE NOT NULL DEFAULT CURRENT_DATE
);

-- Conocimiento tradicional de variedad, aportado por cualquier agricultor que la siembra
-- (función de guardián sin el rol institucional). No se confía en un solo aporte: ver
-- docs/modelo-conceptual-phenoshield.md sección 8.3 para el umbral de coincidencia que
-- promueve esto a requisitos_especie/rasgos_rotacion_especie.
CREATE TABLE caracteristica_variedad_aportada (
  id SERIAL PRIMARY KEY,
  especie VARCHAR NOT NULL,
  variedad_local VARCHAR NOT NULL,
  id_usuario_aportante INT NOT NULL REFERENCES usuarios(id),
  caracteristicas TEXT[],
  ciclo_dias_estimado INT,
  descripcion_libre TEXT,
  fecha_aporte DATE NOT NULL DEFAULT CURRENT_DATE
);

-- Vista pública: lo único que ve otro agricultor de una alerta/respuesta.
-- Nunca expone id_parcela_solicitante, id_usuario_respondiente, ni geometría exacta.
CREATE VIEW vista_publica_alerta AS
  SELECT id, especie, caracteristicas_requeridas, unidad_administrativa_local, fecha_creacion, estado
  FROM alerta_busqueda_variedad;

CREATE VIEW vista_publica_respuesta AS
  SELECT id, id_alerta, descripcion_semilla_ofrecida, fecha_respuesta
  FROM respuesta_alerta;

-- ============================================================
-- Ingesta de datos NASA: jobs asíncronos y cache de consulta
-- ============================================================

-- Sin CHECK de valores fijos en proveedor/producto: el catálogo de fuentes
-- crece (agregamos VNP13A1, GRACE, GAEZ a mitad de este proyecto). Validar
-- valores conocidos en la capa de aplicación, no en la base de datos.
CREATE TABLE job_extraccion (
  id SERIAL PRIMARY KEY,
  id_perfil_climatico INT NOT NULL REFERENCES perfil_climatico_regional(id),
  proveedor VARCHAR NOT NULL,
  producto VARCHAR NOT NULL,
  job_id_externo VARCHAR,
  estado VARCHAR NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'en_proceso', 'completo', 'error')),
  fecha_solicitud TIMESTAMP NOT NULL DEFAULT now(),
  fecha_completado TIMESTAMP
);

-- Capas de parcela: HLS, SRTM, SMAP, POWER, ECOSTRESS — todo lo que se consulta
-- por polígono o centroide de una parcela específica.
CREATE TABLE cache_consulta_grilla (
  id SERIAL PRIMARY KEY,
  id_parcela INT NOT NULL REFERENCES parcela(id),
  capa VARCHAR NOT NULL,
  periodo_inicio DATE NOT NULL,
  periodo_fin DATE NOT NULL,
  valor FLOAT,
  resolucion_nativa VARCHAR NOT NULL,
  version_producto VARCHAR,
  cobertura VARCHAR NOT NULL CHECK (cobertura IN ('completa', 'parcial_nubes', 'sin_dato')),
  fecha_consulta TIMESTAMP NOT NULL DEFAULT now(),
  UNIQUE (id_parcela, capa, periodo_inicio, periodo_fin)
);

-- Calibración de microclima por parcela: delta de temperatura (no offset de días) que
-- hace coincidir la suma térmica de la grilla con la fecha real de un indicador local
-- observado en esa parcela. Ver services/pheno_engine.delta_microclima.
CREATE TABLE calibracion_microclima_parcela (
  id SERIAL PRIMARY KEY,
  id_parcela INT NOT NULL REFERENCES parcela(id),
  indicador VARCHAR NOT NULL,
  delta_temperatura FLOAT NOT NULL,
  n_observaciones INT NOT NULL,
  fecha_calibracion DATE NOT NULL DEFAULT CURRENT_DATE
);

-- Capas regionales: GRACE (~300km) y cualquier otra señal que por diseño
-- nunca varía entre parcelas de la misma región. Separada de la tabla anterior
-- para no repetir el mismo valor fila por fila en cada parcela.
CREATE TABLE cache_consulta_regional (
  id SERIAL PRIMARY KEY,
  id_perfil_climatico INT NOT NULL REFERENCES perfil_climatico_regional(id),
  capa VARCHAR NOT NULL,
  periodo_inicio DATE NOT NULL,
  periodo_fin DATE NOT NULL,
  valor FLOAT,
  fecha_consulta TIMESTAMP NOT NULL DEFAULT now(),
  UNIQUE (id_perfil_climatico, capa, periodo_inicio, periodo_fin)
);

-- ============================================================
-- Notificaciones (Flujo 7) — qué cambió materialmente y qué ya se entregó
-- ============================================================

CREATE TABLE notificacion_pendiente (
  id SERIAL PRIMARY KEY,
  id_parcela INT NOT NULL REFERENCES parcela(id),
  tipo VARCHAR NOT NULL,
  contenido JSONB NOT NULL,
  fecha_generada TIMESTAMP NOT NULL DEFAULT now(),
  entregada BOOLEAN NOT NULL DEFAULT false
);
CREATE INDEX idx_notificacion_pendiente_parcela ON notificacion_pendiente (id_parcela, entregada);
