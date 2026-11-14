-- Mapa del predio: perimetro dibujado por el agricultor y datos por celda.
--
--   parcela.origen_perimetro  'dibujado' (el agricultor marco el deslinde) o 'aproximado'
--                             (cuadrado generado desde un punto y las hectareas). Todo lo
--                             que mira DENTRO del predio (curva satelital, mapa) solo es
--                             del potrero si el perimetro es dibujado.
--   parcela.srid_utm, lado_celda_m   definen la grilla del predio: celdas cuadradas de
--                             ese lado, alineadas al origen de la zona UTM. Se guardan
--                             para que la grilla sea siempre la misma.
--   cache_celda               un valor por celda, capa e intervalo. cache_consulta_grilla
--                             guarda un valor por predio; no tenia donde poner esto.
--
-- Ya incorporado en database/schema.sql para despliegues nuevos.

BEGIN;

ALTER TABLE parcela
  ADD COLUMN origen_perimetro VARCHAR NOT NULL DEFAULT 'aproximado'
    CHECK (origen_perimetro IN ('dibujado', 'aproximado')),
  ADD COLUMN srid_utm INT,
  ADD COLUMN lado_celda_m FLOAT;

-- Predios existentes: todos son cuadrados aproximados; celda de un acre (63,615 m de lado).
UPDATE parcela SET
  srid_utm = (CASE WHEN ST_Y(ST_Centroid(geometria)) < 0 THEN 32700 ELSE 32600 END)
             + floor((ST_X(ST_Centroid(geometria)) + 180) / 6)::int + 1,
  lado_celda_m = 63.615;

CREATE TABLE cache_celda (
  id BIGSERIAL PRIMARY KEY,
  id_parcela INT NOT NULL REFERENCES parcela(id),
  celda_i INT NOT NULL,            -- indices de ST_SquareGrid(lado_celda_m, perimetro en srid_utm)
  celda_j INT NOT NULL,
  capa VARCHAR NOT NULL,           -- 'ndvi'
  periodo_inicio DATE NOT NULL,
  periodo_fin DATE NOT NULL,
  valor FLOAT,
  visible FLOAT,                   -- fraccion de la celda (dentro del perimetro) que se vio, 0 a 1
  fecha_consulta TIMESTAMP NOT NULL DEFAULT now(),
  UNIQUE (id_parcela, celda_i, celda_j, capa, periodo_inicio)
);
CREATE INDEX idx_cache_celda_parcela ON cache_celda (id_parcela, capa, periodo_inicio);

COMMIT;
