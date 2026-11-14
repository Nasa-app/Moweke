-- Fase 2 del plan de MVP: autenticación. usuarios no tenía ni contraseña ni rol.
-- Ya incorporado directo en database/schema.sql para despliegues nuevos -- este
-- archivo queda como registro de lo que se aplicó a la base de Railway ya corriendo.
ALTER TABLE usuarios ADD COLUMN telefono VARCHAR UNIQUE;
ALTER TABLE usuarios ADD COLUMN email VARCHAR UNIQUE;
ALTER TABLE usuarios ADD COLUMN password_hash VARCHAR;
ALTER TABLE usuarios ADD COLUMN rol VARCHAR NOT NULL DEFAULT 'agricultor' CHECK (rol IN ('agricultor', 'admin'));
