"""
Cliente Daymet v4 R1 -- tmin, tmax y lluvia diarios a 1 km para Norteamerica, Hawai y Puerto Rico (NASA ORNL
DAAC, https://doi.org/10.3334/ORNLDAAC/2129). Sin clave ni login. Hace en el resto del mundo el papel que CR2MET
hace en Chile: la referencia contra la que se mide el sesgo de POWER y de ERA5 (repositorio_clima).

VERIFICADO EN VIVO el 17-nov-2026 contra https://daymet.ornl.gov/single-pixel/api/data (servicio de un pixel):
  - Parametros: lat, lon, vars=tmin,tmax,prcp, format=csv y, o bien years=2024,2025, o bien start/end
    ('YYYY-MM-DD', los dos extremos incluidos). La respuesta es un CSV con unas lineas de encabezado de texto
    (latitud, tile, altura del pixel, cita) y luego `year,yday,prcp (mm/day),tmax (deg c),tmin (deg c)`.
  - Calendario de 365 dias: en los anos bisiestos trae el 29 de febrero y OMITE el 31 de diciembre (yday 365 es el
    30 de dic.). Se convierte con fecha = 1 de enero + yday - 1 y el 31 de dic. bisiesto queda como NaN.
  - Pedir un periodo que Daymet todavia no publico (hoy llega hasta el 31-dic-2025) no da error: devuelve TODO el
    registro desde 1980 (420 KB). Por eso se filtra por fecha del lado del cliente y se pide por `years`.
    Daymet publica el ano completo con meses de retraso: no hay dato del ano en curso.
  - Fuera de la cobertura (mar, Europa, Chile, el resto de America) responde HTTP 400 con "Daymet Tile was not
    found": aca se traduce en un DataFrame vacio, no en error.
  - Pedir por http:// responde 302 a https://: no se siguen redirecciones (la unica salida es el host de Daymet).

No viaja ningun dato de la persona: solo latitud y longitud, que quien llama redondea a 0,01 grados.
"""
from __future__ import annotations

import io
import pandas as pd
import requests

URL_BASE = "https://daymet.ornl.gov/single-pixel/api/data"
COLUMNAS = ("tmin", "tmax", "lluvia")
_VARIABLES = {"tmin": "tmin", "tmax": "tmax", "prcp": "lluvia"}
_UNIDADES = {"tmin": "deg c", "tmax": "deg c", "prcp": "mm/day"}
_BYTES_MAX = 4_000_000      # el registro completo 1980-2025 de tres variables pesa ~420 KB
_SIN_DATO = -9990.0         # relleno de Daymet: nunca es un valor real

# Cita de NASA ORNL DAAC segun la pagina del producto (earthdata.nasa.gov/data/catalog/ornl-cloud-daymet-daily-v4r1-2129-4.1).
CITA = ("Thornton, M. M., Shrestha, R., Wei, Y., Thornton, P. E., & Kao, S.-C. (2022). Daymet: Daily Surface Weather "
        "Data on a 1-km Grid for North America, Version 4 R1 (Version 4.1). ORNL Distributed Active Archive Center. "
        "https://doi.org/10.3334/ORNLDAAC/2129")


def en_caja(lat: float, lon: float) -> bool:
    """Descarte barato antes de salir a la red: la caja que contiene a Norteamerica, Hawai y Puerto Rico (Chile,
    Europa, Asia y el resto del mundo quedan fuera y no llaman a Daymet). No decide la cobertura -- dentro de la
    caja hay mar, y eso lo dice el servicio con su 400 --, solo evita consultas que seguro no tienen dato."""
    return 14.0 <= lat <= 84.0 and -180.0 <= lon <= -52.0


def _vacio() -> pd.DataFrame:
    return pd.DataFrame(columns=list(COLUMNAS), index=pd.DatetimeIndex([], name=None), dtype=float)


def _a_tabla(texto: str) -> pd.DataFrame:
    lineas = texto.splitlines()
    inicio = next((i for i, linea in enumerate(lineas) if linea.startswith("year,yday")), None)
    if inicio is None:
        raise ValueError("la respuesta de Daymet no trae la tabla de datos")
    crudo = pd.read_csv(io.StringIO("\n".join(lineas[inicio:])))
    columnas = {}
    for nombre in crudo.columns[2:]:
        variable, _, unidad = nombre.partition(" (")
        variable, unidad = variable.strip(), unidad.rstrip(")").strip().lower()
        if variable not in _VARIABLES or unidad != _UNIDADES[variable]:
            raise ValueError(f"columna inesperada en la respuesta de Daymet: {nombre!r}")
        columnas[nombre] = _VARIABLES[variable]
    if set(columnas.values()) != set(COLUMNAS):
        raise ValueError("la respuesta de Daymet no trae tmin, tmax y lluvia")
    fecha = pd.to_datetime(crudo["year"].astype(int).astype(str) + "-01-01") + pd.to_timedelta(crudo["yday"] - 1, unit="D")
    tabla = crudo.rename(columns=columnas)[list(COLUMNAS)].astype(float).set_axis(fecha)
    return tabla.where(tabla > _SIN_DATO)


def consultar_daymet(lat: float, lon: float, inicio: str, fin: str, timeout: int = 30) -> pd.DataFrame:
    """inicio/fin: 'YYYY-MM-DD'. Una fila por dia entre las dos fechas (tmin y tmax en C, lluvia en mm), con
    NaN en los dias sin dato (el 31 de diciembre de los anos bisiestos, y todo lo que Daymet aun no publica).
    DataFrame vacio si el punto cae fuera de la cobertura (las coordenadas fuera de en_caja() ni siquiera salen a la red). Cualquier otra falla (red, HTTP, formato) levanta."""
    if not en_caja(lat, lon):
        return _vacio()
    inicio_ts, fin_ts = pd.Timestamp(inicio), pd.Timestamp(fin)
    params = {"lat": f"{lat:.2f}", "lon": f"{lon:.2f}", "vars": ",".join(_VARIABLES), "format": "csv",
              "years": ",".join(str(a) for a in range(inicio_ts.year, fin_ts.year + 1))}
    with requests.get(URL_BASE, params=params, timeout=timeout, allow_redirects=False, stream=True) as r:
        if r.status_code == 400 and "Tile was not found" in r.text[:500]:
            return _vacio()
        if 300 <= r.status_code < 400:
            raise requests.HTTPError(f"Daymet redirigio ({r.status_code}); no se sigue", response=r)
        r.raise_for_status()
        cuerpo = b""
        for trozo in r.iter_content(65536):
            cuerpo += trozo
            if len(cuerpo) > _BYTES_MAX:
                raise ValueError("la respuesta de Daymet es mas grande de lo esperado")
    tabla = _a_tabla(cuerpo.decode("utf-8", errors="replace"))
    return tabla.reindex(pd.date_range(inicio_ts, fin_ts, freq="D"))
