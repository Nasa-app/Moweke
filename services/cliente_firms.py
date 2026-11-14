"""
Cliente NASA FIRMS v0.1 -- focos de calor/incendios casi en tiempo real (VIIRS/MODIS).
Extension post-MVP (clasificacion NASA/ESA de indicadores que trajo el usuario).

VERIFICADO POR EJECUCION con clave real (MAP_KEY, registrada por email, ver conversacion):
- Chiloe, primavera, ultimos 5 dias -> 0 focos reales (resultado honesto, no una falla).
- Norte de Chile, verano 2026 (2026-02-05) -> focos reales con frp>0, confirma que el
  cliente SI detecta incendios reales cuando existen, no solo devuelve vacio siempre.

Columnas reales del CSV (confirmadas, no asumidas de la documentacion): latitude,
longitude, bright_ti4, scan, track, acq_date, acq_time, satellite, instrument,
confidence, version, bright_ti5, frp (potencia radiativa del fuego, proxy de intensidad),
daynight (y 'type' solo en productos _SP, no en _NRT).
"""
from __future__ import annotations

from io import StringIO

import pandas as pd
import requests

URL_BASE = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"


def consultar_focos(map_key: str, bbox: tuple[float, float, float, float],
                     sensor: str = "VIIRS_SNPP_NRT", dias: int = 5, timeout: int = 20) -> pd.DataFrame:
    """bbox: (lon_min, lat_min, lon_max, lat_max) -- un area, no un punto: un foco de
    incendio es un evento regional, no algo que tenga sentido leer en un solo pixel.
    dias: 1-5 para productos _NRT -- limite real de la API (verificado: pedir 7 responde
    'Invalid day range. Expects [1..5].', no un error generico). Devuelve DataFrame vacio
    (nunca None ni excepcion) si no hay focos -- es un resultado real, no una falla."""
    lon_min, lat_min, lon_max, lat_max = bbox
    url = f"{URL_BASE}/{map_key}/{sensor}/{lon_min},{lat_min},{lon_max},{lat_max}/{dias}"
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    if r.text[:30].lstrip().startswith(("Invalid", "Error")):
        raise ValueError(f"FIRMS respondio error: {r.text[:200]}")
    return pd.read_csv(StringIO(r.text))
