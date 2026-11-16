"""El tiempo de una comuna sin registro (services.zonas): resumen del pronostico y memoria corta."""
from services import zonas

CRUDO = {
    "current": {"temperature_2m": 11.4, "relative_humidity_2m": 88, "wind_speed_10m": 21.5, "weather_code": 3},
    "daily": {"time": ["2026-11-16", "2026-11-17", "2026-11-18"], "temperature_2m_min": [4.0, -0.5, -2.0],
              "precipitation_sum": [6.2, 0.0, 0.0], "weather_code": [61, 3, 1]},
}


def test_resume_el_tiempo_de_ahora_y_la_primera_helada():
    r = zonas.resumir(CRUDO)
    assert r["temperatura_c"] == 11.4 and r["humedad_relativa"] == 88 and r["viento_kmh"] == 21.5
    assert r["lluvia_hoy_mm"] == 6.2 and r["hoy"] == "2026-11-16"
    assert r["primera_helada"] == "2026-11-17"


def test_sin_minimas_bajo_cero_no_hay_helada():
    crudo = {**CRUDO, "daily": {**CRUDO["daily"], "temperature_2m_min": [4.0, 3.0, None]}}
    assert zonas.resumir(crudo)["primera_helada"] is None


def test_reusa_la_consulta_dentro_de_la_vigencia(monkeypatch):
    zonas._cache.clear()
    llamadas = []
    monkeypatch.setattr(zonas.cliente_openmeteo, "consultar_hoy", lambda lat, lon: llamadas.append((lat, lon)) or CRUDO)
    zonas.clima_de_zona("Quemchi", ahora=1000.0)
    zonas.clima_de_zona("Quemchi", ahora=1000.0 + zonas.VIGENCIA_S - 1)
    assert len(llamadas) == 1
    zonas.clima_de_zona("Quemchi", ahora=1000.0 + zonas.VIGENCIA_S + 1)
    assert len(llamadas) == 2
