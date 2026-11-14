-- Calibracion de la papa generica contra INIA Remehue (Boletin INIA 396, cap. 2, Sandana
-- y Martinez 2019; https://hdl.handle.net/20.500.14001/6763). Reemplaza los placeholders
-- (tb 6, 250+350+1100 = 1700 grados-dia), que en Quemchi daban un ciclo de diez meses.
--
-- Que dice la fuente y con que confianza:
--   - Temperatura base 4 C y tiempo termico = suma de (T media diaria - 4): texto.
--   - Plantacion a madurez fisiologica: 1300-1500 grados-dia segun variedad (promedio de
--     tres temporadas en Osorno): texto.
--   - Reparto por etapa de ocho variedades (Desiree, Karu, Pukara, Patagonia, Yagana,
--     Puyehue, Rayun, Kuyen): solo esta como grafico de barras (Grafico 3); los valores
--     se leyeron del grafico, error estimado +-10 grados-dia. gdd_minimo/gdd_maximo son
--     el menor y el mayor valor entre esas variedades; 'madurez' suma los tramos
--     tuberizacion->floracion y floracion->madurez del grafico.
--   - Desarrollo: optimo 17,5-24 C, se detiene a 35 C (curva del mismo boletin, adaptada
--     de SUBSTOR). El motor crece lineal hasta t_optima, igual que el metodo de INIA, asi
--     que t_optima guarda el FIN de la meseta optima (24), no su centro.
--
-- Verificado con el clima real 2025-26 de Quemchi y de Chiloe interior (CR2MET): plantada
-- el 15-oct emerge a los 32 dias, inicia tuberizacion a los 56 y madura a los 139-142 --
-- dentro de lo que INIA publica para la zona sur (25-35, 50-60 y 130-150 dias). El motor
-- acumula 1,6-2,8 % menos que la suma simple de INIA en esa temporada.
--
-- No se tocan las reglas de dano de la papa: siguen siendo placeholder_sin_validar.
-- Ya incorporado en database/seed_especies.sql para despliegues nuevos.

BEGIN;

UPDATE requisitos_especie SET tb = 4, t_optima = 24, tc = 35, fuente = 'INIA_Boletin_396'
WHERE especie = 'papa' AND variedad_local IS NULL;

UPDATE umbral_fenologico_config SET gdd_minimo = 215, gdd_maximo = 262
WHERE especie = 'papa' AND variedad_local IS NULL AND etapa = 'emergencia';
UPDATE umbral_fenologico_config SET gdd_minimo = 232, gdd_maximo = 293
WHERE especie = 'papa' AND variedad_local IS NULL AND etapa = 'tuberizacion';
UPDATE umbral_fenologico_config SET gdd_minimo = 812, gdd_maximo = 1026
WHERE especie = 'papa' AND variedad_local IS NULL AND etapa = 'madurez';
UPDATE umbral_fenologico_config SET fuente = 'INIA_Boletin_396', fecha_ultima_calibracion = DATE '2026-11-14'
WHERE especie = 'papa' AND variedad_local IS NULL;

COMMIT;
