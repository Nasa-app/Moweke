"""
Cliente HAND (altura sobre el cauce mas cercano) global a 30 m, del Alaska Satellite
Facility (centro de datos de la NASA), calculado sobre Copernicus DEM GLO-30.

Fuente: el mosaico publico en AWS Open Data (bucket glo-30-hand): un GeoTIFF optimizado
para la nube por cada grado de latitud y longitud, con la misma grilla que el DEM GLO-30
que ya usa cliente_dem. Se lee solo la ventana del predio por peticiones HTTP de rango:
sin cuenta, sin clave.

VERIFICADO POR EJECUCION (15-nov-2026): una baldosa del Maule respondio en el bucket, en
EPSG:4326, float32, pixel de 1 segundo de arco, sin valor nodata declarado.

Que mide: la diferencia de altura entre cada pixel y el cauce al que drena. No es una
probabilidad de crecida: no sabe de lluvia, caudales, diques, alcantarillado ni mareas.
Sirve para separar lo que queda pegado al cauce de lo que queda bien por encima de el.
El pixel del propio cauce vale 0.

Advertencias reales:
  - Hereda el DEM de superficie: copas de arboles y construcciones mueven el valor.
  - A 30 m no resuelve zanjas ni canales de riego pequenos: un cauce menor a ese ancho
    puede no aparecer, y el HAND se mide hacia otro cauce mas lejano.
  - Los datos son abiertos pero piden atribucion (ASF DAAC, con Copernicus DEM GLO-30).
    El texto de la licencia no se reviso aca.
"""
from __future__ import annotations

import math

import rasterio
from rasterio.windows import Window, from_bounds

URL_BASE = "https://glo-30-hand.s3.amazonaws.com/v1/2021"
_ENTORNO = {"GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR", "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
            "GDAL_HTTP_TIMEOUT": "60", "GDAL_HTTP_MAX_RETRY": "2"}


def _url_baldosa(lat_sur: int, lon_oeste: int) -> str:
    """La baldosa de un grado cuyo vertice suroeste es (lat_sur, lon_oeste)."""
    ns, ew = ("S" if lat_sur < 0 else "N"), ("W" if lon_oeste < 0 else "E")
    return f"{URL_BASE}/Copernicus_DSM_COG_10_{ns}{abs(lat_sur):02d}_00_{ew}{abs(lon_oeste):03d}_00_HAND.tif"


def leer_hand(lon_min: float, lat_min: float, lon_max: float, lat_max: float) -> list[dict]:
    """El HAND (m) de la caja pedida (WGS84). Una entrada por baldosa de un grado que la
    caja toque -- casi siempre una sola: {'altitud' (m sobre el cauce), 'transform' (affine
    de la ventana), 'crs'}. La clave se llama 'altitud' para que el mismo agrupador por
    celda sirva al DEM y al HAND. Una baldosa que no existe (mar abierto) se salta."""
    salida = []
    with rasterio.Env(**_ENTORNO):
        for lat_sur in range(math.floor(lat_min), math.floor(lat_max) + 1):
            for lon_oeste in range(math.floor(lon_min), math.floor(lon_max) + 1):
                try:
                    ds = rasterio.open("/vsicurl/" + _url_baldosa(lat_sur, lon_oeste))
                except rasterio.errors.RasterioIOError:
                    continue
                with ds:
                    pedida = from_bounds(lon_min, lat_min, lon_max, lat_max, ds.transform)
                    col0 = max(0, math.floor(pedida.col_off))
                    fil0 = max(0, math.floor(pedida.row_off))
                    col1 = min(ds.width, math.ceil(pedida.col_off + pedida.width))
                    fil1 = min(ds.height, math.ceil(pedida.row_off + pedida.height))
                    if col1 <= col0 or fil1 <= fil0:
                        continue
                    ventana = Window(col0, fil0, col1 - col0, fil1 - fil0)
                    salida.append({"altitud": ds.read(1, window=ventana).astype(float),
                                   "transform": ds.window_transform(ventana), "crs": ds.crs})
    return salida
