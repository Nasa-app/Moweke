-- ky (respuesta del rendimiento al deficit de agua, FAO-33 tabla 24) pasa a ser opcional: FAO-56 solo lo
-- publica para ~23 cultivos. Sin ky una especie tiene balance de agua y recomendacion de riego, pero no
-- estimacion de perdida por sequia (el motor la omite cuando ky no es un numero). Ya incorporado en
-- database/schema.sql para despliegues nuevos; este archivo es el registro de lo que se aplica a la base
-- de Railway ya corriendo. Aplicar a mano antes de database/seed_parametros_agua_fao.sql y de la API.
-- Se deshace con ALTER COLUMN ky SET NOT NULL solo si ninguna fila tiene ky NULL.

BEGIN;
ALTER TABLE parametros_agua_cultivo ALTER COLUMN ky DROP NOT NULL;
COMMIT;
