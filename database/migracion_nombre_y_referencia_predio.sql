-- Nombre de referencia que le da el agricultor a su predio y referencia geografica (pais y region) escrita al
-- ubicarlo. La referencia sale de la geocodificacion inversa (services/cliente_geocodificacion.py) y queda en NULL
-- mientras el servicio no responda. Ya incorporado en database/schema.sql para despliegues nuevos.

ALTER TABLE parcela
  ADD COLUMN IF NOT EXISTS nombre VARCHAR(60),
  ADD COLUMN IF NOT EXISTS pais VARCHAR(80),
  ADD COLUMN IF NOT EXISTS region VARCHAR(120);
