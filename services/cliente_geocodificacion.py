"""
Geocodificacion inversa: de un punto a su pais y su region (primer nivel administrativo), para dejar escrito donde
queda un predio. Usa Nominatim (OpenStreetMap), sin clave.

VERIFICADO EN VIVO el 17-nov-2026 contra https://nominatim.openstreetmap.org/reverse con zoom=5: responde
`address.country` y `address.state` (ej. "Región de Los Lagos", "Chile"). La politica de uso exige un User-Agent que
identifique la aplicacion y no mas de una consulta por segundo: aca se consulta una vez por predio, y solo si falta.
Los datos son de OpenStreetMap (ODbL): citar "© OpenStreetMap contributors" donde se muestren.

No viaja ningun dato de la persona: solo latitud y longitud, redondeadas a 0,01 grados (~1 km).
"""
from __future__ import annotations

import requests

URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "mogen-geocodificacion-inversa"
_CAMPOS_REGION = ("state", "region", "province", "state_district", "county")


def referencia(lat: float, lon: float, idioma: str = "es", timeout: float = 6.0) -> tuple[str | None, str | None]:
    """(pais, region) del punto. (None, None) si el servicio no conoce el lugar (mar abierto). Levanta si el servicio
    no responde: quien llama decide reintentar mas tarde."""
    resp = requests.get(
        URL,
        params={"lat": round(lat, 2), "lon": round(lon, 2), "format": "jsonv2", "zoom": 5, "addressdetails": 1,
                "accept-language": idioma},
        headers={"User-Agent": USER_AGENT}, timeout=timeout, allow_redirects=False)
    resp.raise_for_status()
    direccion = resp.json().get("address") or {}
    pais = direccion.get("country")
    region = next((direccion[c] for c in _CAMPOS_REGION if direccion.get(c)), None)
    return (pais[:80] if pais else None), (region[:120] if region else None)
