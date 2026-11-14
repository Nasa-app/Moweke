-- Mogewe — datos de semilla para las especies del proyecto.
-- Esto reemplaza a los diccionarios CULTIVOS/PERFIL/REGLAS que vivian hardcodeados en
-- services/pheno_engine.py, motor_estres.py y motor_rotacion.py. services/catalogo_especies.py
-- construye los objetos de simulacion leyendo estas filas, no codigo Python.
--
-- Alcance: solo papa, ajo_chilote, haba y pradera -- las especies reales de Mogewe.
-- trigo_primavera/maiz/avena/arveja/raps_invierno del codigo original eran ejemplos
-- genericos de demostracion, no parte del alcance de Chiloe -- se dejan fuera a proposito,
-- no se migran.

-- ============================================================
-- requisitos_especie: temperaturas cardinales + idoneidad de sitio
-- ============================================================

INSERT INTO requisitos_especie (especie, variedad_local, tb, t_optima, tc, foto_sens, vern_req, fuente) VALUES
  -- tb reconciliado entre dos placeholders previos (4 y 6) sin fuente — sigue sin validar.
  ('papa', NULL, 6.0, 20, 30, 0, 0, 'placeholder_sin_validar'),
  -- tb/to/tc SI tienen fuente: ficha tecnica INIA (Allium ampeloprasum, via Portal Fruticola) —
  -- minima 7C, optima 15-20C, maxima 30C. El reparto de GDD entre etapas (mas abajo) no viene
  -- de esa ficha, es particion propia calibrada contra la duracion total de ciclo (210-230 dias).
  ('ajo_chilote', NULL, 7.0, 17.5, 30, 0, 0, 'INIA_ficha_tecnica'),
  -- tb/to/tc SI tienen fuente: ficha tecnica CIREN (Haba.pdf) — base 5C, optimo 15-20C, maximo 28C.
  ('haba', NULL, 5.0, 17.5, 28, 0, 0, 'CIREN_ficha_tecnica');
  -- pradera no tiene fila aqui: es perenne, no se simula con reloj de GDD.

-- ============================================================
-- umbral_fenologico_config: GDD por transicion (rango, no punto — el punto medio es lo
-- que usaba el Cultivo hardcodeado; el rango es lo que permite mostrar incertidumbre real)
-- ============================================================

INSERT INTO umbral_fenologico_config (especie, variedad_local, transicion, gdd_minimo, gdd_maximo, fuente) VALUES
  ('papa', NULL, 'siembra_BBCH09', 250, 250, 'placeholder_sin_validar'),
  ('papa', NULL, 'BBCH09_BBCH65', 350, 350, 'placeholder_sin_validar'),  -- "tuberizacion" mapeada a BBCH65
  ('papa', NULL, 'BBCH65_BBCH97', 1100, 1100, 'placeholder_sin_validar'),
  -- Totales (80+250+170=500) calibrados contra la duracion real de ciclo de INIA (210-230
  -- dias) bajo clima sintetico de referencia — el reparto entre etapas sigue sin validar,
  -- solo el total tiene respaldo indirecto.
  ('ajo_chilote', NULL, 'siembra_BBCH09', 80, 80, 'placeholder_sin_validar'),
  ('ajo_chilote', NULL, 'BBCH09_BBCH65', 250, 250, 'placeholder_sin_validar'),  -- "bulbificacion"
  ('ajo_chilote', NULL, 'BBCH65_BBCH97', 170, 170, 'placeholder_sin_validar'),
  -- Suma total (150+250+150=550) cae dentro del rango 450-650 GDD que SI da CIREN para
  -- siembra-cosecha de grano seco. El reparto entre etapas no viene de la ficha.
  ('haba', NULL, 'siembra_BBCH09', 150, 150, 'placeholder_sin_validar'),
  ('haba', NULL, 'BBCH09_BBCH65', 250, 250, 'placeholder_sin_validar'),
  ('haba', NULL, 'BBCH65_BBCH97', 150, 150, 'placeholder_sin_validar');

-- ============================================================
-- rasgos_rotacion_especie
-- ============================================================

INSERT INTO rasgos_rotacion_especie (especie, fija_nitrogeno, familia_botanica, exigente, intervalo_rotacion, siembra_mes, siembra_dia, perenne) VALUES
  ('papa', false, 'solanaceas', true, 3, 10, 15, false),
  ('ajo_chilote', false, 'aliaceas', false, 3, 4, 15, false),
  ('haba', true, 'fabaceas', false, 2, 5, 15, false),
  ('pradera', true, 'pradera', false, 0, NULL, NULL, true);

-- ============================================================
-- regla_dano_especie — ninguna tiene fuente citable, todas placeholder_sin_validar
-- ============================================================

-- Nombres de fase alineados con catalogo_especies.construir_cultivo, que SIEMPRE usa
-- emergencia/floracion/madurez (ver NOMBRE_ETAPA en ese archivo) -- no con el nombre
-- biológico específico (tuberización, bulbificación). Se encontró como bug real al
-- probar contra Postgres (Fase 3 del plan de MVP): con los nombres específicos, las
-- reglas de la etapa media nunca coincidían con las fases que el motor calcula,
-- dejando inactivas justo las reglas de helada en el período más sensible del cultivo.
INSERT INTO regla_dano_especie (especie, variedad_local, fase, peligro, umbral, minimo, efecto, valor) VALUES
  ('papa', NULL, 'emergencia->floracion', 'helada', -1, 1, 'atraso', 14),
  ('papa', NULL, 'emergencia->floracion', 'helada', -4, 1, 'total', 0),
  ('papa', NULL, 'floracion->madurez', 'helada', -1, 1, 'parcial', 0.3),
  ('papa', NULL, 'floracion->madurez', 'calor', 28, 5, 'parcial', 0.25),
  ('papa', NULL, 'floracion->madurez', 'sequia', 0.4, 0, 'parcial', 0.4),
  ('papa', NULL, 'siembra->emergencia', 'anegamiento', 20, 3, 'total', 0),
  ('papa', NULL, 'floracion->madurez', 'anegamiento', 20, 3, 'parcial', 0.4),
  ('papa', NULL, 'floracion->madurez', 'tizon', 90, 3, 'parcial', 0.3),
  ('papa', NULL, '*', 'ceniza', 0, 0, 'parcial', 0.3),

  ('ajo_chilote', NULL, 'emergencia->floracion', 'helada', -3, 1, 'parcial', 0.3),
  ('ajo_chilote', NULL, 'emergencia->floracion', 'helada', -6, 1, 'total', 0),
  ('ajo_chilote', NULL, 'floracion->madurez', 'helada', -2, 1, 'parcial', 0.3),
  ('ajo_chilote', NULL, 'floracion->madurez', 'calor', 30, 5, 'parcial', 0.2),
  ('ajo_chilote', NULL, 'siembra->emergencia', 'anegamiento', 20, 3, 'parcial', 0.3),
  ('ajo_chilote', NULL, 'floracion->madurez', 'anegamiento', 20, 3, 'parcial', 0.35),
  ('ajo_chilote', NULL, 'cosecha', 'lluvia_cosecha', 50, 0, 'parcial', 0.2),
  ('ajo_chilote', NULL, '*', 'ceniza', 0, 0, 'parcial', 0.3),

  ('haba', NULL, 'emergencia->floracion', 'helada', -3, 1, 'parcial', 0.3),
  ('haba', NULL, 'emergencia->floracion', 'helada', -6, 1, 'total', 0),
  ('haba', NULL, 'floracion->madurez', 'helada', -1, 1, 'parcial', 0.5),
  ('haba', NULL, 'floracion->madurez', 'calor', 28, 3, 'parcial', 0.3),
  ('haba', NULL, 'siembra->emergencia', 'anegamiento', 20, 3, 'parcial', 0.3),
  ('haba', NULL, 'floracion->madurez', 'anegamiento', 20, 3, 'parcial', 0.3),
  ('haba', NULL, '*', 'ceniza', 0, 0, 'parcial', 0.3);
  -- pradera no tiene reglas: motor_rotacion.evaluar_cultivos() la trata via perenne=true,
  -- no via "sin reglas" -- son dos caminos distintos al mismo relleno neutro.

-- ============================================================
-- Mitigacion por manejo real (regla_dano_especie.mitigado_por) -- solo tizon de papa.
-- Valores de ventana/factor sin fuente agronomica todavia (fungicida de contacto protege
-- tipicamente 7-14 dias; se usa 14 como referencia conservadora) -- placeholder_sin_validar
-- igual que el resto de esta tabla, calibrar contra ficha tecnica de producto real antes
-- de confiar en el numero, no solo en el mecanismo. ajo_chilote/haba no tienen regla de
-- tizon (es un hongo propio de Solanaceas) -- nada que mitigar ahi.
UPDATE regla_dano_especie
SET mitigado_por = 'fungicida', factor_mitigacion = 0.6, ventana_mitigacion_dias = 14
WHERE especie = 'papa' AND peligro = 'tizon';

-- ============================================================
-- especie: identidad de las cuatro especies curadas. nombre_cientifico enlaza cada una
-- con su fila equivalente de EcoCrop (ej. papa <-> solanum_tuberosum) para que el ranking
-- de idoneidad muestre una sola vez la especie, con el perfil mas maduro.
-- ============================================================
INSERT INTO especie (especie, nombre_cientifico, nombres_comunes, familia_botanica, categorias, fuente) VALUES
  ('papa', 'Solanum tuberosum', 'papa', 'Solanaceae', ARRAY['roots/tubers'], 'curado_a_mano'),
  ('ajo_chilote', 'Allium ampeloprasum', 'ajo chilote', 'Amaryllidaceae', ARRAY['vegetables'], 'curado_a_mano'),
  ('haba', 'Vicia faba', 'haba', 'Fabaceae', ARRAY['pulses (grain legumes)'], 'curado_a_mano'),
  ('pradera', NULL, 'pradera', NULL, ARRAY['forage/pasture'], 'curado_a_mano');

-- ============================================================
-- equivalencia_luz_ghi: categorias de luz de EcoCrop -> GHI del sitio (kWh/m2/dia).
-- Criterio propio sin validar (ver comentario de la tabla en schema.sql): solo penaliza
-- el puntaje de idoneidad, nunca descarta una especie.
-- ============================================================
INSERT INTO equivalencia_luz_ghi (categoria, orden, ghi_min_kwh_m2_dia) VALUES
  ('very bright', 1, 6.0),
  ('clear skies', 2, 4.5),
  ('cloudy skies', 3, 2.5),
  ('light shade', 4, 1.5),
  ('heavy shade', 5, 0.0);
