"""El reporte de campo reancla el calendario del seguimiento (catalogo_especies.calendario_con_reportes)."""
from datetime import date

import pandas as pd

import catalogo_especies as ce
from catalogo_prueba import LAT, clima_prueba, correr, repo_prueba
from pheno_engine import Cultivo

SIEMBRA, HOY = date(2024, 12, 1), date(2025, 1, 10)


def horizontes(idx):
    return pd.Series(["observado" if d <= pd.Timestamp("2025-01-07") else "pronostico" if d <= pd.Timestamp("2025-01-26")
                      else "estimado" for d in idx], index=idx)


def seguimiento(reportes=()):
    clima = clima_prueba(0.0).loc["2024-11-01":"2025-03-31"].copy()
    clima["rh"] = 80.0
    clima["horizonte"] = horizontes(clima.index)
    return correr(ce.seguimiento_cultivo("papa_t", None, repo_prueba(curada=True), clima, SIEMBRA, LAT, 140.0, HOY,
                                         reportes=tuple(reportes)))


def fechas(r):
    return {e["etapa"]: e["fecha"] for e in r["etapas"]}


def test_sin_reportes_el_calendario_es_el_simulado_y_nada_figura_como_confirmado():
    r = seguimiento()
    assert fechas(r)["emergencia"] == "2024-12-13"
    assert not any(e["confirmada"] for e in r["etapas"])


def test_un_brote_mas_tarde_de_lo_simulado_corre_toda_la_etapa_siguiente():
    base, con = seguimiento(), seguimiento([{"fase": "brote", "fecha": date(2024, 12, 25)}])
    assert fechas(con)["emergencia"] == "2024-12-25"
    assert fechas(con)["tuberizacion"] > fechas(base)["tuberizacion"]
    assert fechas(con)["madurez"] > fechas(base)["madurez"]
    assert [e["confirmada"] for e in con["etapas"]] == [True, False, False]


def test_un_brote_mas_temprano_adelanta_las_etapas_siguientes():
    base, con = seguimiento(), seguimiento([{"fase": "brote", "fecha": date(2024, 12, 5)}])
    assert fechas(con)["emergencia"] == "2024-12-05"
    assert fechas(con)["tuberizacion"] < fechas(base)["tuberizacion"]


def test_la_fase_actual_sigue_al_reporte():
    # simulado: ya emergio hace semanas; el agricultor dice que brotó recién el 8 de enero
    con = seguimiento([{"fase": "brote", "fecha": date(2025, 1, 8)}])
    assert con["fase_actual"] == "emergencia->tuberizacion"
    assert fechas(con)["emergencia"] == "2025-01-08"


def test_de_cada_etapa_cuenta_el_reporte_mas_reciente():
    r = seguimiento([{"fase": "brote", "fecha": date(2024, 12, 20)}, {"fase": "brote", "fecha": date(2024, 12, 10)},
                     {"fase": "brote", "fecha": date(2024, 12, 28)}])
    assert fechas(r)["emergencia"] == "2024-12-28"


def test_las_fases_sin_etapa_propia_no_mueven_el_calendario():
    base = seguimiento()
    for fase in ("hojas", "fruto", "amarilla", "cosecha", "flor"):    # papa no tiene floracion
        assert fechas(seguimiento([{"fase": fase, "fecha": date(2024, 12, 20)}])) == fechas(base), fase


def test_un_reporte_fuera_de_la_serie_se_ignora():
    base = seguimiento()
    for fecha in (date(2024, 11, 20), date(2025, 6, 1)):    # antes de la siembra, despues del fin del clima
        assert fechas(seguimiento([{"fase": "brote", "fecha": fecha}])) == fechas(base)


def test_la_funcion_con_una_etapa_media_corrige_las_anteriores_que_quedan_despues():
    c = Cultivo("t", 4, 20, 30, etapas=(("emergencia", 100), ("floracion", 300), ("madurez", 500)))
    idx = pd.date_range("2024-11-01", "2025-06-30", freq="D")
    clima = pd.DataFrame({"tmin": 8.0, "tmax": 18.0, "lluvia": 0.0}, index=idx)
    from pheno_engine import simular
    sim = simular(clima, "2024-11-15", LAT, c)
    # el agricultor ve la flor el 20 de dic, antes de lo que el reloj daba para la emergencia + floracion
    nuevas, conf = ce.calendario_con_reportes(clima, sim, c, "2024-11-15", LAT, [{"fase": "flor", "fecha": date(2024, 12, 20)}])
    assert nuevas["floracion"] == pd.Timestamp("2024-12-20") and set(conf) == {"floracion"}
    assert nuevas["emergencia"] <= nuevas["floracion"] and nuevas["madurez"] > nuevas["floracion"]
