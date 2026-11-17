"""Parametros de agua por especie desde FAO-56 (Allen et al., 1998), para las especies que reciben etapas de
database/derivar_etapas_fao.py. Escribe database/seed_parametros_agua_fao.sql.

Fuentes (c) FAO 1998, todos los derechos reservados; ver la nota de licencia de derivar_etapas_fao.py:
  - Kc inicial, medio y final: tabla 12, cap. 6  https://www.fao.org/3/x0490e/x0490e0b.htm
  - profundidad de raices (zr_m) y fraccion de agotamiento (p): tabla 22, cap. 8  https://www.fao.org/3/x0490e/x0490e0e.htm
  - ky (respuesta del rendimiento al deficit): tabla 24, cap. 8 (viene de FAO-33). Solo cubre ~23 cultivos:
    donde la tabla no trae el cultivo, ky queda NULL y el motor no calcula perdida por sequia (si calcula riego).
Los valores son una guia general. No se copian las tablas: solo se escriben los valores derivados por especie.

Reglas de lectura (verificadas contra la pagina): los rangos ('0.4-0.6', '0.60-0.35') se resumen con su punto
medio, como ya se hizo con la papa; un valor con mas de dos decimales lleva pegada la nota al pie ('1.152' es
1.15 con la nota 2) y se trunca a dos decimales; si la fila de un cultivo no trae Kc inicial, vale el de su grupo
(Small Vegetables, Cereals...). Cuando una especie se alimenta de varias filas ('Cucumber: fresh y machine
harvest') se promedian.

Uso: DATABASE_URL no hace falta. python database/derivar_agua_fao.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from derivar_etapas_fao import MAPEO, _Tabla, descargar_html  # noqa: E402

URL_C8 = "https://www.fao.org/3/x0490e/x0490e0e.htm"
FUENTE = "FAO56_t12_t22_FAO33_t24_mapeo_sin_validar"
SALIDA = Path(__file__).with_name("seed_parametros_agua_fao.sql")

# especie del catalogo -> (nombres de fila en tablas 12 y 22, nombre en tabla 24 o None). Nombres de fila tal
# como los escribe FAO; una subfila ('- dry') se escribe 'Onions - dry'. El mapeo es mio y requiere revision.
AGUA: dict[str, tuple[list[str], str | None]] = {
    "allium_cepa": (["Onions - dry"], "Onion"),
    "allium_cepa_var_cepa": (["Onions - dry"], "Onion"),
    "apium_graveolens": (["Celery"], None),
    "apium_graveolens_var_dulce": (["Celery"], None),
    "arachis_hypogaea": (["Groundnut (Peanut)"], "Groundnet"),
    "beta_vulgaris": (["Beets, table"], None),
    "beta_vulgaris_var_saccharifera": (["Sugar Beet"], "Sugarbeet"),
    "brassica_oleracea_var_botrytis": (["Cauliflower"], None),
    "brassica_oleracea_var_capitata": (["Cabbage"], "Cabbage"),
    "brassica_oleracea_var_gemmifera": (["Brussel Sprouts"], None),
    "brassica_oleracea_var_italica": (["Broccoli"], None),
    "capsicum_annuum": (["Sweet Peppers (bell)"], "Pepper"),
    "carthamus_tinctorius": (["Safflower"], "Safflower"),
    "citrullus_lanatus": (["Watermelon"], "Watermelon"),
    "cucumis_melo": (["Cantaloupe", "Sweet Melons"], None),
    "cucumis_sativus": (["Cucumber - Fresh Market", "Cucumber - Machine harvest"], None),
    "cucurbita_maxima": (["Pumpkin, Winter Squash"], None),
    "cucurbita_mixta": (["Pumpkin, Winter Squash"], None),
    "cucurbita_moschata": (["Pumpkin, Winter Squash"], None),
    "cucurbita_pepo": (["Squash, Zucchini"], None),
    "daucus_carota": (["Carrots"], None),
    "glycine_max": (["Soybeans"], "Soybean"),
    "gossypium_hirsutum": (["Cotton"], "Cotton"),
    "helianthus_annuus": (["Sunflower"], "Sunflower"),
    "ipomoea_batatas": (["Sweet Potato"], None),
    "lactuca_sativa_var_capitata": (["Lettuce"], None),
    "lens_culinaris": (["Lentil"], None),
    "linum_usitatissimum": (["Flax"], None),
    "lycopersicon_esculentum": (["Tomato"], "Tomato"),
    "manihot_esculenta": (["Cassava - year 1"], None),
    "phaseolus_vulgaris": (["Beans, dry and Pulses"], "Beans"),
    "pisum_sativum": (["Peas - Fresh", "Peas - Dry/Seed"], "Peas"),
    "raphanus_sativus": (["Radish"], None),
    "raphanus_sativus_var_radicula": (["Radish"], None),
    "ricinus_communis": (["Castorbean (Ricinus)"], None),
    "sesamum_indicum": (["Sesame"], None),
    "solanum_melongena": (["Egg Plant"], None),
    "sorghum_bicolor": (["Sorghum - grain"], "Sorghum"),
    "spinacia_oleracea": (["Spinach"], None),
    "triticum_aestivum": (["Winter Wheat - with frozen soils", "Winter Wheat - with non-frozen soils"], "Winter wheat"),
    "vigna_radiata": (["Green Gram and Cowpeas"], None),
    "vigna_unguiculata": (["Green Gram and Cowpeas"], None),
    "zea_mays": (["Maize, Field (grain) (field corn)"], "Maize"),
    "zea_mays_ssp_saccharata": (["Maize, Sweet (sweet corn)"], None),
}
# Especies con etapas derivadas que NO reciben parametros de agua, con el motivo.
SIN_AGUA = {
    "oryza_sativa": "arroz inundado: el balance de agua de secano no aplica",
    "brassica_oleracea_var_acephala": "la tabla 12 no trae col rizada",
    "brassica_oleracea_var_gongyloides": "la tabla 12 no trae colinabo",
}


def numero(texto: str) -> float | None:
    """'0.60-0.3511' -> 0.475; '1,15' -> 1.15; '' -> None. Trunca a dos decimales (nota al pie pegada)."""
    partes = []
    for trozo in texto.replace(",", ".").split("-"):
        m = re.match(r"\s*(\d+(?:\.\d{1,2})?)", trozo)
        if m:
            partes.append(float(m.group(1)))
    return sum(partes) / len(partes) if partes else None


def leer_filas(tabla: list[list[str]], columnas: int, grupo_ini: bool = False) -> dict[str, list[str]]:
    """Filas de una tabla FAO -> {'Cultivo' o 'Cultivo - subfila': [celdas tras el nombre]}. Las subfilas ('', '- dry', ...)
    cuelgan del cultivo anterior. Con grupo_ini, una fila de seccion ('a. Small Vegetables', '0.7', ...) deja su Kc
    inicial como valor por defecto de las filas siguientes, que lo traen vacio."""
    filas, cultivo, grupo = {}, None, None
    for r in tabla[1:]:
        if not r:
            continue
        if grupo_ini and re.match(r"^[a-z]\. ", r[0]):
            grupo = r[1] if len(r) > 1 else None
            continue
        if len(r) == 1:
            continue
        if r[0] == "":
            nombre = f"{cultivo} {r[1]}".strip()
            celdas = r[2:]
        else:
            cultivo, nombre, celdas = r[0], r[0], r[1:]
        if not any(celdas):
            continue
        filas[nombre] = celdas
        if grupo_ini and not celdas[0]:
            filas[nombre] = [grupo or ""] + celdas[1:]
    return filas


# La tabla 22 escribe algunos cultivos distinto que la 12.
NOMBRE_T22 = {"Radish": "Radishes", "Winter Wheat - with frozen soils": "Winter Wheat",
              "Winter Wheat - with non-frozen soils": "Winter Wheat"}


def valores_agua(t12: dict, t22: dict, nombres: list[str]) -> dict[str, float]:
    kc = [[numero(x) for x in t12[n][:3]] for n in nombres]
    n22 = [NOMBRE_T22.get(n, n) for n in nombres]
    zr = [[float(v) for v in re.findall(r"\d+\.\d+|\d+", t22[n][0])] for n in n22]
    p = [numero(t22[n][1]) for n in n22]
    media = lambda xs: round(sum(xs) / len(xs), 2)
    return {"kc_ini": media([k[0] for k in kc]), "kc_med": media([k[1] for k in kc]),
            "kc_fin": media([k[2] for k in kc]), "zr_m": media([sum(z) / len(z) for z in zr]), "p": media(p)}


def main() -> None:
    import requests
    p6 = _Tabla()
    p6.feed(descargar_html())
    r = requests.get(URL_C8, timeout=60)
    r.raise_for_status()
    p8 = _Tabla()
    p8.feed(r.content.decode("latin-1"))
    t12 = leer_filas(p6.tablas[1], 5, grupo_ini=True)
    t22 = leer_filas(p8.tablas[0], 2)
    ky = {n: numero(c[0]) for n, c in leer_filas(p8.tablas[5], 1).items()}

    con_etapas = {e for c in MAPEO.values() for e in c} - {"haba"}
    sin_cubrir = sorted(con_etapas - set(AGUA) - set(SIN_AGUA))
    if sin_cubrir:
        sys.exit(f"Especies con etapas sin decision de agua: {sin_cubrir}")
    filas, lineas_ky = [], 0
    for especie in sorted(AGUA):
        nombres, nombre_ky = AGUA[especie]
        faltan = [n for n in nombres if n not in t12 or NOMBRE_T22.get(n, n) not in t22]
        if faltan:
            sys.exit(f"{especie}: no encuentro {faltan} en las tablas 12/22")
        v = valores_agua(t12, t22, nombres)
        k = ky.get(nombre_ky) if nombre_ky else None
        if nombre_ky and k is None:
            sys.exit(f"{especie}: no encuentro Ky '{nombre_ky}'")
        lineas_ky += k is not None
        nota = f"Tabla 12/22: {' + '.join(nombres)}" + (f"; Ky de \"{nombre_ky}\"" if nombre_ky else "; sin Ky en la tabla 24")
        filas.append(f"  ('{especie}', {v['zr_m']}, {v['p']}, {v['kc_ini']}, {v['kc_med']}, {v['kc_fin']}, "
                     f"{'NULL' if k is None else k}, '{FUENTE}', '{nota.replace(chr(39), chr(39) * 2)}')")
    cabecera = [
        "-- Parametros de agua por especie derivados de FAO-56 (tablas 12 y 22) y FAO-33 (tabla 24). GENERADO por",
        "-- database/derivar_agua_fao.py; no editar a mano. Requiere antes migracion_ky_opcional.sql. Aplicar a mano",
        "-- sobre la base antes de desplegar la API.",
        "--",
        "-- Fuente: Allen, Pereira, Raes y Smith (1998), FAO Irrigation and Drainage Paper 56, caps. 6 y 8,",
        "-- (c) FAO 1998, todos los derechos reservados. Se guardan solo valores derivados, no las tablas. Conviene",
        "-- pedir confirmacion escrita a FAO antes de publicar. Los valores son una guia general, sin validar.",
        f"-- {len(filas)} especies; {lineas_ky} con Ky (el resto queda NULL: riego si, perdida por sequia no).",
        "-- Sin parametros de agua: " + "; ".join(f"{e} ({m})" for e, m in SIN_AGUA.items()) + ".",
        "-- No pisa las especies que ya tienen fila (papa, haba, ajo_chilote).",
        "",
        "BEGIN;",
        f"DELETE FROM parametros_agua_cultivo WHERE fuente = '{FUENTE}';",
        "INSERT INTO parametros_agua_cultivo (especie, zr_m, p_agotamiento, kc_ini, kc_med, kc_fin, ky, fuente, nota) VALUES",
        ",\n".join(filas),
        "ON CONFLICT (especie) DO NOTHING;",
        "COMMIT;",
        "",
    ]
    SALIDA.write_text("\n".join(cabecera), encoding="utf-8")
    print(f"{len(filas)} especies ({lineas_ky} con Ky) -> {SALIDA}")


if __name__ == "__main__":
    main()
