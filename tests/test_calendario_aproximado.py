"""Las etapas derivadas de FAO-56 (database/derivar_etapas_fao.py) se anuncian como calendario aproximado."""
import catalogo_especies as ce
from catalogo_prueba import correr
from catalogo_especies import RepositorioEnMemoria

ETAPAS = ("inicial", "desarrollo", "media", "madurez")


def repo(fuente):
    umbrales = [{"especie": "x", "variedad_local": None, "orden": i + 1, "etapa": e,
                 "gdd_minimo": 100, "gdd_maximo": 120, "fuente": fuente} for i, e in enumerate(ETAPAS)]
    return RepositorioEnMemoria(requisitos_rows=[{"especie": "x", "variedad_local": None, "tb": 5}],
                                umbrales_rows=umbrales, rasgos_rows=[], reglas_rows=[])


def test_fuente_derivada_es_aproximada_y_sin_validar():
    r = repo(ce.FUENTE_ETAPAS_DERIVADAS)
    assert correr(ce.calendario_aproximado("x", None, r)) is True
    assert correr(ce.nivel_madurez("x", None, r)) == "perfil_fenologico_regional"


def test_fuente_calibrada_no_es_aproximada():
    r = repo("INIA_Boletin_396")
    assert correr(ce.calendario_aproximado("x", None, r)) is False
    assert correr(ce.nivel_madurez("x", None, r)) == "perfil_calibrado"
