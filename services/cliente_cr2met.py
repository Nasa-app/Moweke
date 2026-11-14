"""
Cliente CR2MET v0.1 -- precipitacion y temperatura diaria para Chile, CR2 (Universidad
de Chile). Extension post-MVP (ver plan, "Extension futura"). VERIFICADO POR EJECUCION
contra el punto de prueba de Chiloe (-42.45, -73.78).

A diferencia de cliente_power.py (REST puntual, sin descarga) esto distribuye grillas
mensuales en NetCDF -- hay que descargar el archivo del mes y extraer el pixel mas
cercano, no hay API de consulta por punto. Por eso esto necesita xarray/netCDF4
(agregados a requirements.txt), que cliente_power.py no necesitaba.

Latencia real verificada: el archivo NRT de un mes se actualiza (`creation_date`) todos
los dias, pero el ultimo dia con dato real quedo 9 dias detras de "hoy" en la prueba
(archivo de noviembre 2026 descargado el 14, con datos solo hasta el dia 5) -- confirma
el ~9 dias de latencia mencionado, no es un dato en vivo como POWER.

Cobertura 0.05 grados (~5km) desde 1960 -- mejor resolucion que POWER para Chile, pero
el aviso de la documentacion de menor desempeno en el extremo norte/sur (desierto de
Atacama, Patagonia austral) no se verifico aqui -- Chiloe esta lejos de esos extremos.
"""
from __future__ import annotations

import os
import time
from datetime import date, timedelta

import pandas as pd
import requests
import xarray as xr

URL_BASE = "https://ftp.cr2.cl/download/cr2met/v2.5_NRT"

# Un archivo por variable por mes -- 'pr' trae precipitacion sola, 'txn' trae tmin+tmax
# juntas en el mismo NetCDF (verificado: variables reales dentro del archivo son
# exactamente 'tmin'/'tmax', coinciden con lo que el motor espera sin renombrar).
_PATRON_ARCHIVO = {
    "pr": "{base}/pr/v2.5_NRT_day/CR2MET_pr_v2.5_NRT_day_{anio}_{mes:02d}_005deg.nc",
    "txn": "{base}/txn/v2.5_NRT_day/CR2MET_tmin_tmax_v2.5_NRT_day_{anio}_{mes:02d}_005deg.nc",
}


def _ruta_cache(directorio_cache: str, variable: str, anio: int, mes: int) -> str:
    os.makedirs(directorio_cache, exist_ok=True)
    return os.path.join(directorio_cache, f"cr2met_{variable}_{anio}_{mes:02d}.nc")


# El producto NRT llega con ~9 dias de atraso: el archivo de un mes solo queda completo
# unos dias despues de que el mes termina.
DIAS_HASTA_MES_DEFINITIVO = 10


def _cache_vencido(ruta: str, anio: int, mes: int) -> bool:
    """BUG REAL que esto corrige: un .nc en cache se reusaba para siempre, aunque se
    hubiera bajado con el mes a medias -- el mes en curso (y el anterior, durante sus
    primeros dias) nunca se completaba. Un archivo es definitivo si se bajo despues de
    que su mes quedo completo; mientras no lo sea, se vuelve a bajar una vez al dia."""
    fin_mes = (date(anio, mes, 28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    bajado = os.path.getmtime(ruta)
    if date.fromtimestamp(bajado) >= fin_mes + timedelta(days=DIAS_HASTA_MES_DEFINITIVO):
        return False
    return time.time() - bajado > 24 * 3600


def descargar_mes(variable: str, anio: int, mes: int, directorio_cache: str, timeout: int = 60) -> str:
    """variable: 'pr' | 'txn'. Reusa el archivo si ya esta en cache -- los .nc de meses
    pasados no cambian (solo el mes en curso se reescribe, y aun asi solo agrega dias,
    no corrige retroactivo segun lo observado)."""
    destino = _ruta_cache(directorio_cache, variable, anio, mes)
    if os.path.exists(destino) and not _cache_vencido(destino, anio, mes):
        return destino
    url = _PATRON_ARCHIVO[variable].format(base=URL_BASE, anio=anio, mes=mes)
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    # Escritura atomica: una descarga cortada no deja un .nc a medias que la proxima
    # llamada tomaria por cache valido.
    parcial = f"{destino}.{os.getpid()}.parcial"
    with open(parcial, "wb") as f:
        f.write(r.content)
    os.replace(parcial, destino)
    return destino


def _extraer_punto(archivo_nc: str, lat: float, lon: float) -> pd.DataFrame:
    with xr.open_dataset(archivo_nc) as ds:
        punto = ds.sel(lat=lat, lon=lon, method="nearest")
        # .to_dataframe() arrastra lat/lon como columnas (quedan como coordenadas
        # escalares tras el .sel) -- se seleccionan solo las variables de dato reales
        # (nunca 'cl_mask', esa es la mascara de tierra/mar del producto, no un dato).
        variables = [v for v in ds.data_vars if v != "cl_mask"]
        return punto.to_dataframe()[variables]


def consultar_cr2met(lat: float, lon: float, inicio: str, fin: str, directorio_cache: str,
                      timeout: int = 60) -> pd.DataFrame:
    """inicio/fin: 'YYYY-MM-DD'. Descarga (o reusa) los meses necesarios de pr y txn,
    extrae el pixel mas cercano a (lat, lon), y devuelve el DataFrame con las mismas
    columnas que cliente_power.consultar_power() (tmin, tmax, lluvia) para que el motor
    pueda consumir cualquiera de las dos fuentes sin cambiar pheno_engine/motor_estres.
    Sin columna 'rh' -- CR2MET no trae humedad relativa, motor_estres.evaluar() ya sabe
    tratar 'tizon' como no evaluable si falta esa columna."""
    inicio_ts, fin_ts = pd.Timestamp(inicio), pd.Timestamp(fin)
    meses = pd.period_range(inicio_ts, fin_ts, freq="M")
    partes = []
    for periodo in meses:
        archivo_pr = descargar_mes("pr", periodo.year, periodo.month, directorio_cache, timeout)
        archivo_txn = descargar_mes("txn", periodo.year, periodo.month, directorio_cache, timeout)
        pr = _extraer_punto(archivo_pr, lat, lon)
        txn = _extraer_punto(archivo_txn, lat, lon)
        partes.append(pr.join(txn, how="outer"))
    clima = pd.concat(partes).sort_index()
    clima = clima.loc[inicio_ts:fin_ts]
    return clima.rename(columns={"pr": "lluvia"})[["tmin", "tmax", "lluvia"]]
