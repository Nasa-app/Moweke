"""NASA HLS: NDVI del predio a 30 m (services/cliente_hls.py, ingesta_predio.resumir_hls, repositorio_clima.leer_ndvi)."""
import asyncio
from datetime import date

import numpy as np

import services.cliente_hls as hls
import services.ingesta_predio as ingesta
import services.repositorio_clima as rc


def _lectura(fecha, pixeles, validos, ndvi_medio, sensor="HLSS30"):
    return {"fecha": fecha, "sensor": sensor, "pixeles": pixeles, "validos": validos,
            "suma_ndvi": ndvi_medio * validos}


# ---------------------------------------------------------------- cliente
def test_sensor_de_distingue_landsat_y_sentinel():
    assert hls.sensor_de("HLS.S30.T18GXU.2026247T143739.v2.0") == "HLSS30"
    assert hls.sensor_de("HLS.L30.T18GWT.2026250T143553.v2.0") == "HLSL30"


def test_pixeles_validos_descarta_nube_sombra_agua_y_sin_dato():
    rojo = np.array([[500, 500, 500, 500, 500, -9999]])
    nir = np.array([[3000, 3000, 3000, 3000, 3000, 3000]])
    # bit 1 nube, bit 3 sombra, bit 5 agua, 0 despejado, 0 despejado, 0 despejado
    fmask = np.array([[0b10, 0b1000, 0b100000, 0, 0b1, 0]], dtype=np.uint8)
    dentro = np.ones_like(rojo, dtype=bool)
    ok = hls.pixeles_validos(rojo, nir, fmask, dentro)
    assert ok.tolist() == [[False, False, False, True, True, False]]   # el bit 0 (cirrus) no descarta


def test_pixeles_validos_ignora_lo_que_cae_fuera_del_poligono():
    rojo, nir = np.array([[500, 500]]), np.array([[3000, 3000]])
    ok = hls.pixeles_validos(rojo, nir, np.zeros((1, 2), dtype=np.uint8), np.array([[True, False]]))
    assert ok.tolist() == [[True, False]]


def _feature(id_, nube, x0, y0, x1, y1, fecha="2026-10-09"):
    sensor = hls.sensor_de(id_)
    nir = hls.BANDA_NIR[sensor]
    return {"id": id_, "properties": {"eo:cloud_cover": nube, "datetime": f"{fecha}T14:00:00Z"},
            "geometry": {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]},
            "assets": {b: {"href": f"https://x/{id_}.{b}.tif"} for b in ("B04", nir, "Fmask")}}


def test_buscar_escenas_deja_una_por_dia_y_sensor_y_solo_las_que_cubren_la_caja(monkeypatch):
    caja = [-73.77, -42.49, -73.75, -42.47]
    pagina = {"features": [
        _feature("HLS.S30.T18GWU.2026282T143739.v2.0", 40, -74, -43, -73, -42),
        _feature("HLS.S30.T18GXU.2026282T143739.v2.0", 15, -74, -43, -73, -42),     # misma fecha: gana la menos nublada
        _feature("HLS.S30.T18GWT.2026282T143739.v2.0", 5, -73.76, -43, -73, -42),   # no cubre el borde oeste
        _feature("HLS.S30.T18GWV.2026283T143739.v2.0", 95, -74, -43, -73, -42, "2026-10-10"),  # demasiada nube
        _feature("HLS.L30.T18GWU.2026282T143553.v2.0", 20, -74, -43, -73, -42),     # otro sensor, mismo dia
    ], "links": []}

    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return pagina
    monkeypatch.setattr(hls.requests, "post", lambda *a, **k: R())
    escenas = hls.buscar_escenas(caja, "2026-10-01", "2026-10-31")
    assert sorted((e["sensor"], e["nube_pct"]) for e in escenas) == [("HLSL30", 20), ("HLSS30", 15)]


def test_url_firmada_no_sigue_la_redireccion_y_avisa_si_el_token_no_sirve(monkeypatch):
    class R:
        def __init__(self, codigo, cabeceras):
            self.status_code, self.headers = codigo, cabeceras
    destino = "https://data.lpdaac.earthdatacloud.nasa.gov/archivo.tif"
    monkeypatch.setattr(hls.requests, "get", lambda *a, **k: R(303, {"Location": "https://firmada"}))
    assert hls._url_firmada("t", destino) == "https://firmada"
    monkeypatch.setattr(hls.requests, "get", lambda *a, **k: R(401, {}))
    try:
        hls._url_firmada("t", destino)
        assert False
    except hls.ErrorHLS as error:
        assert "token" in str(error)


def test_el_token_no_viaja_a_un_servidor_ajeno(monkeypatch):
    llamadas = []
    monkeypatch.setattr(hls.requests, "get", lambda *a, **k: llamadas.append(a))
    for href in ("https://evil.example.com/a.tif", "http://data.lpdaac.earthdatacloud.nasa.gov/a.tif",
                 "https://earthdatacloud.nasa.gov.evil.com/a.tif"):
        try:
            hls._url_firmada("t", href)
            assert False
        except hls.ErrorHLS:
            pass
    assert llamadas == []


def test_un_token_rechazado_detiene_la_lectura_y_una_escena_rota_solo_se_salta(monkeypatch):
    escenas = [{"id": "a", "fecha": "2026-10-01", "sensor": "HLSS30", "activos": {}},
               {"id": "b", "fecha": "2026-10-02", "sensor": "HLSS30", "activos": {}}]

    def lectura(token, escena, geometria):
        if escena["id"] == "a":
            raise hls.ErrorHLS("el predio queda fuera de la tesela")
        return {"fecha": escena["fecha"]}
    monkeypatch.setattr(hls, "ndvi_de_escena", lectura)
    assert hls.ndvi_de_escenas("t", escenas, {}) == [{"fecha": "2026-10-02"}]

    def vencido(token, escena, geometria):
        raise hls.ErrorHLS("Earthdata rechazo el token (401): vencido o sin permiso")
    monkeypatch.setattr(hls, "ndvi_de_escena", vencido)
    try:
        hls.ndvi_de_escenas("t", escenas, {})
        assert False
    except hls.ErrorHLS:
        pass


# ---------------------------------------------------------------- ingesta
def test_resumir_hls_pondera_por_pixeles_y_toma_la_mejor_fraccion_vista():
    # 2026-10-10 y 2026-10-11 caen en el mismo intervalo de 5 dias
    r = ingesta.resumir_hls([_lectura("2026-10-10", 100, 80, 0.40), _lectura("2026-10-11", 100, 20, 0.60)])
    assert len(r) == 1
    assert round(r[0]["ndvi"], 3) == 0.44          # (0.40*80 + 0.60*20) / 100
    assert r[0]["visible"] == 0.8


def test_resumir_hls_un_intervalo_sin_pixeles_validos_queda_sin_ndvi():
    r = ingesta.resumir_hls([_lectura("2026-10-09", 100, 0, 0.0)])
    assert r[0]["ndvi"] is None and r[0]["visible"] == 0.0


def test_resumir_hls_los_intervalos_usan_la_misma_fecha_fija_que_sentinel():
    r = ingesta.resumir_hls([_lectura("2026-10-09", 100, 90, 0.4)])
    assert (r[0]["inicio"] - ingesta._EPOCA_NDVI).days % ingesta.INTERVALO_NDVI_DIAS == 0


def test_hls_sin_token_es_sin_configurar(monkeypatch):
    monkeypatch.delenv("EARTHDATA_TOKEN", raising=False)
    assert ingesta._sin_configurar("hls_ndvi")
    monkeypatch.setenv("EARTHDATA_TOKEN", "x")
    assert not ingesta._sin_configurar("hls_ndvi")


def test_hls_es_una_fuente_diaria_registrada():
    assert "hls_ndvi" in ingesta.FUENTES and "hls_ndvi" in ingesta.FUENTES_DIARIAS
    assert "hls_ndvi" in ingesta._INGESTAS and "hls_ndvi" not in ingesta.FUENTES_DE_SITIO


# ---------------------------------------------------------------- lectura
class _Sesion:
    def __init__(self, filas):
        self.filas = filas

    async def execute(self, sentencia, parametros=None):
        return self

    def mappings(self):
        return self

    def all(self):
        return self.filas


def _fila(inicio, ndvi=None, visible=None, ndvi_hls=None, visible_hls=None):
    return {"periodo_inicio": inicio, "periodo_fin": date(inicio.year, inicio.month, inicio.day + 4),
            "ndvi": ndvi, "visible": visible, "ndvi_hls": ndvi_hls, "visible_hls": visible_hls}


def test_leer_ndvi_prefiere_sentinel_y_completa_con_hls():
    filas = [_fila(date(2026, 10, 5), 0.5, 0.95, 0.4, 0.95),      # las dos: manda Sentinel-2
             _fila(date(2026, 10, 10), None, 0.0, 0.42, 0.9),     # Sentinel-2 no vio nada: entra HLS
             _fila(date(2026, 10, 15), 0.6, 0.3, 0.45, 0.85),     # Sentinel-2 vio poco: entra HLS
             _fila(date(2026, 10, 20), None, None, 0.3, 0.5)]     # HLS vio muy poco: no cuenta
    obs = asyncio.run(rc.leer_ndvi(_Sesion(filas), 1, date(2026, 10, 1)))
    assert [(o["ndvi"], o["fuente"]) for o in obs] == [(0.5, "Sentinel-2"), (0.42, "HLS (NASA)"), (0.45, "HLS (NASA)")]
    assert obs[0]["fecha"] == date(2026, 10, 7)


def test_leer_ndvi_solo_con_hls_cuando_no_hay_copernicus():
    obs = asyncio.run(rc.leer_ndvi(_Sesion([_fila(date(2026, 10, 5), ndvi_hls=0.41, visible_hls=0.9)]), 1, date(2026, 10, 1)))
    assert [(o["ndvi"], o["fuente"]) for o in obs] == [(0.41, "HLS (NASA)")]


# ---------------------------------------------------------------- imagen por celda
def _pixeles():
    """Una ventana de 4x4 pixeles de 30 m en EPSG:4326 (grados), con una esquina nublada (NaN)."""
    from rasterio.transform import from_origin
    ndvi = np.array([[0.2, 0.2, 0.8, 0.8],
                     [0.2, 0.2, 0.8, 0.8],
                     [0.4, 0.4, np.nan, np.nan],
                     [0.4, 0.4, np.nan, np.nan]])
    return {"fecha": "2026-11-10", "sensor": "HLSS30", "ndvi": ndvi, "dentro": np.ones((4, 4), dtype=bool),
            "transform": from_origin(-73.0, -42.0, 0.001, 0.001), "crs": "EPSG:4326"}


def _celda(i, j, x0, y0, x1, y1):
    return {"i": i, "j": j, "geometria": {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}}


def test_visible_de_cuenta_los_pixeles_sin_nube():
    assert hls.visible_de(_pixeles()) == 0.75


def test_ndvi_por_celda_promedia_los_pixeles_de_cada_celda():
    celdas = [_celda(0, 0, -73.000, -42.002, -72.998, -42.000),   # arriba a la izquierda: 0.2
              _celda(1, 0, -72.998, -42.002, -72.996, -42.000),   # arriba a la derecha: 0.8
              _celda(0, 1, -73.000, -42.004, -72.998, -42.002),   # abajo a la izquierda: 0.4
              _celda(1, 1, -72.998, -42.004, -72.996, -42.002)]   # abajo a la derecha: todo nublado
    r = hls.ndvi_por_celda(_pixeles(), celdas)
    assert round(r[(0, 0)][0], 3) == 0.2 and r[(0, 0)][1] == 1.0
    assert round(r[(1, 0)][0], 3) == 0.8
    assert round(r[(0, 1)][0], 3) == 0.4
    assert r[(1, 1)] == (None, 0.0)


def test_celda_mas_chica_que_un_pixel_usa_el_pixel_que_toca():
    r = hls.ndvi_por_celda(_pixeles(), [_celda(0, 0, -72.9995, -42.0005, -72.9993, -42.0003)])
    assert round(r[(0, 0)][0], 3) == 0.2


def test_hls_celdas_es_una_fuente_de_ingesta_con_su_capa_de_mapa():
    assert "hls_celdas" in ingesta.FUENTES and "hls_celdas" in ingesta._INGESTAS
    assert rc.CAPAS_MAPA["ndvi_hls"]["fuente_ingesta"] == "hls_celdas"
    assert ingesta._sin_configurar("hls_celdas") == ingesta._sin_configurar("hls_ndvi")
