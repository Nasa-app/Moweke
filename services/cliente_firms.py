"""
Cliente NASA FIRMS v0.1 -- focos de calor/incendios casi en tiempo real (VIIRS/MODIS).
Extension post-MVP (clasificacion NASA/ESA de indicadores que trajo el usuario).

VERIFICADO POR EJECUCION con clave real (MAP_KEY, registrada por email, ver conversacion):
- Chiloe, primavera, ultimos 5 dias -> 0 focos reales (resultado honesto, no una falla).
- Norte de Chile, verano 2026 (2026-02-05) -> focos reales con frp>0, confirma que el
  cliente SI detecta incendios reales cuando existen, no solo devuelve vacio siempre.

BUG REAL encontrado el 14-nov-2026: este cliente consultaba VIIRS_SNPP_NRT, y Suomi NPP
dejo de publicar el 2-nov-2026. Desde ese dia FIRMS respondia 200 con cero focos en
cualquier parte del mundo, y ese cero se leia como "sin incendios" (el mismo dia,
NOAA-20 y NOAA-21 traian 205 y 182 detecciones en el centro-sur de Chile). Por eso:
el sensor por defecto es NOAA-20, SENSORES_VIGENTES lista los dos VIIRS en operacion, y
consultar_disponibilidad() permite comprobar que un sensor sigue publicando antes de
creerle un cero.

Columnas reales del CSV (confirmadas, no asumidas de la documentacion): latitude,
longitude, bright_ti4, scan, track, acq_date, acq_time, satellite, instrument,
confidence, version, bright_ti5, frp (potencia radiativa del fuego, proxy de intensidad),
daynight (y 'type' solo en productos _SP, no en _NRT).
"""
from __future__ import annotations

from datetime import date
from io import StringIO

import pandas as pd
import requests

URL_BASE = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
URL_DISPONIBILIDAD = "https://firms.modaps.eosdis.nasa.gov/api/data_availability/csv"

# VIIRS en operacion: el mismo instrumento en dos satelites, asi que juntos dan mas pasadas
# al dia. Una misma quema puede aparecer en los dos: son detecciones, no incendios unicos.
SENSORES_VIGENTES = ("VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT")


class ErrorFirms(RuntimeError):
    """Falla de la consulta a FIRMS. Su mensaje nunca contiene la URL ni la clave."""


def _pedir(url: str, map_key: str, timeout: int) -> str:
    """GET a FIRMS. La clave viaja en la ruta de la URL, y las excepciones de requests
    citan la URL entera: se reemplazan por un error sin URL (`from None` corta la cadena),
    para que la clave no termine en un log ni en job_extraccion.detalle."""
    try:
        r = requests.get(url, timeout=timeout)
    except requests.RequestException as error:
        raise ErrorFirms(f"FIRMS no respondio ({type(error).__name__})") from None
    if r.status_code != 200:
        raise ErrorFirms(f"FIRMS respondio HTTP {r.status_code}")
    if r.text[:30].lstrip().startswith(("Invalid", "Error")):
        raise ErrorFirms(f"FIRMS respondio error: {r.text[:200].replace(map_key, '[clave]')}")
    return r.text


def consultar_disponibilidad(map_key: str, timeout: int = 20) -> dict[str, date]:
    """Ultimo dia con datos que FIRMS declara por producto, ej. {'VIIRS_NOAA20_NRT':
    date(2026, 11, 14), 'VIIRS_SNPP_NRT': date(2026, 11, 2)}. VERIFICADO en vivo."""
    tabla = pd.read_csv(StringIO(_pedir(f"{URL_DISPONIBILIDAD}/{map_key}/ALL", map_key, timeout)))
    return {fila["data_id"]: date.fromisoformat(str(fila["max_date"])) for _, fila in tabla.iterrows()}


def consultar_focos(map_key: str, bbox: tuple[float, float, float, float],
                     sensor: str = "VIIRS_NOAA20_NRT", dias: int = 5, timeout: int = 20) -> pd.DataFrame:
    """bbox: (lon_min, lat_min, lon_max, lat_max) -- un area, no un punto: un foco de
    incendio es un evento regional, no algo que tenga sentido leer en un solo pixel.
    dias: 1-5 para productos _NRT -- limite real de la API (verificado: pedir 7 responde
    'Invalid day range. Expects [1..5].', no un error generico). Devuelve DataFrame vacio
    (nunca None ni excepcion) si no hay focos -- es un resultado real, no una falla."""
    lon_min, lat_min, lon_max, lat_max = bbox
    url = f"{URL_BASE}/{map_key}/{sensor}/{lon_min},{lat_min},{lon_max},{lat_max}/{dias}"
    return pd.read_csv(StringIO(_pedir(url, map_key, timeout)))
