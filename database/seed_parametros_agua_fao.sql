-- Parametros de agua por especie derivados de FAO-56 (tablas 12 y 22) y FAO-33 (tabla 24). GENERADO por
-- database/derivar_agua_fao.py; no editar a mano. Requiere antes migracion_ky_opcional.sql. Aplicar a mano
-- sobre la base antes de desplegar la API.
--
-- Fuente: Allen, Pereira, Raes y Smith (1998), FAO Irrigation and Drainage Paper 56, caps. 6 y 8,
-- (c) FAO 1998, todos los derechos reservados. Se guardan solo valores derivados, no las tablas. Conviene
-- pedir confirmacion escrita a FAO antes de publicar. Los valores son una guia general, sin validar.
-- 44 especies; 17 con Ky (el resto queda NULL: riego si, perdida por sequia no).
-- Sin parametros de agua: oryza_sativa (arroz inundado: el balance de agua de secano no aplica); brassica_oleracea_var_acephala (la tabla 12 no trae col rizada); brassica_oleracea_var_gongyloides (la tabla 12 no trae colinabo).
-- No pisa las especies que ya tienen fila (papa, haba, ajo_chilote).

BEGIN;
DELETE FROM parametros_agua_cultivo WHERE fuente = 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar';
INSERT INTO parametros_agua_cultivo (especie, zr_m, p_agotamiento, kc_ini, kc_med, kc_fin, ky, fuente, nota) VALUES
  ('allium_cepa', 0.45, 0.3, 0.7, 1.05, 0.75, 1.1, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Onions - dry; Ky de "Onion"'),
  ('allium_cepa_var_cepa', 0.45, 0.3, 0.7, 1.05, 0.75, 1.1, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Onions - dry; Ky de "Onion"'),
  ('apium_graveolens', 0.4, 0.2, 0.7, 1.05, 1.0, NULL, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Celery; sin Ky en la tabla 24'),
  ('apium_graveolens_var_dulce', 0.4, 0.2, 0.7, 1.05, 1.0, NULL, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Celery; sin Ky en la tabla 24'),
  ('arachis_hypogaea', 0.75, 0.5, 0.4, 1.15, 0.6, 0.7, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Groundnut (Peanut); Ky de "Groundnet"'),
  ('beta_vulgaris', 0.8, 0.5, 0.5, 1.05, 0.95, NULL, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Beets, table; sin Ky en la tabla 24'),
  ('beta_vulgaris_var_saccharifera', 0.95, 0.55, 0.35, 1.2, 0.7, 1.0, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Sugar Beet; Ky de "Sugarbeet"'),
  ('brassica_oleracea_var_botrytis', 0.55, 0.45, 0.7, 1.05, 0.95, NULL, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Cauliflower; sin Ky en la tabla 24'),
  ('brassica_oleracea_var_capitata', 0.65, 0.45, 0.7, 1.05, 0.95, 0.95, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Cabbage; Ky de "Cabbage"'),
  ('brassica_oleracea_var_gemmifera', 0.5, 0.45, 0.7, 1.05, 0.95, NULL, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Brussel Sprouts; sin Ky en la tabla 24'),
  ('brassica_oleracea_var_italica', 0.5, 0.45, 0.7, 1.05, 0.95, NULL, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Broccoli; sin Ky en la tabla 24'),
  ('capsicum_annuum', 0.75, 0.3, 0.6, 1.05, 0.9, 1.1, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Sweet Peppers (bell); Ky de "Pepper"'),
  ('carthamus_tinctorius', 1.5, 0.6, 0.35, 1.07, 0.25, 0.8, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Safflower; Ky de "Safflower"'),
  ('citrullus_lanatus', 1.15, 0.4, 0.4, 1.0, 0.75, 1.1, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Watermelon; Ky de "Watermelon"'),
  ('cucumis_melo', 1.17, 0.43, 0.5, 0.95, 0.68, NULL, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Cantaloupe + Sweet Melons; sin Ky en la tabla 24'),
  ('cucumis_sativus', 0.95, 0.5, 0.55, 1.0, 0.82, NULL, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Cucumber - Fresh Market + Cucumber - Machine harvest; sin Ky en la tabla 24'),
  ('cucurbita_maxima', 1.25, 0.35, 0.5, 1.0, 0.8, NULL, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Pumpkin, Winter Squash; sin Ky en la tabla 24'),
  ('cucurbita_mixta', 1.25, 0.35, 0.5, 1.0, 0.8, NULL, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Pumpkin, Winter Squash; sin Ky en la tabla 24'),
  ('cucurbita_moschata', 1.25, 0.35, 0.5, 1.0, 0.8, NULL, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Pumpkin, Winter Squash; sin Ky en la tabla 24'),
  ('cucurbita_pepo', 0.8, 0.5, 0.5, 0.95, 0.75, NULL, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Squash, Zucchini; sin Ky en la tabla 24'),
  ('daucus_carota', 0.75, 0.35, 0.7, 1.05, 0.95, NULL, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Carrots; sin Ky en la tabla 24'),
  ('glycine_max', 0.95, 0.5, 0.4, 1.15, 0.5, 0.85, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Soybeans; Ky de "Soybean"'),
  ('gossypium_hirsutum', 1.35, 0.65, 0.35, 1.17, 0.6, 0.85, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Cotton; Ky de "Cotton"'),
  ('helianthus_annuus', 1.15, 0.45, 0.35, 1.07, 0.35, 0.95, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Sunflower; Ky de "Sunflower"'),
  ('ipomoea_batatas', 1.25, 0.65, 0.5, 1.15, 0.65, NULL, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Sweet Potato; sin Ky en la tabla 24'),
  ('lactuca_sativa_var_capitata', 0.4, 0.3, 0.7, 1.0, 0.95, NULL, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Lettuce; sin Ky en la tabla 24'),
  ('lens_culinaris', 0.7, 0.5, 0.4, 1.1, 0.3, NULL, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Lentil; sin Ky en la tabla 24'),
  ('linum_usitatissimum', 1.25, 0.5, 0.35, 1.1, 0.25, NULL, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Flax; sin Ky en la tabla 24'),
  ('lycopersicon_esculentum', 1.1, 0.4, 0.6, 1.15, 0.8, 1.05, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Tomato; Ky de "Tomato"'),
  ('manihot_esculenta', 0.65, 0.35, 0.3, 0.8, 0.3, NULL, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Cassava - year 1; sin Ky en la tabla 24'),
  ('phaseolus_vulgaris', 0.75, 0.45, 0.4, 1.15, 0.35, 1.15, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Beans, dry and Pulses; Ky de "Beans"'),
  ('pisum_sativum', 0.8, 0.38, 0.45, 1.15, 0.7, 1.15, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Peas - Fresh + Peas - Dry/Seed; Ky de "Peas"'),
  ('raphanus_sativus', 0.4, 0.3, 0.7, 0.9, 0.85, NULL, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Radish; sin Ky en la tabla 24'),
  ('raphanus_sativus_var_radicula', 0.4, 0.3, 0.7, 0.9, 0.85, NULL, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Radish; sin Ky en la tabla 24'),
  ('ricinus_communis', 1.5, 0.5, 0.35, 1.15, 0.55, NULL, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Castorbean (Ricinus); sin Ky en la tabla 24'),
  ('sesamum_indicum', 1.25, 0.6, 0.35, 1.1, 0.25, NULL, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Sesame; sin Ky en la tabla 24'),
  ('solanum_melongena', 0.95, 0.45, 0.6, 1.05, 0.9, NULL, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Egg Plant; sin Ky en la tabla 24'),
  ('sorghum_bicolor', 1.5, 0.55, 0.3, 1.05, 0.55, 0.9, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Sorghum - grain; Ky de "Sorghum"'),
  ('spinacia_oleracea', 0.4, 0.2, 0.7, 1.0, 0.95, NULL, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Spinach; sin Ky en la tabla 24'),
  ('triticum_aestivum', 1.65, 0.55, 0.55, 1.15, 0.33, 1.05, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Winter Wheat - with frozen soils + Winter Wheat - with non-frozen soils; Ky de "Winter wheat"'),
  ('vigna_radiata', 0.8, 0.45, 0.4, 1.05, 0.47, NULL, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Green Gram and Cowpeas; sin Ky en la tabla 24'),
  ('vigna_unguiculata', 0.8, 0.45, 0.4, 1.05, 0.47, NULL, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Green Gram and Cowpeas; sin Ky en la tabla 24'),
  ('zea_mays', 1.35, 0.55, 0.3, 1.2, 0.47, 1.25, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Maize, Field (grain) (field corn); Ky de "Maize"'),
  ('zea_mays_ssp_saccharata', 1.0, 0.5, 0.3, 1.15, 1.05, NULL, 'FAO56_t12_t22_FAO33_t24_mapeo_sin_validar', 'Tabla 12/22: Maize, Sweet (sweet corn); sin Ky en la tabla 24')
ON CONFLICT (especie) DO NOTHING;
COMMIT;
