-- Indicadores locales configurables por la comunidad: que se observa en una zona (aves,
-- floracion de especies) y que anuncia (precipitacion alta o baja, helada, lluvia temprana
-- o tardia). Un administrador carga lo que dicta la comunidad; los agricultores de la zona
-- reportan cuando lo ven; la senal se muestra como "confirmada" cuando coinciden varios.
-- Es informativo: no entra a la simulacion de fechas ni de perdidas.
-- Ya incorporado directo en database/schema.sql para despliegues nuevos -- este archivo
-- queda como registro de lo que se aplica a la base de Railway ya corriendo.
-- bioindicador_observado (sin uso en el codigo) queda como estaba: esta tabla la reemplaza
-- en la practica, pero borrarla es una decision aparte.

CREATE TABLE IF NOT EXISTS zona_indicadores (
  id SERIAL PRIMARY KEY,
  nombre VARCHAR(120) NOT NULL UNIQUE,
  geometria GEOMETRY(Polygon, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_zona_indicadores_geometria ON zona_indicadores USING GIST (geometria);

CREATE TABLE IF NOT EXISTS indicador_local (
  id SERIAL PRIMARY KEY,
  id_zona INT NOT NULL REFERENCES zona_indicadores(id) ON DELETE CASCADE,
  categoria VARCHAR NOT NULL CHECK (categoria IN ('aves', 'floracion')),
  nombre VARCHAR(120) NOT NULL,            -- 'Ulmo', 'Zarapito'
  evento VARCHAR(200) NOT NULL,            -- que se observa: 'primera floracion', 'llegada'
  significado VARCHAR NOT NULL CHECK (significado IN
    ('precipitacion_alta', 'precipitacion_baja', 'helada', 'precipitacion_temprana', 'precipitacion_tardia')),
  nota VARCHAR(300),                       -- como lo dice la comunidad, en sus palabras
  -- Meses del ano en que el evento cuenta (puede cruzar el fin de ano: 11 -> 2).
  mes_desde SMALLINT NOT NULL CHECK (mes_desde BETWEEN 1 AND 12),
  mes_hasta SMALLINT NOT NULL CHECK (mes_hasta BETWEEN 1 AND 12),
  -- Agricultores distintos que tienen que reportarlo para dar la senal por confirmada.
  umbral_reportes SMALLINT NOT NULL DEFAULT 3 CHECK (umbral_reportes BETWEEN 1 AND 50),
  -- Hasta cuantos dias atras un reporte sigue contando.
  vigencia_dias SMALLINT NOT NULL DEFAULT 90 CHECK (vigencia_dias BETWEEN 7 AND 365),
  activo BOOLEAN NOT NULL DEFAULT true,
  creado TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_indicador_local_zona ON indicador_local (id_zona) WHERE activo;

CREATE TABLE IF NOT EXISTS observacion_indicador (
  id SERIAL PRIMARY KEY,
  id_indicador INT NOT NULL REFERENCES indicador_local(id) ON DELETE CASCADE,
  id_usuario INT NOT NULL REFERENCES usuarios(id),
  fecha_observada DATE NOT NULL,
  creado TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (id_indicador, id_usuario, fecha_observada)
);
CREATE INDEX IF NOT EXISTS idx_observacion_indicador_fecha ON observacion_indicador (id_indicador, fecha_observada);
