"""Deriva etapas fenologicas en grados-dia desde la tabla 11 de FAO-56 (Allen et al., 1998,
cap. 6, https://www.fao.org/3/x0490e/x0490e0b.htm) para las especies del catalogo que no
tienen etapas propias, y escribe database/seed_etapas_fao.sql.

Fuente: FAO Irrigation and Drainage Paper 56, (c) FAO 1998, todos los derechos reservados.
Los terminos del sitio de FAO permiten copiar y usar para investigacion, ensenanza y
productos o servicios no comerciales con atribucion; no es una licencia abierta. Este script
descarga la tabla en cada corrida y NO la guarda en el repo: solo se escriben los valores
derivados. Conviene pedir confirmacion escrita a FAO antes de publicar. El propio capitulo
dice que los valores son "solo una guia general".

Metodo: los dias de cada etapa no se convierten a grados-dia suponiendo temperatura optima
(sobreestima 65-100 %). Se integra el reloj termico del motor (pheno_engine.tiempo_termico_diario)
sobre el clima ERA5 (Open-Meteo archive) de una coordenada representativa de la region de la
fila, desde la fecha de siembra y durante los dias de cada etapa, con tb/to/tc de la especie.
`gdd_minimo` y `gdd_maximo` son el minimo y el maximo entre anos y filas FAO de la misma
especie. Con la papa (un solo punto) reproduce los umbrales de INIA Boletin 396; no es una
validacion general.

Uso:
  python database/derivar_etapas_fao.py --mapeo      # lista cultivo FAO -> especie, sin generar datos
  python database/derivar_etapas_fao.py --generar    # descarga clima, escribe el SQL
Variables: DATABASE_URL (solo lectura de tb/to/tc) y, opcionalmente, --anos 2015-2024.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import OrderedDict
from html.parser import HTMLParser
from pathlib import Path

URL_FAO = "https://www.fao.org/3/x0490e/x0490e0b.htm"
FUENTE = "FAO56_t11_derivado_sin_validar"
ETAPAS = ("inicial", "desarrollo", "media", "madurez")
SALIDA = Path(__file__).with_name("seed_etapas_fao.sql")

# Especies con etapas propias: nunca se tocan.
PROPIAS = {"papa", "ajo_chilote", "haba"}
# Con etapas propias que se derivan solo para mostrar al lado; sus filas salen comentadas en el SQL.
PARA_COMPARAR = {"haba"}

# Cultivo FAO (tal como aparece en la tabla) -> especies del catalogo. Es una estimacion por
# nombre y requiere revision humana. Una lista vacia = excluido a proposito (ver MOTIVO_EXCLUIDO).
MAPEO: dict[str, list[str]] = {
    "Broccoli": ["brassica_oleracea_var_italica"],
    "Cabbage": ["brassica_oleracea_var_capitata"],
    "Cauliflower": ["brassica_oleracea_var_botrytis"],
    "Crucifers1": ["brassica_oleracea_var_gemmifera", "brassica_oleracea_var_acephala",
                   "brassica_oleracea_var_gongyloides"],
    "Carrots": ["daucus_carota"],
    "Celery": ["apium_graveolens", "apium_graveolens_var_dulce"],
    "Lettuce": ["lactuca_sativa_var_capitata"],
    "Onion (dry)": ["allium_cepa", "allium_cepa_var_cepa"],
    "Spinach": ["spinacia_oleracea"],
    "Radish": ["raphanus_sativus", "raphanus_sativus_var_radicula"],
    "Egg plant": ["solanum_melongena"],
    "Sweet peppers (bell)": ["capsicum_annuum"],
    "Tomato": ["lycopersicon_esculentum"],
    "Cantaloupe": ["cucumis_melo"],
    "Sweet melons": ["cucumis_melo"],
    "Cucumber": ["cucumis_sativus"],
    "Pumpkin, Winter squash": ["cucurbita_maxima", "cucurbita_moschata", "cucurbita_mixta"],
    "Squash, Zucchini": ["cucurbita_pepo"],
    "Water melons": ["citrullus_lanatus"],
    "Beets, table": ["beta_vulgaris"],
    "Sugarbeet": ["beta_vulgaris_var_saccharifera"],
    "Cassava: year 1": ["manihot_esculenta"],
    "Sweet potato": ["ipomoea_batatas"],
    "Beans (dry)": ["phaseolus_vulgaris"],
    "Green gram, cowpeas": ["vigna_radiata", "vigna_unguiculata"],
    "Groundnut": ["arachis_hypogaea"],
    "Lentil": ["lens_culinaris"],
    # Solo se calcula para comparar: la tabla no se escribe sobre `haba` (ver PARA_COMPARAR).
    "Faba bean, broad bean": ["haba"],
    "Peas": ["pisum_sativum"],
    "Soybeans": ["glycine_max"],
    "Cotton": ["gossypium_hirsutum"],
    "Flax": ["linum_usitatissimum"],
    "Castor beans": ["ricinus_communis"],
    "Safflower": ["carthamus_tinctorius"],
    "Sesame": ["sesamum_indicum"],
    "Sunflower": ["helianthus_annuus"],
    "Winter Wheat": ["triticum_aestivum"],
    "Maize (grain)": ["zea_mays"],
    "Maize (sweet)": ["zea_mays_ssp_saccharata"],
    "Sorghum": ["sorghum_bicolor"],
    "Rice": ["oryza_sativa"],
}

# Una especie solo recibe etapas si el total de gdd_maximo / total de gdd_minimo es <= este valor: el motor usa
# el punto medio del rango, y con un rango mas ancho entre regiones ese punto medio no representa a ninguna.
RANGO_MAXIMO = 2.0
MOTIVO_RANGO = "rango entre regiones demasiado ancho para usar el punto medio"

# Cultivos de la tabla que no se mapean, con el motivo.
MOTIVO_EXCLUIDO = {
    "Potato": "papa ya tiene etapas propias (INIA Boletin 396)",
    "Beans (green)": "poroto verde: se usa solo Beans (dry) para no mezclar ambos en el rango",
    "Barley/Oats/Wheat": "fila agrupada (una sola fila, India central, siembra en noviembre)",
    "Millet": "junta cuatro especies distintas",
    "Onion (green)": "cebolla verde (otro manejo; A. fistulosum o A. cepa cosechada verde)",
    "Onion (seed)": "produccion de semilla, ciclo de 275 dias",
    "year 2": "Cassava, segundo ano (fila de continuacion) de un cultivo de 18-24 meses",
    "Artichoke": "perenne", "Asparagus": "perenne",
    "Grains (small)": "demasiado generico", "Alfalfa, total season 4": "forraje perenne con cortes",
    "Alfalfa 4 1st cutting cycle": "forraje perenne con cortes",
    "Alfalfa 4, other cutting cycles": "forraje perenne con cortes",
    "Bermuda for seed": "perenne", "Bermuda for hay (several cuttings)": "perenne",
    "Grass Pasture 4 1": "pradera perenne", "Sudan, 1st cutting cycle": "forraje con cortes",
    "Sudan, other cutting cycles": "forraje con cortes",
    "Sugarcane, virgin": "ciclo de 12-24 meses", "Sugarcane, ratoon": "ciclo de 12-24 meses",
    "Banana, 1st yr": "perenne", "Banana, 2nd yr": "perenne", "Pineapple": "perenne",
    "Grapes": "perenne", "Hops": "perenne", "Citrus": "perenne", "Deciduous Orchard": "perenne",
    "Olives": "perenne", "Pistachios": "perenne", "Walnuts": "perenne",
    "Wetlands (Cattails, Bulrush)": "humedal perenne", "Wetlands (short veg.)": "humedal perenne",
}

# Especies del catalogo que duplican a una con etapas propias; no se tocan.
GEMELAS_DE_PROPIAS = {"solanum_tuberosum": "papa", "vicia_faba": "haba"}


class _Tabla(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tablas: list[list[list[str]]] = []
        self._fila: list[str] | None = None
        self._celda: str | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.tablas.append([])
        elif tag == "tr":
            self._fila = []
        elif tag in ("td", "th"):
            self._celda = ""

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._celda is not None and self._fila is not None:
            self._fila.append(" ".join(self._celda.split()))
            self._celda = None
        elif tag == "tr" and self._fila is not None and self.tablas:
            self.tablas[-1].append(self._fila)
            self._fila = None

    def handle_data(self, data):
        if self._celda is not None:
            self._celda += data


def descargar_html() -> str:
    import requests
    r = requests.get(URL_FAO, timeout=60)
    r.raise_for_status()
    return r.content.decode("latin-1")


def _dias(texto: str) -> int | None:
    """'50/30' (dos ciclos en la misma fila) -> el primero; '130\\1' (nota al pie) -> 130."""
    m = re.match(r"\s*(\d+)", texto)
    return int(m.group(1)) if m else None


def parsear_tabla11(html: str) -> list[dict]:
    """Filas de datos de la primera <table>: una por (cultivo, region, fecha). Las filas de un
    mismo cultivo vienen sin nombre en la fila siguiente."""
    p = _Tabla()
    p.feed(html)
    filas, cultivo = [], None
    for r in p.tablas[0][1:]:
        if len(r) < 7:
            continue                     # encabezado de seccion
        if len(r) == 8:
            cultivo, r = r[0], r[1:]
        dias = [_dias(x) for x in r[:4]]
        if cultivo is None or None in dias:
            continue
        filas.append({"cultivo": cultivo, "dias": tuple(dias), "siembra": r[5], "region": r[6]})
    return filas


def mostrar_mapeo(filas: list[dict]) -> None:
    n = OrderedDict()
    for f in filas:
        n[f["cultivo"]] = n.get(f["cultivo"], 0) + 1
    print(f"Tabla 11: {len(filas)} filas, {len(n)} cultivos\n")
    print("MAPEADOS (cultivo FAO [filas] -> especies del catalogo)")
    for c, k in n.items():
        if c in MAPEO:
            print(f"  {c} [{k}] -> {', '.join(MAPEO[c])}")
    print("\nEXCLUIDOS")
    for c, k in n.items():
        if c not in MAPEO:
            print(f"  {c} [{k}]: {MOTIVO_EXCLUIDO.get(c, 'SIN DECIDIR')}")
    especies = {e for c in MAPEO.values() for e in c}
    print(f"\n{len(especies)} especies del catalogo recibirian etapas.")


# Region de la fila FAO -> (lat, lon, fuente de la coordenada, revisar). `revisar` marca las
# regiones genericas o ambiguas: la coordenada es una eleccion mia, no un dato de FAO.
# Cuando la fila nombra varias regiones se usa la primera. Todas son aproximaciones de
# una zona agricola representativa, no la ubicacion de los ensayos de FAO.
IMPERIAL = (32.8, -115.5, "Imperial Valley, California (desierto agricola)", False)
ARIDA = (30.0, 31.2, "Giza/valle del Nilo, Egipto: zona arida regadia (eleccion propia)", True)
MEDITERRANEO = (39.5, -0.4, "Valencia, Espana: huerta mediterranea (eleccion propia)", True)
CALIFORNIA = (36.75, -119.75, "Fresno, valle central de California (eleccion propia)", True)
EUROPA = (47.3, 5.0, "Dijon, Francia: Europa templada (eleccion propia)", True)
TROPICO = (14.17, 121.24, "Los Banos, Filipinas: tropico humedo (eleccion propia)", True)
EEUU_CENTRO = (39.0, -97.0, "Kansas, centro de EE.UU. (eleccion propia)", True)
REGIONES: dict[str, tuple[float, float, str, bool]] = {
    "Calif. Desert, USA": IMPERIAL,
    "Idaho, USA": (42.5, -114.4, "Kimberly, Idaho", False),
    "Calif., USA": CALIFORNIA, "California": CALIFORNIA, "California, USA": CALIFORNIA,
    "Calif., Mediterranean": CALIFORNIA, "Calif., Egypt, Lebanon": CALIFORNIA,
    "Mediterranean": MEDITERRANEO, "Medit.; Europe": MEDITERRANEO, "Medit.; Arid Reg.": MEDITERRANEO,
    "Mediterranean & Arid": MEDITERRANEO, "Medit.; California": MEDITERRANEO,
    "Arid Region": ARIDA, "Arid Regions": ARIDA, "Arid Climate": ARIDA, "Arid climate": ARIDA,
    "Arid Region; Calif.": ARIDA, "Egypt; Pakistan; Calif.": ARIDA,
    "(Semi) Arid": (38.0, -1.1, "Murcia, Espana: semiarido (eleccion propia)", True),
    "(Semi) Arid Climates": (38.0, -1.1, "Murcia, Espana: semiarido (eleccion propia)", True),
    "Europe": EUROPA, "Europe and Medit.": EUROPA,
    "Italy": (44.5, 11.3, "Bolonia, valle del Po", False),
    "Near East (desert)": (31.9, 35.5, "Valle del Jordan (eleccion propia)", True),
    "Tropics": TROPICO, "Tropical regions": TROPICO, "Tropics; Mediterranean": TROPICO,
    "Philippines": (14.17, 121.24, "Los Banos, Filipinas", False),
    "High Latitudes": (55.0, 10.0, "Dinamarca: latitudes altas (eleccion propia)", True),
    "Central USA": EEUU_CENTRO, "USA, Pakis., Med.": EEUU_CENTRO,
    "Continental Climates": (41.0, -96.0, "Lincoln, Nebraska: clima continental (eleccion propia)", True),
    "Pakistan": (31.4, 73.1, "Faisalabad, Punyab", False), "Pakistan, Calif.": (31.4, 73.1, "Faisalabad, Punyab", False),
    "Japan": (36.0, 140.1, "Tsukuba, Japon", False),
    "Yemen": (14.8, 43.0, "Tihama, Yemen (eleccion propia)", True),
    "Texas": (33.6, -101.9, "Lubbock, Texas", False),
    "Arizona": (33.1, -112.0, "Maricopa, Arizona", False),
    "Indonesia": (-7.3, 112.7, "Java Oriental (eleccion propia)", True),
    "China": (33.0, 114.0, "Henan, provincia sesamera (eleccion propia)", True),
    "Central India": (22.7, 75.9, "Indore, Madhya Pradesh", False),
    "East Africa": (-0.3, 36.1, "Nakuru, Kenia (eleccion propia)", True),
    "East Africa (alt.)": (-0.3, 36.1, "Nakuru, Kenia (eleccion propia)", True),
    "Nigeria (humid)": (7.4, 3.9, "Ibadan, Nigeria", False),
    "India (dry, cool)": (30.9, 75.9, "Ludhiana, Punyab indio", False),
    "Spain (spr, sum.); Calif.": (41.6, -0.9, "Zaragoza, valle del Ebro", False),
}
# Sin coordenada, la fila se omite: region vacia en la tabla o sin ubicacion ('35-45 °L',
# 'West Africa' sin fecha de siembra en calendario).

MESES = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def mes_de_siembra(texto: str) -> int | None:
    """Primer mes que nombra la fila ('Oct/Jan' -> 10). 'Winter' -> diciembre (supuesto, hemisferio
    norte). 'Rainy', 'Dry' o 'season' no son fechas: None y la fila se omite."""
    t = texto.lower()
    if t.startswith("winter"):
        return 12
    for palabra in re.findall(r"[a-z]+", t):
        if palabra[:3] in MESES:
            return MESES[palabra[:3]]
    return None


def anos_de(texto: str) -> range:
    a, b = (int(x) for x in texto.split("-"))
    return range(a, b + 1)          # inclusive; el clima se baja hasta junio del ano siguiente


def cargar_cache(ruta: Path | None, lat: float, lon: float, inicio: str, fin: str):
    """ERA5 diario (tmin, tmax) de una coordenada, con cache en disco para no repetir llamadas."""
    import pandas as pd
    if ruta is not None:
        ruta.mkdir(parents=True, exist_ok=True)
        f = ruta / f"era5_{lat}_{lon}_{inicio}_{fin}.csv"
        if f.exists():
            return pd.read_csv(f, index_col=0, parse_dates=True)
    import time
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from services.cliente_openmeteo import consultar_historia
    for intento in range(4):
        try:
            df = consultar_historia(lat, lon, inicio, fin)[["tmin", "tmax"]]
            break
        except Exception:
            if intento == 3:
                raise
            time.sleep(20 * (intento + 1))
    time.sleep(1.5)
    if ruta is not None:
        df.to_csv(f)
    return df


async def leer_cardinales(url: str, especies: list[str]) -> dict[str, tuple[float, float, float]]:
    import asyncpg
    con = await asyncpg.connect(url)
    try:
        filas = await con.fetch(
            "SELECT especie, tb, t_optima, tc FROM requisitos_especie "
            "WHERE variedad_local IS NULL AND especie = ANY($1) AND tb IS NOT NULL AND t_optima IS NOT NULL "
            "AND tc IS NOT NULL", especies)
        return {r["especie"]: (r["tb"], r["t_optima"], r["tc"]) for r in filas}
    finally:
        await con.close()


def derivar(filas: list[dict], cardinales: dict, anos: range, cache: Path | None):
    """-> ({especie: [[min, max] por etapa]}, resumen de filas usadas/omitidas)."""
    import numpy as np
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from services.pheno_engine import tiempo_termico_diario

    por_especie: dict[str, list[list[float]]] = {}      # especie -> lista de [g1..g4] (una por fila y ano)
    omitidas, usadas = [], []
    series: dict[str, object] = {}
    for f in filas:
        if f["cultivo"] not in MAPEO:
            continue
        reg = REGIONES.get(f["region"])
        mes = mes_de_siembra(f["siembra"])
        if reg is None or mes is None:
            omitidas.append((f["cultivo"], f["region"] or "(vacia)", f["siembra"]))
            continue
        lat, lon = reg[0], reg[1]
        clave = f"{lat},{lon}"
        if clave not in series:
            series[clave] = cargar_cache(cache, lat, lon, f"{anos.start}-01-01", f"{anos.stop}-06-30")
        clima = series[clave]
        total = sum(f["dias"])
        n_anos = 0
        for ano in anos:
            ini = np.datetime64(f"{ano}-{mes:02d}-15")
            tramo = clima.loc[ini: ini + np.timedelta64(total - 1, "D")]
            if len(tramo) < total or tramo[["tmin", "tmax"]].isna().any().any():
                continue
            n_anos += 1
            for especie in MAPEO[f["cultivo"]]:
                if especie not in cardinales:
                    continue
                tb, to, tc = cardinales[especie]
                tt = tiempo_termico_diario(tramo["tmin"].to_numpy(), tramo["tmax"].to_numpy(), tb, to, tc)
                cortes = np.cumsum((0,) + f["dias"])
                por_especie.setdefault(especie, []).append(
                    [float(tt[cortes[i]:cortes[i + 1]].sum()) for i in range(4)])
        usadas.append((f["cultivo"], f["region"], f["siembra"], n_anos, reg[3]))
    etapas = {e: [[round(min(v[i] for v in vs)), round(max(v[i] for v in vs))] for i in range(4)]
              for e, vs in por_especie.items()}
    return etapas, usadas, omitidas


def separar_por_rango(etapas: dict) -> tuple[dict, dict]:
    """-> (etapas que se escriben, {especie excluida: razon max/min}). Las de PARA_COMPARAR no se filtran."""
    incluidas, excluidas = {}, {}
    for e, v in etapas.items():
        razon = sum(hi for _, hi in v) / sum(lo for lo, _ in v)
        if e in PARA_COMPARAR or razon <= RANGO_MAXIMO:
            incluidas[e] = v
        else:
            excluidas[e] = round(razon, 2)
    return incluidas, excluidas


def escribir_sql(etapas: dict, usadas: list, omitidas: list, anos: range, excluidas: dict) -> None:
    revisar = sorted({(r, ) for _, r, _, _, rev in usadas if rev})
    lineas = [
        "-- Etapas por especie derivadas de FAO-56, tabla 11. GENERADO por database/derivar_etapas_fao.py;",
        "-- no editar a mano. Aplicar a mano sobre la base antes de desplegar la API.",
        "--",
        "-- Fuente: Allen, Pereira, Raes y Smith (1998), FAO Irrigation and Drainage Paper 56, cap. 6,",
        f"-- tabla 11, {URL_FAO} (c) FAO 1998, todos los derechos reservados. Se guardan solo los",
        "-- valores derivados, no la tabla. Conviene pedir confirmacion escrita a FAO antes de publicar.",
        "-- El capitulo dice que los valores son \"solo una guia general\".",
        "--",
        f"-- Metodo: grados-dia de cada etapa = integral del reloj termico del motor (tb/to/tc de la especie)",
        f"-- sobre ERA5 (Open-Meteo) de una coordenada de la region de la fila, siembra el dia 15 del mes,",
        f"-- anos {anos.start}-{anos.stop - 1}; gdd_minimo/gdd_maximo = minimo/maximo entre anos y filas FAO de la",
        "-- especie. Unico contraste hecho: la papa (4 filas FAO vs INIA Boletin 396); no es una validacion",
        "-- general. Las coordenadas de regiones genericas (Mediterranean, Arid, Tropics, Europe...) son una",
        "-- eleccion propia y estan marcadas para revision en el script (REGIONES).",
        f"-- Filas FAO usadas: {len(usadas)}; omitidas por falta de region o fecha: {len(omitidas)}.",
        "-- Etapas: inicial, desarrollo, media, madurez (reportes 'brotó'/'floreció' no las reanclan).",
        f"-- Solo se escriben las especies con total gdd_maximo / total gdd_minimo <= {RANGO_MAXIMO:g}. Excluidas ({len(excluidas)}, {MOTIVO_RANGO}):",
        *[f"--   {e} (x{r})" for e, r in sorted(excluidas.items())],
        "-- No pisa especies con etapas de otra fuente.",
        "",
        "BEGIN;",
        f"DELETE FROM umbral_fenologico_config WHERE fuente = '{FUENTE}';",
        "INSERT INTO umbral_fenologico_config (especie, variedad_local, orden, etapa, gdd_minimo, gdd_maximo, fuente)",
        "SELECT v.especie, NULL, v.orden, v.etapa, v.gdd_minimo, v.gdd_maximo, v.fuente FROM (VALUES",
    ]
    valores = []
    for especie in sorted(e for e in etapas if e not in PARA_COMPARAR):
        for i, (lo, hi) in enumerate(etapas[especie]):
            valores.append(f"  ('{especie}', {i + 1}, '{ETAPAS[i]}', {lo}, {hi}, '{FUENTE}')")
    lineas.append(",\n".join(valores))
    lineas += [
        ") AS v(especie, orden, etapa, gdd_minimo, gdd_maximo, fuente)",
        "WHERE EXISTS (SELECT 1 FROM especie e WHERE e.especie = v.especie)",
        "  AND NOT EXISTS (SELECT 1 FROM umbral_fenologico_config u WHERE u.especie = v.especie);",
        "COMMIT;",
        "",
        "-- ============================================================================================",
        "-- SOLO PARA COMPARAR, NO SE APLICA: haba ya tiene etapas propias (placeholder_sin_validar,",
        "-- emergencia/floracion/madurez = 150/250/150 grados-dia, 3 etapas). Esto es lo que daria la tabla 11",
        "-- de FAO-56 en 4 etapas (min-max entre filas y anos). Decide el usuario si reemplaza algo.",
    ]
    for especie in sorted(e for e in etapas if e in PARA_COMPARAR):
        for i, (lo, hi) in enumerate(etapas[especie]):
            lineas.append(f"--   ('{especie}', {i + 1}, '{ETAPAS[i]}', {lo}, {hi}, '{FUENTE}')")
    lineas.append("")
    SALIDA.write_text("\n".join(lineas), encoding="utf-8")


def main() -> None:
    import asyncio
    import os
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mapeo", action="store_true")
    ap.add_argument("--generar", action="store_true")
    ap.add_argument("--anos", default="2015-2024")
    ap.add_argument("--cache", type=Path, default=None, help="carpeta para guardar el clima descargado")
    a = ap.parse_args()
    filas = parsear_tabla11(descargar_html())
    if a.mapeo or not a.generar:
        mostrar_mapeo(filas)
        return
    url = os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1)
    especies = sorted({e for c in MAPEO.values() for e in c} - (PROPIAS - PARA_COMPARAR) - set(GEMELAS_DE_PROPIAS))
    cardinales = asyncio.run(leer_cardinales(url, especies))
    faltan = [e for e in especies if e not in cardinales]
    anos = anos_de(a.anos)
    etapas, usadas, omitidas = derivar(filas, cardinales, anos, a.cache)
    etapas, excluidas = separar_por_rango(etapas)
    escribir_sql(etapas, usadas, omitidas, anos, excluidas)
    for e, r in sorted(excluidas.items()):
        print(f"  excluida por rango x{r}: {e}")
    for e in sorted(PARA_COMPARAR & set(etapas)):
        print(f"{e} (solo comparar):", etapas[e])
    print(f"{len(etapas)} especies, {len(usadas)} filas usadas, {len(omitidas)} omitidas -> {SALIDA}")
    if faltan:
        print("Sin tb/to/tc en la base (omitidas):", ", ".join(faltan))
    for o in omitidas:
        print("  omitida:", o)


if __name__ == "__main__":
    main()
