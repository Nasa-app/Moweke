"""Las comunas de Chiloe y el tiempo de cada una, para la pantalla que se ve sin tener predio.

El punto es el pueblo cabecera de la comuna (coordenadas del geocodificador de Open-Meteo, revisadas el 15-nov-2026),
no un deslinde. El cliente solo elige una comuna de esta lista: nunca manda coordenadas, asi que el servidor no consulta
puntos arbitrarios. Las consultas se guardan en memoria unos minutos para no repetirlas por cada visita."""
from __future__ import annotations

import time

from services import cliente_openmeteo

COMUNAS: dict[str, tuple[float, float]] = {
    "Ancud": (-41.8707, -73.8162),
    "Castro": (-42.4721, -73.7732),
    "Chonchi": (-42.6239, -73.775),
    "Curaco de Vélez": (-42.4389, -73.6012),
    "Dalcahue": (-42.3785, -73.6501),
    "Puqueldón": (-42.6, -73.6746),
    "Queilén": (-42.889, -73.4742),
    "Quellón": (-43.1182, -73.6166),
    "Quemchi": (-42.1439, -73.4751),
    "Quinchao": (-42.4709, -73.4914),
}

VIGENCIA_S = 30 * 60
HELADA_MAX_C = 0.0   # una minima de 0 °C o menos en el pronostico se avisa como helada posible

_cache: dict[str, tuple[float, dict]] = {}


def resumir(crudo: dict) -> dict:
    """De la respuesta de Open-Meteo al resumen de la zona: el tiempo de ahora y la primera helada pronosticada."""
    actual, diario = crudo["current"], crudo["daily"]
    primera_helada = next((f for f, m in zip(diario["time"], diario["temperature_2m_min"])
                           if m is not None and m <= HELADA_MAX_C), None)
    return {
        "hoy": diario["time"][0],
        "temperatura_c": actual["temperature_2m"],
        "humedad_relativa": actual["relative_humidity_2m"],
        "viento_kmh": actual["wind_speed_10m"],
        "codigo_tiempo": actual["weather_code"],
        "lluvia_hoy_mm": diario["precipitation_sum"][0],
        "primera_helada": primera_helada,
    }


def clima_de_zona(nombre: str, ahora: float | None = None) -> dict:
    """El resumen de la comuna `nombre` (KeyError si no esta en la lista). Reusa el ultimo dentro de VIGENCIA_S."""
    ahora = time.time() if ahora is None else ahora
    guardado = _cache.get(nombre)
    if guardado and ahora - guardado[0] < VIGENCIA_S:
        return guardado[1]
    lat, lon = COMUNAS[nombre]
    resumen = resumir(cliente_openmeteo.consultar_hoy(lat, lon))
    _cache[nombre] = (ahora, resumen)
    return resumen


MAX_PUNTOS_EN_MEMORIA = 500


def clima_en_punto(lat: float, lon: float, ahora: float | None = None) -> dict:
    """El resumen del tiempo en cualquier punto del mundo. Las coordenadas se redondean a 0,1 grado (unos 11 km): el
    pronostico no cambia a esa escala, el servidor no guarda ni consulta la ubicacion exacta, y los vecinos comparten
    la misma consulta en memoria."""
    ahora = time.time() if ahora is None else ahora
    lat, lon = round(lat, 1), round(lon, 1)
    clave = f"{lat},{lon}"
    guardado = _cache.get(clave)
    if guardado and ahora - guardado[0] < VIGENCIA_S:
        return guardado[1]
    resumen = resumir(cliente_openmeteo.consultar_hoy(lat, lon))
    if len(_cache) >= MAX_PUNTOS_EN_MEMORIA:
        _cache.pop(next(iter(_cache)))
    _cache[clave] = (ahora, resumen)
    return resumen
