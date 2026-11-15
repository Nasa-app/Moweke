"""
Importador de FAO EcoCrop -> database/seed_ecocrop.sql -- ETL de una sola vez, no un
cliente que se llame en produccion (EcoCrop es un volcado estatico, discontinuado por
FAO ~2015, no una API viva).

Fuente real: mirror CSV de GitHub (openclim/ecocrop, EcoCrop_DB.csv), 2568 especies --
el mismo origen FAO que el paquete R `Recocrop` (CRAN) usa para sus "1710 taxa" (Recocrop
filtra mas estricto; aca se usa el CSV completo y se filtra por completitud real, no por
igualar ese numero).

ADVERTENCIA (la misma que ya senalan los mantenedores del dataset, confirmada al revisar
esto con el usuario): EcoCrop son valores de OPINION EXPERTA, no mediciones empiricas --
no es el mismo nivel de confianza que una ficha tecnica INIA/CIREN. Por eso el `fuente`
que se escribe es 'FAO_EcoCrop_opinion_experta', NUNCA 'placeholder_sin_validar' (que
implica "sin fuente") ni el mismo texto que INIA/CIREN (que implica medicion real) --
es un nivel intermedio propio, y services/catalogo_especies.nivel_madurez() solo mira
si fuente == 'placeholder_sin_validar', asi que esto cuenta como "fuente" real a ese
chequeo aunque la fuente misma advierta que es opinion, no medicion.

Alcance deliberadamente acotado a lo que EcoCrop puede respaldar sin inventar nada:
  - requisitos_especie: tb=TMIN, t_optima=punto medio(TOPMN,TOPMX), tc=TMAX,
    ph_suelo_min=PHMIN, ph_suelo_max=PHMAX. Esto alcanza 'perfil_generico' -- sirve para
    idoneidad de sitio (calcular_idoneidad()), NO para simular fenologia
    (construir_cultivo() seguira fallando explicito con EspecieSinPerfilFenologico: no
    hay umbral_fenologico_config, EcoCrop no da reparto de GDD por etapa).
  - requisitos_especie, columnas del metodo EcoCrop (catalogo_especies.puntuar_especie()):
    t_opt_min/t_opt_max=TOPMN/TOPMX, ph_opt_min/ph_opt_max=PHOPMN/PHOPMX,
    temperatura_letal=KTMP (cualquier signo), lluvia_anual_*=RMIN/ROPMN/ROPMX/RMAX (mm
    anuales, tal cual), luz_*=LIMN/LIOPMN/LIOPMX/LIMX (categoria en texto, tal cual),
    fotoperiodo=PHOTO (texto, tal cual), ciclo_min_dias/ciclo_max_dias=GMIN/GMAX (0 en
    el CSV significa "sin dato", se guarda NULL). Todo copia directa: la conversion de
    categoria de luz a radiacion NO se hace aca, vive en la tabla equivalencia_luz_ghi.
  - especie: nombre cientifico, nombres comunes (COMNAME crudo), familia, forma de vida
    y categorias de uso (CAT separado por comas).
  - regla_dano_especie: SOLO si KTMP (temperatura letal real, definicion propia de
    EcoCrop) esta presente y es negativa -> una regla 'helada' con efecto 'total'. Es
    mapeo directo de la propia definicion del campo, no una regla inventada.
  - requisitos de terreno, con `--terreno` (genera database/seed_ecocrop_terreno.sql, aparte del
    seed principal): altitud_max_m=ALTMX, textura_opt/textura_rango=TEXT/TEXTR,
    drenaje_opt/drenaje_rango=DRA/DRAR, salinidad_opt/salinidad_max=SAL/SALR,
    profundidad_opt/profundidad_min=DEP/DEPR, fertilidad_opt/fertilidad_min=FER/FERR. Solo
    actualiza esas once columnas de las filas de EcoCrop que ya existen; no inserta ni toca otra
    cosa. Las columnas se crean con database/migracion_requisitos_terreno.sql y
    database/migracion_suelo_declarado.sql. Los textos de EcoCrop se normalizan a clases cortas
    (ver textura(), drenaje(), salinidad(), profundidad() y fertilidad()).
  - humedad_suelo_min/max, horas_luz_criticas, foto_*, vern_req: quedan SIN poblar.
    EcoCrop no da la fraccion de agua aprovechable ni el umbral numerico de horas de luz
    que el motor fenologico espera -- convertir eso seria inventar un numero.

El SQL generado es idempotente: carga el CSV a una tabla temporal y desde ahi actualiza
las filas de EcoCrop que ya existan e inserta las que falten -- se puede correr sobre
una base nueva o sobre una que ya tenia la version anterior de este seed.
  - rasgos_rotacion_especie: NO se toca. EcoCrop no tiene mes/dia de siembra ni
    intervalo de rotacion -- sin esto, construir_perfil() seguira fallando con
    EspecieSinPerfil para estas especies (correcto: no estan listas para rotacion).

`especie` = nombre cientifico slugificado (ej. 'solanum_tuberosum'), no nombre comun --
COMNAME en el CSV es texto libre multilingue sin estructura, no sirve como identificador.
Esto es deliberadamente un catalogo aparte de papa/ajo_chilote/haba/pradera (que usan
nombre comun en espanol) -- no se tocan esas 4 filas existentes.
"""
from __future__ import annotations

import logging
import re
import sys

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("importar_ecocrop")

URL_CSV = "https://raw.githubusercontent.com/openclim/ecocrop/master/EcoCrop_DB.csv"
FUENTE = "FAO_EcoCrop_opinion_experta"


def slug(nombre_cientifico: str) -> str:
    s = nombre_cientifico.strip().lower()
    s = re.sub(r"[^a-z0-9\s]", "", s)
    return re.sub(r"\s+", "_", s).strip("_")


def escapar(valor) -> str:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return "NULL"
    if isinstance(valor, str):
        return "'" + valor.replace("'", "''") + "'"
    return str(valor)


CATEGORIAS_LUZ = ("very bright", "clear skies", "cloudy skies", "light shade", "heavy shade")

# (columna de la tabla temporal, tipo SQL) en el orden en que se escriben los VALUES.
COLUMNAS = (
    ("especie", "VARCHAR PRIMARY KEY"), ("nombre_cientifico", "VARCHAR"), ("nombres_comunes", "TEXT"),
    ("familia_botanica", "VARCHAR"), ("forma_vida", "VARCHAR"), ("categorias", "TEXT[]"),
    ("ph_suelo_min", "FLOAT"), ("ph_opt_min", "FLOAT"), ("ph_opt_max", "FLOAT"), ("ph_suelo_max", "FLOAT"),
    ("tb", "FLOAT"), ("t_opt_min", "FLOAT"), ("t_optima", "FLOAT"), ("t_opt_max", "FLOAT"), ("tc", "FLOAT"),
    ("temperatura_letal", "FLOAT"),
    ("lluvia_anual_min", "FLOAT"), ("lluvia_anual_opt_min", "FLOAT"),
    ("lluvia_anual_opt_max", "FLOAT"), ("lluvia_anual_max", "FLOAT"),
    ("luz_min", "VARCHAR"), ("luz_opt_min", "VARCHAR"), ("luz_opt_max", "VARCHAR"), ("luz_max", "VARCHAR"),
    ("fotoperiodo", "VARCHAR"), ("ciclo_min_dias", "INT"), ("ciclo_max_dias", "INT"),
)
# Columnas de requisitos_especie que vienen de la tabla temporal (todas menos la
# identidad, que va a la tabla `especie`).
COLUMNAS_REQUISITOS = tuple(c for c, _ in COLUMNAS[6:])


def texto(valor) -> str | None:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    s = str(valor).strip()
    return s if s and s != "NA" else None


def numero(valor) -> float | None:
    return None if pd.isna(valor) else float(valor)


def dias(valor) -> int | None:
    """GMIN/GMAX: 0 en el CSV significa 'sin dato' (685 especies, casi todas arboles),
    no un ciclo de cero dias."""
    return None if pd.isna(valor) or valor <= 0 else int(valor)


def luz(valor) -> str | None:
    s = texto(valor)
    return s.lower() if s and s.lower() in CATEGORIAS_LUZ else None


def familia(valor) -> str | None:
    """FAMNAME viene como ruta taxonomica ('Magnoliopsida:Asteridae:Solanales:Solanaceae');
    la familia es el ultimo tramo."""
    s = texto(valor)
    return s.split(":")[-1].strip() if s else None


def arreglo(valor) -> str:
    s = texto(valor)
    if s is None:
        return "NULL"
    partes = [p.strip() for p in s.split(",") if p.strip()]
    return "ARRAY[" + ", ".join(escapar(p) for p in partes) + "]"


CLASES_TEXTURA = ("light", "medium", "heavy", "organic")
CLASES_DRENAJE = ("poorly", "well", "excessive")
CLASES_SALINIDAD = ("none", "low", "medium", "high")
CLASES_PROFUNDIDAD = ("very_shallow", "shallow", "medium", "deep")    # de menos a mas profundo
CLASES_FERTILIDAD = ("low", "moderate", "high")
COLUMNAS_TERRENO = ("altitud_max_m", "textura_opt", "textura_rango", "drenaje_opt", "drenaje_rango",
                    "salinidad_opt", "salinidad_max", "profundidad_opt", "profundidad_min",
                    "fertilidad_opt", "fertilidad_min")


def altitud(valor) -> int | None:
    """ALTMX: altitud maxima en metros, tal como la publica EcoCrop (cifras redondas de
    opinion experta). Vacio o no positivo = sin dato."""
    if valor is None or pd.isna(valor) or valor <= 0:
        return None
    return int(round(float(valor)))


def _unicas(clases: list[str], validas: tuple[str, ...]) -> list[str] | None:
    vistas = []
    for c in clases:
        if c in validas and c not in vistas:
            vistas.append(c)
    return vistas or None


def textura(valor) -> list[str] | None:
    """TEXT/TEXTR: clases separadas por coma ('heavy, medium, light'). 'wide' = tolera cualquier
    textura mineral y se expande a light, medium y heavy."""
    s = texto(valor)
    if s is None:
        return None
    clases = []
    for p in (x.strip().lower() for x in s.split(",")):
        clases.extend(("light", "medium", "heavy") if p == "wide" else (p,))
    return _unicas(clases, CLASES_TEXTURA)


def drenaje(valor) -> list[str] | None:
    """DRA/DRAR: 'well (dry spells), excessive (dry/moderately dry)' -> ['well', 'excessive']."""
    s = texto(valor)
    if s is None:
        return None
    return _unicas([p.strip().split(" ")[0].lower() for p in s.split(",") if p.strip()], CLASES_DRENAJE)


def salinidad(valor) -> str | None:
    """SAL/SALR: 'medium (4-10 dS/m)' -> 'medium'. Una sola clase por fila."""
    s = texto(valor)
    clase = s.split(" ")[0].lower() if s else None
    return clase if clase in CLASES_SALINIDAD else None


def profundidad(valor) -> str | None:
    """DEP/DEPR: 'very shallow (<20 cm)', 'shallow (20-50 cm)', 'medium (50-150 cm)' o
    'deep (>>150 cm)'. Una sola clase por fila. DEPR (el 'rango') es igual o menos profunda que
    DEP en el 99,9 % de las filas: se guarda como el minimo tolerado (profundidad_min)."""
    s = texto(valor)
    if s is None:
        return None
    clase = s.split("(")[0].strip().lower().replace(" ", "_")
    return clase if clase in CLASES_PROFUNDIDAD else None


def fertilidad(valor) -> str | None:
    """FER/FERR: low | moderate | high, una sola clase. Igual que la profundidad, FERR es el
    minimo tolerado (fertilidad_min)."""
    s = texto(valor)
    clase = s.split(" ")[0].lower() if s else None
    return clase if clase in CLASES_FERTILIDAD else None


def arreglo_de(clases: list[str] | None) -> str:
    return "NULL" if not clases else "ARRAY[" + ", ".join(escapar(c) for c in clases) + "]"


def main_terreno(ruta_csv: str, destino_sql: str) -> None:
    """SQL que llena solo las columnas de terreno de las filas de EcoCrop que ya existen."""
    df = pd.read_csv(ruta_csv, encoding="latin-1")
    # Misma seleccion y deduplicacion que main(): son las filas que hay en requisitos_especie.
    completos = df.dropna(subset=["TMIN", "TOPMN", "TOPMX", "TMAX"]).copy()
    completos["especie"] = completos["ScientificName"].map(slug)
    completos = completos.drop_duplicates(subset=["especie"])

    filas = []
    for _, r in completos.iterrows():
        valores = (escapar(r["especie"]), escapar(altitud(r["ALTMX"])),
                   arreglo_de(textura(r["TEXT"])), arreglo_de(textura(r["TEXTR"])),
                   arreglo_de(drenaje(r["DRA"])), arreglo_de(drenaje(r["DRAR"])),
                   escapar(salinidad(r["SAL"])), escapar(salinidad(r["SALR"])),
                   escapar(profundidad(r["DEP"])), escapar(profundidad(r["DEPR"])),
                   escapar(fertilidad(r["FER"])), escapar(fertilidad(r["FERR"])))
        filas.append("(" + ", ".join(valores) + ")")

    tipos = {"altitud_max_m": "INT", "textura_opt": "TEXT[]", "textura_rango": "TEXT[]", "drenaje_opt": "TEXT[]",
             "drenaje_rango": "TEXT[]", "salinidad_opt": "VARCHAR", "salinidad_max": "VARCHAR",
             "profundidad_opt": "VARCHAR", "profundidad_min": "VARCHAR",
             "fertilidad_opt": "VARCHAR", "fertilidad_min": "VARCHAR"}
    asignaciones = ", ".join(f"{c} = e.{c}" for c in COLUMNAS_TERRENO)
    with open(destino_sql, "w") as f:
        f.write(
            "-- Generado por database/importar_ecocrop.py --terreno -- NO editar a mano.\n"
            "-- Requiere database/migracion_requisitos_terreno.sql y database/migracion_suelo_declarado.sql.\n"
            "-- Solo actualiza las once columnas de terreno de las filas de EcoCrop existentes; es idempotente.\n\n"
            "BEGIN;\n\n"
            "CREATE TEMP TABLE _ecocrop_terreno (\n  especie VARCHAR PRIMARY KEY,\n  "
            + ",\n  ".join(f"{c} {tipos[c]}" for c in COLUMNAS_TERRENO) + "\n) ON COMMIT DROP;\n\n"
            "INSERT INTO _ecocrop_terreno VALUES\n" + ",\n".join(filas) + ";\n\n"
            f"UPDATE requisitos_especie r SET {asignaciones}\n"
            "FROM _ecocrop_terreno e\n"
            f"WHERE r.especie = e.especie AND r.variedad_local IS NULL AND r.fuente = '{FUENTE}';\n\n"
            "COMMIT;\n"
        )
    log.info("escrito %s: %d especies | altitud %d, textura %d, drenaje %d, salinidad %d, profundidad %d, fertilidad %d",
             destino_sql, len(filas),
             sum(altitud(v) is not None for v in completos["ALTMX"]),
             sum(textura(v) is not None for v in completos["TEXT"]),
             sum(drenaje(v) is not None for v in completos["DRA"]),
             sum(salinidad(v) is not None for v in completos["SAL"]),
             sum(profundidad(v) is not None for v in completos["DEP"]),
             sum(fertilidad(v) is not None for v in completos["FER"]))


def main(ruta_csv: str, destino_sql: str) -> None:
    df = pd.read_csv(ruta_csv, encoding="latin-1")
    completos = df.dropna(subset=["TMIN", "TOPMN", "TOPMX", "TMAX"]).copy()
    completos["especie"] = completos["ScientificName"].map(slug)
    antes = len(completos)
    completos = completos.drop_duplicates(subset=["especie"])  # sinonimos/variedades con el mismo slug
    log.info("total CSV: %d | con tb/to/tc completos: %d | tras deduplicar por slug: %d",
              len(df), antes, len(completos))

    filas = []
    for _, r in completos.iterrows():
        valores = (
            escapar(r["especie"]), escapar(texto(r["ScientificName"])), escapar(texto(r["COMNAME"])),
            escapar(familia(r["FAMNAME"])), escapar(texto(r["LIFO"])), arreglo(r["CAT"]),
            escapar(numero(r["PHMIN"])), escapar(numero(r["PHOPMN"])),
            escapar(numero(r["PHOPMX"])), escapar(numero(r["PHMAX"])),
            escapar(numero(r["TMIN"])), escapar(numero(r["TOPMN"])),
            escapar((r["TOPMN"] + r["TOPMX"]) / 2), escapar(numero(r["TOPMX"])), escapar(numero(r["TMAX"])),
            escapar(numero(r["KTMP"])),
            escapar(numero(r["RMIN"])), escapar(numero(r["ROPMN"])),
            escapar(numero(r["ROPMX"])), escapar(numero(r["RMAX"])),
            escapar(luz(r["LIMN"])), escapar(luz(r["LIOPMN"])), escapar(luz(r["LIOPMX"])), escapar(luz(r["LIMX"])),
            escapar(texto(r["PHOTO"])), escapar(dias(r["GMIN"])), escapar(dias(r["GMAX"])),
        )
        filas.append("(" + ", ".join(valores) + ")")

    asignaciones = ", ".join(f"{c} = e.{c}" for c in COLUMNAS_REQUISITOS)
    lista = ", ".join(COLUMNAS_REQUISITOS)
    with open(destino_sql, "w") as f:
        f.write(
            "-- Generado por database/importar_ecocrop.py -- NO editar a mano, regenerar desde el CSV.\n"
            "-- Ver advertencia completa en el encabezado de ese script: opinion experta, no medicion.\n"
            "-- Idempotente: actualiza las filas de EcoCrop existentes e inserta las que falten.\n\n"
            "BEGIN;\n\n"
        )
        f.write("CREATE TEMP TABLE _ecocrop (\n  "
                 + ",\n  ".join(f"{c} {t}" for c, t in COLUMNAS) + "\n) ON COMMIT DROP;\n\n")
        f.write("INSERT INTO _ecocrop VALUES\n" + ",\n".join(filas) + ";\n\n")
        f.write(
            f"UPDATE requisitos_especie r SET {asignaciones}\n"
            f"FROM _ecocrop e\n"
            f"WHERE r.especie = e.especie AND r.variedad_local IS NULL AND r.fuente = '{FUENTE}';\n\n"
            f"INSERT INTO requisitos_especie (especie, variedad_local, {lista}, fuente)\n"
            f"SELECT e.especie, NULL, {', '.join('e.' + c for c in COLUMNAS_REQUISITOS)}, '{FUENTE}'\n"
            f"FROM _ecocrop e\n"
            f"WHERE NOT EXISTS (SELECT 1 FROM requisitos_especie r\n"
            f"                  WHERE r.especie = e.especie AND r.variedad_local IS NULL);\n\n"
            f"INSERT INTO especie (especie, nombre_cientifico, nombres_comunes, familia_botanica, forma_vida, "
            f"categorias, fuente)\n"
            f"SELECT especie, nombre_cientifico, nombres_comunes, familia_botanica, forma_vida, categorias, "
            f"'{FUENTE}'\nFROM _ecocrop\n"
            f"ON CONFLICT (especie) DO UPDATE SET nombre_cientifico = EXCLUDED.nombre_cientifico,\n"
            f"  nombres_comunes = EXCLUDED.nombres_comunes, familia_botanica = EXCLUDED.familia_botanica,\n"
            f"  forma_vida = EXCLUDED.forma_vida, categorias = EXCLUDED.categorias, fuente = EXCLUDED.fuente;\n\n"
            f"INSERT INTO regla_dano_especie (especie, variedad_local, fase, peligro, umbral, minimo, efecto, "
            f"valor, fuente)\n"
            f"SELECT e.especie, NULL, '*', 'helada', e.temperatura_letal, 1, 'total', 0, '{FUENTE}'\n"
            f"FROM _ecocrop e\n"
            f"WHERE e.temperatura_letal < 0\n"
            f"  AND NOT EXISTS (SELECT 1 FROM regla_dano_especie d\n"
            f"                  WHERE d.especie = e.especie AND d.peligro = 'helada' AND d.fuente = '{FUENTE}');\n\n"
            "COMMIT;\n"
        )

    log.info("escrito %s: %d especies (requisitos_especie + especie), %d con temperatura letal negativa "
              "(regla 'helada')", destino_sql, len(filas), int((completos["KTMP"] < 0).sum()))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--terreno":
        main_terreno(sys.argv[2] if len(sys.argv) > 2 else "/tmp/ecocrop_openclim.csv",
                     sys.argv[3] if len(sys.argv) > 3 else "database/seed_ecocrop_terreno.sql")
    else:
        ruta_csv = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ecocrop_openclim.csv"
        destino = sys.argv[2] if len(sys.argv) > 2 else "database/seed_ecocrop.sql"
        main(ruta_csv, destino)
