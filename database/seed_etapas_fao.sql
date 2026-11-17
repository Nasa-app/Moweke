-- Etapas por especie derivadas de FAO-56, tabla 11. GENERADO por database/derivar_etapas_fao.py;
-- no editar a mano. Aplicar a mano sobre la base antes de desplegar la API.
--
-- Fuente: Allen, Pereira, Raes y Smith (1998), FAO Irrigation and Drainage Paper 56, cap. 6,
-- tabla 11, https://www.fao.org/3/x0490e/x0490e0b.htm (c) FAO 1998, todos los derechos reservados. Se guardan solo los
-- valores derivados, no la tabla. Conviene pedir confirmacion escrita a FAO antes de publicar.
-- El capitulo dice que los valores son "solo una guia general".
--
-- Metodo: grados-dia de cada etapa = integral del reloj termico del motor (tb/to/tc de la especie)
-- sobre ERA5 (Open-Meteo) de una coordenada de la region de la fila, siembra el dia 15 del mes,
-- anos 2015-2024; gdd_minimo/gdd_maximo = minimo/maximo entre anos y filas FAO de la
-- especie. Unico contraste hecho: la papa (4 filas FAO vs INIA Boletin 396); no es una validacion
-- general. Las coordenadas de regiones genericas (Mediterranean, Arid, Tropics, Europe...) son una
-- eleccion propia y estan marcadas para revision en el script (REGIONES).
-- Filas FAO usadas: 101; omitidas por falta de region o fecha: 4.
-- Etapas: inicial, desarrollo, media, madurez (reportes 'brotó'/'floreció' no las reanclan).
-- Solo se escriben las especies con total gdd_maximo / total gdd_minimo <= 2. Excluidas (26, rango entre regiones demasiado ancho para usar el punto medio):
--   allium_cepa (x2.17)
--   allium_cepa_var_cepa (x2.17)
--   apium_graveolens (x3.5)
--   apium_graveolens_var_dulce (x2.69)
--   beta_vulgaris_var_saccharifera (x6.05)
--   brassica_oleracea_var_acephala (x3.2)
--   brassica_oleracea_var_gemmifera (x4.27)
--   brassica_oleracea_var_gongyloides (x4.85)
--   capsicum_annuum (x2.38)
--   carthamus_tinctorius (x2.83)
--   cucumis_melo (x6.1)
--   cucurbita_maxima (x2.18)
--   cucurbita_mixta (x2.05)
--   cucurbita_moschata (x2.41)
--   gossypium_hirsutum (x2.36)
--   lactuca_sativa_var_capitata (x2.82)
--   lycopersicon_esculentum (x2.14)
--   phaseolus_vulgaris (x11.1)
--   pisum_sativum (x2.33)
--   raphanus_sativus (x2.77)
--   solanum_melongena (x2.46)
--   spinacia_oleracea (x2.45)
--   triticum_aestivum (x5.55)
--   vigna_unguiculata (x2.04)
--   zea_mays (x5.31)
--   zea_mays_ssp_saccharata (x4.91)
-- No pisa especies con etapas de otra fuente.

BEGIN;
DELETE FROM umbral_fenologico_config WHERE fuente = 'FAO56_t11_derivado_sin_validar';
INSERT INTO umbral_fenologico_config (especie, variedad_local, orden, etapa, gdd_minimo, gdd_maximo, fuente)
SELECT v.especie, NULL, v.orden, v.etapa, v.gdd_minimo, v.gdd_maximo, v.fuente FROM (VALUES
  ('arachis_hypogaea', 1, 'inicial', 319, 410, 'FAO56_t11_derivado_sin_validar'),
  ('arachis_hypogaea', 2, 'desarrollo', 598, 649, 'FAO56_t11_derivado_sin_validar'),
  ('arachis_hypogaea', 3, 'media', 481, 506, 'FAO56_t11_derivado_sin_validar'),
  ('arachis_hypogaea', 4, 'madurez', 287, 328, 'FAO56_t11_derivado_sin_validar'),
  ('beta_vulgaris', 1, 'inicial', 150, 259, 'FAO56_t11_derivado_sin_validar'),
  ('beta_vulgaris', 2, 'desarrollo', 256, 329, 'FAO56_t11_derivado_sin_validar'),
  ('beta_vulgaris', 3, 'media', 233, 298, 'FAO56_t11_derivado_sin_validar'),
  ('beta_vulgaris', 4, 'madurez', 95, 131, 'FAO56_t11_derivado_sin_validar'),
  ('brassica_oleracea_var_botrytis', 1, 'inicial', 66, 157, 'FAO56_t11_derivado_sin_validar'),
  ('brassica_oleracea_var_botrytis', 2, 'desarrollo', 332, 376, 'FAO56_t11_derivado_sin_validar'),
  ('brassica_oleracea_var_botrytis', 3, 'media', 273, 317, 'FAO56_t11_derivado_sin_validar'),
  ('brassica_oleracea_var_botrytis', 4, 'madurez', 100, 120, 'FAO56_t11_derivado_sin_validar'),
  ('brassica_oleracea_var_capitata', 1, 'inicial', 122, 219, 'FAO56_t11_derivado_sin_validar'),
  ('brassica_oleracea_var_capitata', 2, 'desarrollo', 400, 453, 'FAO56_t11_derivado_sin_validar'),
  ('brassica_oleracea_var_capitata', 3, 'media', 300, 343, 'FAO56_t11_derivado_sin_validar'),
  ('brassica_oleracea_var_capitata', 4, 'madurez', 84, 117, 'FAO56_t11_derivado_sin_validar'),
  ('brassica_oleracea_var_italica', 1, 'inicial', 165, 295, 'FAO56_t11_derivado_sin_validar'),
  ('brassica_oleracea_var_italica', 2, 'desarrollo', 468, 502, 'FAO56_t11_derivado_sin_validar'),
  ('brassica_oleracea_var_italica', 3, 'media', 375, 434, 'FAO56_t11_derivado_sin_validar'),
  ('brassica_oleracea_var_italica', 4, 'madurez', 137, 172, 'FAO56_t11_derivado_sin_validar'),
  ('citrullus_lanatus', 1, 'inicial', 19, 78, 'FAO56_t11_derivado_sin_validar'),
  ('citrullus_lanatus', 2, 'desarrollo', 56, 165, 'FAO56_t11_derivado_sin_validar'),
  ('citrullus_lanatus', 3, 'media', 142, 245, 'FAO56_t11_derivado_sin_validar'),
  ('citrullus_lanatus', 4, 'madurez', 231, 275, 'FAO56_t11_derivado_sin_validar'),
  ('cucumis_sativus', 1, 'inicial', 177, 321, 'FAO56_t11_derivado_sin_validar'),
  ('cucumis_sativus', 2, 'desarrollo', 236, 394, 'FAO56_t11_derivado_sin_validar'),
  ('cucumis_sativus', 3, 'media', 353, 496, 'FAO56_t11_derivado_sin_validar'),
  ('cucumis_sativus', 4, 'madurez', 165, 250, 'FAO56_t11_derivado_sin_validar'),
  ('cucurbita_pepo', 1, 'inicial', 231, 301, 'FAO56_t11_derivado_sin_validar'),
  ('cucurbita_pepo', 2, 'desarrollo', 411, 483, 'FAO56_t11_derivado_sin_validar'),
  ('cucurbita_pepo', 3, 'media', 309, 367, 'FAO56_t11_derivado_sin_validar'),
  ('cucurbita_pepo', 4, 'madurez', 189, 220, 'FAO56_t11_derivado_sin_validar'),
  ('daucus_carota', 1, 'inicial', 141, 332, 'FAO56_t11_derivado_sin_validar'),
  ('daucus_carota', 2, 'desarrollo', 306, 550, 'FAO56_t11_derivado_sin_validar'),
  ('daucus_carota', 3, 'media', 506, 946, 'FAO56_t11_derivado_sin_validar'),
  ('daucus_carota', 4, 'madurez', 107, 263, 'FAO56_t11_derivado_sin_validar'),
  ('glycine_max', 1, 'inicial', 157, 253, 'FAO56_t11_derivado_sin_validar'),
  ('glycine_max', 2, 'desarrollo', 212, 364, 'FAO56_t11_derivado_sin_validar'),
  ('glycine_max', 3, 'media', 551, 965, 'FAO56_t11_derivado_sin_validar'),
  ('glycine_max', 4, 'madurez', 129, 306, 'FAO56_t11_derivado_sin_validar'),
  ('helianthus_annuus', 1, 'inicial', 257, 343, 'FAO56_t11_derivado_sin_validar'),
  ('helianthus_annuus', 2, 'desarrollo', 477, 548, 'FAO56_t11_derivado_sin_validar'),
  ('helianthus_annuus', 3, 'media', 752, 801, 'FAO56_t11_derivado_sin_validar'),
  ('helianthus_annuus', 4, 'madurez', 415, 446, 'FAO56_t11_derivado_sin_validar'),
  ('ipomoea_batatas', 1, 'inicial', 95, 153, 'FAO56_t11_derivado_sin_validar'),
  ('ipomoea_batatas', 2, 'desarrollo', 232, 280, 'FAO56_t11_derivado_sin_validar'),
  ('ipomoea_batatas', 3, 'media', 552, 612, 'FAO56_t11_derivado_sin_validar'),
  ('ipomoea_batatas', 4, 'madurez', 352, 412, 'FAO56_t11_derivado_sin_validar'),
  ('lens_culinaris', 1, 'inicial', 71, 295, 'FAO56_t11_derivado_sin_validar'),
  ('lens_culinaris', 2, 'desarrollo', 224, 430, 'FAO56_t11_derivado_sin_validar'),
  ('lens_culinaris', 3, 'media', 555, 753, 'FAO56_t11_derivado_sin_validar'),
  ('lens_culinaris', 4, 'madurez', 368, 473, 'FAO56_t11_derivado_sin_validar'),
  ('linum_usitatissimum', 1, 'inicial', 98, 268, 'FAO56_t11_derivado_sin_validar'),
  ('linum_usitatissimum', 2, 'desarrollo', 267, 365, 'FAO56_t11_derivado_sin_validar'),
  ('linum_usitatissimum', 3, 'media', 442, 806, 'FAO56_t11_derivado_sin_validar'),
  ('linum_usitatissimum', 4, 'madurez', 322, 419, 'FAO56_t11_derivado_sin_validar'),
  ('oryza_sativa', 1, 'inicial', 245, 404, 'FAO56_t11_derivado_sin_validar'),
  ('oryza_sativa', 2, 'desarrollo', 318, 400, 'FAO56_t11_derivado_sin_validar'),
  ('oryza_sativa', 3, 'media', 650, 993, 'FAO56_t11_derivado_sin_validar'),
  ('oryza_sativa', 4, 'madurez', 233, 506, 'FAO56_t11_derivado_sin_validar'),
  ('raphanus_sativus_var_radicula', 1, 'inicial', 38, 117, 'FAO56_t11_derivado_sin_validar'),
  ('raphanus_sativus_var_radicula', 2, 'desarrollo', 86, 115, 'FAO56_t11_derivado_sin_validar'),
  ('raphanus_sativus_var_radicula', 3, 'media', 137, 174, 'FAO56_t11_derivado_sin_validar'),
  ('raphanus_sativus_var_radicula', 4, 'madurez', 37, 59, 'FAO56_t11_derivado_sin_validar'),
  ('ricinus_communis', 1, 'inicial', 15, 165, 'FAO56_t11_derivado_sin_validar'),
  ('ricinus_communis', 2, 'desarrollo', 119, 334, 'FAO56_t11_derivado_sin_validar'),
  ('ricinus_communis', 3, 'media', 363, 423, 'FAO56_t11_derivado_sin_validar'),
  ('ricinus_communis', 4, 'madurez', 194, 343, 'FAO56_t11_derivado_sin_validar'),
  ('sesamum_indicum', 1, 'inicial', 200, 243, 'FAO56_t11_derivado_sin_validar'),
  ('sesamum_indicum', 2, 'desarrollo', 317, 364, 'FAO56_t11_derivado_sin_validar'),
  ('sesamum_indicum', 3, 'media', 390, 481, 'FAO56_t11_derivado_sin_validar'),
  ('sesamum_indicum', 4, 'madurez', 210, 231, 'FAO56_t11_derivado_sin_validar'),
  ('sorghum_bicolor', 1, 'inicial', 156, 284, 'FAO56_t11_derivado_sin_validar'),
  ('sorghum_bicolor', 2, 'desarrollo', 397, 532, 'FAO56_t11_derivado_sin_validar'),
  ('sorghum_bicolor', 3, 'media', 550, 633, 'FAO56_t11_derivado_sin_validar'),
  ('sorghum_bicolor', 4, 'madurez', 342, 469, 'FAO56_t11_derivado_sin_validar'),
  ('vigna_radiata', 1, 'inicial', 85, 165, 'FAO56_t11_derivado_sin_validar'),
  ('vigna_radiata', 2, 'desarrollo', 186, 276, 'FAO56_t11_derivado_sin_validar'),
  ('vigna_radiata', 3, 'media', 299, 385, 'FAO56_t11_derivado_sin_validar'),
  ('vigna_radiata', 4, 'madurez', 255, 309, 'FAO56_t11_derivado_sin_validar')
) AS v(especie, orden, etapa, gdd_minimo, gdd_maximo, fuente)
WHERE EXISTS (SELECT 1 FROM especie e WHERE e.especie = v.especie)
  AND NOT EXISTS (SELECT 1 FROM umbral_fenologico_config u WHERE u.especie = v.especie);
COMMIT;

-- ============================================================================================
-- SOLO PARA COMPARAR, NO SE APLICA: haba ya tiene etapas propias (placeholder_sin_validar,
-- emergencia/floracion/madurez = 150/250/150 grados-dia, 3 etapas). Esto es lo que daria la tabla 11
-- de FAO-56 en 4 etapas (min-max entre filas y anos). Decide el usuario si reemplaza algo.
--   ('haba', 1, 'inicial', 96, 172, 'FAO56_t11_derivado_sin_validar')
--   ('haba', 2, 'desarrollo', 175, 270, 'FAO56_t11_derivado_sin_validar')
--   ('haba', 3, 'media', 190, 327, 'FAO56_t11_derivado_sin_validar')
--   ('haba', 4, 'madurez', 62, 132, 'FAO56_t11_derivado_sin_validar')
