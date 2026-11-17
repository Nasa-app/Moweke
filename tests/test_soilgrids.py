"""Reintento y timeout del cliente de SoilGrids (services/cliente_soilgrids.py)."""
import pytest
import requests

import services.cliente_soilgrids as cs

CAPAS = {"properties": {"layers": [
    {"name": n, "depths": [{"values": {"mean": v}}]}
    for n, v in (("phh2o", 62), ("clay", 200), ("sand", 400), ("silt", 400), ("soc", 116))]}}


class Respuesta:
    def __init__(self, status=200, cuerpo=CAPAS):
        self.status_code, self._cuerpo = status, cuerpo

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)

    def json(self):
        return self._cuerpo


@pytest.fixture
def pedidos(monkeypatch):
    class Registro(list):
        respuestas = []

    registro = Registro()

    def falso(url, params=None, timeout=None):
        registro.append(timeout)
        r = registro.respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(cs.requests, "get", falso)
    monkeypatch.setattr(cs, "ESPERA_REINTENTO_S", 0)
    return registro


def test_el_timeout_por_defecto_aguanta_los_40_segundos_de_isric(pedidos):
    pedidos.respuestas = [Respuesta()]
    assert cs.consultar_suelo(37.9, -4.8)["ph"] == 6.2
    assert pedidos == [90]


def test_un_timeout_se_reintenta_una_vez(pedidos):
    pedidos.respuestas = [requests.ReadTimeout("lento"), Respuesta()]
    assert cs.consultar_suelo(37.9, -4.8)["arcilla_pct"] == 20.0
    assert len(pedidos) == 2


def test_un_error_5xx_se_reintenta_una_vez(pedidos):
    pedidos.respuestas = [Respuesta(503), Respuesta()]
    assert cs.consultar_suelo(37.9, -4.8)["ph"] == 6.2


def test_dos_fallos_seguidos_levantan_y_no_hay_un_tercer_intento(pedidos):
    pedidos.respuestas = [requests.ReadTimeout("lento"), requests.ReadTimeout("lento"), Respuesta()]
    with pytest.raises(requests.ReadTimeout):
        cs.consultar_suelo(37.9, -4.8)
    assert len(pedidos) == 2


def test_un_error_4xx_no_se_reintenta(pedidos):
    pedidos.respuestas = [Respuesta(400), Respuesta()]
    with pytest.raises(requests.HTTPError):
        cs.consultar_suelo(37.9, -4.8)
    assert len(pedidos) == 1
