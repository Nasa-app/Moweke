"""El suelo se lee del entorno del predio: el pixel del centro puede ser un hueco sin dato aunque los vecinos lo tengan."""
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

import cliente_clsoilmaps as cl
import cliente_soilgrids as sg


@pytest.fixture
def raster(tmp_path):
    """200x200 pixeles de 0,001 grados (~110 m), esquina en (-73,-42). Valor 400 salvo huecos."""
    datos = np.full((200, 200), 400.0, dtype="float32")
    ruta = tmp_path / "awc.tif"
    with rasterio.open(ruta, "w", driver="GTiff", height=200, width=200, count=1, dtype="float32",
                       crs="EPSG:4326", transform=from_origin(-73.1, -41.9, 0.001, 0.001), nodata=float("nan")) as ds:
        ds.write(datos, 1)
    return ruta


def poner_huecos(ruta, filas_columnas, valor=float("nan")):
    with rasterio.open(ruta, "r+") as ds:
        a = ds.read(1)
        for f, c in filas_columnas:
            a[f, c] = valor
        ds.write(a, 1)


def test_el_pixel_central_vacio_se_completa_con_los_vecinos(raster):
    lat, lon = -42.0, -73.0
    with rasterio.open(raster) as ds:
        fila, col = ds.index(lon, lat)
    poner_huecos(raster, [(fila, col)])
    assert cl.leer_valor_punto(str(raster), lat, lon) is None
    valor, radio = cl.leer_valor_entorno(str(raster), lat, lon)
    assert valor == 400.0 and radio == 150


def test_si_casi_todo_es_hueco_se_amplia_el_radio(raster):
    lat, lon = -42.0, -73.0
    with rasterio.open(raster) as ds:
        fila, col = ds.index(lon, lat)
    con_dato = {(fila + 6, col), (fila, col + 6), (fila - 6, col)}  # a unos 660 m
    huecos = [(f, c) for f in range(fila - 12, fila + 13) for c in range(col - 12, col + 13) if (f, c) not in con_dato]
    poner_huecos(raster, huecos)
    valor, radio = cl.leer_valor_entorno(str(raster), lat, lon)
    assert valor == 400.0 and radio == 1000


def test_sin_ningun_dato_en_el_radio_mayor_devuelve_none(raster):
    poner_huecos(raster, [(f, c) for f in range(200) for c in range(200)])
    assert cl.leer_valor_entorno(str(raster), -42.0, -73.0) is None


def test_un_punto_fuera_del_raster_devuelve_none(raster):
    assert cl.leer_valor_entorno(str(raster), -10.0, -60.0) is None


def suelo(ph):
    return {"profundidad": "0-5cm", "ph": ph, "arcilla_pct": None if ph is None else 14.0, "arena_pct": None if ph is None else 40.0,
            "limo_pct": None if ph is None else 30.0, "carbono_organico_g_kg": None if ph is None else 50.0}


def test_soilgrids_con_dato_en_el_centro_no_consulta_vecinos(monkeypatch):
    llamadas = []
    monkeypatch.setattr(sg, "consultar_suelo", lambda *a, **k: llamadas.append(a) or suelo(5.3))
    r = sg.consultar_suelo_entorno(-42.0, -73.0)
    assert r["ph"] == 5.3 and r["vecinos"] is False and len(llamadas) == 1


def test_soilgrids_centro_vacio_usa_la_mediana_de_los_vecinos(monkeypatch):
    respuestas = iter([suelo(None), suelo(None), suelo(5.0), suelo(5.4)])
    monkeypatch.setattr(sg, "consultar_suelo", lambda *a, **k: next(respuestas))
    r = sg.consultar_suelo_entorno(-42.0, -73.0)
    assert r["ph"] == pytest.approx(5.2) and r["vecinos"] is True and r["pixeles"] == 2


def test_soilgrids_sin_dato_en_ningun_vecino_sigue_vacio_y_no_pasa_de_cinco_consultas(monkeypatch):
    llamadas = []
    monkeypatch.setattr(sg, "consultar_suelo", lambda *a, **k: llamadas.append(a) or suelo(None))
    r = sg.consultar_suelo_entorno(-42.0, -73.0)
    assert r["ph"] is None and r["vecinos"] is False and len(llamadas) == 5


def test_soilgrids_un_vecino_que_falla_por_red_se_salta(monkeypatch):
    import requests
    respuestas = iter([suelo(None), requests.Timeout(), suelo(5.0), suelo(5.2)])

    def falso(*a, **k):
        r = next(respuestas)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(sg, "consultar_suelo", falso)
    assert sg.consultar_suelo_entorno(-42.0, -73.0)["ph"] == pytest.approx(5.1)
