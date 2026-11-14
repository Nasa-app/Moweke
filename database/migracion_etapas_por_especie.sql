-- Etapas propias por especie. Hasta aca umbral_fenologico_config obligaba a las mismas
-- tres transiciones para todas las especies (CHECK sobre `transicion`) y el codigo las
-- traducia a emergencia/floracion/madurez -- por eso la tuberizacion de la papa y la
-- bulbificacion del ajo figuraban como "floracion". Ahora cada fila es una etapa con su
-- nombre y su posicion; cada especie (o variedad) define cuantas tiene.
--
-- Ya incorporado en database/schema.sql y database/seed_especies.sql para despliegues
-- nuevos -- este archivo queda como registro de lo aplicado a la base de Railway.

BEGIN;

ALTER TABLE umbral_fenologico_config ADD COLUMN orden INT;
ALTER TABLE umbral_fenologico_config ADD COLUMN etapa VARCHAR;

UPDATE umbral_fenologico_config SET
  orden = CASE transicion WHEN 'siembra_BBCH09' THEN 1 WHEN 'BBCH09_BBCH65' THEN 2 ELSE 3 END,
  etapa = CASE transicion WHEN 'siembra_BBCH09' THEN 'emergencia' WHEN 'BBCH09_BBCH65' THEN 'floracion'
                          ELSE 'madurez' END;

-- `transicion` queda como referencia opcional al tramo BBCH que cubre la etapa.
ALTER TABLE umbral_fenologico_config ALTER COLUMN transicion DROP NOT NULL;

-- Nombres reales de la segunda etapa (el seed ya los traia como comentario).
-- Su `transicion` BBCH queda en NULL: 'BBCH65' (floracion) ya no describe esas etapas y
-- el codigo BBCH correcto de tuberizacion/bulbificacion no se ha verificado contra la escala.
UPDATE umbral_fenologico_config SET etapa = 'tuberizacion' WHERE especie = 'papa' AND orden = 2;
UPDATE umbral_fenologico_config SET etapa = 'bulbificacion' WHERE especie = 'ajo_chilote' AND orden = 2;
UPDATE umbral_fenologico_config SET transicion = NULL
WHERE especie IN ('papa', 'ajo_chilote') AND orden IN (2, 3);

ALTER TABLE umbral_fenologico_config ALTER COLUMN orden SET NOT NULL;
ALTER TABLE umbral_fenologico_config ALTER COLUMN etapa SET NOT NULL;
ALTER TABLE umbral_fenologico_config DROP CONSTRAINT umbral_fenologico_config_transicion_check;
ALTER TABLE umbral_fenologico_config DROP CONSTRAINT umbral_fenologico_config_especie_variedad_local_transicion_key;
-- NULLS NOT DISTINCT: la UNIQUE anterior no protegia las filas genericas (variedad NULL).
ALTER TABLE umbral_fenologico_config
  ADD CONSTRAINT umbral_fenologico_etapa_unica UNIQUE NULLS NOT DISTINCT (especie, variedad_local, orden),
  ADD CONSTRAINT umbral_fenologico_nombre_unico UNIQUE NULLS NOT DISTINCT (especie, variedad_local, etapa);

-- Las reglas de dano nombran sus fases con las etapas de la especie ('a->b'): al
-- cambiar el nombre de la etapa hay que cambiarlo aca, o la regla deja de evaluarse.
UPDATE regla_dano_especie SET fase = replace(fase, 'floracion', 'tuberizacion') WHERE especie = 'papa';
UPDATE regla_dano_especie SET fase = replace(fase, 'floracion', 'bulbificacion') WHERE especie = 'ajo_chilote';

COMMIT;
