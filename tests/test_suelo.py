"""Suelo que declara el agricultor (drenaje, sal, profundidad, fertilidad) y correccion de la
temperatura por altitud."""
import pandas as pd
import pytest

import catalogo_especies as ce
from catalogo_prueba import clima_prueba, correr, repo_prueba, req, sitio_de

BASE = dict(tb=4, topt=(12, 20), tc=30, letal=-4, lluvia=(300, 500, 1400, 2200), ph=(5.0, 5.2, 7.5, 8.0), ciclo=(100, 140))


def evaluar(sitio, **terreno):
    fila = (req("sp", **BASE, **terreno), ["vegetables"])
    rk = correr(ce.ranking_idoneidad(sitio, repo_prueba(con_luz=False, extra=[fila])))
    return next(r for r in rk if r["especie"] == "sp")


def con_suelo(**suelo):
    return sitio_de("chiloe", suelo=suelo)


# ---------------------------------------------------------------- drenaje
def test_drenaje_optimo_tolerado_y_fuera():
    sp = dict(drenaje_opt=["well"], drenaje_rango=["well", "excessive"])
    assert evaluar(con_suelo(drenaje="well"), **sp)["factores"]["drenaje"] == 1.0
    tolerado = evaluar(con_suelo(drenaje="excessive"), **sp)
    assert tolerado["factores"]["drenaje"] == 0.75 and tolerado["apta"] is True
    fuera = evaluar(con_suelo(drenaje="poorly"), **sp)
    assert fuera["factores"]["drenaje"] == 0.0 and fuera["apta"] is False and fuera["factor_limitante"] == "drenaje"


def test_drenaje_sin_respuesta_no_filtra():
    r = evaluar(sitio_de("chiloe"), drenaje_opt=["well"], drenaje_rango=["well"])
    assert "drenaje" not in r["factores"] and r["apta"] is True


# ---------------------------------------------------------------- sal
@pytest.mark.parametrize("suelo, esperado", [("low", 1.0), ("medium", 0.5), ("high", 0.0)])
def test_salinidad_escala(suelo, esperado):
    r = evaluar(con_suelo(salinidad=suelo), salinidad_opt="low", salinidad_max="medium")
    assert r["factores"]["salinidad"] == esperado


def test_salinidad_sobre_el_maximo_descarta():
    r = evaluar(con_suelo(salinidad="high"), salinidad_opt="low", salinidad_max="medium")
    assert r["apta"] is False and r["factor_limitante"] == "salinidad"


def test_salinidad_sin_optimo_usa_el_maximo():
    assert evaluar(con_suelo(salinidad="medium"), salinidad_max="medium")["factores"]["salinidad"] == 1.0


def test_salinidad_sin_dato_de_la_especie_no_filtra():
    assert "salinidad" not in evaluar(con_suelo(salinidad="high"))["factores"]


# ---------------------------------------------------------------- profundidad
@pytest.mark.parametrize("suelo, esperado", [("deep", 1.0), ("medium", 1.0), ("shallow", 0.75), ("very_shallow", 0.0)])
def test_profundidad_es_un_minimo(suelo, esperado):
    r = evaluar(con_suelo(profundidad=suelo), profundidad_opt="medium", profundidad_min="shallow")
    assert r["factores"]["profundidad"] == esperado


def test_un_suelo_mas_profundo_nunca_puntua_peor():
    puntajes = [evaluar(con_suelo(profundidad=p), profundidad_opt="deep", profundidad_min="shallow")["puntaje"]
                for p in ("very_shallow", "shallow", "medium", "deep")]
    assert puntajes == sorted(puntajes)


# ---------------------------------------------------------------- fertilidad
def test_fertilidad_baja_se_corrige_con_abono_y_nunca_descarta():
    sp = dict(fertilidad_opt="high", fertilidad_min="moderate")
    optimo = evaluar(con_suelo(fertilidad="high"), **sp)
    assert optimo["factores"]["fertilidad"] == 1.0 and optimo["correcciones"] == []
    medio = evaluar(con_suelo(fertilidad="moderate"), **sp)
    assert medio["factores"]["fertilidad"] == 0.75
    assert medio["correcciones"] == [{"tipo": "fertilizacion", "fertilidad_sitio": "moderate", "fertilidad_requerida": "high"}]
    pobre = evaluar(con_suelo(fertilidad="low"), **sp)
    assert pobre["factores"]["fertilidad"] == 0.5 and pobre["apta"] is True and pobre["correcciones"]


def test_fertilidad_mas_alta_nunca_puntua_peor():
    puntajes = [evaluar(con_suelo(fertilidad=f), fertilidad_opt="high", fertilidad_min="low")["puntaje"]
                for f in ("low", "moderate", "high")]
    assert puntajes == sorted(puntajes)


def test_las_correcciones_de_ph_y_fertilidad_se_acumulan():
    sitio = sitio_de("chiloe", ph=5.1, suelo={"fertilidad": "low"})
    r = evaluar(sitio, fertilidad_opt="high", fertilidad_min="moderate")
    assert {c["tipo"] for c in r["correcciones"]} == {"encalado", "fertilizacion"}


# ---------------------------------------------------------------- preguntas sin responder
def test_suelo_sin_declarar():
    assert ce.suelo_sin_declarar(sitio_de("chiloe")) == ["drenaje", "salinidad", "profundidad", "fertilidad"]
    assert ce.suelo_sin_declarar(con_suelo(drenaje="well", fertilidad="low")) == ["salinidad", "profundidad"]
    todo = con_suelo(drenaje="well", salinidad="low", profundidad="deep", fertilidad="high")
    assert ce.suelo_sin_declarar(todo) == []


# ---------------------------------------------------------------- temperatura por altitud
def test_la_parcela_mas_alta_que_su_celda_es_mas_fria():
    assert ce.delta_temperatura_por_altitud(1000, 500) == pytest.approx(-3.25)
    assert ce.delta_temperatura_por_altitud(200, 400) == pytest.approx(1.3)
    assert ce.delta_temperatura_por_altitud(300, 300) == 0.0


def test_la_correccion_tiene_tope_y_sin_dato_vale_cero():
    assert ce.delta_temperatura_por_altitud(5000, 0) == -ce.CORRECCION_TEMPERATURA_MAX_C
    assert ce.delta_temperatura_por_altitud(0, 5000) == ce.CORRECCION_TEMPERATURA_MAX_C
    assert ce.delta_temperatura_por_altitud(None, 300) == 0.0 and ce.delta_temperatura_por_altitud(300, None) == 0.0


def test_corregir_temperatura_mueve_tmin_y_tmax_y_no_toca_la_lluvia_ni_el_original():
    clima = clima_prueba()
    original = clima.copy()
    corregido = ce.corregir_temperatura(clima, -2.0)
    assert (corregido["tmin"] - clima["tmin"]).eq(-2.0).all() and (corregido["tmax"] - clima["tmax"]).eq(-2.0).all()
    assert corregido["lluvia"].equals(clima["lluvia"])
    pd.testing.assert_frame_equal(clima, original)
    assert ce.corregir_temperatura(clima, 0.0) is clima and ce.corregir_temperatura(None, -2.0) is None


def test_un_clima_mas_frio_cambia_la_lista():
    clima = clima_prueba()
    normales = lambda c: ce.normales_mensuales(c)
    sitio = lambda c: {"normales": normales(c), "ph": 6.5, "ghi_mensual": None, "awc_mm": 100}
    aptas = lambda c: {r["especie"] for r in correr(ce.ranking_idoneidad(sitio(c), repo_prueba(con_luz=False))) if r["apta"]}
    tibio, frio = aptas(ce.corregir_temperatura(clima, +4.0)), aptas(ce.corregir_temperatura(clima, -8.0))
    assert tibio != frio


# ---------------------------------------------------------------- agua del suelo estimada fuera de Chile
def test_el_agua_estimada_de_un_franco_ronda_los_280_mm():
    import services.repositorio_clima as rc
    assert rc.estimar_agua_disponible_mm(20, 40, 11.6) == pytest.approx(280, abs=15)    # 2 % de materia organica


def test_un_suelo_arcilloso_guarda_mas_que_uno_arenoso_y_siempre_queda_en_los_limites():
    import services.repositorio_clima as rc
    arenoso, franco = rc.estimar_agua_disponible_mm(5, 90, 5), rc.estimar_agua_disponible_mm(20, 40, 11.6)
    assert arenoso < franco
    bajo, alto = rc.AGUA_SUELO_ESTIMADA_LIMITES_MM
    assert all(bajo <= v <= alto for v in (arenoso, franco, rc.estimar_agua_disponible_mm(60, 5, 80)))


def test_sin_textura_o_carbono_no_se_inventa_el_agua():
    import services.repositorio_clima as rc
    assert rc.estimar_agua_disponible_mm(None, 40, 10) is None
    assert rc.estimar_agua_disponible_mm(20, 40, None) is None


def test_leer_sitio_prefiere_clsoilmaps_y_estima_solo_si_falta():
    import asyncio
    from datetime import date
    import services.repositorio_clima as rc

    class Sesion:
        def __init__(self, filas):
            self.filas = filas

        async def execute(self, sentencia, parametros=None):
            fila = self.filas.pop(0)
            return type("R", (), {"mappings": lambda s: s, "all": lambda s: fila, "scalar": lambda s: None})()

    suelo = [{"capa": "soilgrids_arcilla_pct", "valor": 20.0}, {"capa": "soilgrids_arena_pct", "valor": 40.0},
             {"capa": "soilgrids_carbono_organico_g_kg", "valor": 11.6}]
    chile = asyncio.run(rc.leer_sitio(Sesion([suelo + [{"capa": "clsoilmaps_awc_total_mm", "valor": 437.0}], [], []]), 1, date(2026, 11, 15)))
    fuera = asyncio.run(rc.leer_sitio(Sesion([suelo, [], []]), 1, date(2026, 11, 15)))
    sin = asyncio.run(rc.leer_sitio(Sesion([[], [], []]), 1, date(2026, 11, 15)))
    assert (chile["awc_mm"], chile["fuente_agua_suelo"]) == (437.0, "clsoilmaps")
    assert fuera["fuente_agua_suelo"] == "estimado_textura" and 250 < fuera["awc_mm"] < 310
    assert sin["awc_mm"] is None and sin["fuente_agua_suelo"] is None


def test_la_materia_organica_se_acota_a_8_por_ciento():
    import services.repositorio_clima as rc
    tope = rc.MATERIA_ORGANICA_MAX_PCT / 1.724 * 10
    assert rc.estimar_agua_disponible_mm(37.1, 17.4, 189) == rc.estimar_agua_disponible_mm(37.1, 17.4, tope)
    assert rc.estimar_agua_disponible_mm(37.1, 17.4, 70) == pytest.approx(314, abs=1)


# ---------------------------------------------------------------- tope del puntaje segun lo que se sabe del suelo
COMPLETO = {"drenaje": "well", "salinidad": "low", "profundidad": "deep", "fertilidad": "high"}


def test_con_el_suelo_completo_no_hay_tope():
    assert ce.tope_por_suelo(sitio_de("chiloe", suelo=COMPLETO)) is None


def test_si_falta_una_respuesta_del_agricultor_el_tope_es_90():
    assert ce.tope_por_suelo(sitio_de("chiloe", suelo={**COMPLETO, "salinidad": None})) == (0.90, "suelo_sin_declarar")
    assert ce.tope_por_suelo(sitio_de("chiloe")) == (0.90, "suelo_sin_declarar")


def test_sin_ph_ni_textura_de_satelite_el_tope_es_80_aunque_haya_respondido_todo():
    sitio = sitio_de("chiloe", ph=False, textura=None, suelo=COMPLETO)
    assert ce.tope_por_suelo(sitio) == (0.80, "sin_suelo_de_satelite")


def test_con_solo_el_ph_ya_hay_base_de_satelite():
    assert ce.tope_por_suelo(sitio_de("chiloe", textura=None, suelo=COMPLETO)) is None
    assert ce.tope_por_suelo(sitio_de("chiloe", ph=False, suelo=COMPLETO)) is None     # queda la textura


def _r(especie, puntaje, dificil=None):
    return {"especie": especie, "apta": True, "puntaje": puntaje, "puntaje_ano_dificil": dificil}


def test_el_tope_limita_el_puntaje_informa_el_motivo_y_conserva_el_orden():
    rk = [_r("a", 1.0, 0.95), _r("b", 0.97, 0.5), _r("c", 0.6, 0.4), _r("d", 0.3)]
    out = ce.aplicar_tope_suelo(rk, sitio_de("chiloe"))
    assert [r["especie"] for r in out] == ["a", "b", "c", "d"]            # a y b empatan en 0,9: desempata el puntaje sin tope
    assert [r["puntaje"] for r in out] == [0.9, 0.9, 0.6, 0.3]
    assert out[0]["puntaje_ano_dificil"] == 0.9 and out[1]["puntaje_ano_dificil"] == 0.5
    assert out[0]["tope_suelo"] == {"tope": 0.9, "motivo": "suelo_sin_declarar", "puntaje_sin_tope": 1.0}
    assert "puntaje_sin_tope" not in out[2]["tope_suelo"]                  # el tope no lo bajo


def test_con_el_suelo_completo_el_ranking_queda_igual():
    rk = [_r("a", 1.0), _r("b", 0.5)]
    assert ce.aplicar_tope_suelo(rk, sitio_de("chiloe", suelo=COMPLETO)) == [_r("a", 1.0), _r("b", 0.5)]


def test_el_ranking_multianual_aplica_el_tope_en_las_dos_salidas():
    from multianual import ranking_multianual
    for suelo, esperado in ((None, 0.90), (COMPLETO, None)):
        sitio = sitio_de("chiloe", suelo=suelo)
        rk, _ = correr(ranking_multianual(sitio, repo_prueba(con_luz=False), None, None, None))
        topes = {r.get("tope_suelo", {}).get("tope") for r in rk}
        assert topes == {esperado}, (suelo, topes)
        if esperado:
            assert max(r["puntaje"] for r in rk if r["puntaje"] is not None) <= esperado
