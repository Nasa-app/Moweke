"""
Ingesta de un predio v0.1 -- las cuatro fuentes que alimentan la idoneidad
(catalogo_especies.ranking_idoneidad), corridas solas al crear la parcela en vez de
dispararse a mano por los endpoints /api/admin/.../ingesta/*.

  explorador_solar  GHI anual y mensual 2004-2016 (radiacion) + elevacion del punto
  soilgrids         pH, textura, carbono organico
  cr2met            tmin/tmax/lluvia diarios de los ultimos doce meses completos
  clsoilmaps        agua disponible total del suelo (0-200 cm)

Y las dos que alimentan el seguimiento diario de un cultivo
(catalogo_especies.seguimiento_cultivo). Vencen: se vuelven a correr cuando su ultimo
dato tiene mas de HORAS_VIGENCIA_DIARIA.

  power             tmin/tmax/lluvia/humedad relativa/radiacion diarios hasta hace ~3 dias
  open_meteo        los ultimos dias segun modelo y el pronostico a 16 dias

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
import logging
import os
from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services import (cliente_clsoilmaps, cliente_cr2met, cliente_openmeteo, cliente_power,
                      cliente_soilgrids, cliente_solar, db)
from services.repositorio_clima import CAPAS_GHI_MENSUAL, guardar_consultas_grilla, ventana_clima

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
    "power": "diario_ag",
    "open_meteo": "pronostico_16d",
    "clsoilmaps": "awc_total_0_200cm",
}
FUENTES = tuple(PRODUCTOS)
FUENTES_DIARIAS = frozenset({"power", "open_meteo"})
FUENTES_DE_SITIO = tuple(f for f in FUENTES if f not in FUENTES_DIARIAS)
HORAS_VIGENCIA_DIARIA = 12
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
    datos = await asyncio.to_thread(cliente_soilgrids.consultar_suelo, lat, lon)
    inicio, fin = date(2020, 1, 1), date(2020, 12, 31)  # version de SoilGrids v2.0
    capas = {"soilgrids_ph": "ph", "soilgrids_arcilla_pct": "arcilla_pct", "soilgrids_arena_pct": "arena_pct",
             "soilgrids_limo_pct": "limo_pct", "soilgrids_carbono_organico_g_kg": "carbono_organico_g_kg"}
    await guardar_consultas_grilla(session, [
        _fila(id_parcela, capa, inicio, fin, datos[clave], "250m", "SoilGrids_v2.0") for capa, clave in capas.items()])
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
    return None if filas else "sin_cobertura"


async def _clsoilmaps(session: AsyncSession, id_parcela: int, lat: float, lon: float) -> str | None:
    os.makedirs(CACHE_CLSOILMAPS, exist_ok=True)
    destino = os.path.join(CACHE_CLSOILMAPS, "Total_AWC_0_200cm.tif")
    async with _candado_clsoilmaps:
        archivo = await asyncio.to_thread(cliente_clsoilmaps.extraer_archivo, CLSOILMAPS_ARCHIVO_INTERNO, destino)
    valor = await asyncio.to_thread(cliente_clsoilmaps.leer_valor_punto, archivo, lat, lon)
    # Mapa estatico: se marca con el ano de publicacion (Zenodo, dic-2022).
    await guardar_consultas_grilla(session, [
        _fila(id_parcela, "clsoilmaps_awc_total_mm", date(2022, 1, 1), date(2022, 12, 31), valor,
              "100m", "CLSoilMaps_v1")])
    return "sin_cobertura" if valor is None else None


def _celda(lat: float, lon: float) -> tuple[float, float]:
    """POWER y Open-Meteo responden por celda de modelo (decenas de km): mandarles el
    punto a ~1 km da el mismo resultado y no revela la ubicacion exacta del predio."""
    return round(lat, 2), round(lon, 2)


def _filas_diarias(id_parcela: int, clima, prefijo: str, resolucion: str, producto: str) -> list[dict]:
    filas = []
    for fecha, dia in clima.iterrows():
        for columna in ("tmin", "tmax", "lluvia", "rh", "radiacion"):
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
    return None if filas else "sin_cobertura"


async def _open_meteo(session: AsyncSession, id_parcela: int, lat: float, lon: float) -> str | None:
    # Los dias pasados no entran a la serie del predio (ahi manda lo observado): se
    # guardan para medir el sesgo del modelo contra CR2MET (repositorio_clima._sesgo_modelo).
    clima = await asyncio.to_thread(cliente_openmeteo.consultar_pronostico, *_celda(lat, lon),
                                     cliente_openmeteo.DIAS_PRONOSTICO_MAX, cliente_openmeteo.DIAS_PASADOS_MAX)
    filas = _filas_diarias(id_parcela, clima, "openmeteo", "celda_de_modelo", "open-meteo_forecast_v1")
    await guardar_consultas_grilla(session, filas)
    return None if filas else "sin_cobertura"


_INGESTAS = {"explorador_solar": _solar, "soilgrids": _soilgrids, "cr2met": _cr2met,
             "power": _power, "open_meteo": _open_meteo, "clsoilmaps": _clsoilmaps}


async def estado_ingesta(session: AsyncSession, id_parcela: int) -> dict:
    """Ultimo intento por fuente: {fuente: {'estado', 'detalle', 'reintentable'}}. estado
    es el de job_extraccion, mas 'sin_iniciar' (nunca se encolo), 'interrumpida' (quedo
    pendiente o en proceso mas de MINUTOS_JOB_VIGENTE) y 'vencida' (fuente diaria completa
    hace mas de HORAS_VIGENCIA_DIARIA). detalle solo distingue 'sin_cobertura'; la causa
    de un error no sale de aca."""
    filas = (await session.execute(text("""
        SELECT DISTINCT ON (proveedor) proveedor, estado, detalle,
               fecha_solicitud < now() - make_interval(mins => CAST(:vigente AS integer)) AS viejo,
               fecha_solicitud < now() - make_interval(mins => CAST(:espera AS integer)) AS enfriado,
               fecha_completado < now() - make_interval(hours => CAST(:horas AS integer)) AS vencido,
               -- CR2MET: vence al cambiar de mes (la ventana se corre) y otra vez el dia 10
               -- (el mes anterior ya quedo completo pese a los ~9 dias de atraso del producto).
               fecha_completado < date_trunc('month', now())
                 OR (extract(day FROM now()) >= 10
                     AND fecha_completado < date_trunc('month', now()) + interval '9 days') AS mes_vencido
        FROM job_extraccion WHERE id_parcela = :id ORDER BY proveedor, id DESC
    """), {"id": id_parcela, "vigente": MINUTOS_JOB_VIGENTE, "espera": MINUTOS_ENTRE_REINTENTOS,
           "horas": HORAS_VIGENCIA_DIARIA})).mappings().all()
    ultimo = {f["proveedor"]: f for f in filas}
    out = {}
    for fuente in FUENTES:
        f = ultimo.get(fuente)
        if f is None:
            out[fuente] = {"estado": "sin_iniciar", "detalle": None, "reintentable": True, "con_error": False}
            continue
        estado = f["estado"]
        if estado in ("pendiente", "en_proceso") and f["viejo"]:
            estado = "interrumpida"
        elif estado == "completo" and ((fuente in FUENTES_DIARIAS and f["vencido"])
                                        or (fuente == "cr2met" and f["mes_vencido"])):
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
