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
    ruta_csv = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ecocrop_openclim.csv"
    destino = sys.argv[2] if len(sys.argv) > 2 else "database/seed_ecocrop.sql"
    main(ruta_csv, destino)
