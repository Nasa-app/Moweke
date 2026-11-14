-- Corrección puntual (Fase 3): alinear fase con lo que catalogo_especies.construir_cultivo
-- realmente genera. Ver comentario en seed_especies.sql -- ya corregido ahí para despliegues
-- nuevos; este archivo queda como registro de lo aplicado a la base de Railway ya corriendo.
UPDATE regla_dano_especie SET fase = REPLACE(fase, 'tuberizacion', 'floracion') WHERE especie = 'papa';
UPDATE regla_dano_especie SET fase = REPLACE(fase, 'bulbificacion', 'floracion') WHERE especie = 'ajo_chilote';
