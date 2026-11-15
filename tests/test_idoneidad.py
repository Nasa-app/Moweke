"""Pruebas del motor que arma la lista de cultivos posibles de un terreno
(services/catalogo_especies.py). Corren sin base de datos, con el catalogo en memoria de
catalogo_prueba.py."""
import pandas as pd
import pytest

import catalogo_especies as ce
from catalogo_prueba import (LAT, SITIOS, clima_prueba, correr, repo_prueba, req, sitio_de)

SITIOS_NOMBRES = list(SITIOS)


def ranking(sitio, repo=None, **kw):
    return correr(ce.ranking_idoneidad(sitio, repo or repo_prueba(), **kw))


def por_especie(rk):
    return {r["especie"]: r for r in rk}


# ---------------------------------------------------------------- piezas sueltas
def test_respuesta_meseta_forma_de_meseta():
    f = ce.respuesta_meseta
    assert f(0, 5, 10, 20, 30) == 0.0           # bajo el minimo
    assert f(5, 5, 10, 20, 30) == 0.0           # justo en el minimo
    assert f(7.5, 5, 10, 20, 30) == pytest.approx(0.5)
    assert f(15, 5, 10, 20, 30) == 1.0          # entre optimos
    assert f(25, 5, 10, 20, 30) == pytest.approx(0.5)
    assert f(35, 5, 10, 20, 30) == 0.0          # sobre el maximo


def test_respuesta_meseta_no_sabemos_no_es_cero():
    assert ce.respuesta_meseta(None, 5, 10, 20, 30) is None
    assert ce.respuesta_meseta(15, None, None, None, None) is None
    assert ce.respuesta_meseta(-50, None, None, 20, 30) == 1.0   # cola abierta: no limita


def test_normales_mensuales_un_mes_incompleto_anula_la_variable():
    clima = clima_prueba()
    assert all(v is not None for v in ce.normales_mensuales(clima)["tmedia"])
    mes_perdido = clima.index.month == 3
    roto = clima.copy()
    roto.loc[mes_perdido, ["tmin", "tmax"]] = float("nan")
    normales = ce.normales_mensuales(roto)
    assert normales["tmedia"] is None and normales["tmin_extrema"] is None
    assert normales["lluvia"] is not None        # la lluvia no dependia de esos dias
    assert ce.normales_mensuales(None) == {"tmedia": None, "tmin_extrema": None, "lluvia": None}


def test_duracion_de_la_temporada():
    assert ce.duracion_temporada_meses(100, 140) == 4
    assert ce.duracion_temporada_meses(120, 120) == 4
    assert ce.duracion_temporada_meses(None, None) == 12
    assert ce.duracion_temporada_meses(5, 5) == 1


# ---------------------------------------------------------------- el terreno filtra
EXPECTATIVAS = {
    # sitio: (aptas, no aptas)
    "chiloe": ({"trigo_t", "arandano_t"}, {"cacao_t", "salicornia_t"}),
    "desierto": ({"salicornia_t"}, {"trigo_t", "cacao_t", "quinoa_t", "arandano_t"}),
    "altiplano": ({"quinoa_t"}, {"cacao_t"}),
    "tropico": ({"cacao_t"}, {"quinoa_t", "salicornia_t"}),
}


@pytest.mark.parametrize("sitio", EXPECTATIVAS)
def test_cada_clima_deja_pasar_sus_especies_y_descarta_las_demas(sitio):
    aptas, no_aptas = EXPECTATIVAS[sitio]
    rk = por_especie(ranking(sitio_de(sitio)))
    for e in aptas:
        assert rk[e]["apta"] is True, f"{e} deberia ser apta en {sitio}: {rk[e]['factores']}"
    for e in no_aptas:
        assert rk[e]["apta"] is False, f"{e} no deberia ser apta en {sitio}: {rk[e]['factores']}"


def test_el_factor_limitante_dice_por_que_se_descarta():
    rk = por_especie(ranking(sitio_de("chiloe")))
    assert rk["cacao_t"]["factor_limitante"] == "temperatura"
    assert por_especie(ranking(sitio_de("desierto")))["trigo_t"]["factor_limitante"] == "humedad"


def test_la_helada_letal_descarta():
    suave = por_especie(ranking(sitio_de("chiloe")))["trigo_t"]
    fria = por_especie(ranking(sitio_de("chiloe", tmin_delta=-10)))["trigo_t"]
    assert suave["apta"] is True
    assert fria["apta"] is False and fria["factor_limitante"] == "helada"


def test_el_exceso_de_lluvia_descarta():
    rk = por_especie(ranking(sitio_de("tropico")))
    assert rk["salicornia_t"]["apta"] is False and rk["salicornia_t"]["factor_limitante"] == "humedad"


def test_forestales_quedan_fuera_salvo_que_se_pidan():
    assert "pino_t" not in por_especie(ranking(sitio_de("chiloe")))
    con = por_especie(ranking(sitio_de("chiloe"), categorias={"forest/wood"}))
    assert set(con) == {"pino_t"}


@pytest.mark.parametrize("sitio", SITIOS_NOMBRES)
def test_invariantes_de_la_lista(sitio):
    rk = ranking(sitio_de(sitio))
    for r in rk:
        if r["apta"] is True:
            sin_luz = {k: v for k, v in r["factores"].items() if k != "radiacion"}
            assert all(v > 0 for v in sin_luz.values())
            assert r["puntaje"] >= ce.PUNTAJE_MINIMO_APTA
        if r.get("marginal"):
            assert r["apta"] is False and 0 < r["puntaje"] < ce.PUNTAJE_MINIMO_APTA
    claves = [(r["apta"] is True, r["puntaje"] if r["puntaje"] is not None else -1.0) for r in rk]
    assert claves == sorted(claves, reverse=True)


def test_la_luz_solo_baja_el_puntaje_nunca_descarta():
    # Una especie que exige luz brillante en un sitio con casi nada de sol: respuesta de luz 0.
    sol = req("sol_t", tb=4, topt=(12, 20), tc=30, letal=-4, lluvia=(300, 500, 1400, 2200),
              ph=(5.0, 5.2, 7.5, 8.0), ciclo=(100, 140), luz_min="luminoso", luz_max="sol pleno")
    sitio = sitio_de("chiloe", ghi_mensual=[1.0] * 12)
    con = por_especie(ranking(sitio, repo_prueba(extra=[(sol, ["vegetables"])])))["sol_t"]
    sin = por_especie(ranking(sitio, repo_prueba(con_luz=False, extra=[(sol, ["vegetables"])])))["sol_t"]
    assert con["factores"]["radiacion"] == 0.0
    assert con["apta"] is True and sin["apta"] is True
    assert con["puntaje"] == pytest.approx(sin["puntaje"] * 0.7, abs=0.002)   # la luz resta hasta 30 %


# ---------------------------------------------------------------- umbral y orden
def test_una_especie_casi_inviable_no_es_apta_sino_marginal():
    # Clima parejo todo el ano: 100 mm al mes. El maximo de la especie (501,5 mm al ano, o
    # 100,3 mm al mes con un ciclo de 4 meses) queda apenas sobre eso: factor de lluvia ~0,06.
    casi = req("casi_t", tb=4, topt=(12, 20), tc=30, letal=-4, lluvia=(100, 300, 475, 501.5),
               ph=(5.0, 5.5, 6.5, 7.5), ciclo=(100, 140))
    parejo = {"normales": {"tmedia": [16.0] * 12, "tmin_extrema": [5.0] * 12, "lluvia": [100.0] * 12},
              "ph": 6.5, "ghi_mensual": None, "awc_mm": 100}
    r = por_especie(ranking(parejo, repo_prueba(con_luz=False, extra=[(casi, ["vegetables"])])))["casi_t"]
    assert 0 < r["puntaje"] < ce.PUNTAJE_MINIMO_APTA
    assert r["apta"] is False and r["marginal"] is True


def _clon(nombre, categorias):
    fila = req(nombre, tb=4, topt=(12, 20), tc=30, letal=-4, lluvia=(300, 500, 1400, 2200),
               ph=(5.0, 5.2, 7.5, 8.0), ciclo=(100, 140))
    return fila, categorias


def test_empates_ordenan_comida_primero_y_el_resultado_no_depende_del_orden_de_entrada():
    clones = [_clon("a_maleza", ["vegetables", "weed"]), _clon("b_forraje", ["forage/pasture"]),
              _clon("c_comida", ["vegetables"]), _clon("d_comida", ["cereals & pseudocereals"])]
    sitio = sitio_de("chiloe")
    esperado = None
    for orden in (clones, clones[::-1], clones[2:] + clones[:2]):
        repo = repo_prueba(con_luz=False, extra=orden)
        # las malezas no se recomiendan por defecto; con el permiso expreso mantienen su lugar en el desempate
        lista = [r["especie"] for r in ranking(sitio, repo, incluir_malezas=True)
                 if r["especie"].endswith(("_maleza", "_forraje", "_comida"))]
        esperado = esperado or lista
        assert lista == esperado
        por_defecto = [r["especie"] for r in ranking(sitio, repo) if r["especie"].endswith(("_maleza", "_forraje", "_comida"))]
        assert "a_maleza" not in por_defecto
    assert esperado == ["c_comida", "d_comida", "a_maleza", "b_forraje"]


def test_con_el_mismo_puntaje_la_especie_con_seguimiento_va_primero():
    clima = clima_prueba()
    sitio = {"normales": ce.normales_mensuales(clima), "ph": 6.5, "ghi_mensual": None, "awc_mm": 150}
    clon = _clon("a_comida", ["roots/tubers"])
    rk = ranking(sitio, repo_prueba(con_luz=False, curada=True, extra=[clon]), clima=clima, lat=LAT)
    claves = [r["especie"] for r in rk]
    assert "papa_t" in claves and "solanum_prueba" not in claves     # la fila de EcoCrop se funde con la curada
    iguales = [r for r in rk if r["puntaje"] == por_especie(rk)["papa_t"]["puntaje"] and r["apta"]]
    assert iguales[0]["especie"] == "papa_t"


# ---------------------------------------------------------------- pH corregible
def test_ph_un_poco_bajo_el_minimo_es_apta_con_encalado():
    r = por_especie(ranking(sitio_de("chiloe", ph=5.1), repo_prueba(con_luz=False)))["trigo_t"]
    assert r["apta"] is True
    assert r["correcciones"] == [{"tipo": "encalado", "ph_sitio": 5.1, "ph_minimo": 5.2}]
    assert 0 < r["factores"]["ph"] <= ce.PH_PISO_ENCALADO


def test_ph_muy_bajo_no_se_corrige():
    r = por_especie(ranking(sitio_de("chiloe", ph=3.0), repo_prueba(con_luz=False)))["trigo_t"]
    assert r["apta"] is False and r["factores"]["ph"] == 0.0
    assert r["correcciones"] == []


def test_ph_alcalino_no_tiene_correccion():
    r = por_especie(ranking(sitio_de("chiloe", ph=8.5), repo_prueba(con_luz=False)))["trigo_t"]
    assert r["apta"] is False and r["factores"]["ph"] == 0.0 and r["correcciones"] == []


def test_ph_mas_bajo_nunca_puntua_mejor():
    puntajes = [por_especie(ranking(sitio_de("chiloe", ph=ph), repo_prueba(con_luz=False)))["trigo_t"]["puntaje"]
                for ph in (3.0, 4.0, 4.5, 4.8, 5.0, 5.2, 5.5, 6.0)]
    assert puntajes == sorted(puntajes)


def test_ph_en_el_optimo_no_pide_correccion():
    r = por_especie(ranking(sitio_de("chiloe", ph=6.5), repo_prueba(con_luz=False)))["trigo_t"]
    assert r["correcciones"] == [] and r["factores"]["ph"] == 1.0


# ---------------------------------------------------------------- especie curada: un solo puntaje
def _curada(**kw):
    clima = clima_prueba(kw.pop("lluvia_factor", 1.0))
    sitio = {"normales": ce.normales_mensuales(clima), "ph": kw.pop("ph", 6.5), "ghi_mensual": None,
             "awc_mm": kw.pop("awc", 150)}
    riego = kw.pop("riego", False)
    repo = repo_prueba(con_luz=False, curada=True, **kw)
    return por_especie(ranking(sitio, repo, clima=clima, lat=LAT, riego=riego))["papa_t"]


def test_el_puntaje_de_la_curada_es_el_menor_entre_simulacion_y_ecocrop():
    sitio_ph_justo = _curada(ph=5.6)           # EcoCrop: pH en rampa (0,5); la simulacion no lo ve
    assert sitio_ph_justo["metodo"] == "simulacion_por_fase"
    assert sitio_ph_justo["puntaje_simulacion"] > sitio_ph_justo["puntaje_ecocrop"]
    assert sitio_ph_justo["puntaje"] == min(sitio_ph_justo["puntaje_simulacion"], sitio_ph_justo["puntaje_ecocrop"])
    ok = _curada(ph=6.5)
    assert ok["puntaje"] == pytest.approx(min(ok["puntaje_simulacion"], ok["puntaje_ecocrop"]))
    assert ok["puntaje"] > sitio_ph_justo["puntaje"]


def test_la_curada_fuera_de_rangos_de_ecocrop_no_es_apta_aunque_la_simulacion_corra():
    r = _curada(ph=3.0)
    assert r["apta"] is False and r["fuera_de_rangos_ecocrop"] is True and r["puntaje"] == 0.0


# ---------------------------------------------------------------- datos faltantes
def test_datos_faltantes_lista_lo_que_no_se_midio():
    completo = sitio_de("chiloe")
    assert ce.datos_faltantes(completo) == []
    sin_ph = sitio_de("chiloe", ph=False)
    assert ce.datos_faltantes(sin_ph) == ["ph"]
    pobre = {"normales": {"tmedia": [1] * 12, "tmin_extrema": None, "lluvia": None}, "ph": None,
             "ghi_mensual": None, "awc_mm": None}
    assert ce.datos_faltantes(pobre) == ["helada", "lluvia", "ph", "radiacion", "agua_suelo", "altitud", "textura"]


def test_sin_dato_de_ph_el_factor_no_filtra_y_la_lista_se_amplia():
    con = sum(r["apta"] is True for r in ranking(sitio_de("chiloe", ph=9.5)))
    sin = sum(r["apta"] is True for r in ranking(sitio_de("chiloe", ph=False)))
    assert sin > con


# ---------------------------------------------------------------- riego
def test_con_riego_la_falta_de_lluvia_no_descarta():
    sitio = sitio_de("desierto", ph=6.8)
    secano = por_especie(ranking(sitio))["trigo_t"]
    riego = por_especie(ranking(sitio, riego=True))["trigo_t"]
    assert secano["apta"] is False and secano["factor_limitante"] == "humedad"
    assert riego["apta"] is True and riego["factores"]["humedad"] == 1.0


def test_con_riego_el_exceso_de_lluvia_sigue_descartando():
    sitio = sitio_de("tropico")
    assert por_especie(ranking(sitio, riego=True))["salicornia_t"]["apta"] is False


def test_riego_no_cambia_nada_donde_ya_llueve_lo_suficiente():
    sitio = sitio_de("chiloe")
    a = {r["especie"]: (r["apta"], r["puntaje"]) for r in ranking(sitio)}
    b = {r["especie"]: (r["apta"], r["puntaje"]) for r in ranking(sitio, riego=True)}
    assert a["trigo_t"] == b["trigo_t"]


def test_con_riego_la_simulacion_por_fase_no_pierde_por_sequia():
    seco = dict(lluvia_factor=0.02, awc=30, lluvia_curada=(None, None, None, None))
    sin_riego = _curada(**seco)
    con_riego = _curada(**seco, riego=True)
    assert sin_riego["puntaje_simulacion"] < con_riego["puntaje_simulacion"] == 1.0


# ---------------------------------------------------------------- lo que devuelve el endpoint
def _lista():
    return [{"especie": e, "apta": a} for e, a in
            [("p", True), ("q", True), ("r", True), ("s", False), ("t", None)]]


def test_seleccionar_aplica_el_limite_a_las_aptas():
    assert [r["especie"] for r in ce.seleccionar_candidatas(_lista(), 2)] == ["p", "q"]
    assert [r["especie"] for r in ce.seleccionar_candidatas(_lista(), 10)] == ["p", "q", "r"]


def test_seleccionar_incluye_no_aptas_si_se_piden():
    assert len(ce.seleccionar_candidatas(_lista(), 10, incluir_no_aptas=True)) == 5


def test_seleccionar_una_especie_ignora_limite_y_aptitud():
    assert [r["especie"] for r in ce.seleccionar_candidatas(_lista(), 1, especie="s, r")] == ["r", "s"]
    assert ce.seleccionar_candidatas(_lista(), 1, especie="no_existe") == []
