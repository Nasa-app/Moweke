-- Nombre de cada especie en espanol e ingles, y variedades locales conocidas con su nombre
-- por idioma. Ya incorporado en database/schema.sql para despliegues nuevos -- este archivo
-- queda como registro de lo que se aplica a la base de Railway ya corriendo.
-- Despues de aplicarlo, cargar database/seed_nombres_especies.sql (los nombres) y
-- database/seed_variedades.sql.

ALTER TABLE especie ADD COLUMN IF NOT EXISTS nombre_es VARCHAR;
ALTER TABLE especie ADD COLUMN IF NOT EXISTS nombre_en VARCHAR;

CREATE TABLE IF NOT EXISTS variedad_especie (
  especie VARCHAR NOT NULL REFERENCES especie(especie),
  clave VARCHAR NOT NULL,
  nombre_es VARCHAR NOT NULL,
  nombre_en VARCHAR NOT NULL,
  fuente VARCHAR NOT NULL,
  PRIMARY KEY (especie, clave)
);

-- Las especies curadas no vienen en seed_nombres_especies.sql (que no las toca): se nombran aquí.
UPDATE especie e SET nombre_es = n.nombre_es, nombre_en = n.nombre_en
FROM (VALUES
  ('papa', 'Papa', 'Potato'),
  ('ajo_chilote', 'Ajo chilote', 'Chiloé garlic'),
  ('haba', 'Haba', 'Faba bean'),
  ('pradera', 'Pradera', 'Pasture')
) AS n(especie, nombre_es, nombre_en)
WHERE e.especie = n.especie;
