"""
Cliente Explorador Solar v0.1 — solar.minenergia.cl (Ministerio de Energia, Chile).

VERIFICADO POR EJECUCION (extension post-MVP, ver plan): el sitio no documenta una API
publica, pero el mapa interactivo llama un endpoint real sin autenticacion. Se encontro
inspeccionando las requests de red del propio mapa, no un endpoint publicado:

    GET /python-router/{"tipo": "VistaRapida", "datos": {"lat": ..., "lon": ...}}

Probado en vivo contra el punto de prueba de Castro (-42.48, -73.76): responde climatologia
2004-2016 (promedios, NO serie diaria) a ~1km de resolucion -- GHI/DNI/DIFH, temperatura,
viento, nubosidad, evaporacion, elevacion SRTM. No reemplaza a cliente_power.py (eso sigue
siendo la fuente de clima DIARIO que el motor fenologico consume) -- esto es para calibrar
services/motor_estres.balance_agua() con radiacion/evaporacion real en vez de la aproximacion
Hargreaves actual, y como dato de sitio (una vez, no por temporada).

Sin API key, sin cuenta, sin limite documentado -- pero es un endpoint no publicado de un
sitio de gobierno chileno, no un servicio con SLA. Tratar como "mejor esfuerzo", no como
fuente con garantia de disponibilidad -- degradar con calma (marcar 'sin_dato' en
cache_consulta_grilla) si falla, no reintentar agresivo.
"""
from __future__ import annotations

import json

import requests

URL_BASE = "https://solar.minenergia.cl/python-router"


def _llamar(tipo: str, datos: dict, timeout: int = 20) -> dict:
    """El endpoint real toma el payload como JSON embebido en la URL (no como body) --
    confirmado inspeccionando las requests que dispara el propio mapa al hacer click."""
    url = f"{URL_BASE}/{json.dumps({'tipo': tipo, 'datos': datos}, separators=(',', ':'))}"
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    cuerpo = r.json()
    if cuerpo.get("_serverStatus") != "ok":
        raise ValueError(f"Explorador Solar respondio error: {cuerpo.get('_serverText')}")
    return cuerpo["_serverData"]


def disponibilidad(lat: float, lon: float, timeout: int = 20) -> bool:
    """True si el punto tiene datos modelados (DA = 'Datos Disponibles'). Verificado:
    False tipico fuera de Chile continental o en zonas sin cobertura del modelo."""
    return bool(_llamar("Disponibilidad", {"lat": lat, "lon": lon}, timeout).get("DA"))


def consultar_vista_rapida(lat: float, lon: float, timeout: int = 20) -> dict:
    """Climatologia puntual 2004-2016 (promedio anual + desglose mensual). VERIFICADO
    contra Castro -- devuelve (nombres reales de la respuesta, no inventados):
      GHI, GLBP, DNI, DIFH: kWh/m2/dia, promedio anual.
      NUB: % de nubosidad promedio anual.
      TMP: temperatura promedio anual (C).
      VEL: velocidad de viento promedio anual (m/s).
      SM_DIRH, SM_DIFH: listas de 12 valores (radiacion directa/difusa mensual).
    Tambien devuelve 'Site' con height_srtm (elevacion del punto) y 'vars_available'
    (lista real de variables que el modelo puede entregar para ese punto -- incluye
    'evap', util para contrastar con motor_estres.balance_agua()).
    Lanza ValueError si el punto no tiene cobertura -- llamar disponibilidad() antes
    si se quiere evitar la excepcion."""
    datos = _llamar("VistaRapida", {"lat": lat, "lon": lon}, timeout)
    vr = datos.get("VR")
    if vr is None:
        raise ValueError(f"Sin datos de VistaRapida para ({lat}, {lon}) -- usar disponibilidad() antes.")
    sitio = (datos.get("Site") or [{}])[0]
    return {
        "ghi_kwh_m2_dia": vr.get("GHI"),
        "dni_kwh_m2_dia": vr.get("DNI"),
        "difh_kwh_m2_dia": vr.get("DIFH"),
        "nubosidad_pct": vr.get("NUB"),
        "temperatura_c": vr.get("TMP"),
        "viento_m_s": vr.get("VEL"),
        "radiacion_directa_mensual": vr.get("SM_DIRH"),
        "radiacion_difusa_mensual": vr.get("SM_DIFH"),
        "elevacion_srtm_m": sitio.get("height_srtm"),
        "variables_disponibles": sitio.get("vars_available", []),
        "periodo": "2004-2016",
    }
