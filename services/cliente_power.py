"""
Cliente NASA POWER v0.1
========================
La unica fuente del catalogo (docs/modelo-conceptual-phenoshield.md seccion 4) que se
consulta por REST directo, sin login -- por eso es la unica que se puede probar con
ejecucion real en cualquier entorno con salida a internet, sin credenciales de Earthdata.

Genera exactamente el DataFrame que services/pheno_engine.simular() y
services/motor_estres.balance_agua() esperan como `clima`: indice de fechas diario,
columnas tmin, tmax (C), lluvia (mm), rh (% HR, para el riesgo de tizon).

BUG REAL encontrado al verificar si de verdad se estaba pidiendo radiacion solar/
insolacion a POWER (se habia dado por hecho que si, nunca se habia revisado el codigo):
nunca se pidio. `MAPEO_COLUMNAS` solo tenia T2M_MIN/T2M_MAX/PRECTOTCORR/RH2M -- la
radiacion real que el proyecto usa viene solo del Explorador Solar (climatologia
2004-2016, no diaria). Corregido: se agrega `ALLSKY_SFC_SW_DWN` -> columna `radiacion`
(MJ/m2/dia, verificado en vivo para Quemchi: 7-22 MJ/m2/dia en noviembre, consistente
con el ciclo estacional real -42S). Util para reemplazar la aproximacion Hargreaves de
`motor_estres.balance_agua()` con radiacion medida real cuando se calibre ese cambio --
todavia no se cambio esa funcion, solo se agrego el dato a la fuente.

HLS/SMAP/MOD13Q1/ECOSTRESS/SRTM no siguen este patron -- van por AppEEARS (Earthdata
Login + jobs asincronos, ver services/cliente_appeears.py). No alimentan directamente
este DataFrame: HLS da la curva EVI (detect_curve_anomaly), SMAP da humedad de suelo
regional, no una columna mas de este clima diario.
"""
from __future__ import annotations

import pandas as pd
import requests

URL_BASE = "https://power.larc.nasa.gov/api/temporal/daily/point"

# Nombres de columna de POWER -> nombres que el motor espera. RH2M entra directo como
# `rh` porque motor_estres.alertas() y pheno_engine lo usan tal cual (riesgo de tizon).
#
# GWETROOT / GWETTOP: humedad del suelo de NASA, "la proporcion del maximo que el suelo puede almacenar"
# (0 a 1), para la zona de raices (~1 m) y la superficie. Es un reanalisis de ~50 km de celda: sirve de
# contexto regional, no es una medicion del predio ni equivale al agua aprovechable del balance FAO-56.
# VERIFICADO en vivo (Castro, nov-2026): se piden en la misma llamada, sin credenciales.
MAPEO_COLUMNAS = {"T2M_MIN": "tmin", "T2M_MAX": "tmax", "PRECTOTCORR": "lluvia", "RH2M": "rh",
                   "ALLSKY_SFC_SW_DWN": "radiacion",
                   "GWETROOT": "humedad_suelo_raiz", "GWETTOP": "humedad_suelo_superficie"}

VALOR_SIN_DATO = -999.0  # asi marca POWER los dias sin dato -- NO es un cero real


def consultar_power(lat: float, lon: float, inicio: str, fin: str, timeout: int = 20) -> pd.DataFrame:
    """inicio/fin: 'YYYY-MM-DD'. Devuelve el DataFrame listo para el motor, con los dias
    sin dato de POWER como NaN -- nunca como -999 crudo, porque eso rompe silenciosamente
    cualquier calculo de GDD o balance de agua que lo tome como temperatura real."""
    params = {
        "parameters": ",".join(MAPEO_COLUMNAS.keys()),
        "community": "ag",
        "longitude": lon,
        "latitude": lat,
        "start": inicio.replace("-", ""),
        "end": fin.replace("-", ""),
        "format": "JSON",
    }
    r = requests.get(URL_BASE, params=params, timeout=timeout)
    r.raise_for_status()
    datos = r.json()["properties"]["parameter"]

    df = pd.DataFrame({
        MAPEO_COLUMNAS[col]: pd.Series(valores, dtype=float)
        for col, valores in datos.items()
    })
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    # float("nan"), no pd.NA: con pd.NA el astype(float) revienta apenas hay un dia sin
    # dato (TypeError) -- y los ultimos dias de cualquier consulta reciente vienen asi.
    return df.replace(VALOR_SIN_DATO, float("nan")).astype(float)


URL_CLIMATOLOGIA = "https://power.larc.nasa.gov/api/temporal/climatology/point"

# ADVERTENCIA REAL, no teorica: T2M_MAX/T2M_MIN en climatologia NO son el promedio de
# maximas/minimas diarias -- son el extremo historico (la hora mas caliente/fria jamas
# registrada ese mes en todo el periodo). Para un promedio real hay que pedir
# T2M_MAX_AVG/T2M_MIN_AVG. Verificado contra la API en vivo: T2M_MAX para Castro daba
# 27-32C (extremo, implausible como "tipico"), T2M_MAX_AVG daba 12-23C (promedio real,
# consistente con el clima oceanico templado de Chiloe). Usar el nombre equivocado
# produciria una anomalia falsa, no un error -- por eso queda fijo aqui, no configurable.
# ALLSKY_SFC_SW_DWN en climatologia SI es el promedio real (a diferencia de T2M_MAX/MIN) --
# verificado en vivo: ciclo estacional plausible para -42S (min. ~4 MJ/m2/dia en jun/jul,
# max. ~22-23 en dic/ene), no hace falta sufijo _AVG para este parametro.
MAPEO_CLIMATOLOGIA = {"T2M_MIN_AVG": "tmin", "T2M_MAX_AVG": "tmax", "PRECTOTCORR": "lluvia", "RH2M": "rh",
                       "ALLSKY_SFC_SW_DWN": "radiacion"}

MESES = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def consultar_climatologia(lat: float, lon: float, timeout: int = 20) -> pd.DataFrame:
    """Promedio historico mensual para el mismo punto (serie larga de POWER, no un
    numero inventado) -- la base contra la que se mide si un dia/mes esta siendo
    anomalo. Un valor por mes, no por dia: comparar un dia puntual contra esto es
    aproximado (el promedio mensual no captura variacion dentro del mes), suficiente
    para una primera senal, no para precision fina."""
    params = {
        "parameters": ",".join(MAPEO_CLIMATOLOGIA.keys()),
        "community": "ag", "longitude": lon, "latitude": lat, "format": "JSON",
    }
    r = requests.get(URL_CLIMATOLOGIA, params=params, timeout=timeout)
    r.raise_for_status()
    datos = r.json()["properties"]["parameter"]
    return pd.DataFrame({MAPEO_CLIMATOLOGIA[col]: [valores[m] for m in MESES]
                          for col, valores in datos.items()}, index=MESES)


MJ_POR_KWH = 3.6
# Periodo que POWER declara para su climatologia (encabezado v2.10.1 del 15-nov-2026: "25-year ... January
# 2001 - December 2025"). La radiacion viene de CERES SYN1deg, celda de 1 grado (~100 km).
PERIODO_CLIMATOLOGIA = ("2001-01-01", "2025-12-31")


def ghi_mensual_kwh(climatologia: pd.DataFrame) -> list[float | None]:
    """Radiacion global horizontal media de cada mes (kWh/m2/dia, enero primero) a partir de
    consultar_climatologia(), que la entrega en MJ/m2/dia. Un mes sin dato (-999) queda en None."""
    return [None if v != v or v < 0 else float(v) / MJ_POR_KWH for v in climatologia.loc[MESES, "radiacion"]]


def anomalia_diaria(clima_actual: pd.DataFrame, climatologia: pd.DataFrame) -> pd.DataFrame:
    """Compara cada dia de `clima_actual` contra el promedio historico de SU PROPIO mes,
    para el mismo punto -- esto es la comparacion "contra si mismo" que le faltaba a una
    consulta de grilla simple. Positivo = mas caliente/humedo/lluvioso que lo normal para
    esa fecha; negativo = menos. Alimenta get_climate_anomaly_shift_power del dispatcher
    de bioma (docs/modelo-conceptual-phenoshield.md 7.2), no reemplaza la comparacion
    contra el fenomeno observado por el agricultor -- esa sigue siendo
    pheno_engine.ajustar_indicador/delta_microclima, y esa SI necesita un dato real de
    campo que todavia no existe."""
    mes = clima_actual.index.month.map(lambda m: MESES[m - 1])
    normal = climatologia.loc[mes]
    normal.index = clima_actual.index
    columnas = [c for c in ("tmin", "tmax", "lluvia", "rh", "radiacion") if c in clima_actual.columns]
    return clima_actual[columnas] - normal[columnas]


def cobertura(df: pd.DataFrame) -> str:
    """'completa' | 'parcial_nubes' | 'sin_dato' -- mismo campo que cache_consulta_grilla.
    POWER no depende de nubes (es un reanalisis, no observacion optica), pero igual puede
    faltar un dia puntual -- se usa el mismo vocabulario del resto del proyecto en vez de
    inventar uno nuevo solo para esta fuente."""
    if df.isna().all().all():
        return "sin_dato"
    if df.isna().any().any():
        return "parcial_nubes"
    return "completa"
