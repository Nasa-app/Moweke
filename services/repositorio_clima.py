"""
Repositorio de clima v0.1 -- primera pieza real de la Fase 5 del plan (todavia no
completa: falta leer_clima_desde_cache() y actualizar_grilla_parcela() orquestando
cliente_power + cliente_appeears, ver plan). Esto solo cubre lo necesario para que
las fuentes nuevas (cliente_solar, cliente_copernicus) puedan escribir en
cache_consulta_grilla de verdad, no solo devolver datos sueltos.

cache_consulta_grilla ya esta disenada para ser generica por fuente (ver comentario en
database/schema.sql: "HLS, SRTM, SMAP, POWER, ECOSTRESS -- todo lo que se consulta por
poligono o centroide de una parcela especifica") -- no hizo falta ninguna columna nueva
para Explorador Solar ni Copernicus, solo valores nuevos de `capa`/`version_producto`.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def guardar_consulta_grilla(
    session: AsyncSession, id_parcela: int, capa: str, periodo_inicio: date, periodo_fin: date,
    valor: float | None, resolucion_nativa: str, version_producto: str | None, cobertura: str,
) -> None:
    """Upsert sobre la UNIQUE (id_parcela, capa, periodo_inicio, periodo_fin) real del
    schema -- una consulta repetida para el mismo periodo actualiza el valor, no duplica
    la fila. cobertura: 'completa' | 'parcial_nubes' | 'sin_dato' (CHECK real de la tabla)."""
    await session.execute(text("""
        INSERT INTO cache_consulta_grilla
            (id_parcela, capa, periodo_inicio, periodo_fin, valor, resolucion_nativa, version_producto, cobertura)
        VALUES
            (:id_parcela, :capa, :periodo_inicio, :periodo_fin, :valor, :resolucion_nativa, :version_producto, :cobertura)
        ON CONFLICT (id_parcela, capa, periodo_inicio, periodo_fin) DO UPDATE SET
            valor = EXCLUDED.valor, resolucion_nativa = EXCLUDED.resolucion_nativa,
            version_producto = EXCLUDED.version_producto, cobertura = EXCLUDED.cobertura,
            fecha_consulta = now()
    """), dict(id_parcela=id_parcela, capa=capa, periodo_inicio=periodo_inicio, periodo_fin=periodo_fin,
               valor=valor, resolucion_nativa=resolucion_nativa, version_producto=version_producto,
               cobertura=cobertura))
    await session.commit()


_UPSERT_GRILLA = text("""
    INSERT INTO cache_consulta_grilla
        (id_parcela, capa, periodo_inicio, periodo_fin, valor, resolucion_nativa, version_producto, cobertura)
    VALUES
        (:id_parcela, :capa, :periodo_inicio, :periodo_fin, :valor, :resolucion_nativa, :version_producto, :cobertura)
    ON CONFLICT (id_parcela, capa, periodo_inicio, periodo_fin) DO UPDATE SET
        valor = EXCLUDED.valor, resolucion_nativa = EXCLUDED.resolucion_nativa,
        version_producto = EXCLUDED.version_producto, cobertura = EXCLUDED.cobertura,
        fecha_consulta = now()
""")


async def guardar_consultas_grilla(session: AsyncSession, filas: list[dict]) -> None:
    """Mismo upsert que guardar_consulta_grilla(), para muchas filas en un solo viaje y
    un solo commit -- un ano de clima diario son mas de mil filas, una por una no escala.
    Cada fila es un dict con las ocho claves del INSERT."""
    if filas:
        await session.execute(_UPSERT_GRILLA, filas)
    await session.commit()


def ventana_clima(hoy: date) -> tuple[date, date]:
    """Los doce meses calendario completos anteriores al mes en curso -- la referencia
    de clima del predio para la idoneidad (un ano observado, no una normal de 30 anos)."""
    fin = hoy.replace(day=1) - timedelta(days=1)
    mes, anio = fin.month - 11, fin.year
    if mes <= 0:
        mes, anio = mes + 12, anio - 1
    return date(anio, mes, 1), fin


CAPAS_GHI_MENSUAL = tuple(f"explorador_solar_ghi_mes_{m:02d}" for m in range(1, 13))
_CAPAS_CLIMA = {"cr2met_tmin": "tmin", "cr2met_tmax": "tmax", "cr2met_lluvia": "lluvia"}


async def leer_sitio(session: AsyncSession, id_parcela: int, hoy: date | None = None) -> dict:
    """Lo que catalogo_especies.ranking_idoneidad() necesita de un predio, leido de
    cache_consulta_grilla: pH (SoilGrids), agua disponible (CLSoilMaps), GHI mensual
    (Explorador Solar) y el clima diario de la ventana de doce meses (CR2MET). Cada dato
    que falte queda en None -- quien llama decide que hacer, aca no se inventa nada."""
    inicio, fin = ventana_clima(hoy or date.today())
    estaticas = ["soilgrids_ph", "clsoilmaps_awc_total_mm", *CAPAS_GHI_MENSUAL]
    filas = (await session.execute(text(
        "SELECT capa, valor FROM cache_consulta_grilla WHERE id_parcela = :id AND capa = ANY(:capas)"
    ), {"id": id_parcela, "capas": estaticas})).mappings().all()
    valores = {f["capa"]: f["valor"] for f in filas}
    ghi = [valores.get(c) for c in CAPAS_GHI_MENSUAL]

    filas_clima = (await session.execute(text("""
        SELECT periodo_inicio AS fecha, capa, valor FROM cache_consulta_grilla
        WHERE id_parcela = :id AND capa = ANY(:capas) AND valor IS NOT NULL
          AND periodo_inicio BETWEEN :inicio AND :fin
        ORDER BY periodo_inicio
    """), {"id": id_parcela, "capas": list(_CAPAS_CLIMA), "inicio": inicio, "fin": fin})).mappings().all()
    clima = None
    if filas_clima:
        clima = pd.DataFrame(filas_clima).pivot(index="fecha", columns="capa", values="valor")
        clima.index = pd.to_datetime(clima.index)
        clima = clima.rename(columns=_CAPAS_CLIMA).reindex(columns=["tmin", "tmax", "lluvia"])

    return {"ph": valores.get("soilgrids_ph"), "awc_mm": valores.get("clsoilmaps_awc_total_mm"),
            "ghi_mensual": ghi if all(v is not None for v in ghi) else None,
            "clima": clima, "periodo_clima": (inicio, fin)}


DIAS_ESTIMADOS_MAX = 365  # hasta donde se extiende la serie con el ano anterior


async def leer_clima_diario(session: AsyncSession, id_parcela: int, desde: date,
                             hoy: date | None = None) -> pd.DataFrame | None:
    """Serie diaria continua del predio desde `desde`, armada con tres horizontes. Cada
    dia trae tmin, tmax, lluvia, rh y dos etiquetas: `fuente` y `horizonte`.

      observado   CR2MET (tmin/tmax/lluvia, 5 km) y, donde CR2MET no llega, POWER. La
                  humedad relativa siempre es de POWER (CR2MET no la trae).
      pronostico  Open-Meteo: los dias recientes que todavia no tienen dato observado
                  (analisis del modelo) y los 16 dias hacia adelante.
      estimado    Mas alla del pronostico: el mismo dia del ano anterior, tomado de lo
                  observado. Es una referencia para completar el ciclo, no un pronostico.

    La serie termina en el primer hueco de tmin/tmax que no se pueda cerrar interpolando
    3 dias -- pheno_engine.simular() se niega a correr sobre huecos. None si no hay nada."""
    hoy = hoy or date.today()
    capas = [f"{p}_{v}" for p in ("cr2met", "power", "openmeteo") for v in ("tmin", "tmax", "lluvia", "rh")]
    filas = (await session.execute(text("""
        SELECT periodo_inicio AS fecha, capa, valor, fecha_consulta::date AS consultado
        FROM cache_consulta_grilla
        WHERE id_parcela = :id AND capa = ANY(:capas) AND valor IS NOT NULL AND periodo_inicio >= :desde
    """), {"id": id_parcela, "capas": capas, "desde": desde - timedelta(days=DIAS_ESTIMADOS_MAX + 1)})).mappings().all()
    if not filas:
        return None
    crudo = pd.DataFrame(filas)
    crudo["fecha"] = pd.to_datetime(crudo["fecha"])
    ancho = crudo.pivot(index="fecha", columns="capa", values="valor").reindex(columns=capas)

    def de(prefijo: str) -> pd.DataFrame:
        return ancho[[f"{prefijo}_{v}" for v in ("tmin", "tmax", "lluvia", "rh")]].set_axis(
            ["tmin", "tmax", "lluvia", "rh"], axis=1)

    cr2met, power, modelo = de("cr2met"), de("power"), de("openmeteo")
    observado = cr2met.combine_first(power)       # CR2MET manda; POWER rellena dias y la rh
    observado["rh"] = power["rh"]
    hay_observado = observado[["tmin", "tmax"]].notna().all(axis=1)
    hay_modelo = modelo[["tmin", "tmax"]].notna().all(axis=1)

    fin = pd.Timestamp(hoy) + pd.Timedelta(days=DIAS_ESTIMADOS_MAX)
    serie = pd.DataFrame(index=pd.date_range(pd.Timestamp(desde), fin, freq="D"),
                         columns=["tmin", "tmax", "lluvia", "rh"], dtype=float)
    serie["fuente"], serie["horizonte"] = None, None
    anterior = observado[hay_observado].copy()
    anterior.index = anterior.index + pd.DateOffset(years=1)
    anterior = anterior[~anterior.index.duplicated()]

    for bloque, vale, fuente, horizonte in (
        (observado, hay_observado, None, "observado"),
        (modelo, hay_modelo, "open_meteo", "pronostico"),
        (anterior, pd.Series(True, index=anterior.index), "ano_anterior", "estimado"),
    ):
        dias = serie.index[serie["horizonte"].isna()].intersection(bloque.index[vale.reindex(bloque.index, fill_value=False)])
        if horizonte == "estimado":
            dias = dias[dias > pd.Timestamp(hoy)]  # el ano anterior nunca tapa un hueco del pasado
        serie.loc[dias, ["tmin", "tmax", "lluvia", "rh"]] = bloque.loc[dias, ["tmin", "tmax", "lluvia", "rh"]]
        serie.loc[dias, "horizonte"] = horizonte
        if fuente is None:
            serie.loc[dias, "fuente"] = ["cr2met" if d in cr2met.index and pd.notna(cr2met.at[d, "tmin"]) else "power"
                                         for d in dias]
        else:
            serie.loc[dias, "fuente"] = fuente

    primero = serie["horizonte"].first_valid_index()
    if primero is None:
        return None
    serie = serie.loc[primero:].copy()  # la serie parte en el primer dia con dato, no antes
    serie[["tmin", "tmax", "lluvia"]] = serie[["tmin", "tmax", "lluvia"]].interpolate(limit=3, limit_area="inside")
    serie[["fuente", "horizonte"]] = serie[["fuente", "horizonte"]].ffill()
    huecos = serie.index[serie[["tmin", "tmax", "lluvia"]].isna().any(axis=1)]
    if len(huecos):
        serie = serie.loc[:huecos[0] - pd.Timedelta(days=1)]
    return serie if len(serie) else None
