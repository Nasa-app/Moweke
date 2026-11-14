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

ACTUALIZACION (credenciales OAuth reales obtenidas): se agrego `obtener_token_oauth()`
(client_credentials, VERIFICADO contra una cuenta real) y `ndvi_estadistico()`/
`backscatter_estadistico()`, que usan la Statistical API de Sentinel Hub en vez de bajar
y procesar bandas crudas -- la API calcula NDVI/backscatter YA enmascarado por nubes
(via SCL) del lado del servidor, para el poligono exacto de la parcela. Esto reemplaza
el plan original de `descargar_producto()` + banda-matematica local -- no hace falta
procesar rasters nosotros mismos para esto.

VERIFICADO EN VIVO sobre la parcela de prueba de Chiloe (poligono real, no solo un punto):
el periodo 25-oct a 4-nov salio 100% enmascarado por nubes en Sentinel-2 (NDVI, confirma
el problema cronico de nubosidad de Chiloe) pero el MISMO periodo en Sentinel-1 (VV) dio
cobertura completa, cero pixeles sin dato -- la prueba concreta de que el radar resuelve
exactamente el hueco que la nubosidad deja en el optico.

`obtener_token()`/`descargar_producto()` (mas abajo) quedan igual que antes -- escritos
contra la documentacion de la OData API para descarga de producto crudo (.SAFE completo),
sin verificar todavia porque ya no son el camino principal: la Statistical API cubre el
caso de uso real (NDVI/backscatter agregado por parcela) sin necesitar el archivo entero.
"""
from __future__ import annotations

import json

import requests

URL_CATALOGO = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
URL_AUTH = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
URL_STATISTICS = "https://sh.dataspace.copernicus.eu/api/v1/statistics"


def obtener_token_oauth(client_id: str, client_secret: str, timeout: int = 20) -> str:
    """VERIFICADO contra una cuenta real de dataspace.copernicus.eu -- OAuth2
    client_credentials (no password grant: un 'OAuth client' se crea aparte en el
    perfil de la cuenta, nunca es el usuario/clave de login). Token valido 1800s (30 min)
    -- quien lo use en un job largo tiene que renovarlo, no asumir que dura toda la sesion."""
    r = requests.post(URL_AUTH, data={
        "grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret,
    }, timeout=timeout)
    r.raise_for_status()
    return r.json()["access_token"]


def _evalscript_ndvi() -> str:
    # Solo se promedian los pixeles que Sen2Cor clasifica como superficie visible: SCL 4
    # (vegetacion), 5 (suelo desnudo), 6 (agua) y 7 (sin clasificar). Antes solo se
    # excluian 3/8/9 (sombra de nube y nube media/alta) y se colaban cirros (10), sombras
    # oscuras (2), nieve (11) y pixeles defectuosos -- BUG REAL visto en la serie de
    # Quemchi: intervalos "validos" con NDVI -0,02 o 0,32 en un predio que marca 0,8.
    # Un NDVI promedio que mezcla pixeles nublados con limpios no significa nada.
    return (
        '//VERSION=3\n'
        'function setup() { return { input: [{bands: ["B04","B08","SCL","dataMask"]}], '
        'output: [{id:"ndvi",bands:1,sampleType:"FLOAT32"},{id:"dataMask",bands:1}] }; }\n'
        'function evaluatePixel(s) {\n'
        '  let ndvi = (s.B08 - s.B04) / (s.B08 + s.B04);\n'
        '  let visible = (s.SCL == 4 || s.SCL == 5 || s.SCL == 6 || s.SCL == 7);\n'
        '  return { ndvi: [ndvi], dataMask: [visible ? s.dataMask : 0] };\n'
        '}'
    )


def _evalscript_backscatter(polarizacion: str) -> str:
    return (
        '//VERSION=3\n'
        f'function setup() {{ return {{ input: [{{bands: ["{polarizacion}","dataMask"]}}], '
        f'output: [{{id:"{polarizacion.lower()}",bands:1,sampleType:"FLOAT32"}},{{id:"dataMask",bands:1}}] }}; }}\n'
        f'function evaluatePixel(s) {{ return {{ {polarizacion.lower()}: [s.{polarizacion}], dataMask: [s.dataMask] }}; }}'
    )


def _estadistica_agregada(token: str, coleccion: str, evalscript: str, bbox: list[float],
                           fecha_inicio: str, fecha_fin: str, intervalo_dias: int,
                           data_filter: dict | None, timeout: int) -> list[dict]:
    cuerpo = {
        "input": {"bounds": {"bbox": bbox},
                   "data": [{"type": coleccion, **({"dataFilter": data_filter} if data_filter else {})}]},
        "aggregation": {
            "timeRange": {"from": f"{fecha_inicio}T00:00:00Z", "to": f"{fecha_fin}T23:59:59Z"},
            "aggregationInterval": {"of": f"P{intervalo_dias}D"},
            "evalscript": evalscript,
        },
        "calculations": {"default": {}},
    }
    r = requests.post(URL_STATISTICS, json=cuerpo, headers={"Authorization": f"Bearer {token}"}, timeout=timeout)
    r.raise_for_status()
    return r.json()["data"]


def ndvi_estadistico(token: str, bbox: list[float], fecha_inicio: str, fecha_fin: str,
                      intervalo_dias: int = 10, timeout: int = 60) -> list[dict]:
    """bbox: [lon_min, lat_min, lon_max, lat_max] -- el poligono de la parcela, no un punto.
    VERIFICADO: devuelve NDVI medio por intervalo, con los pixeles nublados (SCL) ya
    excluidos del promedio -- 'noDataCount' en cada intervalo dice cuantos pixeles del
    poligono quedaron fuera por nubes (65536/65536 = intervalo entero inservible, visto
    en vivo para Chiloe en un periodo real)."""
    datos = _estadistica_agregada(token, "sentinel-2-l2a", _evalscript_ndvi(), bbox,
                                   fecha_inicio, fecha_fin, intervalo_dias, None, timeout)
    return [{"desde": d["interval"]["from"], "hasta": d["interval"]["to"],
              **d["outputs"]["ndvi"]["bands"]["B0"]["stats"]} for d in datos]


def backscatter_estadistico(token: str, bbox: list[float], fecha_inicio: str, fecha_fin: str,
                             polarizacion: str = "VV", intervalo_dias: int = 10, timeout: int = 60) -> list[dict]:
    """Igual que ndvi_estadistico() pero Sentinel-1 (SAR) -- sin mascara de nubes porque
    no la necesita. VERIFICADO: en el mismo periodo donde ndvi_estadistico() dio el
    intervalo entero sin dato (nublado), esto devolvio cobertura completa -- es la
    confirmacion concreta de que resuelve el hueco de nubosidad persistente."""
    datos = _estadistica_agregada(token, "sentinel-1-grd", _evalscript_backscatter(polarizacion), bbox,
                                   fecha_inicio, fecha_fin, intervalo_dias,
                                   {"acquisitionMode": "IW"}, timeout)
    return [{"desde": d["interval"]["from"], "hasta": d["interval"]["to"],
              **d["outputs"][polarizacion.lower()]["bands"]["B0"]["stats"]} for d in datos]


# ---------------------------------------------------------------- catalogo crudo (sin auth)
# NO VERIFICADO / sin uso principal hoy: descarga del .SAFE completo. Las funciones de
# arriba (Statistical API) cubren el caso de uso real sin necesitar esto -- se deja
# escrito por si algun dia hace falta el archivo crudo completo (ej. para Fase 6 avanzada
# con bandas que la Statistical API no calcule).


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
