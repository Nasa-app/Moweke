-- Flujo punto -> predio -> idoneidad (humedad, radiacion, tolerancia climatica).
-- Ya incorporado en database/schema.sql y database/seed_especies.sql para despliegues
-- nuevos -- este archivo queda como registro de lo que se aplica a la base de Railway
-- ya corriendo. Despues de esto hay que volver a correr database/seed_ecocrop.sql
-- (ahora idempotente: actualiza las filas existentes y llena las columnas nuevas).

BEGIN;

-- Requisitos que el metodo EcoCrop necesita y que el importador no cargaba: rango
-- optimo de temperatura y pH (antes solo el punto medio / los extremos), temperatura
-- letal con cualquier signo (regla_dano_especie solo guarda las negativas), lluvia anual,
-- categorias de luz, fotoperiodo y duracion del ciclo.
ALTER TABLE requisitos_especie
  ADD COLUMN t_opt_min FLOAT,
  ADD COLUMN t_opt_max FLOAT,
  ADD COLUMN temperatura_letal FLOAT,
  ADD COLUMN ph_opt_min FLOAT,
  ADD COLUMN ph_opt_max FLOAT,
  ADD COLUMN lluvia_anual_min FLOAT,
  ADD COLUMN lluvia_anual_opt_min FLOAT,
  ADD COLUMN lluvia_anual_opt_max FLOAT,
  ADD COLUMN lluvia_anual_max FLOAT,
  ADD COLUMN luz_min VARCHAR,
  ADD COLUMN luz_opt_min VARCHAR,
  ADD COLUMN luz_opt_max VARCHAR,
  ADD COLUMN luz_max VARCHAR,
  ADD COLUMN fotoperiodo VARCHAR,
  ADD COLUMN ciclo_min_dias INT,
  ADD COLUMN ciclo_max_dias INT;

-- Identidad de la especie, separada de sus requisitos: hasta ahora `especie` era solo
-- un texto repetido en cuatro tablas, sin nombre cientifico, nombre comun ni categoria
-- de uso -- sin esto no se puede mostrar el resultado ni filtrar forestales/ornamentales.
CREATE TABLE especie (
  especie VARCHAR PRIMARY KEY,
  nombre_cientifico VARCHAR,
  nombres_comunes TEXT,          -- texto libre multilingue tal como viene de la fuente
  familia_botanica VARCHAR,
  forma_vida VARCHAR,
  categorias TEXT[],
  fuente VARCHAR NOT NULL
);

INSERT INTO especie (especie, nombre_cientifico, nombres_comunes, familia_botanica, categorias, fuente) VALUES
  ('papa', 'Solanum tuberosum', 'papa', 'Solanaceae', ARRAY['roots/tubers'], 'curado_a_mano'),
  ('ajo_chilote', 'Allium ampeloprasum', 'ajo chilote', 'Amaryllidaceae', ARRAY['vegetables'], 'curado_a_mano'),
  ('haba', 'Vicia faba', 'haba', 'Fabaceae', ARRAY['pulses (grain legumes)'], 'curado_a_mano'),
  ('pradera', NULL, 'pradera', NULL, ARRAY['forage/pasture'], 'curado_a_mano');

-- Equivalencia entre las categorias de luz de EcoCrop y la radiacion global horizontal
-- (GHI) del sitio. EcoCrop NO publica esta equivalencia ni usa la luz en su modelo: los
-- umbrales son criterio propio de este proyecto, sin validar -- por eso viven en una
-- tabla con `fuente` y no en el codigo, y por eso el motor solo los usa para penalizar
-- el puntaje, nunca para descartar una especie. `orden` 1 = mas luz.
CREATE TABLE equivalencia_luz_ghi (
  categoria VARCHAR PRIMARY KEY,
  orden INT NOT NULL UNIQUE,
  ghi_min_kwh_m2_dia FLOAT NOT NULL,   -- limite inferior (inclusivo) de la categoria
  fuente VARCHAR NOT NULL DEFAULT 'criterio_propio_sin_validar'
);

INSERT INTO equivalencia_luz_ghi (categoria, orden, ghi_min_kwh_m2_dia) VALUES
  ('very bright', 1, 6.0),
  ('clear skies', 2, 4.5),
  ('cloudy skies', 3, 2.5),
  ('light shade', 4, 1.5),
  ('heavy shade', 5, 0.0);

-- job_extraccion pasa a registrar tambien las ingestas por predio (Fase A.1 del plan):
-- antes solo podia colgar de un perfil climatico regional y ningun endpoint la escribia.
ALTER TABLE job_extraccion ALTER COLUMN id_perfil_climatico DROP NOT NULL;
ALTER TABLE job_extraccion ADD COLUMN id_parcela INT REFERENCES parcela(id);
ALTER TABLE job_extraccion ADD COLUMN detalle TEXT;
CREATE INDEX idx_job_extraccion_parcela ON job_extraccion (id_parcela, proveedor);

COMMIT;
