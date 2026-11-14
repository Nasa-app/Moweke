"""
Cliente CLSoilMaps v0.1 -- capacidad de campo, punto de marchitez y agua disponible,
Chile completo, 100m, CC-BY-4.0 (Dondé et al./CR2, Zenodo 10.5281/zenodo.7464210).
Extension post-MVP (ver plan).

VERIFICADO POR EJECUCION, con un hallazgo real: el zip de Zenodo (ROSETTA_MEAN.zip,
10GB) SI soporta HTTP Range requests (`accept-ranges: bytes`, confirmado con curl) --
la primera verificacion de este modulo dijo lo contrario, estaba mal hecha (un -H
"Range:" manual no se comporto igual que curl -r). Esto permite extraer SOLO el archivo
que hace falta del zip remoto sin bajar los 10GB completos: se listo el contenido real
con solo 4 peticiones HTTP (el central directory del zip esta al final, es chico), y
'Total_AWC_0_200cm.tif' -- agua disponible ya sumada en las 6 profundidades estandar,
exactamente lo que motor_estres.balance_agua() necesita como `capacidad_mm` -- pesa
328.6 MB comprimido (DEFLATE) dentro del zip, no 10GB.

Limitacion real: esta DEFLATE-comprimido, no STORED -- no se puede leer una ventana
pequena sin decodificar el stream completo desde el principio (zlib no es seekable a
mitad de stream). Por eso esto extrae el archivo completo de 328MB (no solo un pixel)
la primera vez, lo guarda localmente, y de ahi en adelante cualquier consulta de punto
es una lectura local instantanea con rasterio -- no vuelve a tocar la red.
"""
from __future__ import annotations

import os
import zipfile

import rasterio
import requests

URL_ROSETTA_MEAN = "https://zenodo.org/records/7464210/files/ROSETTA_MEAN.zip"


class _ArchivoZipRemoto:
    """File-like sobre HTTP Range con buffer de lectura adelantada -- sin esto, zipfile
    pide de a pocos KB por llamada y se gastan las ~130 peticiones/minuto que Zenodo
    permite (ver 'x-ratelimit-limit' real observado) en segundos. Con un buffer de 8MB
    por peticion, extraer un archivo de cientos de MB son decenas de peticiones, no miles."""

    def __init__(self, url: str, tamano_buffer: int = 8 * 1024 * 1024, timeout: int = 60):
        self.url, self.timeout, self.tamano_buffer = url, timeout, tamano_buffer
        self.size = int(requests.head(url, timeout=timeout).headers["content-length"])
        self.pos = 0
        self._buf_inicio = self._buf_fin = -1
        self._buf = b""
        self.peticiones = 0

    def seek(self, offset, whence=0):
        if whence == 0:
            self.pos = offset
        elif whence == 1:
            self.pos += offset
        elif whence == 2:
            self.pos = self.size + offset
        return self.pos

    def tell(self):
        return self.pos

    def seekable(self) -> bool:
        return True

    def read(self, n: int = -1) -> bytes:
        fin_pedido = self.size - 1 if n is None or n < 0 else min(self.pos + n - 1, self.size - 1)
        if self.pos > fin_pedido:
            return b""
        if not (self._buf_inicio <= self.pos and fin_pedido <= self._buf_fin):
            self._rellenar_buffer(self.pos, fin_pedido)
        datos = self._buf[self.pos - self._buf_inicio: fin_pedido - self._buf_inicio + 1]
        self.pos = fin_pedido + 1
        return datos

    def _rellenar_buffer(self, desde: int, hasta_al_menos: int) -> None:
        fin = min(desde + max(self.tamano_buffer, hasta_al_menos - desde + 1) - 1, self.size - 1)
        self.peticiones += 1
        r = requests.get(self.url, headers={"Range": f"bytes={desde}-{fin}"}, timeout=self.timeout)
        r.raise_for_status()
        self._buf, self._buf_inicio, self._buf_fin = r.content, desde, fin


def listar_contenido(url_zip: str = URL_ROSETTA_MEAN, timeout: int = 60) -> list[str]:
    """Lista los nombres reales dentro del zip remoto SIN descargarlo -- solo lee el
    central directory (al final del archivo). Verificado: 4 peticiones HTTP, 56 entradas."""
    archivo = _ArchivoZipRemoto(url_zip, timeout=timeout)
    return zipfile.ZipFile(archivo).namelist()


def extraer_archivo(ruta_interna: str, destino_local: str, url_zip: str = URL_ROSETTA_MEAN,
                     timeout: int = 60) -> str:
    """Descarga y descomprime SOLO `ruta_interna` del zip remoto -- el resto del zip
    (los otros ~54 archivos) nunca se transfiere. DEFLATE no es seekable a mitad de
    stream, asi que esto si transfiere el archivo completo (no una ventana), pero sigue
    siendo ~30x menos que bajar el zip entero para una sola variable."""
    if os.path.exists(destino_local):
        return destino_local
    archivo = _ArchivoZipRemoto(url_zip, timeout=timeout)
    with zipfile.ZipFile(archivo) as zf:
        with zf.open(ruta_interna) as origen, open(destino_local, "wb") as salida:
            while True:
                bloque = origen.read(1024 * 1024)
                if not bloque:
                    break
                salida.write(bloque)
    return destino_local


def leer_valor_punto(archivo_tif: str, lat: float, lon: float) -> float | None:
    """Lectura local con rasterio -- instantanea, una vez que extraer_archivo() ya trajo
    el .tif. Devuelve None si el punto cae en el nodata del raster (ej. fuera de Chile,
    o mar)."""
    with rasterio.open(archivo_tif) as ds:
        fila, columna = ds.index(lon, lat)
        # (lat, lon) fuera de la extension real del raster (ej. fuera de Chile) --
        # ds.index() no lanza error para esto, solo devuelve una fila/columna que cae
        # fuera de la grilla. BUG REAL encontrado al probar con un punto del Atlantico:
        # la lectura de ventana tiraba IndexError en vez de un None honesto.
        if not (0 <= fila < ds.height and 0 <= columna < ds.width):
            return None
        valor = ds.read(1, window=((fila, fila + 1), (columna, columna + 1)))[0, 0]
        nodata = ds.nodata
        if nodata is not None and valor == nodata:
            return None
        if valor != valor:  # NaN real dentro de la extension (ej. mar, segun el propio raster)
            return None
        return float(valor)
