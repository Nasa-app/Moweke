"""
Cliente Open-Meteo v0.1 -- pronostico diario a 16 dias mas los ultimos dias ya
transcurridos, REST sin clave. Es la unica fuente del proyecto que mira hacia adelante:
POWER llega hasta hace ~3 dias y CR2MET hasta hace ~9 (medido el 14-nov-2026).

VERIFICADO POR EJECUCION contra Castro (-42.48, -73.76): 21 dias (5 pasados + 16 de
pronostico), sin nulos, mismas columnas y unidades que cliente_power.consultar_power()
(tmin/tmax en C, lluvia en mm, rh en %, radiacion en MJ/m2/dia) -- el motor consume
cualquiera de las dos sin cambios.

Tres advertencias reales:
  - NO es una fuente NASA ni una observacion: es salida de modelos numericos. Los dias
    "pasados" que devuelve son el analisis del modelo, no una medicion de estacion.
  - El uso gratuito es solo no comercial (condiciones de open-meteo.com); un despliegue
    comercial necesita su plan de pago.
  - Responde para la celda del modelo mas cercana, no para el punto exacto: en la prueba
    devolvio la celda (-42.4956, -73.7206) con elevacion 0 m para un punto a 76 msnm.
"""
from __future__ import annotations

import pandas as pd
import requests

URL_BASE = "https://api.open-meteo.com/v1/forecast"

MAPEO_COLUMNAS = {
    "temperature_2m_min": "tmin", "temperature_2m_max": "tmax", "precipitation_sum": "lluvia",
    "relative_humidity_2m_mean": "rh", "shortwave_radiation_sum": "radiacion",
}

DIAS_PRONOSTICO_MAX = 16  # tope real de la API


def consultar_pronostico(lat: float, lon: float, dias: int = DIAS_PRONOSTICO_MAX, dias_pasados: int = 5,
                          timeout: int = 20) -> pd.DataFrame:
    """Un dia por fila, desde `dias_pasados` atras hasta `dias` adelante (hoy incluido),
    en la zona horaria local del punto. Los valores que la API no tenga quedan en NaN."""
    params = {
        "latitude": lat, "longitude": lon, "daily": ",".join(MAPEO_COLUMNAS),
        "forecast_days": dias, "past_days": dias_pasados, "timezone": "auto",
    }
    r = requests.get(URL_BASE, params=params, timeout=timeout)
    r.raise_for_status()
    diario = r.json()["daily"]
    df = pd.DataFrame({nombre: pd.Series(diario[col], dtype=float) for col, nombre in MAPEO_COLUMNAS.items()})
    df.index = pd.to_datetime(diario["time"])
    return df
