"""La lluvia de los ultimos dias del predio (services.riego.lluvia_reciente), dicha en milimetros y dias."""
import pandas as pd

from riego import lluvia_reciente


def serie(valores, fin="2026-11-15"):
    return pd.Series(valores, index=pd.date_range(end=fin, periods=len(valores), freq="D"), dtype=float)


def test_suma_los_siete_dias_anteriores_a_hoy_y_dice_hace_cuanto_llovio():
    # dias 6 al 15 de nov; hoy es el 15: la ventana va del 8 al 14
    lluvia = serie([0, 0, 5, 0, 0, 12, 0, 0, 0, 7])
    r = lluvia_reciente(lluvia, "2026-11-15")
    assert r["total_mm"] == 17.0 and r["dias_con_dato"] == 7
    assert r["ultima_lluvia"] == {"hace_dias": 4, "mm": 12.0}


def test_la_lluvia_de_hoy_no_cuenta_porque_el_dia_no_termino():
    r = lluvia_reciente(serie([0, 0, 0, 0, 0, 0, 0, 9]), "2026-11-15")
    assert r["total_mm"] == 0.0 and r["ultima_lluvia"] is None


def test_sin_lluvia_en_la_ventana_no_hay_ultima_lluvia():
    r = lluvia_reciente(serie([0.0] * 10), "2026-11-15")
    assert r["total_mm"] == 0.0 and r["ultima_lluvia"] is None


def test_la_llovizna_bajo_un_milimetro_no_cuenta_como_dia_de_lluvia():
    r = lluvia_reciente(serie([0, 0, 0, 0.4, 0, 0, 0, 0]), "2026-11-15")
    assert r["ultima_lluvia"] is None and r["total_mm"] == 0.4


def test_los_dias_sin_dato_no_se_cuentan_como_cero():
    r = lluvia_reciente(serie([2, None, None, 3, 0, 1, None, 5]), "2026-11-15")   # ventana: 8 al 14
    assert r["dias_con_dato"] == 4 and r["total_mm"] == 6.0


def test_los_dias_despues_de_hoy_no_entran():
    lluvia = serie([0, 0, 20, 0, 20, 20, 20], fin="2026-11-17")   # el 13 llovio; 15, 16 y 17 son pronostico o estimado
    r = lluvia_reciente(lluvia, "2026-11-15")
    assert r["total_mm"] == 20.0 and r["ultima_lluvia"] == {"hace_dias": 2, "mm": 20.0}
