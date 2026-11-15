-- Variedades locales conocidas de Chiloe. Los nombres propios no se traducen; los que
-- describen algo (lengua de vaca, yema de huevo) llevan su equivalente en ingles.
-- Lista curada a mano, SIN verificar con una fuente: validar con quien conoce las variedades
-- de la zona antes de darla por cerrada. Agregar variedades aqui, no en el codigo.

INSERT INTO variedad_especie (especie, clave, nombre_es, nombre_en, fuente) VALUES
  ('papa', 'michuñe_azul', 'Michuñe azul', 'Blue Michuñe', 'curado_a_mano_sin_verificar'),
  ('papa', 'michuñe_negra', 'Michuñe negra', 'Black Michuñe', 'curado_a_mano_sin_verificar'),
  ('papa', 'michuñe_roja', 'Michuñe roja', 'Red Michuñe', 'curado_a_mano_sin_verificar'),
  ('papa', 'guadacho', 'Guadacho', 'Guadacho', 'curado_a_mano_sin_verificar'),
  ('papa', 'camota', 'Camota', 'Camota', 'curado_a_mano_sin_verificar'),
  ('papa', 'cordillera', 'Cordillera', 'Cordillera', 'curado_a_mano_sin_verificar'),
  ('papa', 'huicaña', 'Huicaña', 'Huicaña', 'curado_a_mano_sin_verificar'),
  ('papa', 'ñocha', 'Ñocha', 'Ñocha', 'curado_a_mano_sin_verificar'),
  ('papa', 'lengua_de_vaca', 'Lengua de vaca', 'Cow''s tongue', 'curado_a_mano_sin_verificar'),
  ('papa', 'yema_de_huevo', 'Yema de huevo', 'Egg yolk', 'curado_a_mano_sin_verificar'),
  ('papa', 'pata_de_guanaco', 'Pata de guanaco', 'Guanaco foot', 'curado_a_mano_sin_verificar')
ON CONFLICT (especie, clave) DO UPDATE SET nombre_es = EXCLUDED.nombre_es,
  nombre_en = EXCLUDED.nombre_en, fuente = EXCLUDED.fuente;
