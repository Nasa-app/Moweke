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
    idoneidad de sitio (calcular_idoneidad(), cuando exista), NO para simular fenologia
    (construir_cultivo() seguira fallando explicito con EspecieSinPerfilFenologico: no
    hay umbral_fenologico_config, EcoCrop no da reparto de GDD por etapa).
  - regla_dano_especie: SOLO si KTMP (temperatura letal real, definicion propia de
    EcoCrop) esta presente y es negativa -> una regla 'helada' con efecto 'total'. Es
    mapeo directo de la propia definicion del campo, no una regla inventada.
  - humedad_suelo_min/max, horas_luz_criticas, foto_*, vern_req: quedan SIN poblar.
    EcoCrop da lluvia anual (mm) y fotoperiodo categorico, no la fraccion de agua
    aprovechable ni el umbral numerico de horas de luz que el motor espera -- convertir
    eso seria inventar un numero, no traducir uno real.
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


def main(ruta_csv: str, destino_sql: str) -> None:
    df = pd.read_csv(ruta_csv, encoding="latin-1")
    completos = df.dropna(subset=["TMIN", "TOPMN", "TOPMX", "TMAX"]).copy()
    completos["especie"] = completos["ScientificName"].map(slug)
    antes = len(completos)
    completos = completos.drop_duplicates(subset=["especie"])  # sinonimos/variedades con el mismo slug
    log.info("total CSV: %d | con tb/to/tc completos: %d | tras deduplicar por slug: %d",
              len(df), antes, len(completos))

    filas_req, filas_regla = [], []
    for _, r in completos.iterrows():
        t_optima = (r["TOPMN"] + r["TOPMX"]) / 2
        ph_min = r["PHMIN"] if pd.notna(r["PHMIN"]) else None
        ph_max = r["PHMAX"] if pd.notna(r["PHMAX"]) else None
        filas_req.append(
            f"('{r['especie']}', NULL, {escapar(ph_min)}, {escapar(ph_max)}, "
            f"{r['TMIN']}, {t_optima}, {r['TMAX']}, '{FUENTE}')"
        )
        if pd.notna(r["KTMP"]) and r["KTMP"] < 0:
            filas_regla.append(
                f"('{r['especie']}', NULL, '*', 'helada', {r['KTMP']}, 1, 'total', 0, '{FUENTE}')"
            )

    with open(destino_sql, "w") as f:
        f.write(
            "-- Generado por database/importar_ecocrop.py -- NO editar a mano, regenerar desde el CSV.\n"
            "-- Ver advertencia completa en el encabezado de ese script: opinion experta, no medicion;\n"
            "-- alcance acotado a requisitos_especie + regla_dano_especie (helada por KTMP).\n\n"
        )
        f.write("INSERT INTO requisitos_especie (especie, variedad_local, ph_suelo_min, ph_suelo_max, "
                 "tb, t_optima, tc, fuente) VALUES\n")
        f.write(",\n".join(filas_req) + ";\n\n")
        if filas_regla:
            f.write("INSERT INTO regla_dano_especie (especie, variedad_local, fase, peligro, umbral, "
                     "minimo, efecto, valor, fuente) VALUES\n")
            f.write(",\n".join(filas_regla) + ";\n")

    log.info("escrito %s: %d filas de requisitos_especie, %d filas de regla_dano_especie (helada por KTMP)",
              destino_sql, len(filas_req), len(filas_regla))


if __name__ == "__main__":
    ruta_csv = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ecocrop_openclim.csv"
    destino = sys.argv[2] if len(sys.argv) > 2 else "database/seed_ecocrop.sql"
    main(ruta_csv, destino)
