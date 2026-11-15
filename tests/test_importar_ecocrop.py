"""Normalizacion de los requisitos de terreno de EcoCrop (database/importar_ecocrop.py)."""
import importlib.util
import os

import pandas as pd
import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("importar_ecocrop", os.path.join(RAIZ, "database", "importar_ecocrop.py"))
imp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(imp)

NA = float("nan")


def test_altitud_redondea_y_descarta_lo_vacio():
    assert imp.altitud(2000.0) == 2000
    assert imp.altitud(1234.6) == 1235
    assert imp.altitud(NA) is None and imp.altitud(0) is None and imp.altitud(None) is None


def test_textura_conserva_el_orden_y_expande_wide():
    assert imp.textura("medium, light") == ["medium", "light"]
    assert imp.textura("wide") == ["light", "medium", "heavy"]
    assert imp.textura("heavy, medium, light, wide, organic") == ["heavy", "medium", "light", "organic"]
    assert imp.textura(NA) is None and imp.textura("NA") is None and imp.textura("desconocida") is None


def test_drenaje_se_queda_con_la_clase_de_cada_item():
    assert imp.drenaje("poorly (saturated >50% of year), well (dry spells)") == ["poorly", "well"]
    assert imp.drenaje("excessive (dry/moderately dry)") == ["excessive"]
    assert imp.drenaje(NA) is None


def test_salinidad_una_clase_por_fila():
    assert imp.salinidad("low (<4 dS/m)") == "low"
    assert imp.salinidad("medium (4-10 dS/m)") == "medium"
    assert imp.salinidad("high (>10 dS/m))") == "high"      # el CSV trae un parentesis de mas
    assert imp.salinidad("none") == "none"
    assert imp.salinidad(NA) is None and imp.salinidad("raro") is None


def test_profundidad_una_clase_por_fila():
    assert imp.profundidad("very shallow (<20 cm)") == "very_shallow"
    assert imp.profundidad("shallow (20-50 cm)") == "shallow"
    assert imp.profundidad("medium (50-150 cm)") == "medium"
    assert imp.profundidad("deep (>>150 cm)") == "deep"
    assert imp.profundidad(NA) is None and imp.profundidad("rara (1 cm)") is None


def test_fertilidad_una_clase_por_fila():
    assert [imp.fertilidad(v) for v in ("low", "moderate", "high")] == ["low", "moderate", "high"]
    assert imp.fertilidad(NA) is None and imp.fertilidad("rica") is None


def test_arreglo_de():
    assert imp.arreglo_de(None) == "NULL" and imp.arreglo_de([]) == "NULL"
    assert imp.arreglo_de(["a", "b"]) == "ARRAY['a', 'b']"


def test_el_sql_de_terreno_solo_actualiza_las_columnas_nuevas(tmp_path):
    csv = tmp_path / "mini.csv"
    pd.DataFrame([
        {"ScientificName": "Solanum tuberosum", "TMIN": 4, "TOPMN": 12, "TOPMX": 20, "TMAX": 28, "ALTMX": 3500,
         "TEXT": "medium, light", "TEXTR": "wide", "DRA": "well (dry spells)", "DRAR": "well (dry spells), "
         "excessive (dry/moderately dry)", "SAL": "low (<4 dS/m)", "SALR": "medium (4-10 dS/m)",
         "DEP": "medium (50-150 cm)", "DEPR": "shallow (20-50 cm)", "FER": "moderate", "FERR": "low"},
        {"ScientificName": "Sin Datos", "TMIN": 4, "TOPMN": 12, "TOPMX": 20, "TMAX": 28, "ALTMX": NA,
         "TEXT": NA, "TEXTR": NA, "DRA": NA, "DRAR": NA, "SAL": NA, "SALR": NA,
         "DEP": NA, "DEPR": NA, "FER": NA, "FERR": NA},
        {"ScientificName": "Incompleta", "TMIN": NA, "TOPMN": 12, "TOPMX": 20, "TMAX": 28, "ALTMX": 100,
         "TEXT": "heavy", "TEXTR": "heavy", "DRA": "poorly (saturated >50% of year)", "DRAR": NA, "SAL": NA, "SALR": NA,
         "DEP": "deep (>>150 cm)", "DEPR": NA, "FER": "high", "FERR": NA},
    ]).to_csv(csv, index=False, encoding="latin-1")
    destino = tmp_path / "terreno.sql"
    imp.main_terreno(str(csv), str(destino))
    sql = destino.read_text()
    assert "('solanum_tuberosum', 3500, ARRAY['medium', 'light'], ARRAY['light', 'medium', 'heavy'], " \
           "ARRAY['well'], ARRAY['well', 'excessive'], 'low', 'medium', 'medium', 'shallow', 'moderate', 'low')" in sql
    assert "('sin_datos', " + ", ".join(["NULL"] * 11) + ")" in sql
    assert "incompleta" not in sql                              # sin temperaturas completas no esta en el catalogo
    assert sql.count("UPDATE requisitos_especie") == 1
    assert "INSERT INTO requisitos_especie" not in sql and "DELETE" not in sql
    assert "r.variedad_local IS NULL" in sql and "FAO_EcoCrop_opinion_experta" in sql
