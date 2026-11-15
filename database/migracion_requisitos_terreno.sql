-- Requisitos de terreno de EcoCrop que el importador no cargaba: altitud maxima, textura,
-- drenaje y salinidad del suelo. Ya incorporado en database/schema.sql para despliegues
-- nuevos -- este archivo queda como registro de lo que se aplica a la base de Railway ya
-- corriendo. Despues hay que correr database/seed_ecocrop_terreno.sql (lo genera
-- database/importar_ecocrop.py) para llenar las columnas.
--
-- Solo agrega columnas: no borra ni reescribe nada existente. Se deshace con
-- ALTER TABLE requisitos_especie DROP COLUMN <cada una>.

BEGIN;

ALTER TABLE requisitos_especie
  ADD COLUMN IF NOT EXISTS altitud_max_m INT,        -- ALTMX: altitud maxima en m s.n.m.
  ADD COLUMN IF NOT EXISTS textura_opt TEXT[],       -- TEXT: clases optimas (light | medium | heavy | organic)
  ADD COLUMN IF NOT EXISTS textura_rango TEXT[],     -- TEXTR: clases que tolera
  ADD COLUMN IF NOT EXISTS drenaje_opt TEXT[],       -- DRA: poorly | well | excessive
  ADD COLUMN IF NOT EXISTS drenaje_rango TEXT[],     -- DRAR
  ADD COLUMN IF NOT EXISTS salinidad_opt VARCHAR,    -- SAL: none | low | medium | high
  ADD COLUMN IF NOT EXISTS salinidad_max VARCHAR;    -- SALR: la clase mas salina que tolera

COMMIT;
