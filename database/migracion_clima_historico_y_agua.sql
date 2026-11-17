-- Dos tablas nuevas: los parametros de agua de cada cultivo con seguimiento por etapa, y el clima
-- historico diario de cada predio (35 anos, un renglon por ano). Ya incorporadas en
-- database/schema.sql para despliegues nuevos -- este archivo queda como registro de lo que se aplica
-- a la base de Railway ya corriendo.
--
-- Solo crea tablas: no toca ninguna existente. Se deshace con DROP TABLE de las dos.

BEGIN;

-- Parametros del balance de agua FAO-56 y de la respuesta del rendimiento (FAO-33). Los valores salen de
-- FAO Irrigation and Drainage Paper 56 (tablas 12 y 22) y 33 (tabla 24), leidos el 15-nov-2026.
CREATE TABLE IF NOT EXISTS parametros_agua_cultivo (
  especie VARCHAR PRIMARY KEY,
  zr_m FLOAT NOT NULL CHECK (zr_m > 0),                  -- profundidad efectiva de raices (m), centro del rango de la tabla 22
  p_agotamiento FLOAT NOT NULL CHECK (p_agotamiento > 0 AND p_agotamiento < 1),  -- fraccion de agotamiento sin estres
  kc_ini FLOAT NOT NULL,
  kc_med FLOAT NOT NULL,
  kc_fin FLOAT NOT NULL,
  ky FLOAT NOT NULL CHECK (ky > 0),                      -- respuesta del rendimiento al deficit de agua, toda la temporada
  fuente VARCHAR NOT NULL,
  nota TEXT
);

INSERT INTO parametros_agua_cultivo (especie, zr_m, p_agotamiento, kc_ini, kc_med, kc_fin, ky, fuente, nota) VALUES
  ('papa', 0.5, 0.35, 0.5, 1.15, 0.75, 1.1, 'FAO56_tablas_12_22_FAO33_tabla_24',
   'Zr 0,4-0,6 m. Kc medio y final y Ky leidos de las tablas; el Kc inicial (0,5) es el valor publicado habitual pero su columna esta como imagen en la version en linea y no se pudo leer: revisar.'),
  ('haba', 0.6, 0.45, 0.5, 1.15, 0.3, 1.15, 'FAO56_tablas_12_22_FAO33_tabla_24',
   'Zr 0,5-0,7 m. Kc de haba para grano seco (final 0,30; fresca 1,10). Ky de haba no aparece en la tabla 24: se usa el de frijol (1,15).'),
  ('ajo_chilote', 0.4, 0.30, 0.7, 1.0, 0.7, 1.1, 'FAO56_tablas_12_22_FAO33_tabla_24',
   'Zr 0,3-0,5 m. Kc medio y final de ajo leidos de la tabla; el inicial (0,70) no se pudo leer. Ky de ajo no esta en la tabla 24: se usa el de cebolla (1,1).')
ON CONFLICT (especie) DO NOTHING;

-- Clima diario de 1991 al ultimo ano completo, de ERA5 por Open-Meteo, corregido contra el CR2MET de la
-- predio (ver services/ingesta_predio._clima_historico). Un renglon por ano; cada arreglo tiene un valor por
-- dia, desde el 1 de enero (365 o 366).
CREATE TABLE IF NOT EXISTS clima_historico_parcela (
  id_parcela INT NOT NULL REFERENCES parcela(id) ON DELETE CASCADE,
  anio INT NOT NULL,
  tmin REAL[] NOT NULL,
  tmax REAL[] NOT NULL,
  lluvia REAL[] NOT NULL,
  fuente VARCHAR NOT NULL,
  version_producto VARCHAR NOT NULL,
  fecha_consulta TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (id_parcela, anio)
);

COMMIT;
