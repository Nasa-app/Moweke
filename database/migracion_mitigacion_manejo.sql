-- Conecta manejo real del predio (fungicida/pesticida) con el riesgo de regla_dano_especie
-- (services/motor_estres.Regla.mitigado_por). Ya incorporado directo en database/schema.sql
-- y database/seed_especies.sql para despliegues nuevos -- este archivo queda como registro
-- de lo que se aplicó a la base de Railway ya corriendo.

ALTER TABLE regla_dano_especie ADD COLUMN mitigado_por VARCHAR;
ALTER TABLE regla_dano_especie ADD COLUMN factor_mitigacion FLOAT NOT NULL DEFAULT 0;
ALTER TABLE regla_dano_especie ADD COLUMN ventana_mitigacion_dias INT NOT NULL DEFAULT 0;

ALTER TABLE manejo_predio ADD CONSTRAINT manejo_predio_tipo_labor_check
  CHECK (tipo_labor IN ('aporque', 'fertilizacion', 'riego', 'drenaje', 'fungicida', 'pesticida'));

UPDATE regla_dano_especie
SET mitigado_por = 'fungicida', factor_mitigacion = 0.6, ventana_mitigacion_dias = 14
WHERE especie = 'papa' AND peligro = 'tizon';
