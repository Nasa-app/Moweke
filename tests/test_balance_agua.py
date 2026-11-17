"""Balance de agua FAO-56 por cultivo (services/motor_estres.py)."""
import asyncio

import numpy as np
import pandas as pd
import pytest

from motor_estres import (ParametrosAgua, Regla, balance_agua, balance_agua_fao56, evaluar, factores_et0,
                          kc_diario)
from pheno_engine import Cultivo, clima_sintetico, simular

PARAMS = ParametrosAgua(zr_m=0.5, p=0.35, kc_ini=0.5, kc_med=1.15, kc_fin=0.75, ky=1.1)


def serie(dias, lluvia=0.0, et0=4.0):
    idx = pd.date_range("2025-01-01", periods=dias, freq="D")
    clima = pd.DataFrame({"tmin": 8.0, "tmax": 18.0, "lluvia": float(lluvia)}, index=idx)
    return clima, np.full(dias, et0), pd.Series(1.0, index=idx)


def test_sin_lluvia_el_agotamiento_crece_con_lo_que_transpira_el_cultivo():
    clima, et0, kc = serie(10)
    a = balance_agua_fao56(clima, et0, kc, 400.0, PARAMS)
    # TAW = 400 * 0,5/2 = 100 mm, RAW = 35 mm: en 10 dias salen 40 mm, y el estres empieza al pasar RAW
    assert a["ks"].iloc[:8].eq(1.0).all() and a["ks"].iloc[9] < 1.0
    assert a["agua"].iloc[-1] == pytest.approx(1 - a["eta"].sum() / 100)


def test_el_cultivo_nunca_transpira_mas_de_lo_que_pide_y_sin_agua_deja_de_transpirar():
    clima, et0, kc = serie(60)
    a = balance_agua_fao56(clima, et0, kc, 200.0, PARAMS)
    assert (a["eta"] <= a["etc"] + 1e-9).all()
    taw = 200.0 * 0.5 / 2.0
    assert a["ks"].iloc[-1] < 0.01 and a["eta"].iloc[-1] < 0.05          # el agua se agota de a poco: Ks tiende a cero
    assert 0.98 * taw < a["eta"].sum() <= taw                            # transpiro casi todo el TAW y nunca mas


def test_mas_profundidad_de_raices_o_de_suelo_da_mas_agua():
    clima, et0, kc = serie(60)
    poco = balance_agua_fao56(clima, et0, kc, 400.0, ParametrosAgua(0.3, 0.35, 0.5, 1.15, 0.75, 1.1))["eta"].sum()
    mucho = balance_agua_fao56(clima, et0, kc, 400.0, ParametrosAgua(0.6, 0.35, 0.5, 1.15, 0.75, 1.1))["eta"].sum()
    assert poco == pytest.approx(60.0, rel=0.05) and mucho == pytest.approx(120.0, rel=0.05)
    # un suelo somero limita las raices aunque la especie llegue mas hondo
    somero = balance_agua_fao56(clima, et0, kc, 400.0, PARAMS, prof_suelo_m=0.25)["eta"].sum()
    assert somero == pytest.approx(400.0 * 0.25 / 2.0, rel=0.05)


def test_el_agua_de_todo_el_perfil_no_alimenta_a_una_raiz_corta():
    """El balde viejo (todo el perfil de 2 m) daba agua de sobra a un cultivo de raiz corta."""
    clima, et0, kc = serie(250)                       # una sequia larga: la demanda supera el agua de cualquiera de los dos
    zona_de_raices = balance_agua_fao56(clima, et0, kc, 400.0, PARAMS)["eta"].sum()
    perfil_completo = balance_agua_fao56(clima, et0, kc, 400.0, ParametrosAgua(2.0, 0.35, 0.5, 1.15, 0.75, 1.1))["eta"].sum()
    assert zona_de_raices == pytest.approx(100.0, rel=0.03) and perfil_completo == pytest.approx(400.0, rel=0.03)


def test_con_riego_no_hay_estres_pero_la_lluvia_en_exceso_sigue_contando():
    clima, et0, kc = serie(60)
    a = balance_agua_fao56(clima, et0, kc, 200.0, PARAMS, riego=True)
    assert a["ks"].eq(1.0).all() and np.allclose(a["eta"], a["etc"])
    lluvioso = clima.copy()
    lluvioso["lluvia"] = 80.0
    assert balance_agua_fao56(lluvioso, et0, kc, 100.0, PARAMS, riego=True)["exceso"].sum() > 0


def test_la_lluvia_repone_el_agotamiento_y_el_excedente_drena():
    clima, et0, kc = serie(40)
    clima.loc[clima.index[20], "lluvia"] = 500.0
    a = balance_agua_fao56(clima, et0, kc, 400.0, PARAMS)
    assert a["agua"].iloc[20] == pytest.approx(1.0)
    assert a["ks"].iloc[21] == 1.0


def test_el_exceso_es_el_del_perfil_completo_como_antes():
    clima, et0, kc = serie(30, lluvia=30.0)
    nuevo = balance_agua_fao56(clima, et0, kc, 150.0, PARAMS)["exceso"]
    viejo = balance_agua(clima, -42.0, 150.0, et0=et0)["exceso"]
    assert np.allclose(nuevo.values, viejo.values)


def test_factores_et0_por_mes_y_sin_calibrar():
    idx = pd.date_range("2025-01-30", periods=4, freq="D")
    assert list(factores_et0(list(range(1, 13)), idx)) == [1, 1, 2, 2]
    assert list(factores_et0(None, idx)) == [1, 1, 1, 1]


# ---------------------------------------------------------------- coeficiente de cultivo
CULTIVO = Cultivo("t", 4, 20, 30, etapas=(("emergencia", 100), ("desarrollo", 300), ("madurez", 500)))


def test_kc_sube_en_el_desarrollo_se_sostiene_y_baja_al_final():
    idx = pd.date_range("2025-01-01", periods=140, freq="D")
    fechas = {"emergencia": pd.Timestamp("2025-01-21"), "desarrollo": pd.Timestamp("2025-03-02"),
              "madurez": pd.Timestamp("2025-05-11")}          # 40 dias de desarrollo, 70 hasta la madurez
    kc = kc_diario(idx, "2025-01-01", fechas, CULTIVO, PARAMS)
    en = lambda d: float(kc[pd.Timestamp(d)])
    assert en("2025-01-10") == PARAMS.kc_ini
    assert en("2025-02-10") == pytest.approx(0.5 + (1.15 - 0.5) * 20 / 40)
    assert en("2025-03-02") == PARAMS.kc_med and en("2025-04-01") == PARAMS.kc_med
    assert PARAMS.kc_fin < en("2025-04-30") < PARAMS.kc_med
    assert en("2025-05-11") == PARAMS.kc_fin and en("2025-05-20") == PARAMS.kc_fin


def test_kc_con_etapas_sin_alcanzar_deja_la_curva_abierta():
    idx = pd.date_range("2025-01-01", periods=60, freq="D")
    kc = kc_diario(idx, "2025-01-01", {"emergencia": pd.Timestamp("2025-01-21")}, CULTIVO, PARAMS)
    assert kc.iloc[0] == PARAMS.kc_ini and kc.iloc[-1] > PARAMS.kc_ini and kc.notna().all()


# ---------------------------------------------------------------- perdida continua (FAO-33)
def _evaluar(factor_lluvia, riego=False, awc=300.0, ky=1.1, reglas=()):
    clima = clima_sintetico("2024-06-01", "2026-06-30", tmedia=14, amp=5, rango=9, seed=3)
    clima["lluvia"] = clima["lluvia"] * factor_lluvia
    siembra = pd.Timestamp("2025-10-15")
    fechas = simular(clima, siembra, -34.5, CULTIVO)
    et0 = np.full(len(clima), 3.5)
    kc = kc_diario(clima.index, siembra, fechas, CULTIVO, PARAMS)
    params = ParametrosAgua(0.5, 0.35, 0.5, 1.15, 0.75, ky)
    agua = balance_agua_fao56(clima, et0, kc, awc, params, riego=riego, lat=-34.5)
    return evaluar(clima, agua, siembra, fechas, CULTIVO, reglas), agua, fechas, siembra


def test_la_perdida_hidrica_crece_de_forma_continua_al_secarse_el_ano():
    perdidas = [_evaluar(f)[0]["perdida"] for f in (1.5, 1.0, 0.6, 0.3, 0.1, 0.0)]
    assert perdidas == sorted(perdidas)
    assert perdidas[0] < perdidas[-1]
    assert len(set(perdidas)) >= 4                                    # sin escalones de todo o nada


def test_la_perdida_es_ky_por_el_deficit_de_la_temporada():
    r, agua, fechas, siembra = _evaluar(0.2)
    ciclo = agua.loc[siembra:fechas["madurez"]]
    esperado = 1.1 * (1 - ciclo["eta"].sum() / ciclo["etc"].sum())
    hidrica = [e["valor"] for e in r["eventos"] if e["peligro"] == "sequia"]
    assert sum(hidrica) == pytest.approx(esperado, rel=0.05)


def test_con_riego_no_hay_perdida_hidrica():
    r = _evaluar(0.0, riego=True)[0]
    assert not [e for e in r["eventos"] if e["peligro"] == "sequia"] and r["perdida"] == 0.0


def test_las_reglas_de_sequia_viejas_no_se_aplican_con_el_balance_nuevo():
    regla = Regla("emergencia->desarrollo", "sequia", 0.0, 0, "parcial", 0.9)   # siempre se cumpliria
    con_regla = _evaluar(1.5, reglas=(regla,))[0]
    sin_regla = _evaluar(1.5)[0]
    assert con_regla["perdida"] == sin_regla["perdida"]


def test_el_balance_viejo_sigue_aplicando_las_reglas_de_sequia():
    clima = clima_sintetico("2024-06-01", "2026-06-30", tmedia=14, amp=5, rango=9, seed=3)
    clima["lluvia"] = 0.0                                                          # un ano sin una gota
    siembra = pd.Timestamp("2025-10-15")
    fechas = simular(clima, siembra, -34.5, CULTIVO)
    regla = Regla("emergencia->desarrollo", "sequia", 0.3, 0, "parcial", 0.9)      # mas de 30 % de los dias con poca agua
    r = evaluar(clima, balance_agua(clima, -34.5, 300.0), siembra, fechas, CULTIVO, (regla,))
    assert r["perdida"] == pytest.approx(0.9)


def test_un_ky_mayor_da_mas_perdida():
    bajo, alto = _evaluar(0.3, ky=0.5)[0]["perdida"], _evaluar(0.3, ky=1.2)[0]["perdida"]
    assert bajo < alto


# ---------------------------------------------------------------- ky opcional (FAO-56 no lo publica para todos)
def test_sin_ky_hay_balance_de_agua_pero_no_perdida_por_sequia():
    r, agua, _, _ = _evaluar(0.0, ky=float("nan"))
    assert agua["agua"].min() < 1.0                                    # el balance corre: hay agotamiento
    assert not [e for e in r["eventos"] if e["peligro"] == "sequia"]


def test_ky_nulo_de_la_base_llega_al_motor_como_nan():
    import math

    import catalogo_especies as ce
    fila = {"especie": "x", "zr_m": 0.5, "p_agotamiento": 0.4, "kc_ini": 0.5, "kc_med": 1.1, "kc_fin": 0.8, "ky": None}
    repo = ce.RepositorioEnMemoria(requisitos_rows=[], umbrales_rows=[], rasgos_rows=[], reglas_rows=[],
                                   parametros_agua_rows=[fila])
    params = asyncio.run(ce.construir_parametros_agua("x", repo))
    assert math.isnan(params.ky) and params.zr_m == 0.5
