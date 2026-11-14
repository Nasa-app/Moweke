-- Parcela de prueba para verificar cache_consulta_grilla con las fuentes nuevas
-- (cliente_solar, cliente_copernicus) -- no es seed de producto, es fixture de
-- verificacion, igual que el usuario "Agricultor Prueba" ya creado via /api/auth/registro.
-- Punto elegido tierra adentro (-42.45, -73.78, 76 msnm segun Explorador Solar) despues
-- de que el punto de prueba anterior (-42.48, -73.76) resultara ser practicamente costero
-- (6 msnm, bandera "shallow ocean" en AppEEARS) -- confirmado por dos fuentes independientes.
INSERT INTO perfil_climatico_regional (bioma_tipo, utm_zone) VALUES ('templado_costero', '18S');

INSERT INTO parcela (id_usuario, id_perfil_climatico, geometria, altitud_msnm)
SELECT 1, id,
       ST_SetSRID(ST_MakePolygon(ST_MakeLine(ARRAY[
         ST_MakePoint(-73.781, -42.449), ST_MakePoint(-73.779, -42.449),
         ST_MakePoint(-73.779, -42.451), ST_MakePoint(-73.781, -42.451),
         ST_MakePoint(-73.781, -42.449)
       ])), 4326),
       76
FROM perfil_climatico_regional WHERE bioma_tipo = 'templado_costero' ORDER BY id DESC LIMIT 1;
