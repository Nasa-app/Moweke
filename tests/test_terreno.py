"""Altitud y textura del suelo como factores de la lista de especies."""
import pytest

import catalogo_especies as ce
from catalogo_prueba import SITIOS, correr, repo_prueba, req, sitio_de

BASE = dict(tb=4, topt=(12, 20), tc=30, letal=-4, lluvia=(300, 500, 1400, 2200), ph=(5.0, 5.2, 7.5, 8.0), ciclo=(100, 140))


def especie(nombre, **terreno):
    return (req(nombre, **BASE, **terreno), ["vegetables"])


def evaluar(sitio, *especies):
    rk = correr(ce.ranking_idoneidad(sitio, repo_prueba(con_luz=False, extra=list(especies))))
    return {r["especie"]: r for r in rk}


# ---------------------------------------------------------------- clase de textura
@pytest.mark.parametrize("arcilla, arena, clase", [
    (5, 90, "light"),        # arena
    (10, 75, "light"),       # arena franca
    (15, 60, "light"),       # franco arenoso
    (20, 40, "medium"),      # franco
    (25, 55, "medium"),      # franco arcillo arenoso
    (30, 20, "medium"),      # franco arcilloso
    (50, 20, "heavy"),       # arcilla
    (40, 50, "heavy"),       # arcillo arenoso
    (36, 46, "heavy"),       # arcillo arenoso, en el borde
    (36, 30, "medium"),      # arcilla a medias: no llega al corte
])
def test_clase_de_textura(arcilla, arena, clase):
    assert ce.clase_textura(arcilla, arena) == clase


def test_clase_de_textura_sin_dato():
    assert ce.clase_textura(None, 50) is None and ce.clase_textura(30, None) is None


# ---------------------------------------------------------------- factor de textura
def test_clases_posibles_incluyen_las_vecinas_dentro_del_error_del_dato():
    assert ce.clases_textura_posibles(17.2, 52.6) == ["light", "medium"]    # en el borde entre dos clases
    assert ce.clases_textura_posibles(5, 90) == ["light"]                    # lejos de cualquier corte
    assert ce.clases_textura_posibles(None, 50) == [] and ce.clases_textura_posibles(30, None) == []


def test_un_sitio_en_el_borde_no_cambia_de_veredicto_por_una_decima():
    sp = especie("t_borde", textura_opt=["medium"], textura_rango=["medium"])     # no tolera lo arenoso
    for arena in (51.9, 52.1):
        sitio = sitio_de("chiloe", textura=ce.clase_textura(17.2, arena),
                         textura_posibles=ce.clases_textura_posibles(17.2, arena))
        assert evaluar(sitio, sp)["t_borde"]["factores"]["textura"] == 1.0


def test_un_sitio_lejos_del_borde_si_se_descarta():
    sp = especie("t_lejos", textura_opt=["medium"], textura_rango=["medium", "light"])
    sitio = sitio_de("chiloe", textura="heavy", textura_posibles=ce.clases_textura_posibles(50, 20))
    assert evaluar(sitio, sp)["t_lejos"]["factores"]["textura"] == 0.0


def test_textura_optima_1_tolerada_leve_y_fuera_cero():
    sp = especie("t_opt", textura_opt=["medium"], textura_rango=["medium", "light"])
    assert evaluar(sitio_de("chiloe", textura="medium"), sp)["t_opt"]["factores"]["textura"] == 1.0
    tolerada = evaluar(sitio_de("chiloe", textura="light"), sp)["t_opt"]
    assert tolerada["factores"]["textura"] == 0.75 and tolerada["apta"] is True
    fuera = evaluar(sitio_de("chiloe", textura="heavy"), sp)["t_opt"]
    assert fuera["factores"]["textura"] == 0.0 and fuera["apta"] is False and fuera["factor_limitante"] == "textura"


def test_textura_sin_optima_usa_el_rango_como_referencia():
    sp = especie("t_rango", textura_rango=["medium", "heavy"])
    assert evaluar(sitio_de("chiloe", textura="heavy"), sp)["t_rango"]["factores"]["textura"] == 1.0
    assert evaluar(sitio_de("chiloe", textura="light"), sp)["t_rango"]["factores"]["textura"] == 0.0


def test_textura_sin_dato_no_filtra():
    sp = especie("t_dato", textura_opt=["heavy"], textura_rango=["heavy"])
    sin_sitio = evaluar(sitio_de("chiloe", textura=None), sp)["t_dato"]
    assert "textura" not in sin_sitio["factores"] and sin_sitio["apta"] is True
    sin_especie = evaluar(sitio_de("chiloe", textura="light"), especie("t_nada"))["t_nada"]
    assert "textura" not in sin_especie["factores"]


# ---------------------------------------------------------------- factor de altitud
def test_altitud_hasta_el_maximo_1_y_baja_a_0_diez_por_ciento_mas_arriba():
    sp = especie("a_max", altitud_max_m=1000)
    f = lambda alt: evaluar(sitio_de("chiloe", altitud_m=alt), sp)["a_max"]["factores"].get("altitud")
    assert f(0) == 1.0 and f(1000) == 1.0
    assert f(1050) == pytest.approx(0.5)
    assert f(1100) == 0.0 and f(3000) == 0.0


def test_altitud_sobre_el_maximo_descarta():
    sp = especie("a_alto", altitud_max_m=1000)
    r = evaluar(sitio_de("chiloe", altitud_m=2500), sp)["a_alto"]
    assert r["apta"] is False and r["factor_limitante"] == "altitud"


def test_altitud_sin_dato_no_filtra():
    sp = especie("a_dato", altitud_max_m=500)
    r = evaluar(sitio_de("chiloe", altitud_m=None), sp)["a_dato"]
    assert "altitud" not in r["factores"] and r["apta"] is True
    assert "altitud" not in evaluar(sitio_de("chiloe", altitud_m=4000), especie("a_nada"))["a_nada"]["factores"]


def test_altitud_mas_alta_nunca_puntua_mejor():
    sp = especie("a_mono", altitud_max_m=1500)
    puntajes = [evaluar(sitio_de("chiloe", altitud_m=a), sp)["a_mono"]["puntaje"] for a in (0, 500, 1500, 1580, 1650, 2500)]
    assert puntajes == sorted(puntajes, reverse=True)


def test_los_datos_faltantes_incluyen_altitud_y_textura():
    assert ce.datos_faltantes(sitio_de("chiloe", altitud_m=None)) == ["altitud"]
    assert ce.datos_faltantes(sitio_de("chiloe", textura=None)) == ["textura"]
