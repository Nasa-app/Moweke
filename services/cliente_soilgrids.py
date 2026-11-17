"""
Cliente SoilGrids (ISRIC) v0.1 -- pH, textura y carbono organico, extension post-MVP.

VERIFICADO POR EJECUCION: API de consulta puntual real, sin auth, sin descarga de
raster (a diferencia de CLSoilMaps) -- services/cliente_clsoilmaps.py.consultar_vista_rapida
le falta exactamente esto: pH no esta entre las variables de ROSETTA_MEAN (ver
FileDesc.txt citado en ese modulo). SoilGrids cubre ese hueco especifico, no reemplaza
a CLSoilMaps (ese sigue siendo la fuente de agua disponible).

Verificado tambien el caso fuera de cobertura (punto en el oceano, -40,-40): la API
responde 200 con "mean": null, NO un error ni un 404 -- la ausencia de dato hay que
leerla del valor, no de un codigo de estado o una excepcion.
"""
from __future__ import annotations

import time

import requests

URL_BASE = "https://rest.isric.org/soilgrids/v2.0/properties/query"

# Nombre SoilGrids -> factor de division real (d_factor de la propia API, confirmado
# en vivo) para llegar a la unidad real. ej. phh2o viene en pH*10 -> dividir por 10.
_PROPIEDADES = {
    "phh2o": ("ph", 10),
    "clay": ("arcilla_pct", 10),
    "sand": ("arena_pct", 10),
    "silt": ("limo_pct", 10),
    "soc": ("carbono_organico_g_kg", 10),
}


# La API publica de ISRIC tarda a veces 24-40 s (medido el 17-nov-2026): con 30 s fallaba la ingesta del suelo. Un
# solo reintento tras un timeout o un error 5xx; mas, y se toparia con su limite de ~5 consultas por minuto.
TIMEOUT_S = 90
ESPERA_REINTENTO_S = 3


def _pedir(params: dict, timeout: int) -> requests.Response:
    for intento in (1, 2):
        try:
            r = requests.get(URL_BASE, params=params, timeout=timeout)
            if r.status_code < 500:
                r.raise_for_status()
                return r
            error = requests.HTTPError(f"SoilGrids respondio {r.status_code}", response=r)
        except (requests.Timeout, requests.ConnectionError) as e:
            error = e
        if intento == 2:
            raise error
        time.sleep(ESPERA_REINTENTO_S)


def consultar_suelo(lat: float, lon: float, profundidad: str = "0-5cm", timeout: int = TIMEOUT_S) -> dict:
    """profundidad: una de las bandas reales de SoilGrids ('0-5cm','5-15cm','15-30cm',
    '30-60cm','60-100cm','100-200cm'). Devuelve None por variable si el punto cae fuera
    de cobertura (verificado: la API responde 200 con "mean": null, no un error)."""
    params = {
        "lon": lon, "lat": lat, "depth": profundidad, "value": "mean",
        "property": list(_PROPIEDADES.keys()),
    }
    capas = _pedir(params, timeout).json()["properties"]["layers"]
    out = {"profundidad": profundidad}
    for capa in capas:
        nombre, factor = _PROPIEDADES[capa["name"]]
        valor = capa["depths"][0]["values"]["mean"]
        out[nombre] = None if valor is None else valor / factor
    return out


# SoilGrids enmascara pixeles de 250 m (agua, roca, urbano) y el del centro de un predio puede ser uno de ellos
# aunque los de al lado tengan dato. Si el centro viene vacio se prueban cuatro puntos a 250 m (norte, este, sur,
# oeste) y se saca la mediana de lo que haya. La API publica limita a unas 5 consultas por minuto: son como mucho 5.
DISTANCIA_VECINOS_M = 250
VALIDOS_BUSCADOS = 2


def consultar_suelo_entorno(lat: float, lon: float, profundidad: str = "0-5cm", timeout: int = TIMEOUT_S) -> dict:
    """Como consultar_suelo(), pero con vecinos si el punto central no tiene dato. Agrega 'pixeles' (cuantos
    puntos aportaron) y 'vecinos' (True si el valor no es el del centro)."""
    from statistics import median
    import math

    centro = consultar_suelo(lat, lon, profundidad, timeout)
    if centro["ph"] is not None:
        return {**centro, "pixeles": 1, "vecinos": False}
    dlat = DISTANCIA_VECINOS_M / 110_574
    dlon = DISTANCIA_VECINOS_M / (111_320 * max(math.cos(math.radians(lat)), 0.01))
    validos = []
    for la, lo in ((lat + dlat, lon), (lat, lon + dlon), (lat - dlat, lon), (lat, lon - dlon)):
        try:
            punto = consultar_suelo(la, lo, profundidad, timeout)
        except requests.RequestException:
            continue
        if punto["ph"] is not None:
            validos.append(punto)
            if len(validos) >= VALIDOS_BUSCADOS:
                break
    if not validos:
        return {**centro, "pixeles": 0, "vecinos": False}
    claves = [k for k in centro if k != "profundidad"]
    mediana = {k: median(p[k] for p in validos if p[k] is not None) if any(p[k] is not None for p in validos) else None for k in claves}
    return {"profundidad": profundidad, **mediana, "pixeles": len(validos), "vecinos": True}
