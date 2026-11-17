"""Referencia geografica del predio (services/cliente_geocodificacion.py)."""
import pytest

import services.cliente_geocodificacion as cg


class Respuesta:
    def __init__(self, cuerpo, status=200):
        self._cuerpo, self.status_code = cuerpo, status

    def json(self):
        return self._cuerpo

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def test_devuelve_pais_y_region_y_redondea_el_punto(monkeypatch):
    pedido = {}

    def falso(url, params, headers, timeout, allow_redirects):
        pedido.update(params=params, headers=headers)
        return Respuesta({"address": {"state": "Región de Los Lagos", "country": "Chile"}})

    monkeypatch.setattr(cg.requests, "get", falso)
    assert cg.referencia(-42.1537, -73.4821) == ("Chile", "Región de Los Lagos")
    assert (pedido["params"]["lat"], pedido["params"]["lon"]) == (-42.15, -73.48)
    assert pedido["headers"]["User-Agent"] == cg.USER_AGENT


def test_sin_region_usa_provincia_y_en_mar_abierto_no_hay_nada(monkeypatch):
    monkeypatch.setattr(cg.requests, "get", lambda *a, **k: Respuesta({"address": {"country": "Peru", "province": "Lima"}}))
    assert cg.referencia(-12.0, -77.0) == ("Peru", "Lima")
    monkeypatch.setattr(cg.requests, "get", lambda *a, **k: Respuesta({"error": "Unable to geocode"}))
    assert cg.referencia(0.0, -30.0) == (None, None)


def test_un_error_del_servicio_se_propaga(monkeypatch):
    monkeypatch.setattr(cg.requests, "get", lambda *a, **k: Respuesta({}, 503))
    with pytest.raises(RuntimeError):
        cg.referencia(-33.0, -70.0)
