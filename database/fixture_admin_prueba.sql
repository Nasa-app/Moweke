-- Usuario admin de prueba, autorizado explicitamente por el usuario, solo para verificar
-- end-to-end los endpoints admin nuevos (ingesta/solar, copernicus/disponibilidad) via
-- HTTP real. Mismo patron que "Agricultor Prueba" ya existente (id=1).
INSERT INTO usuarios (nombre, pais, email, password_hash, rol, geometria)
VALUES ('Admin Prueba', 'Chile', 'admin-prueba@mogewe.test',
        '$2b$12$u5Anv.bnnxVSUOF1qr7Ofuk1MM2hWNrEw9JWdm.mkzgnvGkD1zsvi', 'admin',
        ST_SetSRID(ST_MakePoint(-73.78, -42.45), 4326))
RETURNING id;
