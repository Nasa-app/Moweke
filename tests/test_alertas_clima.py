"""Cambios fuertes de clima del predio (services.alertas_clima)."""
import pandas as pd

from services.alertas_clima import cambios_fuertes


def serie(filas, inicio="2026-11-15"):
    df = pd.DataFrame(filas, columns=["tmin", "tmax", "lluvia"], dtype=float)
    df.index = pd.date_range(inicio, periods=len(df), freq="D")
    df["horizonte"] = "pronostico"
    return df


def tipos(alertas):
    return [(a["tipo"], a["primer_dia"], a["ultimo_dia"]) for a in alertas]


def test_dias_normales_no_alertan():
    assert cambios_fuertes(serie([(6, 13, 4), (7, 14, 2), (5, 12, 8)]), "2026-11-16") == []


def test_helada_junta_los_dias_seguidos_y_marca_la_fuerte():
    a = cambios_fuertes(serie([(5, 12, 0), (-1, 11, 0), (-4, 10, 0), (3, 12, 0)]), "2026-11-15")
    assert tipos(a) == [("helada", "2026-11-16", "2026-11-17")]
    assert a[0]["valor"] == -4.0 and a[0]["fuerte"] is True


def test_salto_brusco_de_la_maxima_usa_el_dia_anterior_a_hoy():
    # el 15 hace 16 y el 16 hace 8: el enfriamiento se mide contra el dia anterior a hoy
    a = cambios_fuertes(serie([(8, 16, 0), (4, 8, 0)]), "2026-11-16")
    assert tipos(a) == [("enfriamiento_brusco", "2026-11-16", "2026-11-16")] and a[0]["valor"] == -8.0


def test_lo_anterior_a_hoy_no_se_avisa():
    assert cambios_fuertes(serie([(-5, 10, 0), (4, 12, 0)]), "2026-11-16") == []


def test_calor_y_lluvia_fuerte():
    a = cambios_fuertes(serie([(10, 20, 0), (12, 27, 31)]), "2026-11-16")
    assert {t[0] for t in tipos(a)} == {"calor", "lluvia_fuerte", "calentamiento_brusco"}


def test_dias_sin_dato_no_alertan():
    assert cambios_fuertes(serie([(5, 12, 0), (None, None, None)]), "2026-11-15") == []
    assert cambios_fuertes(None, "2026-11-15") == []
