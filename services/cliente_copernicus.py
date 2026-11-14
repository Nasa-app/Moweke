"""
Cliente Copernicus Data Space v0.1 -- Sentinel-1/2, extension post-MVP (ver plan,
"Extension futura - Copernicus y Explorador Solar").

VERIFICADO POR EJECUCION: la busqueda de catalogo (OData API de
catalogue.dataspace.copernicus.eu) funciona SIN autenticacion -- probado en vivo contra
el punto de Castro, devuelve granulos reales de Sentinel-1 (SAR) y Sentinel-2 L2A
(reflectancia de superficie) con fecha y, para Sentinel-2, el atributo real `cloudCover`
por escena (permite filtrar nubes ANTES de descargar, a diferencia de AppEEARS donde el
dato nublado solo se sabe despues de bajarlo -- es la mitad del problema de nubosidad
persistente de Chiloe que ya encontramos con MOD13Q1).

NO VERIFICADO / BLOQUEADO: la DESCARGA real de un producto (`descargar_producto`,
`Nodes(...)/$value` u objeto S3 en `S3Path`) necesita una cuenta gratuita de Copernicus
Data Space Ecosystem (OAuth2 client credentials o claves S3) -- no se tiene todavia.
Mismo patron que con AppEEARS/Earthdata: la funcion esta escrita contra la documentacion
real de la API pero no se puede probar sin esa cuenta. Pedir credenciales antes de confiar
en `descargar_producto()`.

Sentinel-1 es radar (SAR) -- no tiene nubes que filtrar, por eso buscar_sentinel1() no
tiene parametro nube_max.
"""
from __future__ import annotations

import json

import requests

URL_CATALOGO = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
URL_AUTH = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"


def _punto_wkt(lat: float, lon: float) -> str:
    return f"geography'SRID=4326;POINT({lon} {lat})'"


def _buscar(filtro: str, limite: int, con_atributos: bool, timeout: int) -> list[dict]:
    params = {
        "$filter": filtro,
        "$top": str(limite),
        "$orderby": "ContentDate/Start desc",
    }
    if con_atributos:
        params["$expand"] = "Attributes"
    r = requests.get(URL_CATALOGO, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json().get("value", [])


def _atributo(producto: dict, nombre: str):
    for a in producto.get("Attributes", []):
        if a["Name"] == nombre:
            return a["Value"]
    return None


def buscar_sentinel2(lat: float, lon: float, fecha_inicio: str, fecha_fin: str,
                      nube_max: float | None = None, limite: int = 10, timeout: int = 20) -> list[dict]:
    """fechas 'YYYY-MM-DD'. Busca L2A (reflectancia de superficie, listo para NDVI/EVI) --
    no L1C (tope de atmosfera, sin correccion atmosferica, no apto para indices de
    vegetacion). nube_max filtra por el atributo real cloudCover de la escena (0-100),
    ANTES de cualquier descarga -- confirmar que el valor es realista para el area de
    interes, no solo para el centro de la escena (una escena puede estar despejada en
    Castro y nublada en el resto del tile)."""
    filtro = (
        f"Collection/Name eq 'SENTINEL-2' and contains(Name,'MSIL2A') and "
        f"OData.CSC.Intersects(area={_punto_wkt(lat, lon)}) and "
        f"ContentDate/Start gt {fecha_inicio}T00:00:00.000Z and "
        f"ContentDate/Start lt {fecha_fin}T23:59:59.999Z"
    )
    productos = _buscar(filtro, limite, con_atributos=True, timeout=timeout)
    out = []
    for p in productos:
        nubes = _atributo(p, "cloudCover")
        if nube_max is not None and nubes is not None and nubes > nube_max:
            continue
        out.append({
            "id": p["Id"], "nombre": p["Name"], "fecha": p["ContentDate"]["Start"],
            "cloud_cover_pct": nubes, "s3_path": p.get("S3Path"),
        })
    return out


def buscar_sentinel1(lat: float, lon: float, fecha_inicio: str, fecha_fin: str,
                      limite: int = 10, timeout: int = 20) -> list[dict]:
    """SAR -- sin nubes que filtrar. Util especificamente cuando Sentinel-2/MODIS no
    tienen escena limpia disponible (ver advertencia de cliente_copernicus mas arriba)."""
    filtro = (
        f"Collection/Name eq 'SENTINEL-1' and "
        f"OData.CSC.Intersects(area={_punto_wkt(lat, lon)}) and "
        f"ContentDate/Start gt {fecha_inicio}T00:00:00.000Z and "
        f"ContentDate/Start lt {fecha_fin}T23:59:59.999Z"
    )
    productos = _buscar(filtro, limite, con_atributos=False, timeout=timeout)
    return [{"id": p["Id"], "nombre": p["Name"], "fecha": p["ContentDate"]["Start"],
              "s3_path": p.get("S3Path")} for p in productos]


def obtener_token(usuario: str, clave: str, timeout: int = 20) -> str:
    """NO VERIFICADO -- escrito contra la documentacion de CDSE (OAuth2 password grant,
    client_id publico 'cdse-public'), nunca probado: necesita una cuenta real de
    dataspace.copernicus.eu que todavia no se tiene. Antes de confiar en esto, correrlo
    una vez contra una cuenta real y corregir segun la respuesta observada -- mismo
    criterio que se aplico con cliente_appeears.iniciar_sesion()."""
    r = requests.post(URL_AUTH, data={
        "client_id": "cdse-public", "username": usuario, "password": clave, "grant_type": "password",
    }, timeout=timeout)
    r.raise_for_status()
    return r.json()["access_token"]


def descargar_producto(token: str, id_producto: str, destino: str, timeout: int = 120) -> str:
    """NO VERIFICADO -- ver advertencia del modulo. El endpoint documentado es
    `GET /odata/v1/Products(<id>)/$value` con `Authorization: Bearer <token>`."""
    url = f"{URL_CATALOGO}({id_producto})/$value"
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=timeout, stream=True)
    r.raise_for_status()
    with open(destino, "wb") as f:
        for chunk in r.iter_content(chunk_size=1 << 20):
            f.write(chunk)
    return destino
