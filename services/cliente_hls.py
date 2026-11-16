"""
Cliente HLS v0.1 -- NDVI a 30 m de NASA (Harmonized Landsat Sentinel-2, v2.0), directo del
catalogo STAC de LP DAAC, sin AppEEARS y sin usuario/clave: solo un token de Earthdata
(EARTHDATA_TOKEN). Es la fuente NASA del verdor del predio.

Dos sensores en el mismo producto: HLSL30 (Landsat 8/9, rojo B04, infrarrojo cercano B05) y
HLSS30 (Sentinel-2 armonizado a la grilla de Landsat, rojo B04, infrarrojo cercano B8A).

VERIFICADO POR EJECUCION (15-nov-2026, Castro): la busqueda STAC es abierta; los archivos
piden el token. El servidor responde 303 a una URL firmada (CloudFront) que acepta lecturas
por rango pero rechaza HEAD, asi que la redireccion se resuelve con el token SIN seguirla y
la URL firmada se abre con rasterio y CPL_VSIL_CURL_USE_HEAD=NO. El token que se le pasa a
GDAL no sirve. Se lee solo la ventana del predio, no la tesela de 110 km.

Mascara de calidad (Fmask): un pixel sirve si los bits 1 a 5 son 0 (nube, nube adyacente,
sombra de nube, nieve o hielo, agua). Un pixel sin dato de reflectancia (-9999) tampoco.

Los tokens de Earthdata vencen (el cargado en Railway vence el 2027-01-13): cuando venza, la
fuente falla con 401 y el detalle queda en job_extraccion.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from urllib.parse import urlparse

import numpy as np
import rasterio
import requests
from rasterio.features import geometry_mask
from rasterio.warp import transform_geom
from rasterio.windows import Window, from_bounds

URL_STAC = "https://cmr.earthdata.nasa.gov/stac/LPCLOUD/search"
COLECCIONES = ("HLSL30_2.0", "HLSS30_2.0")
BANDA_NIR = {"HLSL30": "B05", "HLSS30": "B8A"}
NUBE_ESCENA_MAX_PCT = 70      # una escena mas nublada que esto no deja pixeles utiles para un predio
LECTURAS_SIMULTANEAS = 4
INTENTOS_POR_ESCENA = 3
_ENTORNO = {"GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR", "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
            "CPL_VSIL_CURL_USE_HEAD": "NO", "GDAL_HTTP_TIMEOUT": "60", "GDAL_HTTP_MAX_RETRY": "2"}
_SIN_DATO = -9999


class ErrorHLS(Exception):
    pass


def sensor_de(id_escena: str) -> str:
    """'HLS.S30.T18GXU.2026247T143739.v2.0' -> 'HLSS30'."""
    return "HLS" + id_escena.split(".")[1]


def buscar_escenas(caja: list[float], desde: str, hasta: str, nube_max: int = NUBE_ESCENA_MAX_PCT,
                   timeout: int = 30) -> list[dict]:
    """Escenas HLS que cubren por completo la caja (lon_min, lat_min, lon_max, lat_max) entre dos
    fechas ISO. Cada una: {'id', 'fecha' (YYYY-MM-DD), 'sensor', 'nube_pct', 'activos': {banda: url}}.
    Dos teselas vecinas se solapan unos kilometros: de las que cubren la caja entera, una sola por
    dia y sensor (la menos nublada), para no contar dos veces el mismo pixel."""
    cuerpo = {"collections": list(COLECCIONES), "bbox": caja, "limit": 200,
              "datetime": f"{desde}T00:00:00Z/{hasta}T23:59:59Z"}
    escenas = {}
    url, pagina = URL_STAC, 0
    while url and pagina < 10:
        r = requests.post(url, json=cuerpo, timeout=timeout)
        r.raise_for_status()
        datos = r.json()
        for f in datos.get("features", []):
            nube = f["properties"].get("eo:cloud_cover")
            if nube is None or nube > nube_max or not _cubre(f, caja):
                continue
            sensor = sensor_de(f["id"])
            fecha = f["properties"]["datetime"][:10]
            nir = BANDA_NIR[sensor]
            activos = {b: f["assets"][b]["href"] for b in ("B04", nir, "Fmask") if b in f["assets"]}
            if len(activos) < 3:
                continue
            previa = escenas.get((fecha, sensor))
            if previa is None or nube < previa["nube_pct"]:
                escenas[(fecha, sensor)] = {"id": f["id"], "fecha": fecha, "sensor": sensor,
                                            "nube_pct": nube, "activos": activos}
        siguiente = next((l for l in datos.get("links", []) if l.get("rel") == "next"), None)
        url, pagina = (siguiente["href"] if siguiente else None), pagina + 1
        if siguiente and siguiente.get("body"):
            cuerpo = siguiente["body"]
    return sorted(escenas.values(), key=lambda e: e["fecha"])


def _cubre(feature: dict, caja: list[float]) -> bool:
    """La tesela cubre la caja entera: una caja cortada por el borde de la tesela daria un NDVI
    de solo una parte del predio, con la misma apariencia que uno completo."""
    xs = [p[0] for anillo in feature["geometry"]["coordinates"] for p in anillo]
    ys = [p[1] for anillo in feature["geometry"]["coordinates"] for p in anillo]
    return min(xs) <= caja[0] and min(ys) <= caja[1] and max(xs) >= caja[2] and max(ys) >= caja[3]


def _url_firmada(token: str, href: str, timeout: int = 30) -> str:
    """El token solo viaja a servidores de NASA Earthdata: el href sale de la respuesta del catalogo, y un
    href ajeno no debe recibirlo."""
    anfitrion = urlparse(href).hostname or ""
    if urlparse(href).scheme != "https" or not anfitrion.endswith(".earthdatacloud.nasa.gov"):
        raise ErrorHLS("un archivo del catalogo no apunta a Earthdata")
    r = requests.get(href, headers={"Authorization": f"Bearer {token}"}, allow_redirects=False, timeout=timeout)
    if r.status_code in (401, 403):
        raise ErrorHLS(f"Earthdata rechazo el token ({r.status_code}): vencido o sin permiso")
    if r.status_code not in (301, 302, 303, 307) or "Location" not in r.headers:
        raise ErrorHLS(f"respuesta inesperada de LP DAAC: {r.status_code}")
    destino = r.headers["Location"]
    if urlparse(destino).scheme != "https":
        raise ErrorHLS("LP DAAC redirigio a una direccion que no es https")
    return destino


def _leer(url: str, geometria: dict) -> tuple[np.ndarray, np.ndarray, "rasterio.Affine", object]:
    """Los pixeles de la banda en la caja del poligono: (valores, dentro, transform, crs) con la forma de la
    ventana. `geometria` en lon/lat; transform y crs son los de la ventana, para ubicar cada pixel."""
    with rasterio.open("/vsicurl/" + url) as ds:
        poligono = transform_geom("EPSG:4326", ds.crs, geometria)
        xs = [p[0] for anillo in poligono["coordinates"] for p in anillo]
        ys = [p[1] for anillo in poligono["coordinates"] for p in anillo]
        pedida = from_bounds(min(xs), min(ys), max(xs), max(ys), ds.transform)
        col0, fil0 = max(0, int(np.floor(pedida.col_off))), max(0, int(np.floor(pedida.row_off)))
        col1 = min(ds.width, int(np.ceil(pedida.col_off + pedida.width)))
        fil1 = min(ds.height, int(np.ceil(pedida.row_off + pedida.height)))
        if col1 <= col0 or fil1 <= fil0:
            raise ErrorHLS("el predio queda fuera de la tesela")
        ventana = Window(col0, fil0, col1 - col0, fil1 - fil0)
        valores = ds.read(1, window=ventana)
        transform = ds.window_transform(ventana)
        crs = ds.crs
    dentro = ~geometry_mask([poligono], valores.shape, transform)
    if not dentro.any():   # predio mas chico que un pixel: cuenta el pixel que toca
        dentro = ~geometry_mask([poligono], valores.shape, transform, all_touched=True)
    return valores, dentro, transform, crs


def _leer_ventana(url: str, geometria: dict) -> tuple[np.ndarray, np.ndarray]:
    """Los pixeles de la banda que caen dentro del poligono: (valores, dentro)."""
    valores, dentro, _, _ = _leer(url, geometria)
    return valores, dentro


def pixeles_validos(rojo: np.ndarray, nir: np.ndarray, fmask: np.ndarray, dentro: np.ndarray) -> np.ndarray:
    """Pixeles del poligono con reflectancia y sin nube, sombra, nieve ni agua."""
    limpio = ((fmask.astype(np.uint16) >> 1) & 0b11111) == 0
    con_dato = (rojo != _SIN_DATO) & (nir != _SIN_DATO) & ((rojo.astype(float) + nir) > 0)
    return dentro & limpio & con_dato


def ndvi_de_escena(token: str, escena: dict, geometria: dict) -> dict:
    """{'fecha', 'sensor', 'pixeles', 'validos', 'suma_ndvi'}: pixeles = los del poligono, validos = los
    sin nube; suma_ndvi = la suma de su NDVI (se suma y no se promedia para poder ponderar por pixeles
    cuando dos escenas caen en el mismo intervalo)."""
    nir_banda = BANDA_NIR[escena["sensor"]]
    with rasterio.Env(**_ENTORNO):
        rojo, dentro = _leer_ventana(_url_firmada(token, escena["activos"]["B04"]), geometria)
        nir, _ = _leer_ventana(_url_firmada(token, escena["activos"][nir_banda]), geometria)
        fmask, _ = _leer_ventana(_url_firmada(token, escena["activos"]["Fmask"]), geometria)
    if not (rojo.shape == nir.shape == fmask.shape):
        raise ErrorHLS("las bandas de la escena no coinciden en tamano")
    ok = pixeles_validos(rojo, nir, fmask, dentro)
    r, n = rojo[ok].astype(float), nir[ok].astype(float)
    return {"fecha": escena["fecha"], "sensor": escena["sensor"], "pixeles": int(dentro.sum()),
            "validos": int(ok.sum()), "suma_ndvi": float(((n - r) / (n + r)).sum())}


def ndvi_de_escenas(token: str, escenas: list[dict], geometria: dict) -> list[dict]:
    """Lee las escenas de a LECTURAS_SIMULTANEAS. Una escena que falla por un motivo propio (archivo
    corrupto, tesela sin la ventana) se salta; un token rechazado detiene todo, porque fallaria igual en
    cada una."""
    def una(escena):
        for intento in range(INTENTOS_POR_ESCENA):
            try:
                return ndvi_de_escena(token, escena, geometria)
            except ErrorHLS as error:
                if "token" in str(error):
                    raise
                return None
            except (rasterio.errors.RasterioIOError, requests.RequestException):
                continue   # las lecturas por rango fallan de vez en cuando (medido: 1 de 16)
        return None
    with ThreadPoolExecutor(LECTURAS_SIMULTANEAS) as pool:
        return [l for l in pool.map(una, escenas) if l is not None]


def ndvi_pixeles(token: str, escena: dict, geometria: dict) -> dict:
    """El NDVI de cada pixel de la escena dentro del poligono: {'fecha', 'sensor', 'ndvi' (NaN donde hay nube,
    sombra, nieve, agua o no hay dato), 'dentro', 'transform', 'crs'}. Para dibujar el predio pixel a pixel."""
    nir_banda = BANDA_NIR[escena["sensor"]]
    with rasterio.Env(**_ENTORNO):
        rojo, dentro, transform, crs = _leer(_url_firmada(token, escena["activos"]["B04"]), geometria)
        nir, _, _, _ = _leer(_url_firmada(token, escena["activos"][nir_banda]), geometria)
        fmask, _, _, _ = _leer(_url_firmada(token, escena["activos"]["Fmask"]), geometria)
    if not (rojo.shape == nir.shape == fmask.shape):
        raise ErrorHLS("las bandas de la escena no coinciden en tamano")
    ok = pixeles_validos(rojo, nir, fmask, dentro)
    r, n = rojo.astype(float), nir.astype(float)
    ndvi = np.full(rojo.shape, np.nan)
    ndvi[ok] = (n[ok] - r[ok]) / (n[ok] + r[ok])
    return {"fecha": escena["fecha"], "sensor": escena["sensor"], "ndvi": ndvi, "dentro": dentro,
            "transform": transform, "crs": crs}


def visible_de(pixeles: dict) -> float:
    """Fraccion de los pixeles del poligono que se ven (sin nube ni sombra)."""
    total = int(pixeles["dentro"].sum())
    return float(np.isfinite(pixeles["ndvi"]).sum() / total) if total else 0.0


def ndvi_por_celda(pixeles: dict, celdas: list[dict]) -> dict[tuple[int, int], tuple[float | None, float]]:
    """{(i, j): (NDVI medio, visible)} para cada celda ({'i', 'j', 'geometria' en lon/lat}). Cuenta los pixeles
    cuyo centro cae dentro de la celda; una celda mas chica que un pixel usa el pixel que toca. `visible` es la
    parte de esos pixeles sin nube; el NDVI es None si no se ve ninguno."""
    forma = pixeles["ndvi"].shape
    salida = {}
    for c in celdas:
        poligono = transform_geom("EPSG:4326", pixeles["crs"], c["geometria"])
        dentro = ~geometry_mask([poligono], forma, pixeles["transform"])
        if not dentro.any():
            dentro = ~geometry_mask([poligono], forma, pixeles["transform"], all_touched=True)
        total = int(dentro.sum())
        valores = pixeles["ndvi"][dentro]
        validos = valores[np.isfinite(valores)]
        salida[(c["i"], c["j"])] = (float(validos.mean()) if validos.size else None,
                                    float(validos.size / total) if total else 0.0)
    return salida
