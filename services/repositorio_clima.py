"""
Repositorio de clima v0.1 -- primera pieza real de la Fase 5 del plan (todavia no
completa: falta leer_clima_desde_cache() y actualizar_grilla_parcela() orquestando
cliente_power + cliente_appeears, ver plan). Esto solo cubre lo necesario para que
las fuentes nuevas (cliente_solar, cliente_copernicus) puedan escribir en
cache_consulta_grilla de verdad, no solo devolver datos sueltos.

cache_consulta_grilla ya esta disenada para ser generica por fuente (ver comentario en
database/schema.sql: "HLS, SRTM, SMAP, POWER, ECOSTRESS -- todo lo que se consulta por
poligono o centroide de un predio especifico") -- no hizo falta ninguna columna nueva
para Explorador Solar ni Copernicus, solo valores nuevos de `capa`/`version_producto`.
"""
from __future__ import annotations

import json
import math
from datetime import date, timedelta

import numpy as np
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
# La misma radiacion mensual (kWh/m2/dia), de la climatologia de 25 anos de NASA POWER. Es global y manda en
# leer_sitio(); el Explorador Solar (solo Chile, mas fino) queda de respaldo.
CAPAS_GHI_POWER = tuple(f"power_ghi_mes_{m:02d}" for m in range(1, 13))
FUENTE_RADIACION_POWER = "NASA POWER"
FUENTE_RADIACION_EXPLORADOR = "Explorador Solar (Chile)"
# leer_sitio()["fuente_clima"]: "cr2met" (Chile), "power" (POWER sin corregir o corregido solo contra CR2MET parcial) o esto.
FUENTE_CLIMA_POWER_DAYMET = "power_daymet"
# Factor por mes que lleva la ET0 de Hargreaves (con el clima de CR2MET) al nivel de Penman-Monteith (ERA5): ver
# ingesta_predio._clima_historico. Enero = mes 1.
CAPAS_ET0_FACTOR_MENSUAL = tuple(f"et0_factor_hargreaves_mes_{m:02d}" for m in range(1, 13))
_CAPAS_CLIMA = {"cr2met_tmin": "tmin", "cr2met_tmax": "tmax", "cr2met_lluvia": "lluvia"}
_CAPAS_POWER = {"power_tmin": "tmin", "power_tmax": "tmax", "power_lluvia": "lluvia"}
_CAPAS_DAYMET = {"daymet_tmin": "tmin", "daymet_tmax": "tmax", "daymet_lluvia": "lluvia"}
# Daymet publica el ano completo con meses de retraso: la ventana de doce meses casi nunca le queda dentro. Se mide el
# sesgo de POWER en los ultimos anos con dato de los dos (desde el 1 de enero de hace tantos anos), no en la ventana.
ANIOS_TRASLAPE_DAYMET = 3
COBERTURA_CR2MET_MIN = 0.9   # fraccion de dias de la ventana con CR2MET para llamar al clima "cr2met"


PROFUNDIDAD_AGUA_SUELO_MM = 2000     # CLSoilMaps suma 0-200 cm: la estimacion usa la misma profundidad
AGUA_SUELO_ESTIMADA_LIMITES_MM = (50.0, 600.0)
MATERIA_ORGANICA_MAX_PCT = 8.0       # tope de validez de Saxton y Rawls: por encima se extrapola
FUENTE_AGUA_CLSOILMAPS = "clsoilmaps"
FUENTE_AGUA_TEXTURA = "estimado_textura"


def estimar_agua_disponible_mm(arcilla_pct: float | None, arena_pct: float | None,
                               carbono_organico_g_kg: float | None) -> float | None:
    """Agua aprovechable (mm en 0-200 cm) estimada desde la textura, para donde CLSoilMaps (solo Chile) no llega.
    Ecuaciones de pedotransferencia de Saxton y Rawls (2006): contenido de agua a capacidad de campo (33 kPa) menos
    el del punto de marchitez (1500 kPa), con arcilla, arena y materia organica (carbono x 1,724) de SoilGrids, y
    multiplicado por 2000 mm de perfil. Limites de esa fuente: SoilGrids da la capa superficial y aqui se extiende
    a todo el perfil, la materia organica se acota a 8 % (las ecuaciones no valen mas alla: con 12 % de Oregon sale 321 mm
    y con 8 %, 314; sin tope, un suelo de turba de Chiloe daria 600 mm contra 437 medidos), y no hay pedregosidad ni salinidad. Es una estimacion gruesa (mas baja que CLSoilMaps en
    Chiloe: unos 280 mm para un franco contra 437 medidos), y por eso se informa como estimada. None si falta un dato."""
    if arcilla_pct is None or arena_pct is None or carbono_organico_g_kg is None:
        return None
    s, c = arena_pct / 100.0, arcilla_pct / 100.0
    mo = min(carbono_organico_g_kg * 1.724 / 10.0, MATERIA_ORGANICA_MAX_PCT)
    t1500 = -0.024 * s + 0.487 * c + 0.006 * mo + 0.005 * s * mo - 0.013 * c * mo + 0.068 * s * c + 0.031
    t1500 += 0.14 * t1500 - 0.02
    t33 = -0.251 * s + 0.195 * c + 0.011 * mo + 0.006 * s * mo - 0.027 * c * mo + 0.452 * s * c + 0.299
    t33 += 1.283 * t33 ** 2 - 0.374 * t33 - 0.015
    bajo, alto = AGUA_SUELO_ESTIMADA_LIMITES_MM
    return min(max((t33 - t1500) * PROFUNDIDAD_AGUA_SUELO_MM, bajo), alto)


def inicio_traslape_daymet(hoy: date) -> date:
    """Desde cuando se guarda el clima de POWER para medir su sesgo contra Daymet (anterior a la ventana)."""
    return date(hoy.year - ANIOS_TRASLAPE_DAYMET, 1, 1)


def elegir_referencia(cr2met: pd.DataFrame, daymet: pd.DataFrame) -> tuple[str | None, pd.DataFrame | None]:
    """La serie contra la que se corrigen POWER y ERA5: CR2MET si trae dias suficientes (Chile), si no Daymet
    (Norteamerica, Hawai y Puerto Rico), si no ninguna. Devuelve ('cr2met' | 'daymet' | None, serie)."""
    for nombre, serie in (("cr2met", cr2met), ("daymet", daymet)):
        if int(serie[["tmin", "tmax", "lluvia"]].notna().all(axis=1).sum()) >= MIN_DIAS_TRASLAPE:
            return nombre, serie
    return None, None


async def leer_historia(session: AsyncSession, id_parcela: int) -> dict[int, pd.DataFrame]:
    """El clima diario historico del predio, corregido: {ano: DataFrame(tmin, tmax, lluvia)} con un dia por
    fila desde el 1 de enero. Vacio si todavia no se ingirio."""
    filas = (await session.execute(text(
        "SELECT anio, tmin, tmax, lluvia FROM clima_historico_parcela WHERE id_parcela = :id ORDER BY anio"
    ), {"id": id_parcela})).mappings().all()
    return {f["anio"]: pd.DataFrame({"tmin": f["tmin"], "tmax": f["tmax"], "lluvia": f["lluvia"]},
                                      index=pd.date_range(f"{f['anio']}-01-01", periods=len(f["tmin"]), freq="D"))
            for f in filas}


async def guardar_historia(session: AsyncSession, id_parcela: int, anios: dict[int, pd.DataFrame],
                           fuente: str, version: str) -> None:
    """Upsert del clima historico, un renglon por ano, en un solo viaje y un solo commit."""
    filas = [{"id": id_parcela, "anio": a, "tmin": [round(float(v), 2) for v in d["tmin"]],
              "tmax": [round(float(v), 2) for v in d["tmax"]], "lluvia": [round(float(v), 1) for v in d["lluvia"]],
              "fuente": fuente, "version": version} for a, d in anios.items()]
    if filas:
        await session.execute(text("""
            INSERT INTO clima_historico_parcela (id_parcela, anio, tmin, tmax, lluvia, fuente, version_producto)
            VALUES (:id, :anio, :tmin, :tmax, :lluvia, :fuente, :version)
            ON CONFLICT (id_parcela, anio) DO UPDATE SET tmin = EXCLUDED.tmin, tmax = EXCLUDED.tmax,
                lluvia = EXCLUDED.lluvia, fuente = EXCLUDED.fuente, version_producto = EXCLUDED.version_producto,
                fecha_consulta = now()
        """), filas)
    await session.commit()


async def leer_factores_et0(session: AsyncSession, id_parcela: int) -> list[float] | None:
    """Los 12 factores de calibracion de la ET0 del predio (enero primero), o None si no estan todos."""
    filas = (await session.execute(text(
        "SELECT capa, valor FROM cache_consulta_grilla WHERE id_parcela = :id AND capa = ANY(:capas)"
    ), {"id": id_parcela, "capas": list(CAPAS_ET0_FACTOR_MENSUAL)})).mappings().all()
    valores = {f["capa"]: f["valor"] for f in filas}
    factores = [valores.get(c) for c in CAPAS_ET0_FACTOR_MENSUAL]
    return factores if all(v is not None for v in factores) else None


async def leer_sitio(session: AsyncSession, id_parcela: int, hoy: date | None = None) -> dict:
    """Lo que catalogo_especies.ranking_idoneidad() necesita de un predio, leido de
    cache_consulta_grilla: pH, arcilla y arena (SoilGrids), agua disponible (CLSoilMaps), GHI mensual
    (Explorador Solar) y el clima diario de la ventana de doce meses (CR2MET). Cada dato
    que falte queda en None -- quien llama decide que hacer, aca no se inventa nada."""
    inicio, fin = ventana_clima(hoy or date.today())
    estaticas = ["soilgrids_ph", "soilgrids_arcilla_pct", "soilgrids_arena_pct", "soilgrids_carbono_organico_g_kg",
                 "clsoilmaps_awc_total_mm",
                 "cr2met_elevacion_celda_m", *CAPAS_ET0_FACTOR_MENSUAL, *CAPAS_GHI_MENSUAL, *CAPAS_GHI_POWER]
    filas = (await session.execute(text(
        "SELECT capa, valor FROM cache_consulta_grilla WHERE id_parcela = :id AND capa = ANY(:capas)"
    ), {"id": id_parcela, "capas": estaticas})).mappings().all()
    valores = {f["capa"]: f["valor"] for f in filas}
    ghi_power = [valores.get(c) for c in CAPAS_GHI_POWER]
    ghi_explorador = [valores.get(c) for c in CAPAS_GHI_MENSUAL]
    if all(v is not None for v in ghi_power):
        ghi, fuente_radiacion = ghi_power, FUENTE_RADIACION_POWER
    elif all(v is not None for v in ghi_explorador):
        ghi, fuente_radiacion = ghi_explorador, FUENTE_RADIACION_EXPLORADOR
    else:
        ghi, fuente_radiacion = [None], None
    et0_factor = [valores.get(c) for c in CAPAS_ET0_FACTOR_MENSUAL]

    hoy = hoy or date.today()
    filas_clima = (await session.execute(text("""
        SELECT periodo_inicio AS fecha, capa, valor FROM cache_consulta_grilla
        WHERE id_parcela = :id AND capa = ANY(:capas) AND valor IS NOT NULL
          AND periodo_inicio BETWEEN :inicio AND :fin
        ORDER BY periodo_inicio
    """), {"id": id_parcela, "capas": [*_CAPAS_CLIMA, *_CAPAS_POWER, *_CAPAS_DAYMET],
           "inicio": min(inicio, inicio_traslape_daymet(hoy)), "fin": fin})).mappings().all()
    clima, fuente_clima = None, None
    if filas_clima:
        ancho = pd.DataFrame(filas_clima).pivot(index="fecha", columns="capa", values="valor")
        ancho.index = pd.to_datetime(ancho.index)
        en_ventana = (ancho.index >= pd.Timestamp(inicio)) & (ancho.index <= pd.Timestamp(fin))

        def de(capas: dict) -> pd.DataFrame:
            return ancho.reindex(columns=list(capas)).rename(columns=capas)[["tmin", "tmax", "lluvia"]]

        cr2met, power = de(_CAPAS_CLIMA)[en_ventana], de(_CAPAS_POWER)
        # Donde CR2MET existe manda; POWER (global, celda de ~55 km) rellena lo que falte, corregido contra la
        # referencia (CR2MET, o Daymet fuera de Chile) donde ambos se solapan (igual que leer_clima_diario).
        origen, referencia = elegir_referencia(cr2met, de(_CAPAS_DAYMET))
        if origen != "daymet":
            power = power[en_ventana]     # con CR2MET solo cuenta la ventana, como siempre
        sesgo = None if referencia is None else _sesgo_power(referencia, power)
        power = _corregir(power, sesgo)
        power = power[(power.index >= pd.Timestamp(inicio)) & (power.index <= pd.Timestamp(fin))]
        clima = cr2met.combine_first(power).dropna(how="all")
        if not clima.empty:
            dias_ventana = (fin - inicio).days + 1
            dias_cr2met = int(cr2met[["tmin", "tmax"]].notna().all(axis=1).sum())
            if dias_cr2met >= COBERTURA_CR2MET_MIN * dias_ventana:
                fuente_clima = "cr2met"
            else:
                fuente_clima = FUENTE_CLIMA_POWER_DAYMET if origen == "daymet" and sesgo else "power"
        else:
            clima = None

    # Altura media del predio segun el mismo DEM con que se calculo la de la celda de CR2MET:
    # la diferencia entre ambas es la correccion de temperatura por altitud.
    altitud_dem = (await session.execute(text(
        "SELECT avg(valor) FROM cache_celda WHERE id_parcela = :id AND capa = 'altitud_m' AND valor IS NOT NULL"
    ), {"id": id_parcela})).scalar()
    awc_mm, fuente_agua = valores.get("clsoilmaps_awc_total_mm"), FUENTE_AGUA_CLSOILMAPS
    if awc_mm is None:
        awc_mm = estimar_agua_disponible_mm(valores.get("soilgrids_arcilla_pct"), valores.get("soilgrids_arena_pct"),
                                            valores.get("soilgrids_carbono_organico_g_kg"))
        fuente_agua = FUENTE_AGUA_TEXTURA if awc_mm is not None else None
    return {"ph": valores.get("soilgrids_ph"), "awc_mm": awc_mm, "fuente_agua_suelo": fuente_agua,
            "arcilla_pct": valores.get("soilgrids_arcilla_pct"), "arena_pct": valores.get("soilgrids_arena_pct"),
            "altitud_celda_m": valores.get("cr2met_elevacion_celda_m"),
            "altitud_dem_m": None if altitud_dem is None else float(altitud_dem),
            "ghi_mensual": ghi if all(v is not None for v in ghi) else None, "fuente_radiacion": fuente_radiacion,
            "et0_factor_mensual": et0_factor if all(v is not None for v in et0_factor) else None,
            "clima": clima, "fuente_clima": fuente_clima, "periodo_clima": (inicio, fin)}


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

    Contra Daymet (17-nov-2026, mismos tres puntos, ajuste con anos pares y prueba en impares) la media mensual
    baja el error absoluto de tmin de POWER de 1,01 / 3,18 / 1,84 a 1,00 / 2,12 / 1,71 (Willamette / Montana /
    Iowa). En las heladas ayuda donde el sesgo es grande (Montana, POWER 2,5 C mas frio: 211 dias con tmin < 0 por
    ano contra 167 de Daymet, corregido 160) y no donde es chico (Willamette: 41 sin corregir, 45 corregido, 42
    Daymet; Iowa: 144 / 150 / 145). Los cuantiles no mejoran a la media con el traslape corto de POWER.

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


def corregir_contra_referencia(referencia: pd.DataFrame, otra: pd.DataFrame) -> tuple[pd.DataFrame, dict | None]:
    """La serie `otra` (tmin, tmax, lluvia) corregida con su sesgo contra la serie de referencia del mismo predio
    (CR2MET, o Daymet fuera de Chile; ver elegir_referencia), y el sesgo aplicado (None si no hay dias en comun
    suficientes: entonces no se corrige)."""
    sesgo = _sesgo_power(referencia, otra)
    return _corregir(otra, sesgo), sesgo


CUANTILES_AJUSTE = np.linspace(0.02, 0.98, 49)
VENTANA_CUANTILES_DIAS = 15     # el mapa de un dia del ano se arma con los dias a +-15 de ese dia, de todos los anos
MIN_DIAS_CUANTILES = 5 * 365    # con menos traslape que esto los cuantiles no se sostienen: queda la media mensual


def corregir_historia_contra_daymet(daymet: pd.DataFrame, era5: pd.DataFrame) -> tuple[pd.DataFrame, str | None]:
    """ERA5 (tmin, tmax, lluvia; decadas de dias) corregido contra Daymet. Devuelve la serie y el metodo usado:
    'cuantiles' o 'media_mensual' (None si no hay traslape suficiente: se devuelve sin corregir).

    tmax y lluvia llevan la correccion de siempre (corregir_contra_referencia). La minima, con cuantiles por dia
    del ano: cada valor de ERA5 pasa al valor de Daymet que tiene su mismo rango entre los dias parecidos del
    ano; fuera del rango ajustado se le suma el desplazamiento del extremo. Restar una media por mes no devuelve
    los extremos que la celda aplana; esto si, y es lo que cuenta las heladas.

    MEDIDO el 17-nov-2026 con ERA5 y Daymet de 1991 a 2025, ajustando con los anos pares (17 anos) y probando
    en los impares, en tres puntos: Willamette (Oregon, 45,00 N 123,15 O), Montana (46,87 N 113,99 O) e Iowa
    (42,03 N 93,62 O). Dias de helada por ano (tmin < 0 C) en los anos de prueba, Daymet / ERA5 sin corregir /
    media mensual / cuantiles: Willamette 42,4 / 63,0 / 49,7 / 43,7; Montana 167,1 / 136,2 / 166,5 / 170,3; Iowa
    144,9 / 128,6 / 143,6 / 144,1. Con tmin < -2 C: 14,8 / 32,7 / 21,8 / 16,4; 127,5 / 102,8 / 119,7 / 130,3;
    118,2 / 107,4 / 121,5 / 118,4. Error absoluto medio de tmin: 1,06 / 0,87 / 0,84; 2,81 / 2,01 / 1,96; 2,16 /
    1,61 / 1,55 (sin corregir / media / cuantiles). Los cuantiles igualan o mejoran a la media en las heladas, y
    donde mas pesa es en climas templados como Willamette, donde la helada es un evento marginal. Con pocos anos
    de ajuste ya no ganan (con los ultimos 10 y prueba en los 25 anteriores, Willamette dio 34,2 contra 39,8 de
    Daymet con cuantiles y 42,3 con media): por eso solo se usan con el registro largo y no con el traslape de
    unos pocos anos que tiene POWER, que sigue con la media mensual."""
    comun = daymet[["tmin", "tmax", "lluvia"]].join(era5[["tmin", "tmax", "lluvia"]], rsuffix="_e").dropna()
    corregido, sesgo = corregir_contra_referencia(daymet, era5[["tmin", "tmax", "lluvia"]])
    if sesgo is None:
        return corregido, None
    if len(comun) < MIN_DIAS_CUANTILES:
        return corregido, "media_mensual"
    dia_comun = comun.index.dayofyear.to_numpy()
    dia_era5 = era5.index.dayofyear.to_numpy()
    minima = era5["tmin"].to_numpy(dtype=float).copy()
    for dia in range(1, 367):
        cerca = np.abs(dia_comun - dia)
        cerca = np.minimum(cerca, 366 - cerca) <= VENTANA_CUANTILES_DIAS
        indices = np.flatnonzero(dia_era5 == dia)
        if cerca.sum() < 60 or not len(indices):
            continue
        origen = np.quantile(comun["tmin_e"].to_numpy()[cerca], CUANTILES_AJUSTE)
        destino = np.quantile(comun["tmin"].to_numpy()[cerca], CUANTILES_AJUSTE)
        x = era5["tmin"].to_numpy(dtype=float)[indices]
        y = np.interp(x, origen, destino)
        y = np.where(x < origen[0], x + destino[0] - origen[0], y)
        minima[indices] = np.where(x > origen[-1], x + destino[-1] - origen[-1], y)
    corregido = corregido.copy()
    corregido["tmin"] = pd.Series(minima, index=era5.index)
    corregido["tmin"] = corregido[["tmin", "tmax"]].min(axis=1).where(corregido["tmin"].notna())
    return corregido, "cuantiles"


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
    capas = [f"{p}_{v}" for p in ("cr2met", "power", "openmeteo", "daymet") for v in ("tmin", "tmax", "lluvia", "rh")]
    filas = (await session.execute(text("""
        SELECT periodo_inicio AS fecha, capa, valor, fecha_consulta::date AS consultado
        FROM cache_consulta_grilla
        WHERE id_parcela = :id AND capa = ANY(:capas) AND valor IS NOT NULL AND periodo_inicio >= :desde
    """), {"id": id_parcela, "capas": capas, "desde": min(desde - timedelta(days=DIAS_ESTIMADOS_MAX + 1), inicio_traslape_daymet(hoy))})).mappings().all()
    if not filas:
        return None
    crudo = pd.DataFrame(filas)
    crudo["fecha"] = pd.to_datetime(crudo["fecha"])
    ancho = crudo.pivot(index="fecha", columns="capa", values="valor").reindex(columns=capas)

    def de(prefijo: str) -> pd.DataFrame:
        return ancho[[f"{prefijo}_{v}" for v in ("tmin", "tmax", "lluvia", "rh")]].set_axis(
            ["tmin", "tmax", "lluvia", "rh"], axis=1)

    corte = pd.Timestamp(desde - timedelta(days=DIAS_ESTIMADOS_MAX + 1))
    cr2met, power, modelo, daymet = de("cr2met"), de("power"), de("openmeteo"), de("daymet")
    origen, referencia = elegir_referencia(cr2met, daymet)
    if origen != "daymet":
        cr2met, power, modelo = (b[b.index >= corte] for b in (cr2met, power, modelo))   # con CR2MET, como siempre
    sesgo_power = None if referencia is None else _sesgo_power(referencia, power)
    sesgo_modelo = None if referencia is None else _sesgo_modelo(referencia, modelo)
    power, modelo = _corregir(power, sesgo_power), _corregir(modelo, sesgo_modelo)
    power, modelo, cr2met = (b[b.index >= corte] for b in (power, modelo, cr2met))
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
            respaldo = ("power_corregido_daymet" if origen == "daymet" else "power_corregido") if sesgo_power else "power"
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


HUMEDAD_SUELO_VENTANA_DIAS = 14   # POWER publica con unos dias de atraso: se mira un tramo, no solo hoy
HUMEDAD_SUELO_DIAS_MOSTRADOS = 7
RESOLUCION_HUMEDAD_SUELO_KM = 50  # celda de 0,5 grado de latitud


def resumir_humedad_suelo(filas) -> dict | None:
    """De las filas (capa, fecha, valor) de la humedad del suelo de NASA POWER, el dato mas reciente de la zona de
    raices y su recorrido de los ultimos dias. None si no hay ninguno. Los valores son la proporcion (0 a 1) del
    maximo que el suelo puede almacenar, en una celda de unos 50 km: contexto regional, no una medicion del predio."""
    raiz = {f["fecha"]: f["valor"] for f in filas if f["capa"] == "power_humedad_suelo_raiz"}
    if not raiz:
        return None
    superficie = {f["fecha"]: f["valor"] for f in filas if f["capa"] == "power_humedad_suelo_superficie"}
    ultimo = max(raiz)
    return {"zona_raices": round(raiz[ultimo], 2),
            "superficie": round(superficie[ultimo], 2) if ultimo in superficie else None,
            "fecha": ultimo.isoformat(),
            "ultimos_dias": [{"fecha": d.isoformat(), "zona_raices": round(v, 2)}
                             for d, v in sorted(raiz.items())[-HUMEDAD_SUELO_DIAS_MOSTRADOS:]],
            "fuente": "NASA POWER", "resolucion_km": RESOLUCION_HUMEDAD_SUELO_KM}


async def leer_humedad_suelo_nasa(session: AsyncSession, id_parcela: int, hoy: date | None = None) -> dict | None:
    hoy = hoy or date.today()
    filas = (await session.execute(text("""
        SELECT capa, periodo_inicio AS fecha, valor FROM cache_consulta_grilla
        WHERE id_parcela = :id AND capa IN ('power_humedad_suelo_raiz', 'power_humedad_suelo_superficie')
          AND valor IS NOT NULL AND periodo_inicio <= :hoy AND periodo_inicio > :desde
        ORDER BY periodo_inicio
    """), {"id": id_parcela, "hoy": hoy, "desde": hoy - timedelta(days=HUMEDAD_SUELO_VENTANA_DIAS)})).mappings().all()
    return resumir_humedad_suelo(filas)


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
    'ndvi', 'visible', 'fuente'}], solo los intervalos en que se vio al menos VISIBLE_MIN del predio.
    Sentinel-2 (10 m) manda; NASA HLS (30 m) completa los intervalos donde Sentinel-2 no tiene un dato
    valido, y es la unica fuente donde no hay credenciales de Copernicus."""
    filas = (await session.execute(text("""
        SELECT periodo_inicio, periodo_fin,
               max(valor) FILTER (WHERE capa = 'sentinel2_ndvi_5d') AS ndvi,
               max(valor) FILTER (WHERE capa = 'sentinel2_visible_5d') AS visible,
               max(valor) FILTER (WHERE capa = 'hls_ndvi_5d') AS ndvi_hls,
               max(valor) FILTER (WHERE capa = 'hls_visible_5d') AS visible_hls
        FROM cache_consulta_grilla
        WHERE id_parcela = :id AND periodo_inicio >= :desde
          AND capa IN ('sentinel2_ndvi_5d', 'sentinel2_visible_5d', 'hls_ndvi_5d', 'hls_visible_5d')
        GROUP BY periodo_inicio, periodo_fin ORDER BY periodo_inicio
    """), {"id": id_parcela, "desde": desde})).mappings().all()
    observaciones = []
    for f in filas:
        for ndvi, visible, fuente in ((f["ndvi"], f["visible"], "Sentinel-2"), (f["ndvi_hls"], f["visible_hls"], "HLS (NASA)")):
            if ndvi is not None and (visible or 0) >= VISIBLE_MIN:
                observaciones.append({"fecha": f["periodo_inicio"] + (f["periodo_fin"] - f["periodo_inicio"]) / 2,
                                      "ndvi": ndvi, "visible": visible, "fuente": fuente})
                break
    return observaciones


# ---------------------------------------------------------------- mapa del predio (grilla)
LADO_ACRE_M = 63.615       # lado de un cuadrado de un acre (4046,86 m2)
# Tope de celdas por predio: cada celda es una consulta al satelite en cada refresco. Un
# predio que con celdas de un acre pasaria el tope usa celdas de 2, 3... acres de lado.
CELDAS_MAX = 150
FRACCION_MIN_CELDA = 0.1   # una celda con menos que esto dentro del perimetro se dibuja pero no se consulta
DIAS_MAPA_MAX = 120        # un dato de vegetacion mas viejo que esto ya no se muestra como estado actual
CELDAS_COMUNES_MIN = 0.8   # fraccion de celdas que debe verse en una misma pasada para usarla como fecha comun


# Capas que el mapa sabe dibujar. `capa_bd` es el nombre en cache_celda; `fuente_ingesta`,
# la fuente de ingesta_predio que la llena; `dinamica` dice si cambia en el tiempo (se
# elige una fecha) o es un dato fijo del terreno.
CAPAS_MAPA = {
    "ndvi": {"capa_bd": "ndvi", "dinamica": True, "fuente_ingesta": "sentinel2_celdas", "resolucion_m": 10,
             "unidad": "NDVI (0 a 1; mas alto = vegetacion mas vigorosa)", "fuente": "Sentinel-2 L2A (Copernicus)"},
    "ndvi_hls": {"capa_bd": "ndvi_hls", "dinamica": True, "fuente_ingesta": "hls_celdas", "resolucion_m": 30,
                 "unidad": "NDVI (0 a 1; mas alto = vegetacion mas vigorosa)", "fuente": "HLS v2.0 (NASA: Landsat 8/9 y Sentinel-2)"},
    "altitud": {"capa_bd": "altitud_m", "dinamica": False, "fuente_ingesta": "relieve", "resolucion_m": 30,
                "unidad": "metros sobre el nivel del mar", "fuente": "Copernicus DEM GLO-30 (modelo de superficie)"},
    "pendiente": {"capa_bd": "pendiente_pct", "dinamica": False, "fuente_ingesta": "relieve", "resolucion_m": 30,
                  "unidad": "% de pendiente", "fuente": "Copernicus DEM GLO-30 (modelo de superficie)"},
    "hand": {"capa_bd": "hand_m", "dinamica": False, "fuente_ingesta": "inundacion", "resolucion_m": 30,
             "unidad": "metros sobre el cauce mas cercano",
             "fuente": "HAND global 30 m del ASF DAAC de NASA (sobre Copernicus DEM GLO-30)"},
}

# Clases de cercania al cauce segun el HAND medio de la celda. Son un criterio de lectura, no un
# umbral de crecida: el HAND no conoce caudales, lluvia, diques ni mareas.
HAND_MUY_CERCA_M = 2.0
HAND_CERCA_M = 5.0
FRACCION_MIN_CERCANIA = 0.1   # parte del predio que debe caer en una clase para que el predio entero la tome


async def leer_cercania_cauce(session: AsyncSession, id_parcela: int) -> dict:
    """Resumen de la cercania al cauce del predio, a partir de la capa 'hand_m' por celda:
    `clase` ('muy_cerca' bajo HAND_MUY_CERCA_M, 'cerca' bajo HAND_CERCA_M, 'lejos'), la parte del
    predio en cada franja y el HAND minimo y mediano. Cada celda pesa por la parte de ella
    que cae dentro del perimetro. `clase` es None mientras no haya dato."""
    celdas = {(c["i"], c["j"]): c["fraccion"] for c in await leer_grilla(session, id_parcela)}
    filas = (await session.execute(text("""
        SELECT DISTINCT ON (celda_i, celda_j) celda_i AS i, celda_j AS j, valor FROM cache_celda
        WHERE id_parcela = :id AND capa = 'hand_m' AND valor IS NOT NULL ORDER BY celda_i, celda_j, periodo_inicio DESC
    """), {"id": id_parcela})).mappings().all()
    datos = [(f["valor"], celdas.get((f["i"], f["j"]), 0.0)) for f in filas]
    area = sum(w for _, w in datos)
    if not datos or area <= 0:
        return {"clase": None, "celdas_con_dato": 0, "umbrales_m": [HAND_MUY_CERCA_M, HAND_CERCA_M]}
    parte = lambda tope: sum(w for v, w in datos if v < tope) / area
    muy_cerca, cerca = parte(HAND_MUY_CERCA_M), parte(HAND_CERCA_M)
    valores = sorted(v for v, _ in datos)
    clase = ("muy_cerca" if muy_cerca >= FRACCION_MIN_CERCANIA
             else "cerca" if cerca >= FRACCION_MIN_CERCANIA else "lejos")
    return {"clase": clase, "celdas_con_dato": len(datos), "umbrales_m": [HAND_MUY_CERCA_M, HAND_CERCA_M],
            "parte_muy_cerca": round(muy_cerca, 2), "parte_cerca": round(cerca, 2),
            "hand_minimo_m": round(valores[0], 1), "hand_mediano_m": round(valores[len(valores) // 2], 1)}


def lado_celda_para(area_m2: float) -> float:
    """Lado de celda para un predio de esa superficie: un acre, o el multiplo entero de
    ese lado que deja la grilla bajo CELDAS_MAX."""
    factor = max(1, math.ceil(math.sqrt(area_m2 / LADO_ACRE_M ** 2 / CELDAS_MAX)))
    return LADO_ACRE_M * factor


async def leer_grilla(session: AsyncSession, id_parcela: int) -> list[dict]:
    """Las celdas del predio, recortadas a su perimetro: [{'i', 'j', 'geometria' (GeoJSON
    WGS84), 'fraccion' (parte de la celda que queda dentro), 'relleno' (parte de la caja
    de la celda recortada que ocupa su geometria)}]. La grilla es ST_SquareGrid sobre el
    perimetro en parcela.srid_utm con celdas de parcela.lado_celda_m: mientras esos dos
    valores y el perimetro no cambien, los indices (i, j) son siempre los mismos."""
    filas = (await session.execute(text("""
        WITH p AS (SELECT ST_Transform(geometria, srid_utm) AS g, lado_celda_m AS lado FROM parcela WHERE id = :id),
             c AS (SELECT s.i, s.j, p.lado, ST_CollectionExtract(ST_Intersection(s.geom, p.g), 3) AS dentro
                   FROM p, LATERAL ST_SquareGrid(p.lado, p.g) s WHERE ST_Intersects(s.geom, p.g))
        SELECT i, j, ST_AsGeoJSON(ST_Transform(dentro, 4326), 6) AS geojson,
               ST_Area(dentro) / (lado * lado) AS fraccion,
               ST_Area(dentro) / ST_Area(ST_Envelope(ST_Transform(dentro, 4326))::geography) AS relleno
        FROM c WHERE ST_Area(dentro) > 1 ORDER BY j DESC, i
    """), {"id": id_parcela})).mappings().all()
    return [{"i": f["i"], "j": f["j"], "geometria": json.loads(f["geojson"]),
             "fraccion": min(1.0, f["fraccion"]), "relleno": min(1.0, f["relleno"])} for f in filas]


async def guardar_celdas(session: AsyncSession, filas: list[dict]) -> None:
    """Upsert en cache_celda. Cada fila: id_parcela, celda_i, celda_j, capa, periodo_inicio,
    periodo_fin, valor, visible."""
    if filas:
        await session.execute(text("""
            INSERT INTO cache_celda (id_parcela, celda_i, celda_j, capa, periodo_inicio, periodo_fin, valor, visible)
            VALUES (:id_parcela, :celda_i, :celda_j, :capa, :periodo_inicio, :periodo_fin, :valor, :visible)
            ON CONFLICT (id_parcela, celda_i, celda_j, capa, periodo_inicio) DO UPDATE SET
                periodo_fin = EXCLUDED.periodo_fin, valor = EXCLUDED.valor, visible = EXCLUDED.visible,
                fecha_consulta = now()
        """), filas)
    await session.commit()


async def leer_mapa(session: AsyncSession, id_parcela: int, capa: str = "ndvi", hoy: date | None = None) -> dict:
    """El mapa del predio como GeoJSON: una entidad por celda, con la forma del perimetro,
    y el ultimo valor util de `capa` en cada una.

    Si hay una pasada reciente en que se vio la mayoria de las celdas, todas muestran esa
    fecha (`fecha_comun`): asi las diferencias entre celdas son del terreno y no de la
    fecha. Si no la hay (zona nublada), cada celda muestra su ultimo dato y trae su propia
    fecha. Una celda sin dato util en DIAS_MAPA_MAX queda con valor None."""
    hoy = hoy or date.today()
    config = CAPAS_MAPA[capa]
    grilla = await leer_grilla(session, id_parcela)
    # Una capa fija del terreno (relieve) no tiene fecha que elegir ni nubes que descontar.
    filas = (await session.execute(text("""
        SELECT celda_i AS i, celda_j AS j, periodo_inicio, periodo_fin, valor, visible FROM cache_celda
        WHERE id_parcela = :id AND capa = :capa AND valor IS NOT NULL
          AND (NOT :dinamica OR (visible >= :visible AND periodo_inicio >= :desde))
        ORDER BY periodo_inicio DESC
    """), {"id": id_parcela, "capa": config["capa_bd"], "dinamica": config["dinamica"], "visible": VISIBLE_MIN,
           "desde": hoy - timedelta(days=DIAS_MAPA_MAX)})).mappings().all()

    consultables = {(c["i"], c["j"]) for c in grilla if c["fraccion"] >= FRACCION_MIN_CELDA}
    por_fecha: dict[date, dict] = {}
    ultimo: dict[tuple, dict] = {}
    for f in filas:
        clave = (f["i"], f["j"])
        por_fecha.setdefault(f["periodo_inicio"], {})[clave] = f
        ultimo.setdefault(clave, f)   # las filas vienen de la mas reciente a la mas antigua
    fecha_comun = None
    if config["dinamica"]:
        fecha_comun = next((d for d in sorted(por_fecha, reverse=True)
                            if consultables and len(por_fecha[d]) >= CELDAS_COMUNES_MIN * len(consultables)), None)
    elegido = por_fecha[fecha_comun] if fecha_comun else ultimo

    entidades, valores = [], []
    for c in grilla:
        f = elegido.get((c["i"], c["j"]))
        centro = (f["periodo_inicio"] + (f["periodo_fin"] - f["periodo_inicio"]) / 2
                  if f and config["dinamica"] else None)
        if f:
            valores.append(f["valor"])
        entidades.append({"type": "Feature", "geometry": c["geometria"], "properties": {
            "i": c["i"], "j": c["j"], "fraccion_dentro": round(c["fraccion"], 2),
            "valor": round(f["valor"], 3) if f else None,
            "fecha": centro.isoformat() if centro else None,
            "dias_de_antiguedad": (hoy - centro).days if centro else None,
            "visible": round(f["visible"], 2) if f and config["dinamica"] else None}})
    valores.sort()
    return {"type": "FeatureCollection", "features": entidades, "capa": capa,
            "unidad": config["unidad"], "fuente": config["fuente"], "resolucion_de_la_fuente_m": config["resolucion_m"],
            "fecha_comun": (fecha_comun + timedelta(days=2)).isoformat() if fecha_comun else None,
            "celdas": len(grilla), "celdas_con_dato": len(valores),
            "resumen": None if not valores else {
                "minimo": round(valores[0], 3), "maximo": round(valores[-1], 3),
                "mediana": round(valores[len(valores) // 2], 3)}}
