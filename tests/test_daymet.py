"""Daymet como referencia de sesgo fuera de Chile (services/cliente_daymet.py, repositorio_clima.py, ingesta_predio.py)."""
import asyncio
from datetime import date

import numpy as np
import pandas as pd
import pytest
import requests

import services.cliente_daymet as cd
import services.ingesta_predio as ingesta
import services.repositorio_clima as rc


def correr(corrutina):
    return asyncio.run(corrutina)


ENCABEZADO = ("Latitude: 45.0  Longitude: -123.15\nX & Y on Lambert Conformal Conic: -1718762.59 504911.24\nTile: 12089\n"
              "Elevation: 221 meters\nAll years; all variables; Daymet Software Version 4.0\nHow to cite: Thornton; M.M.\n")
CABECERA = "year,yday,prcp (mm/day),tmax (deg c),tmin (deg c)\n"


class RespuestaFalsa:
    def __init__(self, texto="", status=200):
        self.status_code, self.text, self._cuerpo = status, texto, texto.encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def iter_content(self, n):
        yield self._cuerpo

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)


@pytest.fixture
def pedidos(monkeypatch):
    """Registra los pedidos a requests.get y responde con lo que cada prueba ponga en `pedidos.respuesta`."""
    class Registro(list):
        respuesta = RespuestaFalsa(ENCABEZADO + CABECERA)

    registro = Registro()

    def falso(url, **kwargs):
        registro.append((url, kwargs))
        return registro.respuesta
    monkeypatch.setattr(cd.requests, "get", falso)
    return registro


# ---------------------------------------------------------------- cliente
def test_el_cliente_lee_el_csv_y_pone_nan_en_el_31_de_diciembre_de_un_ano_bisiesto(pedidos):
    # 2020 es bisiesto: yday 60 es el 29 de febrero y yday 365 es el 30 de diciembre; el 31 no existe en Daymet.
    pedidos.respuesta = RespuestaFalsa(ENCABEZADO + CABECERA +
                                       "2020,60,1.50,12.00,3.00\n2020,364,0.00,8.00,-2.50\n2020,365,2.00,9.00,-1.00\n")
    df = cd.consultar_daymet(45.0, -123.15, "2020-12-29", "2020-12-31")
    assert list(df.columns) == ["tmin", "tmax", "lluvia"]
    assert list(df.index) == list(pd.date_range("2020-12-29", "2020-12-31"))
    assert df.loc["2020-12-29"].tolist() == [-2.5, 8.0, 0.0]
    assert df.loc["2020-12-30"].tolist() == [-1.0, 9.0, 2.0]
    assert df.loc["2020-12-31"].isna().all()          # NaN, no un centinela ni un cero


def test_el_29_de_febrero_se_ubica_en_su_fecha(pedidos):
    pedidos.respuesta = RespuestaFalsa(ENCABEZADO + CABECERA + "2020,59,0.0,10.0,1.0\n2020,60,0.0,11.0,2.0\n2020,61,0.0,12.0,3.0\n")
    df = cd.consultar_daymet(45.0, -123.15, "2020-02-28", "2020-03-01")
    assert df["tmin"].tolist() == [1.0, 2.0, 3.0]
    assert df.index[1] == pd.Timestamp("2020-02-29")


def test_un_relleno_de_daymet_no_pasa_como_dato(pedidos):
    pedidos.respuesta = RespuestaFalsa(ENCABEZADO + CABECERA + "2021,1,-9999.0,-9999.0,-9999.0\n2021,2,0.0,9.0,2.0\n")
    df = cd.consultar_daymet(45.0, -123.15, "2021-01-01", "2021-01-02")
    assert df.iloc[0].isna().all() and df.iloc[1].tolist() == [2.0, 9.0, 0.0]


def test_un_periodo_sin_publicar_devuelve_todo_el_registro_y_se_filtra_por_fecha(pedidos):
    # Daymet responde con TODO el registro cuando se pide un ano que todavia no publico: no se cuela en la serie.
    pedidos.respuesta = RespuestaFalsa(ENCABEZADO + CABECERA + "1980,1,0.0,9.0,1.0\n2025,365,0.0,8.0,0.5\n")
    df = cd.consultar_daymet(45.0, -123.15, "2026-01-01", "2026-01-03")
    assert len(df) == 3 and df.isna().all().all()


def test_fuera_de_cobertura_devuelve_vacio_sin_error(pedidos):
    pedidos.respuesta = RespuestaFalsa('{"message":"Daymet Tile was not found with input lat and lon: /api/data?lat=45.0"}', 400)
    df = cd.consultar_daymet(45.0, -127.0, "2024-01-01", "2024-01-31")       # mar frente a Oregon
    assert df.empty and list(df.columns) == ["tmin", "tmax", "lluvia"]


@pytest.mark.parametrize("lat,lon", [(-42.45, -73.78), (51.5, 0.0), (-33.4, -70.6), (35.7, 139.7)])
def test_chile_europa_y_asia_ni_salen_a_la_red(pedidos, lat, lon):
    assert cd.consultar_daymet(lat, lon, "2024-01-01", "2024-01-31").empty
    assert pedidos == []


def test_el_pedido_manda_solo_el_punto_redondeado_con_timeout_y_sin_redirecciones(pedidos):
    pedidos.respuesta = RespuestaFalsa(ENCABEZADO + CABECERA + "2024,1,0.0,9.0,1.0\n")
    cd.consultar_daymet(45.004321, -123.151234, "2024-01-01", "2024-01-01")
    url, kwargs = pedidos[0]
    assert url.startswith("https://daymet.ornl.gov/")
    assert kwargs["allow_redirects"] is False and kwargs["timeout"] > 0
    assert kwargs["params"] == {"lat": "45.00", "lon": "-123.15", "vars": "tmin,tmax,prcp", "format": "csv", "years": "2024"}
    assert "headers" not in kwargs and "cookies" not in kwargs and "auth" not in kwargs


def test_una_redireccion_no_se_sigue(pedidos):
    pedidos.respuesta = RespuestaFalsa("", 302)
    with pytest.raises(requests.HTTPError):
        cd.consultar_daymet(45.0, -123.15, "2024-01-01", "2024-01-02")


def test_un_error_del_servidor_se_levanta(pedidos):
    pedidos.respuesta = RespuestaFalsa("Internal Server Error", 500)
    with pytest.raises(requests.HTTPError):
        cd.consultar_daymet(45.0, -123.15, "2024-01-01", "2024-01-02")


def test_otro_400_no_se_toma_por_falta_de_cobertura(pedidos):
    pedidos.respuesta = RespuestaFalsa('{"message":"invalid parameter"}', 400)
    with pytest.raises(requests.HTTPError):
        cd.consultar_daymet(45.0, -123.15, "2024-01-01", "2024-01-02")


def test_unidades_inesperadas_se_rechazan(pedidos):
    pedidos.respuesta = RespuestaFalsa(ENCABEZADO + "year,yday,prcp (in/day),tmax (deg c),tmin (deg c)\n2024,1,0,1,1\n")
    with pytest.raises(ValueError):
        cd.consultar_daymet(45.0, -123.15, "2024-01-01", "2024-01-01")


def test_una_respuesta_gigante_se_corta(pedidos):
    pedidos.respuesta = RespuestaFalsa("x" * (cd._BYTES_MAX + 10))
    with pytest.raises(ValueError):
        cd.consultar_daymet(45.0, -123.15, "2024-01-01", "2024-01-01")


# ---------------------------------------------------------------- eleccion de la referencia
def _serie(dias, tmin=2.0, tmax=10.0, lluvia=1.0, desde="2025-01-01"):
    idx = pd.date_range(desde, periods=dias, freq="D")
    return pd.DataFrame({"tmin": tmin, "tmax": tmax, "lluvia": lluvia}, index=idx)


def test_cr2met_manda_sobre_daymet():
    origen, ref = rc.elegir_referencia(_serie(60, tmin=1.0), _serie(60, tmin=5.0))
    assert origen == "cr2met" and (ref["tmin"] == 1.0).all()


def test_sin_cr2met_suficiente_manda_daymet():
    assert rc.elegir_referencia(_serie(5), _serie(60))[0] == "daymet"
    assert rc.elegir_referencia(_serie(0), _serie(60))[0] == "daymet"


def test_sin_ninguna_referencia_no_se_corrige():
    assert rc.elegir_referencia(_serie(0), _serie(10)) == (None, None)


# ---------------------------------------------------------------- leer_sitio: Chile no cambia, fuera de Chile usa Daymet
class SesionFalsa:
    def __init__(self, *respuestas):
        self.respuestas, self.sentencias, self.parametros = list(respuestas), [], []

    async def execute(self, sentencia, parametros=None):
        self.sentencias.append(str(sentencia))
        self.parametros.append(parametros)
        return self.respuestas.pop(0)


class Resultado:
    def __init__(self, filas=(), escalar=None):
        self._filas, self._escalar = list(filas), escalar

    def mappings(self):
        return self

    def all(self):
        return self._filas

    def scalar(self):
        return self._escalar


def _filas(prefijo, desde, hasta, **valores):
    v = {"tmin": 5.0, "tmax": 15.0, "lluvia": 2.0, **valores}
    return [{"fecha": d.date(), "capa": f"{prefijo}_{k}", "valor": x}
            for d in pd.date_range(desde, hasta, freq="D") for k, x in v.items()]


def _sitio(filas_clima):
    sesion = SesionFalsa(Resultado([]), Resultado(filas_clima), Resultado(escalar=None))
    return correr(rc.leer_sitio(sesion, 5, date(2026, 11, 15))), sesion


def test_fuera_de_chile_con_daymet_power_se_corrige_y_la_fuente_lo_dice():
    # POWER 2,0 C mas calido que Daymet durante los tres anos de traslape; la ventana es nov-2025 a oct-2026.
    filas = _filas("power", "2023-01-01", "2026-10-31", tmin=5.0) + _filas("daymet", "2023-01-01", "2025-12-31", tmin=3.0)
    sitio, sesion = _sitio(filas)
    assert sitio["fuente_clima"] == rc.FUENTE_CLIMA_POWER_DAYMET == "power_daymet"
    assert len(sitio["clima"]) == 365 and sitio["clima"].index[0] == pd.Timestamp("2025-11-01")   # solo la ventana
    assert sitio["clima"]["tmin"].round(2).eq(3.0).all()
    assert min(p["inicio"] for p in sesion.parametros[1:2]) == date(2023, 1, 1)                  # lee el traslape


def test_con_daymet_sin_traslape_suficiente_queda_power_sin_corregir():
    filas = _filas("power", "2025-11-01", "2026-10-31", tmin=5.0) + _filas("daymet", "2025-12-01", "2025-12-10", tmin=3.0)
    sitio, _ = _sitio(filas)
    assert sitio["fuente_clima"] == "power" and (sitio["clima"]["tmin"] == 5.0).all()


def test_en_chile_cr2met_manda_y_daymet_no_cambia_nada():
    ventana = ("2025-11-01", "2026-10-31")
    solo_cr2met = _filas("cr2met", *ventana, tmin=3.0) + _filas("power", *ventana, tmin=6.0)
    con_daymet = solo_cr2met + _filas("daymet", "2023-01-01", "2025-12-31", tmin=-9.0)
    (a, _), (b, _) = _sitio(solo_cr2met), _sitio(con_daymet)
    assert a["fuente_clima"] == b["fuente_clima"] == "cr2met"
    pd.testing.assert_frame_equal(a["clima"], b["clima"])


def test_en_chile_con_power_anterior_a_la_ventana_la_correccion_es_la_de_siempre():
    # Filas de POWER anteriores a la ventana (un predio viejo) no entran a medir el sesgo contra CR2MET.
    ventana = ("2025-11-01", "2026-10-31")
    base = _filas("cr2met", *ventana, tmin=3.0) + _filas("power", *ventana, tmin=6.0)
    con_viejo = base + _filas("power", "2024-01-01", "2025-10-31", tmin=40.0)
    (a, _), (b, _) = _sitio(base), _sitio(con_viejo)
    pd.testing.assert_frame_equal(a["clima"], b["clima"])


# ---------------------------------------------------------------- correccion de la historia
def _historia(anios=12, sesgo_frio=-1.5, semilla=1):
    """Daymet sintetico y un ERA5 con la minima mas fria y mas dispersa: lo que aplana una celda grande."""
    rng = np.random.default_rng(semilla)
    idx = pd.date_range("2000-01-01", periods=int(anios * 365.25), freq="D")
    base = 5.0 + 8.0 * np.sin(2 * np.pi * (idx.dayofyear - 110) / 365.25)
    ruido = rng.normal(0, 3.0, len(idx))
    daymet = pd.DataFrame({"tmin": base + ruido, "tmax": base + 8 + ruido, "lluvia": rng.gamma(0.5, 4.0, len(idx))}, index=idx)
    era5 = pd.DataFrame({"tmin": base + 1.4 * ruido + sesgo_frio, "tmax": base + 8 + ruido,
                         "lluvia": daymet["lluvia"].to_numpy() * 0.8}, index=idx)
    return daymet, era5


def test_los_cuantiles_devuelven_los_extremos_que_la_media_no():
    daymet, era5 = _historia()
    corregido, metodo = rc.corregir_historia_contra_daymet(daymet, era5)
    assert metodo == "cuantiles"
    ref = (daymet["tmin"] < 0).sum()
    media, _ = rc.corregir_contra_referencia(daymet, era5)
    assert abs((corregido["tmin"] < 0).sum() - ref) < abs((media["tmin"] < 0).sum() - ref)
    assert abs((corregido["tmin"] < -5).sum() - (daymet["tmin"] < -5).sum()) <= 0.1 * (daymet["tmin"] < -5).sum()
    assert (corregido["tmin"] <= corregido["tmax"]).all() and corregido.notna().all().all()


def test_con_poco_traslape_la_historia_cae_a_la_media_mensual():
    daymet, era5 = _historia(anios=3)
    _, metodo = rc.corregir_historia_contra_daymet(daymet, era5)
    assert metodo == "media_mensual"


def test_sin_traslape_la_historia_no_se_corrige():
    daymet, era5 = _historia(anios=1)
    corregido, metodo = rc.corregir_historia_contra_daymet(daymet.iloc[:10], era5)
    assert metodo is None
    pd.testing.assert_frame_equal(corregido, era5[["tmin", "tmax", "lluvia"]])


# ---------------------------------------------------------------- ingesta
@pytest.fixture
def guardado(monkeypatch):
    filas = []

    async def guardar(session, nuevas):
        filas.extend(nuevas)
    monkeypatch.setattr(ingesta, "guardar_consultas_grilla", guardar)
    return filas


def test_la_ingesta_de_daymet_guarda_tres_capas_y_se_salta_los_nan(monkeypatch, guardado):
    hoy = date.today()
    visto = {}

    def falso(lat, lon, inicio, fin, timeout=30):
        visto.update(lat=lat, lon=lon, inicio=inicio)
        df = pd.DataFrame({"tmin": [1.0, float("nan")], "tmax": [9.0, float("nan")], "lluvia": [0.0, float("nan")]},
                          index=pd.to_datetime(["2025-12-30", "2025-12-31"]))
        return df
    monkeypatch.setattr(ingesta.cliente_daymet, "consultar_daymet", falso)
    detalle = correr(ingesta._daymet(object(), 5, 45.004, -123.151))
    assert detalle is None
    assert {f["capa"] for f in guardado} == {"daymet_tmin", "daymet_tmax", "daymet_lluvia"} and len(guardado) == 3
    assert (visto["lat"], visto["lon"]) == (45.0, -123.15)               # el punto sale redondeado a 0,01
    assert date.fromisoformat(visto["inicio"]) == rc.inicio_traslape_daymet(hoy)


def test_sin_cobertura_de_daymet_la_fuente_queda_sin_cobertura(monkeypatch, guardado):
    monkeypatch.setattr(ingesta.cliente_daymet, "consultar_daymet",
                        lambda *a, **k: pd.DataFrame(columns=["tmin", "tmax", "lluvia"]))
    assert correr(ingesta._daymet(object(), 5, -42.45, -73.78)) == "sin_cobertura"
    assert guardado == []


def test_daymet_corre_despues_de_cr2met_y_antes_de_la_historia():
    orden = list(ingesta.PRODUCTOS)
    assert orden.index("cr2met") < orden.index("daymet") < orden.index("clima_historico")
    assert "daymet" in ingesta._INGESTAS and "daymet" in ingesta.FUENTES_DE_SITIO


def _era5_sintetico(hoy):
    idx = pd.date_range("1991-01-01", f"{hoy.year - 1}-12-31", freq="D")
    base = 8.0 + 8.0 * np.sin(2 * np.pi * (idx.dayofyear - 110) / 365.25)
    era5 = pd.DataFrame({"tmin": base, "tmax": base + 8, "lluvia": 1.0, "et0_pm": 2.0, "radiacion": 15.0}, index=idx)
    return era5


class SesionHistoria:
    """_clima_historico lee de la base solo el CR2MET de la ventana."""
    def __init__(self, filas):
        self._filas = filas

    async def execute(self, sentencia, parametros=None):
        return Resultado(self._filas)


def _historia_ingestada(monkeypatch, filas_cr2met, daymet):
    hoy = date.today()
    guardada = {}

    async def guardar(session, id_parcela, anios, fuente, version):
        guardada.update(anios=anios, fuente=fuente)

    async def guardar_grilla(session, filas):
        pass
    monkeypatch.setattr(ingesta, "guardar_historia", guardar)
    monkeypatch.setattr(ingesta, "guardar_consultas_grilla", guardar_grilla)
    monkeypatch.setattr(ingesta.cliente_openmeteo, "consultar_historia", lambda *a, **k: _era5_sintetico(hoy))
    monkeypatch.setattr(ingesta.cliente_daymet, "consultar_daymet", daymet)
    return guardada


def test_la_historia_fuera_de_chile_se_corrige_con_daymet_y_la_fuente_lo_dice(monkeypatch):
    def daymet(lat, lon, inicio, fin, timeout=30):
        era5 = _era5_sintetico(date.today())
        out = era5[["tmin", "tmax", "lluvia"]].copy()
        out["tmin"] -= 2.0
        return out
    guardada = _historia_ingestada(monkeypatch, [], daymet)
    assert correr(ingesta._clima_historico(SesionHistoria([]), 5, 45.0, -123.15)) is None
    assert guardada["fuente"] == "era5_open_meteo_corregido_daymet"
    assert guardada["anios"][2000]["tmin"].mean() < _era5_sintetico(date.today()).loc["2000", "tmin"].mean() - 1.5


def test_la_historia_sin_cobertura_de_daymet_ni_cr2met_queda_sin_corregir(monkeypatch):
    guardada = _historia_ingestada(monkeypatch, [], lambda *a, **k: pd.DataFrame(columns=["tmin", "tmax", "lluvia"]))
    correr(ingesta._clima_historico(SesionHistoria([]), 5, 51.5, 0.0))
    assert guardada["fuente"] == "era5_open_meteo_sin_corregir"


def test_la_historia_en_chile_no_toca_daymet(monkeypatch):
    def no_debe_llamarse(*a, **k):
        raise AssertionError("llamo a Daymet teniendo CR2MET")
    hoy = date.today()
    inicio, fin = rc.ventana_clima(hoy)
    filas = [{"fecha": d.date(), "capa": f"cr2met_{k}", "valor": v}
             for d in pd.date_range(inicio, fin, freq="D") for k, v in (("tmin", 7.0), ("tmax", 15.0), ("lluvia", 1.0))]
    guardada = _historia_ingestada(monkeypatch, filas, no_debe_llamarse)
    correr(ingesta._clima_historico(SesionHistoria(filas), 5, -42.45, -73.78))
    assert guardada["fuente"] == "era5_open_meteo_corregido_cr2met"
