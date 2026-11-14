"""
Cliente Copernicus DEM GLO-30 v0.1 -- elevacion a 1 segundo de arco (~30 m), para el
relieve y la pendiente dentro de un predio.

Fuente: el mosaico publico de Copernicus DEM en AWS Open Data (un GeoTIFF optimizado
para la nube por cada grado de latitud y longitud). Se lee solo la ventana del predio
por peticiones HTTP de rango: sin cuenta, sin clave, sin bajar el archivo de un grado.

VERIFICADO POR EJECUCION (14-nov-2026): San Fernando y Quemchi, ventana de ~900 m en 1 a
4 segundos; altitud y pendiente coherentes con el terreno (valle casi plano: pendiente
mediana 1,4 %; lomajes de Chiloe: 12,7 %).

Por que no por la cuenta de Copernicus que ya usa el proyecto: probado, el modelo de
30 m responde 403 con esas credenciales (solo esta habilitado el de 90 m, mas grueso que
una celda de un acre).

Tres advertencias reales:
  - Es un modelo de SUPERFICIE, no de terreno: incluye copas de arboles y construcciones.
    El borde de un bosque o un galpon aparece como una pendiente que no existe en el suelo.
  - A 30 m, una diferencia de un par de puntos de pendiente entre celdas vecinas no es
    significativa; sirve para separar lo plano de lo inclinado, no para nivelar un potrero.
  - Los datos son abiertos pero piden atribucion (Copernicus DEM, DLR/Airbus, provisto
    por la UE y ESA). El texto de la licencia no se reviso aca.
"""
from __future__ import annotations

import math

import numpy as np
import rasterio
from rasterio.windows import Window, from_bounds

URL_BASE = "https://copernicus-dem-30m.s3.amazonaws.com"
_ENTORNO = {"GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR", "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
            "GDAL_HTTP_TIMEOUT": "60", "GDAL_HTTP_MAX_RETRY": "2"}
MARGEN_PIXELES = 2   # borde extra alrededor de la ventana, para que la pendiente tenga vecinos


def _url_baldosa(lat_sur: int, lon_oeste: int) -> str:
    """La baldosa de un grado cuyo vertice suroeste es (lat_sur, lon_oeste)."""
    ns, ew = ("S" if lat_sur < 0 else "N"), ("W" if lon_oeste < 0 else "E")
    nombre = f"Copernicus_DSM_COG_10_{ns}{abs(lat_sur):02d}_00_{ew}{abs(lon_oeste):03d}_00_DEM"
    return f"{URL_BASE}/{nombre}/{nombre}.tif"


def leer_relieve(lon_min: float, lat_min: float, lon_max: float, lat_max: float) -> list[dict]:
    """Altitud y pendiente de la caja pedida (WGS84). Una entrada por baldosa de un grado
    que la caja toque -- casi siempre una sola: {'altitud' (m), 'pendiente' (%),
    'transform' (affine de la ventana), 'crs'}. La pendiente se calcula con diferencias
    entre pixeles vecinos, pasando el tamano del pixel a metros en la latitud de la caja.
    Una baldosa que no existe (mar abierto) se salta."""
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
                    col0 = max(0, math.floor(pedida.col_off) - MARGEN_PIXELES)
                    fil0 = max(0, math.floor(pedida.row_off) - MARGEN_PIXELES)
                    col1 = min(ds.width, math.ceil(pedida.col_off + pedida.width) + MARGEN_PIXELES)
                    fil1 = min(ds.height, math.ceil(pedida.row_off + pedida.height) + MARGEN_PIXELES)
                    if col1 - col0 < 2 or fil1 - fil0 < 2:
                        continue
                    ventana = Window(col0, fil0, col1 - col0, fil1 - fil0)
                    altitud = ds.read(1, window=ventana).astype(float)
                    transform = ds.window_transform(ventana)
                    metros_x = abs(ds.res[0]) * 111_320 * math.cos(math.radians((lat_min + lat_max) / 2))
                    metros_y = abs(ds.res[1]) * 110_540
                    hacia_y, hacia_x = np.gradient(altitud, metros_y, metros_x)
                    salida.append({"altitud": altitud, "pendiente": 100 * np.hypot(hacia_x, hacia_y),
                                   "transform": transform, "crs": ds.crs})
    return salida
