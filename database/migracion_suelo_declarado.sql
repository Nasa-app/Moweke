-- Profundidad y fertilidad del suelo (EcoCrop DEP/DEPR y FER/FERR) y las cuatro respuestas del
-- agricultor sobre su suelo: drenaje, sal, profundidad y fertilidad. Ya incorporado en
-- database/schema.sql para despliegues nuevos -- este archivo queda como registro de lo que se
-- aplica a la base de Railway ya corriendo. Despues hay que correr
-- database/seed_ecocrop_terreno.sql (lo genera database/importar_ecocrop.py --terreno).
--
-- Solo agrega columnas, todas opcionales: no borra ni reescribe nada existente. Se deshace con
-- ALTER TABLE ... DROP COLUMN <cada una>.

BEGIN;

ALTER TABLE requisitos_especie
  ADD COLUMN IF NOT EXISTS profundidad_opt VARCHAR,   -- DEP: very_shallow | shallow | medium | deep
  ADD COLUMN IF NOT EXISTS profundidad_min VARCHAR,   -- DEPR: la menos profunda que tolera
  ADD COLUMN IF NOT EXISTS fertilidad_opt VARCHAR,    -- FER: low | moderate | high
  ADD COLUMN IF NOT EXISTS fertilidad_min VARCHAR;    -- FERR: la menos fertil que tolera

-- Lo que el agricultor responde sobre su suelo. NULL = no ha respondido.
ALTER TABLE parcela
  ADD COLUMN IF NOT EXISTS suelo_drenaje VARCHAR
    CHECK (suelo_drenaje IN ('poorly', 'well', 'excessive')),
  ADD COLUMN IF NOT EXISTS suelo_salinidad VARCHAR
    CHECK (suelo_salinidad IN ('low', 'medium', 'high')),
  ADD COLUMN IF NOT EXISTS suelo_profundidad VARCHAR
    CHECK (suelo_profundidad IN ('very_shallow', 'shallow', 'medium', 'deep')),
  ADD COLUMN IF NOT EXISTS suelo_fertilidad VARCHAR
    CHECK (suelo_fertilidad IN ('low', 'moderate', 'high'));

COMMIT;
