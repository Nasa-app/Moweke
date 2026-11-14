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


def consultar_suelo(lat: float, lon: float, profundidad: str = "0-5cm", timeout: int = 30) -> dict:
    """profundidad: una de las bandas reales de SoilGrids ('0-5cm','5-15cm','15-30cm',
    '30-60cm','60-100cm','100-200cm'). Devuelve None por variable si el punto cae fuera
    de cobertura (verificado: la API responde 200 con "mean": null, no un error)."""
    params = {
        "lon": lon, "lat": lat, "depth": profundidad, "value": "mean",
        "property": list(_PROPIEDADES.keys()),
    }
    r = requests.get(URL_BASE, params=params, timeout=timeout)
    r.raise_for_status()
    capas = r.json()["properties"]["layers"]
    out = {"profundidad": profundidad}
    for capa in capas:
        nombre, factor = _PROPIEDADES[capa["name"]]
        valor = capa["depths"][0]["values"]["mean"]
        out[nombre] = None if valor is None else valor / factor
    return out
