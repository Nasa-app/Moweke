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


def test_clima_en_punto_redondea_y_comparte_la_consulta(monkeypatch):
    zonas._cache.clear()
    llamadas = []
    monkeypatch.setattr(zonas.cliente_openmeteo, "consultar_hoy", lambda lat, lon: llamadas.append((lat, lon)) or CRUDO)
    zonas.clima_en_punto(-42.14391, -73.47512, ahora=1000.0)
    zonas.clima_en_punto(-42.1401, -73.4799, ahora=1001.0)
    assert llamadas == [(-42.1, -73.5)]


def test_clima_en_punto_limita_la_memoria(monkeypatch):
    zonas._cache.clear()
    monkeypatch.setattr(zonas.cliente_openmeteo, "consultar_hoy", lambda lat, lon: CRUDO)
    monkeypatch.setattr(zonas, "MAX_PUNTOS_EN_MEMORIA", 3)
    for i in range(6):
        zonas.clima_en_punto(float(i), 0.0, ahora=1000.0)
    assert len(zonas._cache) == 3


def test_resumen_sitio_redondea_y_trae_lo_que_ve_tu_terreno():
    from datetime import date

    import main
    sitio = {"periodo_clima": (date(2025, 11, 1), date(2026, 10, 31)), "ghi_mensual": [4.123456] * 12,
             "fuente_radiacion": "NASA POWER", "ph": 5.8, "awc_mm": 90.0, "altitud_celda_m": 12.4}
    normales = {"tmedia": [10.123] * 12, "tmin_extrema": [-1.456] * 12, "lluvia": [100.0] * 12}
    r = main._resumen_sitio({"suelo": {"drenaje": None}}, sitio, normales, 55.6, 0.456, "franca")
    assert r["periodo_clima"] == ["2025-11-01", "2026-10-31"]
    assert r["temperatura_media_mensual"][0] == 10.12 and r["lluvia_anual_mm"] == 1200.0
    assert r["altitud_m"] == 56 and r["altitud_celda_m"] == 12 and r["correccion_temperatura_c"] == 0.46
    assert r["textura"] == "franca" and r["ph"] == 5.8
