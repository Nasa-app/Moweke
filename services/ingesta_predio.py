"""
Ingesta de un predio v0.1 -- las cuatro fuentes que alimentan la idoneidad
(catalogo_especies.ranking_idoneidad), corridas solas al crear la parcela en vez de
dispararse a mano por los endpoints /api/admin/.../ingesta/*.

  explorador_solar  GHI anual y mensual 2004-2016 (radiacion) + elevacion del punto
  soilgrids         pH, textura, carbono organico
  cr2met            tmin/tmax/lluvia diarios de los ultimos doce meses completos
  clsoilmaps        agua disponible total del suelo (0-200 cm)
  relieve           altitud y pendiente de cada celda de la grilla del predio (Copernicus
                    DEM GLO-30, datos abiertos, sin credenciales). Dato fijo: corre una vez
  inundacion        altura sobre el cauce mas cercano (HAND de ASF, 30 m, sobre Copernicus
                    DEM GLO-30; abierto, sin credenciales) por celda de la grilla. Dato fijo
  sentinel2_nubes   cuantas pasadas despejadas de Sentinel-2 hubo en 24 meses (catalogo
                    publico, sin credenciales): decide si en el predio vale la pena
                    seguir el cultivo con la curva optica del satelite

Y las que alimentan el seguimiento diario de un cultivo
(catalogo_especies.seguimiento_cultivo). Vencen: se vuelven a correr cuando su ultimo
dato tiene mas de HORAS_VIGENCIA_DIARIA.

  power             tmin/tmax/lluvia/humedad relativa/radiacion diarios hasta hace ~3 dias
  open_meteo        los ultimos dias segun modelo y el pronostico a 16 dias
  firms             focos de calor de los ultimos 5 dias cerca del predio (solo si hay
                    FIRMS_MAP_KEY en el entorno; sin clave la fuente queda 'sin_configurar')
  sentinel2_ndvi    NDVI del poligono cada 5 dias, con la fraccion del predio que se vio.
                    Necesita COPERNICUS_CLIENT_ID/SECRET, y solo corre donde sentinel2_nubes
                    midio cielo suficientemente despejado ('no_aplica' en el resto)
  sentinel2_celdas  el mismo NDVI pero por celda de la grilla del predio (cache_celda):
                    es lo que dibuja el mapa. Corre en cualquier zona -- en una nublada el
                    mapa muestra datos mas viejos, y lo dice

CR2MET tambien vence, una vez al mes: la ventana de doce meses se corre el dia 1 y el
mes recien terminado solo queda completo hacia el dia 10 (ver estado_ingesta).

AppEEARS, Copernicus y FIRMS quedan fuera a proposito: no entran a ninguno de los dos
calculos.

Quien dispara esto: el propio agricultor al crear una parcela o consultar (encolar +
tarea en segundo plano de la API), y services/tarea_refresco_clima.py desde un cron.

Cada fuente deja una fila en job_extraccion por intento (pendiente -> en_proceso ->
completo | error). Una fuente que falla no detiene a las demas, y el detalle del error
queda en la base -- nunca se devuelve al agricultor, que solo ve el estado.

Las llamadas a los clientes son bloqueantes (requests, rasterio, xarray): van por
asyncio.to_thread para no congelar el resto de la API mientras se descarga.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from rasterio.features import geometry_mask
from rasterio.transform import xy
from rasterio.warp import transform as reproyectar

from services import (cliente_clsoilmaps, cliente_copernicus, cliente_cr2met, cliente_dem, cliente_firms,
                      cliente_hand, cliente_openmeteo, cliente_power, cliente_soilgrids, cliente_solar, db)
from services.motor_estres import calibrar_et0_mensual
from services.repositorio_clima import (CAPAS_ET0_FACTOR_MENSUAL, CAPAS_GHI_MENSUAL, CAPAS_GHI_POWER,
                                        CAPAS_DISPONIBILIDAD_OPTICA,
                                        FRACCION_MIN_CELDA, NUBOSIDAD_ESCENA_MAX_PCT, RADIO_INCENDIO_KM,
                                        VENTANA_OPTICA_DIAS, corregir_contra_cr2met, guardar_celdas,
                                        guardar_consultas_grilla, guardar_historia, leer_disponibilidad_optica,
                                        leer_grilla, ventana_clima)

log = logging.getLogger("ingesta_predio")

CACHE_CR2MET = os.environ.get("CR2MET_CACHE_DIR", "/tmp/cr2met_cache")
CACHE_CLSOILMAPS = os.environ.get("CLSOILMAPS_CACHE_DIR", "/tmp/clsoilmaps_cache")
CLSOILMAPS_ARCHIVO_INTERNO = "ROSETTA_MEAN/Total_AWC_0_200cm.tif"

# En este orden: las rapidas primero, CLSoilMaps al final (la primera extraccion de un
# despliegue tarda ~20 min y el ranking puede responder sin ese dato).
PRODUCTOS = {
    "explorador_solar": "vista_rapida_2004_2016",
    "soilgrids": "v2.0_0-5cm",
    "cr2met": "v2.5_nrt_diario",
    "clima_historico": "openmeteo_era5_v1",
    "power": "diario_ag",
    "open_meteo": "pronostico_16d",
    "firms": "VIIRS_NOAA20_NOAA21_NRT_5d",
    "sentinel2_nubes": "catalogo_L2A_24_meses",
    "relieve": "copernicus_dem_glo30",
    "inundacion": "asf_hand_glo30_v1",
    "sentinel2_ndvi": "L2A_ndvi_5d",
    "sentinel2_celdas": "L2A_ndvi_5d_por_celda",
    "clsoilmaps": "awc_total_0_200cm",
}
FUENTES = tuple(PRODUCTOS)
FUENTES_DIARIAS = frozenset({"power", "open_meteo", "firms", "sentinel2_ndvi", "sentinel2_celdas"})
DIAS_FIRMS = 5  # tope real de la API para productos _NRT
# Un sensor cuyo ultimo dato es mas viejo que esto se da por caido: su "cero focos" no
# vale como "sin incendios" (asi fallo en silencio VIIRS_SNPP_NRT desde el 2-nov-2026).
DIAS_SENSOR_VIGENTE = 3
FUENTES_DE_SITIO = tuple(f for f in FUENTES if f not in FUENTES_DIARIAS)
HORAS_VIGENCIA_DIARIA = 12
# Sentinel-2 pasa cada ~5 dias: refrescar su NDVI dos veces al dia solo gastaria cuota.
HORAS_VIGENCIA = {"sentinel2_ndvi": 72, "sentinel2_celdas": 72}
# Medido: con 4 consultas a la vez sobre 49 celdas Copernicus respondio 429 (tope de
# unidades de proceso por minuto). Dos a la vez queda bajo el tope.
CONSULTAS_SIMULTANEAS_CELDAS = 2
# Primera carga de una celda: lo que el mapa llega a mostrar (repositorio_clima.DIAS_MAPA_MAX).
# Pedir 400 dias por celda, como al predio entero, triplicaba el gasto sin usarse todavia.
DIAS_CELDAS_INICIAL = 120
DIAS_NDVI_INICIAL = 400      # primera carga: una temporada completa mas su linea de base
DIAS_NDVI_REVISION = 15      # refrescos: el tramo que todavia puede recibir pasadas nuevas
INTERVALO_NDVI_DIAS = 5
# POWER corrige sus ultimos dias: cada refresco vuelve a pedir este tramo ya guardado.
DIAS_REVISION_POWER = 10

# Un job pendiente o en proceso mas viejo que esto se da por interrumpido (el proceso
# se reinicio a mitad de camino) y se puede volver a encolar.
MINUTOS_JOB_VIGENTE = 60
# Una fuente con error no se reintenta antes de esto: el reintento lo dispara el
# agricultor, y cada uno es una llamada a un servicio externo.
MINUTOS_ENTRE_REINTENTOS = 5

# Las descargas grandes a disco se serializan: dos predios nuevos a la vez no deben
# bajar el mismo archivo dos veces.
_candado_cr2met = asyncio.Lock()
_candado_clsoilmaps = asyncio.Lock()


def _fila(id_parcela: int, capa: str, inicio: date, fin: date, valor, resolucion: str, producto: str) -> dict:
    sin_dato = valor is None or valor != valor  # None o NaN
    return dict(id_parcela=id_parcela, capa=capa, periodo_inicio=inicio, periodo_fin=fin,
                valor=None if sin_dato else float(valor), resolucion_nativa=resolucion,
                version_producto=producto, cobertura="sin_dato" if sin_dato else "completa")


async def _solar(session: AsyncSession, id_parcela: int, lat: float, lon: float) -> str | None:
    inicio, fin = date(2004, 1, 1), date(2016, 12, 31)  # periodo real de la climatologia
    capas = ("explorador_solar_ghi", "explorador_solar_dni", "explorador_solar_difh", *CAPAS_GHI_MENSUAL)
    if not await asyncio.to_thread(cliente_solar.disponibilidad, lat, lon):
        await guardar_consultas_grilla(session, [
            _fila(id_parcela, c, inicio, fin, None, "1km", "explorador_solar_v1") for c in capas])
        return "sin_cobertura"

    datos = await asyncio.to_thread(cliente_solar.consultar_vista_rapida, lat, lon)
    directa, difusa = datos["radiacion_directa_mensual"], datos["radiacion_difusa_mensual"]
    # GHI mensual = directa + difusa horizontal (verificado: su promedio de doce meses
    # reproduce el GHI anual de la misma respuesta). Indice 0 = enero.
    mensual = [None] * 12
    if directa and difusa and len(directa) == 12 and len(difusa) == 12:
        mensual = [a + b for a, b in zip(directa, difusa)]
    valores = (datos["ghi_kwh_m2_dia"], datos["dni_kwh_m2_dia"], datos["difh_kwh_m2_dia"], *mensual)
    await guardar_consultas_grilla(session, [
        _fila(id_parcela, c, inicio, fin, v, "1km", "explorador_solar_v1") for c, v in zip(capas, valores)])

    elevacion = datos.get("elevacion_srtm_m")
    if elevacion is not None:
        await session.execute(
            text("UPDATE parcela SET altitud_msnm = :alt WHERE id = :id AND altitud_msnm IS NULL"),
            {"alt": round(float(elevacion)), "id": id_parcela})
        await session.commit()
    return None


async def _soilgrids(session: AsyncSession, id_parcela: int, lat: float, lon: float) -> str | None:
    datos = await asyncio.to_thread(cliente_soilgrids.consultar_suelo_entorno, lat, lon)
    inicio, fin = date(2020, 1, 1), date(2020, 12, 31)  # version de SoilGrids v2.0
    capas = {"soilgrids_ph": "ph", "soilgrids_arcilla_pct": "arcilla_pct", "soilgrids_arena_pct": "arena_pct",
             "soilgrids_limo_pct": "limo_pct", "soilgrids_carbono_organico_g_kg": "carbono_organico_g_kg"}
    producto = "SoilGrids_v2.0_vecinos" if datos["vecinos"] else "SoilGrids_v2.0"
    await guardar_consultas_grilla(session, [
        _fila(id_parcela, capa, inicio, fin, datos[clave], "250m", producto) for capa, clave in capas.items()])
    return "sin_cobertura" if datos["ph"] is None else None


async def _cr2met(session: AsyncSession, id_parcela: int, lat: float, lon: float) -> str | None:
    inicio, fin = ventana_clima(date.today())
    async with _candado_cr2met:
        clima = await asyncio.to_thread(
            cliente_cr2met.consultar_cr2met, lat, lon, inicio.isoformat(), fin.isoformat(), CACHE_CR2MET)
    filas = []
    for fecha, dia in clima.iterrows():
        for capa, columna in (("cr2met_tmin", "tmin"), ("cr2met_tmax", "tmax"), ("cr2met_lluvia", "lluvia")):
            valor = dia[columna]
            if valor == valor:  # se salta el NaN (fuera de la mascara de Chile, o latencia del NRT)
                filas.append(_fila(id_parcela, capa, fecha.date(), fecha.date(), valor,
                                    "0.05deg_~5km", "cr2met_v2.5_nrt"))
    await guardar_consultas_grilla(session, filas)
    if filas:
        await _elevacion_celda(session, id_parcela, lat, lon, fin)
    return None if filas else "sin_cobertura"


async def _elevacion_celda(session: AsyncSession, id_parcela: int, lat: float, lon: float, mes: date) -> None:
    """Altura media de la celda de 5 km de CR2MET que da el clima del predio. El NetCDF no la trae
    (CR2 usa la topografia solo por dentro), asi que se calcula con el DEM de Copernicus sobre la
    huella de la celda. Con ella, la temperatura se corrige a la altura de la parcela. No debe
    tumbar la ingesta del clima: si falla, se avisa en el log y la parcela queda sin correccion."""
    try:
        async with _candado_cr2met:
            archivo = await asyncio.to_thread(cliente_cr2met.descargar_mes, "txn", mes.year, mes.month, CACHE_CR2MET)
        lat_c, lon_c = cliente_cr2met.centro_de_celda(archivo, lat, lon)
        medio = cliente_cr2met.LADO_CELDA_GRADOS / 2
        altura = await asyncio.to_thread(cliente_dem.elevacion_media, lon_c - medio, lat_c - medio, lon_c + medio, lat_c + medio)
    except Exception:
        log.warning("parcela %s: no se pudo calcular la altura de la celda de CR2MET", id_parcela, exc_info=True)
        return
    await guardar_consultas_grilla(session, [
        _fila(id_parcela, "cr2met_elevacion_celda_m", _PERIODO_DEM[0], _PERIODO_DEM[1], altura,
              "0.05deg_~5km", "copernicus_dem_glo30_media_de_la_celda")])


ANIO_INICIO_HISTORIA = 1991   # la normal estandar de la OMM empieza ahi; con el reciente son 35 anos
ATRASO_ERA5_DIAS = 8          # el archivo de reanalisis llega con unos dias de atraso


async def _clima_historico(session: AsyncSession, id_parcela: int, lat: float, lon: float) -> str | None:
    """El clima diario de 1991 al ultimo ano completo: ERA5 (Open-Meteo), corregido contra el CR2MET de la parcela
    como ya se corrige POWER (desplazamiento mensual de temperatura y un cociente de lluvia), y la calibracion
    mensual de la ET0 de Hargreaves contra la Penman-Monteith de ERA5. Guarda un renglon por ano completo. Corre
    despues de CR2MET, que aporta el traslape para corregir; sin el, guarda la serie sin corregir y lo dice."""
    hoy = date.today()
    era5 = await asyncio.to_thread(cliente_openmeteo.consultar_historia, lat, lon, f"{ANIO_INICIO_HISTORIA}-01-01",
                                   (hoy - timedelta(days=ATRASO_ERA5_DIAS)).isoformat())
    if era5[["tmin", "tmax", "lluvia"]].isna().any().any():
        raise ValueError("la serie de reanalisis trae huecos")
    inicio, fin = ventana_clima(hoy)
    filas = (await session.execute(text(
        "SELECT periodo_inicio AS fecha, capa, valor FROM cache_consulta_grilla WHERE id_parcela = :id AND "
        "capa = ANY(:capas) AND valor IS NOT NULL AND periodo_inicio BETWEEN :inicio AND :fin"),
        {"id": id_parcela, "capas": ["cr2met_tmin", "cr2met_tmax", "cr2met_lluvia"], "inicio": inicio, "fin": fin})).mappings().all()
    cr2met = None
    if filas:
        cr2met = pd.DataFrame(filas).pivot(index="fecha", columns="capa", values="valor")
        cr2met.index = pd.to_datetime(cr2met.index)
        cr2met = cr2met.rename(columns={"cr2met_tmin": "tmin", "cr2met_tmax": "tmax", "cr2met_lluvia": "lluvia"})
    corregido, sesgo = (era5[["tmin", "tmax", "lluvia"]], None) if cr2met is None else \
        corregir_contra_cr2met(cr2met, era5[["tmin", "tmax", "lluvia"]])
    if cr2met is not None:
        factores = calibrar_et0_mensual(cr2met, era5["et0_pm"], lat)
        await guardar_consultas_grilla(session, [
            _fila(id_parcela, capa, inicio, fin, v, "0.05deg_~5km", "hargreaves_calibrado_vs_penman_monteith_era5")
            for capa, v in zip(CAPAS_ET0_FACTOR_MENSUAL, factores)])
    anios = {}
    for anio in range(ANIO_INICIO_HISTORIA, hoy.year):
        d = corregido.loc[str(anio)]
        if len(d) == (366 if pd.Timestamp(anio, 12, 31).dayofyear == 366 else 365):
            anios[anio] = d
    await guardar_historia(session, id_parcela, anios, "era5_open_meteo" + ("_corregido_cr2met" if sesgo else "_sin_corregir"),
                           PRODUCTOS["clima_historico"])
    return None if anios else "sin_cobertura"


async def _clsoilmaps(session: AsyncSession, id_parcela: int, lat: float, lon: float) -> str | None:
    os.makedirs(CACHE_CLSOILMAPS, exist_ok=True)
    destino = os.path.join(CACHE_CLSOILMAPS, "Total_AWC_0_200cm.tif")
    async with _candado_clsoilmaps:
        archivo = await asyncio.to_thread(cliente_clsoilmaps.extraer_archivo, CLSOILMAPS_ARCHIVO_INTERNO, destino)
    entorno = await asyncio.to_thread(cliente_clsoilmaps.leer_valor_entorno, archivo, lat, lon)
    valor, radio = entorno if entorno else (None, None)
    # Mapa estatico: se marca con el ano de publicacion (Zenodo, dic-2022). Es la mediana de los pixeles con dato
    # alrededor del predio; el radio usado queda en el nombre del producto.
    await guardar_consultas_grilla(session, [
        _fila(id_parcela, "clsoilmaps_awc_total_mm", date(2022, 1, 1), date(2022, 12, 31), valor,
              "100m", "CLSoilMaps_v1" if radio is None else f"CLSoilMaps_v1_mediana_{radio}m")])
    return "sin_cobertura" if valor is None else None


def _celda(lat: float, lon: float) -> tuple[float, float]:
    """POWER y Open-Meteo responden por celda de modelo (decenas de km): mandarles el
    punto a ~1 km da el mismo resultado y no revela la ubicacion exacta del predio."""
    return round(lat, 2), round(lon, 2)


COLUMNAS_DIARIAS = ("tmin", "tmax", "lluvia", "rh", "radiacion", "humedad_suelo_raiz", "humedad_suelo_superficie",
                    "codigo_tiempo")


def _filas_diarias(id_parcela: int, clima, prefijo: str, resolucion: str, producto: str) -> list[dict]:
    """Una fila por dia y columna. Solo se guardan las columnas que la fuente trae: POWER entrega tambien la
    humedad del suelo; Open-Meteo no."""
    filas = []
    columnas = [c for c in COLUMNAS_DIARIAS if c in clima.columns]
    for fecha, dia in clima.iterrows():
        for columna in columnas:
            valor = dia[columna]
            if valor == valor:  # se salta el NaN (dia todavia sin dato)
                filas.append(_fila(id_parcela, f"{prefijo}_{columna}", fecha.date(), fecha.date(), valor,
                                    resolucion, producto))
    return filas


async def _power(session: AsyncSession, id_parcela: int, lat: float, lon: float) -> str | None:
    hoy = date.today()
    ultimo = (await session.execute(text(
        "SELECT max(periodo_inicio) FROM cache_consulta_grilla WHERE id_parcela = :id AND capa = 'power_tmin'"
    ), {"id": id_parcela})).scalar_one()
    # Primera vez: toda la ventana de clima del predio (humedad relativa del ano completo,
    # que CR2MET no trae). Despues, solo el tramo que POWER todavia puede corregir.
    desde = ventana_clima(hoy)[0] if ultimo is None else ultimo - timedelta(days=DIAS_REVISION_POWER)
    clima = await asyncio.to_thread(cliente_power.consultar_power, *_celda(lat, lon),
                                     desde.isoformat(), hoy.isoformat(), 60)
    filas = _filas_diarias(id_parcela, clima, "power", "0.5deg_~55km", "POWER_daily_ag")
    await guardar_consultas_grilla(session, filas)
    if filas:
        await _power_radiacion_mensual(session, id_parcela, lat, lon)
    return None if filas else "sin_cobertura"


async def _power_radiacion_mensual(session: AsyncSession, id_parcela: int, lat: float, lon: float) -> None:
    """La radiacion mensual de la climatologia de 25 anos de POWER (kWh/m2/dia), que usa el ranking de especies.
    Es un dato fijo: se pide una sola vez por predio. Si falla, no detiene la ingesta diaria: el ranking cae al
    Explorador Solar (repositorio_clima.leer_sitio)."""
    ya = (await session.execute(text(
        "SELECT count(*) FROM cache_consulta_grilla WHERE id_parcela = :id AND capa = ANY(:capas) AND valor IS NOT NULL"),
        {"id": id_parcela, "capas": list(CAPAS_GHI_POWER)})).scalar_one()
    if ya >= len(CAPAS_GHI_POWER):
        return
    try:
        climatologia = await asyncio.to_thread(cliente_power.consultar_climatologia, *_celda(lat, lon), 60)
        mensual = cliente_power.ghi_mensual_kwh(climatologia)
    except Exception:
        log.warning("parcela %s: no se pudo pedir la climatologia de radiacion de POWER", id_parcela, exc_info=True)
        return
    inicio, fin = (date.fromisoformat(d) for d in cliente_power.PERIODO_CLIMATOLOGIA)
    await guardar_consultas_grilla(session, [
        _fila(id_parcela, capa, inicio, fin, valor, "1deg_~100km", "POWER_climatologia_25a_CERES_SYN1deg")
        for capa, valor in zip(CAPAS_GHI_POWER, mensual)])


async def _open_meteo(session: AsyncSession, id_parcela: int, lat: float, lon: float) -> str | None:
    # Los dias pasados no entran a la serie del predio (ahi manda lo observado): se
    # guardan para medir el sesgo del modelo contra CR2MET (repositorio_clima._sesgo_modelo).
    clima = await asyncio.to_thread(cliente_openmeteo.consultar_pronostico, *_celda(lat, lon),
                                     cliente_openmeteo.DIAS_PRONOSTICO_MAX, cliente_openmeteo.DIAS_PASADOS_MAX)
    filas = _filas_diarias(id_parcela, clima, "openmeteo", "celda_de_modelo", "open-meteo_forecast_v1")
    await guardar_consultas_grilla(session, filas)
    return None if filas else "sin_cobertura"


def _distancia_km(lat1: float, lon1: float, lat2, lon2):
    """Haversine. lat2/lon2 pueden ser columnas de pandas."""
    p1, p2 = math.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def resumir_focos(focos, lat: float, lon: float, hoy: date, radio_km: float = RADIO_INCENDIO_KM,
                  dias: int = DIAS_FIRMS) -> list[dict]:
    """Las detecciones de FIRMS (un DataFrame con latitude, longitude, acq_date,
    confidence, frp) reducidas a una fila por dia de la ventana consultada: cuantas hubo
    dentro del radio, a que distancia quedo la mas cercana y la potencia radiativa mas
    alta. Un dia sin detecciones sale con focos = 0 -- 'se reviso y no habia' es un dato,
    no un hueco. Se descartan las de confianza baja ('l' en VIIRS), en su mayoria falsas.
    `hoy` y acq_date van en fecha UTC. Con dos satelites, una misma quema puede contarse
    mas de una vez: `focos` son detecciones, no incendios distintos."""
    ventana = [hoy - timedelta(days=d) for d in range(dias - 1, -1, -1)]
    por_dia = {d: {"fecha": d, "focos": 0, "distancia_min_km": None, "frp_max_mw": None} for d in ventana}
    if len(focos):
        f = focos[focos["confidence"].astype(str).str.lower().str[0] != "l"].copy()
        f["km"] = _distancia_km(lat, lon, f["latitude"].astype(float), f["longitude"].astype(float))
        f = f[f["km"] <= radio_km]
        for dia, grupo in f.groupby(f["acq_date"].astype(str)):
            d = date.fromisoformat(dia)
            if d in por_dia:
                por_dia[d].update(focos=len(grupo), distancia_min_km=round(float(grupo["km"].min()), 2),
                                  frp_max_mw=float(grupo["frp"].max()))
    return list(por_dia.values())


async def _firms(session: AsyncSession, id_parcela: int, lat: float, lon: float) -> str | None:
    clave = os.environ["FIRMS_MAP_KEY"]  # encolar() no deja pendiente esta fuente sin clave
    # La caja se arma alrededor del punto redondeado a ~1 km (lo unico que ve FIRMS); la
    # distancia de cada foco se mide despues, aca, contra el centroide real.
    lat_c, lon_c = _celda(lat, lon)
    margen_lat = (RADIO_INCENDIO_KM + 1.5) / 111.0
    margen_lon = margen_lat / max(math.cos(math.radians(lat_c)), 0.1)
    caja = (round(lon_c - margen_lon, 3), round(lat_c - margen_lat, 3),
            round(lon_c + margen_lon, 3), round(lat_c + margen_lat, 3))
    hoy_utc = datetime.now(timezone.utc).date()
    disponibilidad = await asyncio.to_thread(cliente_firms.consultar_disponibilidad, clave)
    sensores = [s for s in cliente_firms.SENSORES_VIGENTES
                if s in disponibilidad and (hoy_utc - disponibilidad[s]).days <= DIAS_SENSOR_VIGENTE]
    if not sensores:
        raise cliente_firms.ErrorFirms("ningun sensor VIIRS de FIRMS tiene datos recientes")
    partes = [await asyncio.to_thread(cliente_firms.consultar_focos, clave, caja, s, DIAS_FIRMS) for s in sensores]
    # BUG REAL (Copiapo, 14-nov-2026): un sensor con detecciones y otro sin ninguna. La
    # tabla vacia no trae columnas y, al concatenarla, pandas dejaba latitude/longitude
    # como 'object'; el calculo de distancia reventaba. Solo se juntan las que traen filas.
    partes = [p for p in partes if len(p)]
    focos = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()
    producto = "+".join(sensores)
    filas = []
    for dia in resumir_focos(focos, lat, lon, hoy_utc):
        f = dia["fecha"]
        filas.append(_fila(id_parcela, "firms_focos_dia", f, f, dia["focos"], "375m_VIIRS", producto))
        if dia["focos"]:
            filas.append(_fila(id_parcela, "firms_distancia_min_km", f, f, dia["distancia_min_km"],
                               "375m_VIIRS", producto))
            filas.append(_fila(id_parcela, "firms_frp_max_dia", f, f, dia["frp_max_mw"], "375m_VIIRS", producto))
    await guardar_consultas_grilla(session, filas)
    return None


def resumir_disponibilidad_optica(escenas: list[dict], inicio: date, fin: date) -> dict:
    """Escenas de cliente_copernicus.buscar_sentinel2() -> que tan seguido hubo una pasada
    despejada sobre el punto entre `inicio` y `fin`. Un dia con varias escenas (tiles que
    se traslapan) cuenta una vez, con la menos nublada. La nubosidad es la de la escena
    completa (~110 km), no la del predio: es un indicador de la zona.

      pasadas_despejadas_pct        dias con pasada bajo NUBOSIDAD_ESCENA_MAX_PCT
      ventanas_con_pasada_pct       ventanas de VENTANA_OPTICA_DIAS con al menos una
      hueco_mediano_dias            dias tipicos entre dos pasadas despejadas"""
    por_dia: dict[date, float] = {}
    for e in escenas:
        if e.get("cloud_cover_pct") is None:
            continue
        dia = date.fromisoformat(e["fecha"][:10])
        if inicio <= dia <= fin:
            por_dia[dia] = min(por_dia.get(dia, 100.0), float(e["cloud_cover_pct"]))
    claras = sorted(d for d, nubes in por_dia.items() if nubes <= NUBOSIDAD_ESCENA_MAX_PCT)
    ventanas = [inicio + timedelta(days=n) for n in range(0, (fin - inicio).days + 1, VENTANA_OPTICA_DIAS)]
    con_pasada = sum(1 for v in ventanas if any(v <= d < v + timedelta(days=VENTANA_OPTICA_DIAS) for d in claras))
    huecos = sorted((b - a).days for a, b in zip(claras, claras[1:]))
    return {"pasadas": len(por_dia),
            "pasadas_despejadas_pct": round(100 * len(claras) / len(por_dia), 1) if por_dia else None,
            "ventanas_con_pasada_pct": round(100 * con_pasada / len(ventanas), 1) if por_dia else None,
            "hueco_mediano_dias": float(huecos[len(huecos) // 2]) if huecos else None}


async def _sentinel2_nubes(session: AsyncSession, id_parcela: int, lat: float, lon: float) -> str | None:
    fin = ventana_clima(date.today())[1]                      # ultimo mes completo
    inicio = date(fin.year - 2, fin.month, 1) + timedelta(days=31)
    inicio = inicio.replace(day=1)                            # 24 meses completos
    escenas, desde = [], inicio
    while desde <= fin:                                       # por semestres: el catalogo corta en 1000 escenas
        hasta = min(fin, (desde + timedelta(days=183)).replace(day=1) - timedelta(days=1))
        escenas += await asyncio.to_thread(cliente_copernicus.buscar_sentinel2, *_celda(lat, lon),
                                           desde.isoformat(), hasta.isoformat(), None, 1000, 120)
        desde = hasta + timedelta(days=1)
    resumen = resumir_disponibilidad_optica(escenas, inicio, fin)
    await guardar_consultas_grilla(session, [
        _fila(id_parcela, capa, inicio, fin, resumen[clave], "escena_~110km", "sentinel-2-l2a_catalogo")
        for capa, clave in CAPAS_DISPONIBILIDAD_OPTICA.items()])
    return None if resumen["pasadas"] else "sin_cobertura"


_EPOCA_NDVI = date(2015, 1, 1)


async def _sentinel2_ndvi(session: AsyncSession, id_parcela: int, lat: float, lon: float) -> str | None:
    """NDVI medio del poligono por intervalo de INTERVALO_NDVI_DIAS, y que fraccion del
    poligono se vio en cada uno. Los intervalos van alineados a una fecha fija: asi dos
    corridas piden los mismos tramos y el upsert los pisa en vez de dejar tramos corridos."""
    caja = (await session.execute(text(
        "SELECT ST_XMin(geometria) AS a, ST_YMin(geometria) AS b, ST_XMax(geometria) AS c, ST_YMax(geometria) AS d "
        "FROM parcela WHERE id = :id"), {"id": id_parcela})).mappings().first()
    ultimo = (await session.execute(text(
        "SELECT max(periodo_inicio) FROM cache_consulta_grilla WHERE id_parcela = :id AND capa = 'sentinel2_visible_5d'"
    ), {"id": id_parcela})).scalar_one()
    hoy = date.today()
    desde = hoy - timedelta(days=DIAS_NDVI_INICIAL) if ultimo is None else ultimo - timedelta(days=DIAS_NDVI_REVISION)
    desde = _EPOCA_NDVI + timedelta(days=((desde - _EPOCA_NDVI).days // INTERVALO_NDVI_DIAS) * INTERVALO_NDVI_DIAS)

    token = await asyncio.to_thread(cliente_copernicus.obtener_token_oauth,
                                    os.environ["COPERNICUS_CLIENT_ID"], os.environ["COPERNICUS_CLIENT_SECRET"])
    datos = await asyncio.to_thread(cliente_copernicus.ndvi_estadistico, token,
                                    [caja["a"], caja["b"], caja["c"], caja["d"]],
                                    desde.isoformat(), hoy.isoformat(), INTERVALO_NDVI_DIAS, 120)
    filas = []
    for d in datos:
        inicio = date.fromisoformat(d["desde"][:10])
        fin = inicio + timedelta(days=INTERVALO_NDVI_DIAS - 1)
        visible = 1 - d["noDataCount"] / d["sampleCount"] if d.get("sampleCount") else 0.0
        cobertura = "sin_dato" if visible == 0 else "completa" if visible >= 0.99 else "parcial_nubes"
        comun = dict(id_parcela=id_parcela, periodo_inicio=inicio, periodo_fin=fin, resolucion_nativa="10m",
                     version_producto="sentinel-2-l2a", cobertura=cobertura)
        ndvi = d.get("mean")
        filas.append({**comun, "capa": "sentinel2_visible_5d", "valor": round(visible, 4)})
        filas.append({**comun, "capa": "sentinel2_ndvi_5d",
                      "valor": None if visible == 0 or ndvi is None or ndvi != ndvi else float(ndvi)})
    await guardar_consultas_grilla(session, filas)
    return None if any(f["valor"] for f in filas if f["capa"] == "sentinel2_visible_5d") else "sin_cobertura"


async def _sentinel2_celdas(session: AsyncSession, id_parcela: int, lat: float, lon: float) -> str | None:
    """NDVI de cada celda de la grilla, promediando solo los pixeles que caen dentro del
    perimetro. Una consulta por celda, de a CONSULTAS_SIMULTANEAS_CELDAS a la vez. Cada
    celda se guarda apenas llega y pide desde su propio ultimo dato: si la corrida se corta
    o una celda falla, la siguiente retoma solo lo que falta. Si Copernicus empieza a
    limitar, la corrida se corta ahi mismo en vez de insistir celda por celda."""
    grilla = [c for c in await leer_grilla(session, id_parcela) if c["fraccion"] >= FRACCION_MIN_CELDA]
    lado = (await session.execute(text("SELECT lado_celda_m FROM parcela WHERE id = :id"),
                                  {"id": id_parcela})).scalar_one()
    ultimos = {(f.celda_i, f.celda_j): f.ultimo for f in (await session.execute(text(
        "SELECT celda_i, celda_j, max(periodo_inicio) AS ultimo FROM cache_celda "
        "WHERE id_parcela = :id AND capa = 'ndvi' GROUP BY celda_i, celda_j"), {"id": id_parcela})).all()}
    hoy = date.today()
    # Sentinel-2 mide cada 10 m: la imagen de trabajo de una celda no necesita mas que eso.
    lado_px = max(4, min(64, round(lado / 10)))

    def desde_de(celda: dict) -> date:
        ultimo = ultimos.get((celda["i"], celda["j"]))
        desde = hoy - timedelta(days=DIAS_CELDAS_INICIAL) if ultimo is None else ultimo - timedelta(days=DIAS_NDVI_REVISION)
        return _EPOCA_NDVI + timedelta(days=((desde - _EPOCA_NDVI).days // INTERVALO_NDVI_DIAS) * INTERVALO_NDVI_DIAS)

    token = await asyncio.to_thread(cliente_copernicus.obtener_token_oauth,
                                    os.environ["COPERNICUS_CLIENT_ID"], os.environ["COPERNICUS_CLIENT_SECRET"])
    turno = asyncio.Semaphore(CONSULTAS_SIMULTANEAS_CELDAS)

    limitado = asyncio.Event()

    async def consultar(celda: dict) -> list[dict] | None:
        async with turno:
            if limitado.is_set():
                return None   # el servicio ya esta limitando: no se piden mas celdas en esta corrida
            try:
                datos = await asyncio.to_thread(cliente_copernicus.ndvi_estadistico, token, None,
                                                desde_de(celda).isoformat(), hoy.isoformat(), INTERVALO_NDVI_DIAS, 60,
                                                celda["geometria"], lado_px)
            except cliente_copernicus.LimiteCopernicus:
                limitado.set()
                raise
        filas = []
        for d in datos:
            inicio = date.fromisoformat(d["desde"][:10])
            # La API cuenta como "sin dato" los pixeles de la caja que quedan fuera de la
            # geometria: lo visible se mide contra la parte de la caja que la celda ocupa.
            dentro = d["sampleCount"] * celda["relleno"] if d.get("sampleCount") else 0
            visible = min(1.0, (d["sampleCount"] - d["noDataCount"]) / dentro) if dentro else 0.0
            ndvi = d.get("mean")
            filas.append(dict(id_parcela=id_parcela, celda_i=celda["i"], celda_j=celda["j"], capa="ndvi",
                              periodo_inicio=inicio, periodo_fin=inicio + timedelta(days=INTERVALO_NDVI_DIAS - 1),
                              valor=None if visible == 0 or ndvi is None or ndvi != ndvi else float(ndvi),
                              visible=round(visible, 4)))
        return filas

    con_dato, hechas, primer_error = False, 0, None
    for tarea in asyncio.as_completed([consultar(c) for c in grilla]):
        try:
            filas = await tarea
        except Exception as error:
            primer_error = primer_error or error
            continue
        if filas is None:
            continue
        await guardar_celdas(session, filas)
        hechas += 1
        con_dato = con_dato or any(f["valor"] is not None for f in filas)
    if hechas < len(grilla):
        motivo = str(primer_error) if isinstance(primer_error, cliente_copernicus.LimiteCopernicus) \
            else type(primer_error).__name__
        raise RuntimeError(f"quedaron {len(grilla) - hechas} de {len(grilla)} celdas sin consultar ({motivo}); "
                           "las demas estan guardadas y el proximo refresco retoma desde ahi")
    return None if con_dato else "sin_cobertura"


def relieve_por_celda(baldosas: list[dict], perimetro: dict, srid_utm: int, lado: float,
                      campos: tuple[str, ...] = ("altitud", "pendiente")) -> dict:
    """Promedia `campos` (por defecto altitud y pendiente) de los pixeles del raster que tocan
    el perimetro, agrupados por celda de la grilla: {(i, j): {campo: media, 'pixeles'}}. Un
    pixel pertenece a la celda donde cae su centro; la celda (i, j) de ST_SquareGrid empieza
    en (i * lado, j * lado) en la zona UTM del predio. Se descarta el pixel sin dato en el
    primer campo."""
    suma: dict[tuple, list] = {}
    for b in baldosas:
        filas, columnas = b[campos[0]].shape
        dentro = geometry_mask([perimetro], out_shape=(filas, columnas), transform=b["transform"],
                               invert=True, all_touched=True)
        f, c = np.nonzero(dentro)
        if not len(f):
            continue
        lon, lat = xy(b["transform"], f, c)
        x, y = reproyectar(b["crs"], f"EPSG:{srid_utm}", list(lon), list(lat))
        ci, cj = np.floor(np.asarray(x) / lado).astype(int), np.floor(np.asarray(y) / lado).astype(int)
        valores = [b[campo][f, c] for campo in campos]
        for k, (i, j) in enumerate(zip(ci, cj)):
            if valores[0][k] != valores[0][k]:
                continue
            acum = suma.setdefault((int(i), int(j)), [0] + [0.0] * len(campos))
            acum[0] += 1
            for n, v in enumerate(valores):
                acum[n + 1] += float(v[k])
    return {clave: {**{campo: acum[n + 1] / acum[0] for n, campo in enumerate(campos)}, "pixeles": acum[0]}
            for clave, acum in suma.items()}


# Copernicus DEM se levanto con TanDEM-X entre 2011 y 2015: se usa como marca del dato fijo.
_PERIODO_DEM = (date(2011, 1, 1), date(2015, 12, 31))


async def _relieve(session: AsyncSession, id_parcela: int, lat: float, lon: float) -> str | None:
    p = (await session.execute(text("""
        SELECT srid_utm, lado_celda_m, ST_AsGeoJSON(geometria) AS perimetro,
               ST_XMin(geometria) AS a, ST_YMin(geometria) AS b, ST_XMax(geometria) AS c, ST_YMax(geometria) AS d
        FROM parcela WHERE id = :id"""), {"id": id_parcela})).mappings().first()
    baldosas = await asyncio.to_thread(cliente_dem.leer_relieve, p["a"], p["b"], p["c"], p["d"])
    por_celda = relieve_por_celda(baldosas, json.loads(p["perimetro"]), p["srid_utm"], p["lado_celda_m"])
    validas = {(c["i"], c["j"]) for c in await leer_grilla(session, id_parcela)}
    filas = []
    for (ci, cj), v in por_celda.items():
        if (ci, cj) not in validas:
            continue   # un pixel que toca el borde puede tener su centro en una celda de afuera
        comun = dict(id_parcela=id_parcela, celda_i=ci, celda_j=cj, periodo_inicio=_PERIODO_DEM[0],
                     periodo_fin=_PERIODO_DEM[1], visible=1.0)
        filas.append({**comun, "capa": "altitud_m", "valor": round(v["altitud"], 2)})
        filas.append({**comun, "capa": "pendiente_pct", "valor": round(v["pendiente"], 2)})
    await guardar_celdas(session, filas)
    return None if filas else "sin_cobertura"


# El HAND de ASF se calculo sobre el mismo DEM: el periodo es el de ese insumo.
async def _inundacion(session: AsyncSession, id_parcela: int, lat: float, lon: float) -> str | None:
    """Altura media sobre el cauce (HAND) de cada celda de la grilla, en la capa 'hand_m'."""
    p = (await session.execute(text("""
        SELECT srid_utm, lado_celda_m, ST_AsGeoJSON(geometria) AS perimetro,
               ST_XMin(geometria) AS a, ST_YMin(geometria) AS b, ST_XMax(geometria) AS c, ST_YMax(geometria) AS d
        FROM parcela WHERE id = :id"""), {"id": id_parcela})).mappings().first()
    baldosas = await asyncio.to_thread(cliente_hand.leer_hand, p["a"], p["b"], p["c"], p["d"])
    por_celda = relieve_por_celda(baldosas, json.loads(p["perimetro"]), p["srid_utm"], p["lado_celda_m"],
                                  campos=("altitud",))
    validas = {(c["i"], c["j"]) for c in await leer_grilla(session, id_parcela)}
    filas = [dict(id_parcela=id_parcela, celda_i=ci, celda_j=cj, capa="hand_m", periodo_inicio=_PERIODO_DEM[0],
                  periodo_fin=_PERIODO_DEM[1], valor=round(v["altitud"], 2), visible=1.0)
             for (ci, cj), v in por_celda.items() if (ci, cj) in validas]
    await guardar_celdas(session, filas)
    return None if filas else "sin_cobertura"


_INGESTAS = {"explorador_solar": _solar, "soilgrids": _soilgrids, "cr2met": _cr2met,
             "clima_historico": _clima_historico, "power": _power, "open_meteo": _open_meteo, "firms": _firms,
             "sentinel2_nubes": _sentinel2_nubes, "relieve": _relieve, "inundacion": _inundacion,
             "sentinel2_ndvi": _sentinel2_ndvi,
             "sentinel2_celdas": _sentinel2_celdas, "clsoilmaps": _clsoilmaps}


def _sin_configurar(fuente: str) -> bool:
    """Las fuentes con credenciales. Sin ellas no se encolan (no es un error que
    reintentar cada dia): la fuente se informa como 'sin_configurar'."""
    if fuente == "firms":
        return not os.environ.get("FIRMS_MAP_KEY")
    if fuente in ("sentinel2_ndvi", "sentinel2_celdas"):
        return not (os.environ.get("COPERNICUS_CLIENT_ID") and os.environ.get("COPERNICUS_CLIENT_SECRET"))
    return False


async def estado_ingesta(session: AsyncSession, id_parcela: int) -> dict:
    """Ultimo intento por fuente: {fuente: {'estado', 'detalle', 'reintentable'}}. estado
    es el de job_extraccion, mas 'sin_iniciar' (nunca se encolo), 'interrumpida' (quedo
    pendiente o en proceso mas de MINUTOS_JOB_VIGENTE) y 'vencida' (fuente diaria completa
    hace mas que su vigencia). 'sin_configurar' es una fuente que necesita una clave que no
    esta en el entorno; 'no_aplica', una que no corresponde correr en este predio. detalle
    solo distingue 'sin_cobertura'; la causa de un error no sale de aca."""
    filas = (await session.execute(text("""
        SELECT DISTINCT ON (proveedor) proveedor, estado, detalle,
               fecha_solicitud < now() - make_interval(mins => CAST(:vigente AS integer)) AS viejo,
               fecha_solicitud < now() - make_interval(mins => CAST(:espera AS integer)) AS enfriado,
               extract(epoch FROM now() - fecha_completado) / 3600 AS horas_desde,
               -- CR2MET: vence al cambiar de mes (la ventana se corre) y otra vez el dia 10
               -- (el mes anterior ya quedo completo pese a los ~9 dias de atraso del producto).
               fecha_completado < date_trunc('month', now())
                 OR (extract(day FROM now()) >= 10
                     AND fecha_completado < date_trunc('month', now()) + interval '9 days') AS mes_vencido,
               -- Clima historico: vence al empezar un ano (el ano que termino pasa a ser un ano completo).
               fecha_completado < date_trunc('year', now()) AS anio_vencido
        FROM job_extraccion WHERE id_parcela = :id ORDER BY proveedor, id DESC
    """), {"id": id_parcela, "vigente": MINUTOS_JOB_VIGENTE, "espera": MINUTOS_ENTRE_REINTENTOS})).mappings().all()
    ultimo = {f["proveedor"]: f for f in filas}
    optica = await leer_disponibilidad_optica(session, id_parcela)
    out = {}
    for fuente in FUENTES:
        if _sin_configurar(fuente):
            out[fuente] = {"estado": "sin_configurar", "detalle": None, "reintentable": False, "con_error": False}
            continue
        if fuente == "sentinel2_ndvi" and not optica["viable"]:
            # Zona con pocas pasadas despejadas, o todavia sin medir: no se gasta cuota.
            out[fuente] = {"estado": "no_aplica", "detalle": None, "reintentable": False, "con_error": False}
            continue
        f = ultimo.get(fuente)
        if f is None:
            out[fuente] = {"estado": "sin_iniciar", "detalle": None, "reintentable": True, "con_error": False}
            continue
        estado = f["estado"]
        if estado in ("pendiente", "en_proceso") and f["viejo"]:
            estado = "interrumpida"
        elif estado == "completo" and (
                (fuente in FUENTES_DIARIAS and f["horas_desde"] is not None
                 and f["horas_desde"] > HORAS_VIGENCIA.get(fuente, HORAS_VIGENCIA_DIARIA))
                or (fuente == "cr2met" and f["mes_vencido"])
                or (fuente == "clima_historico" and f["anio_vencido"])):
            estado = "vencida"
        out[fuente] = {"estado": estado,
                       "detalle": "sin_cobertura" if f["detalle"] == "sin_cobertura" else None,
                       "reintentable": estado in ("interrumpida", "vencida")
                                       or (estado == "error" and bool(f["enfriado"])),
                       "con_error": estado == "error"}
    return out


async def encolar(session: AsyncSession, id_parcela: int, fuentes: tuple[str, ...] = FUENTES,
                  reintentar_errores_ya: bool = False) -> dict[str, int]:
    """Deja en 'pendiente' cada fuente reintentable (nunca corrida, interrumpida, vencida,
    o con un error de hace mas de MINUTOS_ENTRE_REINTENTOS) y devuelve {fuente: id_job}. Las
    completas y las que ya estan en curso no se tocan -- llamar esto dos veces seguidas
    no duplica descargas.

    fuentes: subconjunto a considerar. reintentar_errores_ya: salta la espera entre
    reintentos -- solo para la tarea programada, que trae su propia espera; la espera
    existe para acotar los reintentos que dispara un agricultor."""
    estado = await estado_ingesta(session, id_parcela)
    jobs = {}
    for fuente in fuentes:
        if estado[fuente]["reintentable"] or (reintentar_errores_ya and estado[fuente]["con_error"]):
            jobs[fuente] = (await session.execute(text("""
                INSERT INTO job_extraccion (id_parcela, proveedor, producto, estado)
                VALUES (:id, :proveedor, :producto, 'pendiente') RETURNING id
            """), {"id": id_parcela, "proveedor": fuente, "producto": PRODUCTOS[fuente]})).scalar_one()
    await session.commit()
    return jobs


async def _marcar(session: AsyncSession, id_job: int, estado: str, detalle: str | None = None) -> None:
    cierre = ", fecha_completado = now()" if estado in ("completo", "error") else ""
    await session.execute(
        text(f"UPDATE job_extraccion SET estado = :estado, detalle = :detalle{cierre} WHERE id = :id"),
        {"id": id_job, "estado": estado, "detalle": detalle})
    await session.commit()


async def ingerir_predio(id_parcela: int, jobs: dict[str, int]) -> None:
    """Tarea en segundo plano: corre, una por una, las fuentes que encolar() dejo
    pendientes. Abre su propia sesion -- la del request que la lanzo ya esta cerrada
    cuando esto corre."""
    async with db.SessionLocal() as session:
        centro = (await session.execute(text(
            "SELECT ST_Y(ST_Centroid(geometria)) AS lat, ST_X(ST_Centroid(geometria)) AS lon "
            "FROM parcela WHERE id = :id"), {"id": id_parcela})).mappings().first()
        if centro is None:
            return
        for fuente, id_job in jobs.items():
            await _marcar(session, id_job, "en_proceso")
            try:
                detalle = await _INGESTAS[fuente](session, id_parcela, centro["lat"], centro["lon"])
                await _marcar(session, id_job, "completo", detalle)
            except Exception as error:
                await session.rollback()
                log.exception("ingesta %s fallo para la parcela %s", fuente, id_parcela)
                await _marcar(session, id_job, "error", f"{type(error).__name__}: {error}"[:500])
