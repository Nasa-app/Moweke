-- Ecorregion por predio. La tabla ecoregion_wwf existia vacia desde el schema inicial
-- ("import unico desde el shapefile WWF"); el diseno dejaba la asignacion para "cuando
-- exista una segunda region real", y ya existe (hay predios en Chiloe y en el valle central).
--
-- Los datos son de "Biomes and Ecoregions 2017" (RESOLVE), la revision del mapa de WWF:
-- ver database/importar_ecorregiones.py. Despues de esto hay que correr
-- database/seed_ecorregiones.sql, que carga las ecorregiones y las asigna a las parcelas.
--
-- No se toca `bioma_tipo` ni perfil_climatico_regional: son la clasificacion propia de
-- cuatro valores del proyecto, y no hay equivalencia publicada con los biomas de WWF.
-- Ya incorporado en database/schema.sql para despliegues nuevos.

BEGIN;

ALTER TABLE ecoregion_wwf
  ADD COLUMN eco_id INT,                 -- identificador de la ecorregion en la fuente
  ADD COLUMN bioma_wwf VARCHAR,          -- uno de los 14 biomas de WWF, tal como viene
  ADD COLUMN reino VARCHAR,              -- reino biogeografico (ej. Neotropic)
  ADD COLUMN fuente VARCHAR,
  ADD CONSTRAINT ecoregion_wwf_eco_id_key UNIQUE (eco_id);

ALTER TABLE parcela ADD COLUMN id_ecoregion INT REFERENCES ecoregion_wwf(id);

COMMIT;
