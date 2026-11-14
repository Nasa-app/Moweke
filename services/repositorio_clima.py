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

# Correccion de sesgo de celda. POWER (~55 km) y Open-Meteo (celda de modelo) promedian
# mar, tierra y relieve: medido contra CR2MET (5 km) en tres puntos, POWER da minimas
# 1,4-2,5 C mas altas, la mitad de la lluvia y casi ninguna helada. Se corrige cada
# predio contra su propio CR2MET, con los dias en que ambas fuentes coinciden. Es un
# ajuste de un solo ano de traslape: reduce el sesgo medio, no reconstruye los extremos.
MIN_DIAS_TRASLAPE = 30   # con menos dias en comun no se corrige nada
MIN_DIAS_MES = 10        # con menos dias de un mes, ese mes usa el sesgo de todo el traslape
FACTOR_LLUVIA = (0.5, 3.0)


def _sesgo_power(cr2met: pd.DataFrame, power: pd.DataFrame) -> dict | None:
    """Sesgo de POWER contra CR2MET: diferencia media de tmin y tmax por mes calendario
    (se resta) y un solo cociente de lluvia acumulada para todo el traslape (se multiplica).

    Medido ajustando con dias pares y probando en impares, en tres puntos: el sesgo de
    temperatura baja de 1,5-2,8 C a menos de 0,2 C y el error absoluto medio cae a cerca
    de la mitad; la lluvia anual queda a menos de 15 % de CR2MET. Lo que NO arregla: las
    heladas. POWER ve 1 de 9, 1 de 18 y 0 de 5; corregido ve 4, 4 y 0 -- restar una media
    no devuelve los extremos que la celda aplana.

    La lluvia lleva un cociente unico y no uno por mes: el de un mes seco sale de muy
    pocos milimetros (nov-2025 en Quemchi: 31 contra 15) y, aplicado al mismo mes del ano
    siguiente, duplico una lluvia que POWER ya traia bien."""
    comun = cr2met[["tmin", "tmax", "lluvia"]].join(power[["tmin", "tmax", "lluvia"]], rsuffix="_p").dropna()
    if len(comun) < MIN_DIAS_TRASLAPE:
        return None
    total = {"tmin": float((comun.tmin_p - comun.tmin).mean()), "tmax": float((comun.tmax_p - comun.tmax).mean()),
             "lluvia": float(comun.lluvia.sum() / comun.lluvia_p.sum()) if comun.lluvia_p.sum() > 0 else 1.0}
    sesgo = {"dias_traslape": len(comun), "tmin": {}, "tmax": {},
             "lluvia": min(max(total["lluvia"], FACTOR_LLUVIA[0]), FACTOR_LLUVIA[1])}
    for mes in range(1, 13):
        m = comun[comun.index.month == mes]
        hay = len(m) >= MIN_DIAS_MES
        sesgo["tmin"][mes] = float((m.tmin_p - m.tmin).mean()) if hay else total["tmin"]
        sesgo["tmax"][mes] = float((m.tmax_p - m.tmax).mean()) if hay else total["tmax"]
    # El sesgo de un mes sale de ~30 dias de un solo ano: se suaviza con sus dos meses
    # vecinos (pesos 1-2-1, circular) para no arrastrar el ruido de un mes atipico. El
    # ciclo estacional del sesgo (en Chiloe, de -4 C en enero a -0,2 C en agosto) se conserva.
    for variable in ("tmin", "tmax"):
        crudo = sesgo[variable]
        sesgo[variable] = {mes: (crudo[(mes - 2) % 12 + 1] + 2 * crudo[mes] + crudo[mes % 12 + 1]) / 4
                           for mes in range(1, 13)}
    return sesgo


def _sesgo_modelo(cr2met: pd.DataFrame, modelo: pd.DataFrame) -> dict | None:
    """Sesgo de Open-Meteo: una sola diferencia media de tmin y de tmax con los dias
    recientes en comun (su historia guardada es de ~3 meses, no alcanza para un sesgo por
    mes). La lluvia NO se corrige: ensayado, el cociente de un tramo corto no se sostiene
    en el tramo siguiente (en San Fernando empeoro de 252 a 148 mm contra 228 reales)."""
    comun = cr2met[["tmin", "tmax"]].join(modelo[["tmin", "tmax"]], rsuffix="_m").dropna()
    if len(comun) < MIN_DIAS_TRASLAPE:
        return None
    return {"dias_traslape": len(comun), "tmin": float((comun.tmin_m - comun.tmin).mean()),
            "tmax": float((comun.tmax_m - comun.tmax).mean())}


def _corregir(bloque: pd.DataFrame, sesgo: dict | None) -> pd.DataFrame:
    if sesgo is None:
        return bloque
    out = bloque.copy()
    por_mes = isinstance(sesgo["tmin"], dict)
    meses = out.index.month
    for variable in ("tmin", "tmax"):
        resta = meses.map(sesgo[variable]) if por_mes else sesgo[variable]
        out[variable] = out[variable] - resta
    if "lluvia" in sesgo:
        out["lluvia"] = out["lluvia"] * sesgo["lluvia"]
    # Corregir minima y maxima por separado puede cruzarlas en un dia de poca amplitud.
    out["tmin"] = out[["tmin", "tmax"]].min(axis=1).where(out["tmin"].notna())
    return out


async def leer_clima_diario(session: AsyncSession, id_parcela: int, desde: date,
                             hoy: date | None = None) -> pd.DataFrame | None:
    """Serie diaria continua del predio desde `desde`, armada con tres horizontes. Cada
    dia trae tmin, tmax, lluvia, rh y dos etiquetas: `fuente` y `horizonte`.

      observado   CR2MET (tmin/tmax/lluvia, 5 km) y, donde CR2MET no llega, POWER. La
                  humedad relativa siempre es de POWER (CR2MET no la trae).
      pronostico  Open-Meteo: los dias recientes que todavia no tienen dato observado
                  (analisis del modelo) y los 16 dias hacia adelante.

    POWER y Open-Meteo entran corregidos por su sesgo contra el CR2MET del mismo predio
    (ver _sesgo_power/_sesgo_modelo); `fuente` lo dice ('power_corregido',
    'open_meteo_corregido') y serie.attrs['correccion_sesgo'] trae los valores aplicados.
    La humedad relativa no se corrige: no hay contra que medirla.
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
    sesgo_power, sesgo_modelo = _sesgo_power(cr2met, power), _sesgo_modelo(cr2met, modelo)
    power, modelo = _corregir(power, sesgo_power), _corregir(modelo, sesgo_modelo)
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
        (modelo, hay_modelo, "open_meteo_corregido" if sesgo_modelo else "open_meteo", "pronostico"),
        (anterior, pd.Series(True, index=anterior.index), "ano_anterior", "estimado"),
    ):
        dias = serie.index[serie["horizonte"].isna()].intersection(bloque.index[vale.reindex(bloque.index, fill_value=False)])
        if horizonte == "estimado":
            dias = dias[dias > pd.Timestamp(hoy)]  # el ano anterior nunca tapa un hueco del pasado
        serie.loc[dias, ["tmin", "tmax", "lluvia", "rh"]] = bloque.loc[dias, ["tmin", "tmax", "lluvia", "rh"]]
        serie.loc[dias, "horizonte"] = horizonte
        if fuente is None:
            respaldo = "power_corregido" if sesgo_power else "power"
            serie.loc[dias, "fuente"] = ["cr2met" if d in cr2met.index and pd.notna(cr2met.at[d, "tmin"]) else respaldo
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
    if not len(serie):
        return None
    redondo = lambda v: {k: round(x, 2) for k, x in v.items()} if isinstance(v, dict) else round(v, 2)
    serie.attrs["correccion_sesgo"] = {
        fuente: None if sesgo is None else {k: v if k == "dias_traslape" else redondo(v) for k, v in sesgo.items()}
        for fuente, sesgo in (("power", sesgo_power), ("open_meteo", sesgo_modelo))}
    return serie


# Radio dentro del cual un foco de calor de FIRMS cuenta como "cercano" al predio. Es un
# criterio de producto, no un umbral agronomico: no hay funcion de dano de cultivo
# asociada, por eso un foco se informa como alerta y no entra al calculo de perdida.
RADIO_INCENDIO_KM = 10.0
_CAPAS_INCENDIO = {"firms_focos_dia": "focos", "firms_distancia_min_km": "distancia_min_km",
                   "firms_frp_max_dia": "frp_max_mw"}


async def leer_incendios(session: AsyncSession, id_parcela: int, desde: date | None = None) -> dict:
    """Focos de calor de FIRMS dentro de RADIO_INCENDIO_KM del predio, por dia.
    `revisado` son el primer y el ultimo dia para los que hay consulta guardada (None si
    FIRMS nunca corrio para el predio): sin eso, 'sin focos' no se distingue de 'sin revisar'."""
    filas = (await session.execute(text("""
        SELECT periodo_inicio AS fecha, capa, valor FROM cache_consulta_grilla
        WHERE id_parcela = :id AND capa = ANY(:capas) AND valor IS NOT NULL
          AND (CAST(:desde AS date) IS NULL OR periodo_inicio >= CAST(:desde AS date))
        ORDER BY periodo_inicio
    """), {"id": id_parcela, "capas": list(_CAPAS_INCENDIO), "desde": desde})).mappings().all()
    por_dia: dict[date, dict] = {}
    for f in filas:
        por_dia.setdefault(f["fecha"], {})[_CAPAS_INCENDIO[f["capa"]]] = f["valor"]
    dias = sorted(por_dia)
    return {"radio_km": RADIO_INCENDIO_KM,
            "revisado": [dias[0].isoformat(), dias[-1].isoformat()] if dias else None,
            "dias_con_focos": [{"fecha": d.isoformat(), "focos": int(v["focos"]),
                                "distancia_min_km": v.get("distancia_min_km"), "frp_max_mw": v.get("frp_max_mw")}
                               for d, v in sorted(por_dia.items()) if v.get("focos")]}


# Curva optica del satelite (NDVI de Sentinel-2): solo sirve donde el cielo deja ver el
# suelo con frecuencia. Medido con el catalogo publico en 24 meses: en Quemchi menos de
# la mitad de las ventanas de 10 dias tuvo una pasada despejada; en San Fernando, casi
# todas. Los tres numeros de abajo son criterio de producto, no un estandar publicado.
NUBOSIDAD_ESCENA_MAX_PCT = 20.0      # una pasada cuenta como despejada bajo esta nubosidad de escena
VENTANA_OPTICA_DIAS = 10             # cada cuanto hace falta una observacion para seguir un cultivo
VENTANAS_CON_PASADA_MIN_PCT = 66.0   # con menos ventanas cubiertas, la curva no se ofrece
CAPAS_DISPONIBILIDAD_OPTICA = {"sentinel2_pasadas": "pasadas",
                               "sentinel2_pasadas_despejadas_pct": "pasadas_despejadas_pct",
                               "sentinel2_ventanas_con_pasada_pct": "ventanas_con_pasada_pct",
                               "sentinel2_hueco_mediano_dias": "hueco_mediano_dias"}


async def leer_disponibilidad_optica(session: AsyncSession, id_parcela: int) -> dict:
    """Si en el predio se puede seguir un cultivo con la curva optica, y con que numeros
    se decidio. `viable` es None mientras no se haya medido."""
    filas = (await session.execute(text("""
        SELECT DISTINCT ON (capa) capa, valor, periodo_inicio, periodo_fin FROM cache_consulta_grilla
        WHERE id_parcela = :id AND capa = ANY(:capas) ORDER BY capa, periodo_fin DESC
    """), {"id": id_parcela, "capas": list(CAPAS_DISPONIBILIDAD_OPTICA)})).mappings().all()
    medido = {CAPAS_DISPONIBILIDAD_OPTICA[f["capa"]]: f["valor"] for f in filas}
    ventanas = medido.get("ventanas_con_pasada_pct")
    return {"viable": None if ventanas is None else ventanas >= VENTANAS_CON_PASADA_MIN_PCT,
            "periodo_medido": [filas[0]["periodo_inicio"].isoformat(), filas[0]["periodo_fin"].isoformat()] if filas else None,
            **medido, "ventana_dias": VENTANA_OPTICA_DIAS, "nubosidad_escena_max_pct": NUBOSIDAD_ESCENA_MAX_PCT,
            "ventanas_con_pasada_min_pct": VENTANAS_CON_PASADA_MIN_PCT}


VISIBLE_MIN = 0.8  # fraccion del poligono que debe verse para que un NDVI cuente


async def leer_ndvi(session: AsyncSession, id_parcela: int, desde: date) -> list[dict]:
    """Observaciones de NDVI del poligono desde `desde`: [{'fecha' (centro del intervalo),
    'ndvi', 'visible'}], solo los intervalos en que se vio al menos VISIBLE_MIN del predio."""
    filas = (await session.execute(text("""
        SELECT periodo_inicio, periodo_fin,
               max(valor) FILTER (WHERE capa = 'sentinel2_ndvi_5d') AS ndvi,
               max(valor) FILTER (WHERE capa = 'sentinel2_visible_5d') AS visible
        FROM cache_consulta_grilla
        WHERE id_parcela = :id AND capa IN ('sentinel2_ndvi_5d', 'sentinel2_visible_5d') AND periodo_inicio >= :desde
        GROUP BY periodo_inicio, periodo_fin ORDER BY periodo_inicio
    """), {"id": id_parcela, "desde": desde})).mappings().all()
    return [{"fecha": f["periodo_inicio"] + (f["periodo_fin"] - f["periodo_inicio"]) / 2,
             "ndvi": f["ndvi"], "visible": f["visible"]}
            for f in filas if f["ndvi"] is not None and (f["visible"] or 0) >= VISIBLE_MIN]
