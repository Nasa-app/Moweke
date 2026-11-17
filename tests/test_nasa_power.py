"""NASA POWER: humedad del suelo y radiacion mensual (services/cliente_power.py, repositorio_clima.py, ingesta_predio.py)."""
import asyncio
from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

import main
import services.cliente_power as cp
import services.ingesta_predio as ingesta
import services.repositorio_clima as rc


def correr(corrutina):
    return asyncio.run(corrutina)


# ---------------------------------------------------------------- cliente
def _respuesta(parametros):
    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return {"properties": {"parameter": parametros}}
    return R()


def test_consultar_power_trae_la_humedad_del_suelo_y_limpia_los_dias_sin_dato(monkeypatch):
    dias = {"20261110": 0.8, "20261111": -999.0}
    monkeypatch.setattr(cp.requests, "get", lambda *a, **k: _respuesta({
        "T2M_MIN": dias, "T2M_MAX": dias, "PRECTOTCORR": dias, "RH2M": dias, "ALLSKY_SFC_SW_DWN": dias,
        "GWETROOT": dias, "GWETTOP": {"20261110": 0.7, "20261111": 0.71}}))
    df = cp.consultar_power(-42.47, -73.77, "2026-11-10", "2026-11-11")
    assert {"humedad_suelo_raiz", "humedad_suelo_superficie"} <= set(df.columns)
    assert df["humedad_suelo_raiz"].iloc[0] == 0.8 and pd.isna(df["humedad_suelo_raiz"].iloc[1])   # -999 no es un dato
    assert df["humedad_suelo_superficie"].iloc[1] == 0.71


def test_el_pedido_a_power_incluye_los_parametros_de_humedad_del_suelo(monkeypatch):
    visto = {}

    def falso(url, params=None, timeout=None):
        visto.update(params)
        return _respuesta({"T2M_MIN": {"20261110": 1.0}, "T2M_MAX": {"20261110": 9.0}, "PRECTOTCORR": {"20261110": 0.0},
                           "RH2M": {"20261110": 80.0}, "ALLSKY_SFC_SW_DWN": {"20261110": 20.0},
                           "GWETROOT": {"20261110": 0.8}, "GWETTOP": {"20261110": 0.7}})
    monkeypatch.setattr(cp.requests, "get", falso)
    cp.consultar_power(-42.47, -73.77, "2026-11-10", "2026-11-10")
    assert {"GWETROOT", "GWETTOP"} <= set(visto["parameters"].split(","))


def test_la_radiacion_mensual_se_pasa_de_mj_a_kwh_y_un_mes_sin_dato_queda_en_none():
    clima = pd.DataFrame({"radiacion": [36.0, 18.0, -999.0] + [7.2] * 9}, index=cp.MESES)
    ghi = cp.ghi_mensual_kwh(clima)
    assert ghi[0] == pytest.approx(10.0) and ghi[1] == pytest.approx(5.0) and ghi[2] is None
    assert ghi[11] == pytest.approx(2.0) and len(ghi) == 12


# ---------------------------------------------------------------- ingesta
def test_las_filas_diarias_de_power_guardan_la_humedad_del_suelo():
    clima = pd.DataFrame({"tmin": [3.0], "tmax": [11.0], "lluvia": [0.0], "rh": [80.0], "radiacion": [20.0],
                          "humedad_suelo_raiz": [0.83], "humedad_suelo_superficie": [float("nan")]},
                         index=pd.to_datetime(["2026-11-10"]))
    filas = ingesta._filas_diarias(5, clima, "power", "0.5deg_~55km", "POWER_daily_ag")
    capas = {f["capa"]: f["valor"] for f in filas}
    assert capas["power_humedad_suelo_raiz"] == 0.83
    assert "power_humedad_suelo_superficie" not in capas          # el NaN se salta, como el resto


def test_las_filas_diarias_de_open_meteo_no_exigen_columnas_que_no_trae():
    clima = pd.DataFrame({"tmin": [3.0], "tmax": [11.0], "lluvia": [0.0], "rh": [80.0], "radiacion": [20.0]},
                         index=pd.to_datetime(["2026-11-10"]))
    capas = {f["capa"] for f in ingesta._filas_diarias(5, clima, "openmeteo", "celda_de_modelo", "open-meteo")}
    assert capas == {f"openmeteo_{c}" for c in ("tmin", "tmax", "lluvia", "rh", "radiacion")}


class SesionFalsa:
    def __init__(self, *respuestas):
        self.respuestas, self.sentencias = list(respuestas), []

    async def execute(self, sentencia, parametros=None):
        self.sentencias.append(str(sentencia))
        return self.respuestas.pop(0)


class Resultado:
    def __init__(self, filas=(), escalar=None):
        self._filas, self._escalar = list(filas), escalar

    def mappings(self):
        return self

    def all(self):
        return self._filas

    def scalar_one(self):
        return self._escalar

    def scalar(self):
        return self._escalar


@pytest.fixture
def guardado(monkeypatch):
    filas = []

    async def guardar(session, nuevas):
        filas.extend(nuevas)
    monkeypatch.setattr(ingesta, "guardar_consultas_grilla", guardar)
    return filas


def _climatologia():
    return pd.DataFrame({"radiacion": [36.0] * 12}, index=cp.MESES)


def test_la_radiacion_mensual_se_guarda_una_vez_con_las_doce_capas(monkeypatch, guardado):
    monkeypatch.setattr(cp, "consultar_climatologia", lambda lat, lon, timeout=20: _climatologia())
    correr(ingesta._power_radiacion_mensual(SesionFalsa(Resultado(escalar=0)), 5, -42.1439, -73.4751))
    assert [f["capa"] for f in guardado] == list(rc.CAPAS_GHI_POWER)
    assert all(f["valor"] == pytest.approx(10.0) for f in guardado)
    assert guardado[0]["periodo_inicio"] == date(2001, 1, 1) and guardado[0]["periodo_fin"] == date(2025, 12, 31)


def test_si_la_radiacion_ya_esta_guardada_no_se_vuelve_a_pedir(monkeypatch, guardado):
    def no_debe_llamarse(*a, **k):
        raise AssertionError("pidio la climatologia otra vez")
    monkeypatch.setattr(cp, "consultar_climatologia", no_debe_llamarse)
    correr(ingesta._power_radiacion_mensual(SesionFalsa(Resultado(escalar=12)), 5, -42.1, -73.4))
    assert guardado == []


def test_si_power_falla_la_ingesta_diaria_sigue(monkeypatch, guardado):
    def falla(*a, **k):
        raise RuntimeError("POWER caido")
    monkeypatch.setattr(cp, "consultar_climatologia", falla)
    correr(ingesta._power_radiacion_mensual(SesionFalsa(Resultado(escalar=0)), 5, -42.1, -73.4))   # no levanta
    assert guardado == []


# ---------------------------------------------------------------- lectura para el ranking
def _sitio(capas):
    """leer_sitio hace tres consultas: capas fijas, clima diario y altitud del DEM."""
    filas = [{"capa": c, "valor": v} for c, v in capas.items()]
    return correr(rc.leer_sitio(SesionFalsa(Resultado(filas), Resultado([]), Resultado(escalar=None)), 5, date(2026, 11, 15)))


def test_el_ranking_usa_la_radiacion_de_power_y_dice_de_donde_sale():
    power = {c: 5.0 for c in rc.CAPAS_GHI_POWER}
    explorador = {c: 3.0 for c in rc.CAPAS_GHI_MENSUAL}
    sitio = _sitio({**power, **explorador})
    assert sitio["ghi_mensual"] == [5.0] * 12 and sitio["fuente_radiacion"] == rc.FUENTE_RADIACION_POWER


def test_sin_power_cae_al_explorador_solar():
    sitio = _sitio({c: 3.0 for c in rc.CAPAS_GHI_MENSUAL})
    assert sitio["ghi_mensual"] == [3.0] * 12 and sitio["fuente_radiacion"] == rc.FUENTE_RADIACION_EXPLORADOR


def test_con_power_incompleto_no_se_mezclan_las_fuentes():
    parcial = {c: 5.0 for c in rc.CAPAS_GHI_POWER[:11]}           # falta un mes
    sitio = _sitio({**parcial, **{c: 3.0 for c in rc.CAPAS_GHI_MENSUAL}})
    assert sitio["ghi_mensual"] == [3.0] * 12 and sitio["fuente_radiacion"] == rc.FUENTE_RADIACION_EXPLORADOR


def test_sin_ninguna_fuente_de_radiacion_queda_en_none():
    sitio = _sitio({"soilgrids_ph": 5.5})
    assert sitio["ghi_mensual"] is None and sitio["fuente_radiacion"] is None


# ---------------------------------------------------------------- humedad del suelo para el riego
def _f(capa, dia, valor):
    return {"capa": capa, "fecha": date(2026, 11, dia), "valor": valor}


def test_la_humedad_del_suelo_usa_el_dato_mas_reciente_y_resume_la_semana():
    filas = [_f("power_humedad_suelo_raiz", d, 0.80 + d / 1000) for d in range(1, 11)]
    filas += [_f("power_humedad_suelo_superficie", 10, 0.71)]
    r = rc.resumir_humedad_suelo(filas)
    assert r["fecha"] == "2026-11-10" and r["zona_raices"] == 0.81 and r["superficie"] == 0.71
    assert [d["fecha"] for d in r["ultimos_dias"]] == [f"2026-11-{d:02d}" for d in range(4, 11)]
    assert r["fuente"] == "NASA POWER" and r["resolucion_km"] == 50


def test_la_superficie_queda_en_none_si_no_hay_dato_ese_dia():
    filas = [_f("power_humedad_suelo_raiz", 9, 0.8), _f("power_humedad_suelo_superficie", 8, 0.7)]
    assert rc.resumir_humedad_suelo(filas)["superficie"] is None


def test_sin_humedad_del_suelo_no_se_inventa_nada():
    assert rc.resumir_humedad_suelo([]) is None
    assert rc.resumir_humedad_suelo([_f("power_humedad_suelo_superficie", 9, 0.7)]) is None
    sesion = SesionFalsa(Resultado([]))
    assert correr(rc.leer_humedad_suelo_nasa(sesion, 5, date(2026, 11, 15))) is None


def test_el_endpoint_usa_el_lector_de_humedad():
    assert main.leer_humedad_suelo_nasa is rc.leer_humedad_suelo_nasa


# ---------------------------------------------------------------- clima de la ventana: CR2MET o POWER
def _filas_clima(prefijo, desde, hasta, tmin=5.0, tmax=15.0, lluvia=2.0):
    dias = pd.date_range(desde, hasta, freq="D")
    return [{"fecha": d.date(), "capa": f"{prefijo}_{v}", "valor": x}
            for d in dias for v, x in (("tmin", tmin), ("tmax", tmax), ("lluvia", lluvia))]


def _sitio_clima(filas_clima):
    return correr(rc.leer_sitio(SesionFalsa(Resultado([]), Resultado(filas_clima), Resultado(escalar=None)),
                                5, date(2026, 11, 15)))


def test_fuera_de_chile_el_clima_de_la_ventana_sale_de_power():
    sitio = _sitio_clima(_filas_clima("power", "2025-11-01", "2026-10-31"))
    assert sitio["fuente_clima"] == "power"
    assert len(sitio["clima"]) == 365
    assert sitio["clima"].notna().all().all()


def test_con_cr2met_completo_el_clima_no_cambia():
    filas = _filas_clima("cr2met", "2025-11-01", "2026-10-31", tmin=3.0) \
        + _filas_clima("power", "2025-11-01", "2026-10-31", tmin=6.0)
    sitio = _sitio_clima(filas)
    assert sitio["fuente_clima"] == "cr2met"
    assert (sitio["clima"]["tmin"] == 3.0).all()


def test_sin_ningun_clima_no_hay_fuente():
    sitio = _sitio_clima([])
    assert sitio["clima"] is None and sitio["fuente_clima"] is None


def test_cr2met_parcial_rellena_con_power_y_se_marca_power():
    filas = _filas_clima("cr2met", "2025-11-01", "2026-03-31") + _filas_clima("power", "2025-11-01", "2026-10-31")
    sitio = _sitio_clima(filas)
    assert sitio["fuente_clima"] == "power"
    assert len(sitio["clima"]) == 365


def test_el_perimetro_fuera_de_chile_se_acepta():
    anillo = [[-123.16, 45.0], [-123.15, 45.0], [-123.15, 45.01], [-123.16, 45.01]]
    assert '"Polygon"' in main._validar_perimetro({"type": "Polygon", "coordinates": [anillo]})


@pytest.mark.parametrize("lon,lat", [(-123.15, 95.0), (-200.0, 45.0)])
def test_el_perimetro_con_coordenadas_fuera_de_rango_se_rechaza(lon, lat):
    anillo = [[lon, lat], [lon + 0.01, lat], [lon + 0.01, lat - 0.01]]
    with pytest.raises(main.HTTPException) as e:
        main._validar_perimetro({"type": "Polygon", "coordinates": [anillo]})
    assert "fuera de rango" in e.value.detail


@pytest.mark.parametrize("lat,lon", [(45.0, 179.9), (45.0, -179.9), (85.0, 10.0)])
def test_un_punto_en_el_antimeridiano_o_los_polos_se_rechaza_antes_de_tocar_la_base(lat, lon):
    nuevo = main.ParcelaNueva(lat=lat, lon=lon, hectareas=1.0)
    pedido = SimpleNamespace(headers={}, client=SimpleNamespace(host="10.9.9.9"))
    with pytest.raises(main.HTTPException) as e:
        correr(main.crear_parcela(nuevo, SimpleNamespace(), pedido, None, {"id": 1, "nombre": "x", "rol": "agricultor"}))
    assert e.value.status_code == 422
