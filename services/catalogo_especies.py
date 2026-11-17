"""
Catalogo de especies v0.1
=========================
Construye Cultivo (pheno_engine), entradas de PERFIL (motor_rotacion) y reglas de dano
(motor_estres) a partir de datos, no de diccionarios fijos en codigo. Esto es lo que
permite incorporar una especie nueva sin escribir Python: basta con que existan filas
en requisitos_especie / umbral_fenologico_config / rasgos_rotacion_especie /
regla_dano_especie (database/schema.sql) -- a mano, vía GAEZ, vía ficha tecnica, o vía
caracteristica_variedad_aportada acumulada de agricultores.

La jerarquia de madurez de la especie (docs/modelo-conceptual-phenoshield.md 8.3) decide
que se puede construir, no solo que etiqueta mostrar:

  sin_perfil                 -> no hay nada. No se puede construir ni Cultivo ni idoneidad.
  perfil_generico             -> hay requisitos_especie (tb/to/tc, humedad, luz, suelo).
                                  Permite calcular_idoneidad(). construir_cultivo() falla
                                  explicito -- no hay reparto de GDD por etapa todavia.
  perfil_fenologico_regional  -> hay umbral_fenologico_config (aunque sea placeholder).
                                  construir_cultivo() ya puede simular, con confianza baja.
  perfil_calibrado            -> umbral_fenologico_config.fuente no es placeholder ni derivada de FAO-56.

Este modulo no asume un motor de base de datos particular -- recibe un `repo` (cualquier
objeto con los cuatro metodos async de RepositorioEspecies) para poder probarse sin
Postgres, y para que el repositorio real (SQLAlchemy sobre database/schema.sql,
services/repositorio_postgres.py) se conecte sin cambiar esta logica.

Todo async, de punta a punta, porque la implementacion real hace I/O de verdad contra
Postgres -- RepositorioEnMemoria tambien es async (sin esperar nada) solo para cumplir
la misma interfaz, no porque lo necesite.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from statistics import median
from typing import Protocol

import pandas as pd

from pheno_engine import ClimaIncompleto, Cultivo, actualizar_calendario_con_confirmacion, simular
from motor_estres import (PROFUNDIDAD_SUELO_M, ParametrosAgua, Regla, balance_agua, balance_agua_fao56, evaluar,
                          et0_hargreaves, factores_et0, fases, kc_diario, zona_raices_mm)
from riego import recomendar_riego
from cultivos_reconocidos import es_cultivo_reconocido


class EspecieSinPerfil(Exception):
    """No hay ningun dato (ni siquiera generico) para esta especie/variedad."""


class EspecieSinPerfilFenologico(Exception):
    """Hay requisitos_especie (sirve para idoneidad de sitio) pero no
    umbral_fenologico_config -- no se puede construir un reloj de GDD todavia."""


class RepositorioEspecies(Protocol):
    async def requisitos(self, especie: str, variedad_local: str | None) -> dict | None: ...
    async def umbrales_fenologicos(self, especie: str, variedad_local: str | None) -> list[dict]: ...
    async def rasgos_rotacion(self, especie: str) -> dict | None: ...
    async def especies_con_rasgos_rotacion(self) -> list[str]: ...
    async def reglas_dano(self, especie: str, variedad_local: str | None) -> list[dict]: ...
    async def listar_especies(self) -> list[tuple[str, str | None]]: ...
    async def requisitos_genericos(self) -> list[dict]: ...
    async def especies_con_fenologia(self) -> set[str]: ...
    async def identidades(self) -> dict[str, dict]: ...
    async def equivalencias_luz(self) -> list[dict]: ...
    async def parametros_agua(self, especie: str) -> dict | None: ...


# Agua aprovechable de 0 a 200 cm cuando el predio no tiene el dato de CLSoilMaps (un franco medio da unos
# 150 mm por metro). Antes eran 100 mm para todo el perfil; ahora la capacidad se reparte por la profundidad
# de raices, y 100 mm dejaban una zona de raices de 25 mm: una sequia segura.
AWC_POR_DEFECTO_MM = 200.0


async def construir_parametros_agua(especie: str, repo: RepositorioEspecies) -> ParametrosAgua | None:
    """Los parametros de agua FAO-56 del cultivo, o None si no estan cargados: el balance cae al balde viejo."""
    fila = await repo.parametros_agua(especie)
    if not fila:
        return None
    # ky NULL (FAO-56 no lo publica para ese cultivo) -> NaN: el motor calcula el riego pero no la perdida por sequia.
    ky = fila["ky"] if fila["ky"] is not None else float("nan")
    return ParametrosAgua(fila["zr_m"], fila["p_agotamiento"], fila["kc_ini"], fila["kc_med"], fila["kc_fin"], ky)


def balance_del_cultivo(clima: pd.DataFrame, lat: float, siembra, fechas: dict, c: Cultivo, params: ParametrosAgua | None,
                        cap_mm: float | None, riego: bool = False, et0_factores: list | None = None,
                        prof_suelo_m: float | None = None, riegos: tuple = ()) -> pd.DataFrame:
    """El balance de agua que usa un cultivo: FAO-56 por zona de raices si hay parametros; si no, el balde del
    perfil completo de antes (con riego, sin sequia). La ET0 es Hargreaves calibrada por mes contra Penman-Monteith.
    `riegos`: fechas en que el agricultor rego (solo las usa el balance FAO-56)."""
    if params is None:
        agua = balance_agua(clima, lat, cap_mm if cap_mm else 100.0)
        return agua.assign(agua=1.0) if riego else agua
    et0 = et0_hargreaves(clima, lat) * factores_et0(et0_factores, clima.index)
    kc = kc_diario(clima.index, siembra, fechas, c, params)
    return balance_agua_fao56(clima, et0, kc, cap_mm if cap_mm else AWC_POR_DEFECTO_MM, params,
                              prof_suelo_m=prof_suelo_m, riego=riego, lat=lat, riegos=riegos)


# Fuente de las etapas derivadas de la tabla 11 de FAO-56 (database/derivar_etapas_fao.py): dias por etapa
# pasados a grados-dia con el clima de una region de referencia, no medidos en terreno.
FUENTE_ETAPAS_DERIVADAS = "FAO56_t11_derivado_sin_validar"


def _fuente_sin_validar(fuente: str) -> bool:
    return fuente == "placeholder_sin_validar" or fuente == FUENTE_ETAPAS_DERIVADAS


async def calendario_aproximado(especie: str, variedad_local: str | None, repo: RepositorioEspecies) -> bool:
    """True si las etapas de la especie salen de la derivacion FAO-56 y no de una ficha de terreno: el
    calendario es una guia aproximada y el frontend debe decirlo."""
    umbrales = await repo.umbrales_fenologicos(especie, variedad_local)
    return any(u["fuente"] == FUENTE_ETAPAS_DERIVADAS for u in umbrales)


async def nivel_madurez(especie: str, variedad_local: str | None, repo: RepositorioEspecies) -> str:
    umbrales = await repo.umbrales_fenologicos(especie, variedad_local)
    if umbrales:
        sin_validar = any(_fuente_sin_validar(u["fuente"]) for u in umbrales)
        return "perfil_fenologico_regional" if sin_validar else "perfil_calibrado"
    if await repo.requisitos(especie, variedad_local):
        return "perfil_generico"
    return "sin_perfil"


async def _idoneidad_simulada(especie: str, variedad_local: str | None, repo: RepositorioEspecies,
                               clima: pd.DataFrame, lat: float, cap_mm: float | None,
                               riego: bool = False, et0_factores: list | None = None,
                               prof_suelo_m: float | None = None) -> dict | None:
    """Corre el mismo camino real que motor_rotacion.evaluar_cultivos() usa (simular +
    evaluar), para que la supervivencia ante un evento dependa de EN QUE FASE ocurre
    (regla_dano_especie.fase), no de si el promedio anual de temperatura cruza tb/tc en
    algun momento -- eso es lo que el chequeo generico de mas abajo no puede ver (BUG
    REAL encontrado: papa daba 'no apta' por una helada puntual que en la simulacion real
    solo le causa un atraso de 14 dias, no la mata).

    None si no se puede simular (sin perfil fenologico, perenne, sin fecha de siembra en
    rasgos_rotacion_especie, o el clima disponible no alcanza para esa fecha) -- quien
    llama cae al chequeo generico en ese caso, nunca inventa un resultado."""
    preparada = await preparar_simulacion(especie, variedad_local, repo)
    if preparada is None:
        return None
    return simular_idoneidad(preparada, clima, lat, cap_mm, riego, et0_factores, prof_suelo_m)


async def preparar_simulacion(especie: str, variedad_local: str | None, repo: RepositorioEspecies) -> dict | None:
    """Lo que la simulacion por fase necesita de una especie, leido una sola vez de la base: asi se puede correr
    sobre muchos anos de clima sin volver a consultar. None si no hay perfil fenologico o la especie es perenne."""
    try:
        c = await construir_cultivo(especie, variedad_local, repo)
    except (EspecieSinPerfil, EspecieSinPerfilFenologico):
        return None
    rasgos = await repo.rasgos_rotacion(especie)
    if not rasgos or rasgos.get("perenne") or rasgos.get("siembra_mes") is None:
        return None  # pradera/perenne no se siembra una vez al ano -- no aplica este chequeo
    return {"cultivo": c, "mes": rasgos["siembra_mes"], "dia": rasgos.get("siembra_dia") or 1,
            "reglas": await construir_reglas(especie, variedad_local, repo),
            "params": await construir_parametros_agua(especie, repo)}


def simular_idoneidad(preparada: dict, clima: pd.DataFrame, lat: float, cap_mm: float | None, riego: bool = False,
                      et0_factores: list | None = None, prof_suelo_m: float | None = None) -> dict | None:
    """La simulacion por fase de una especie preparada sobre `clima`. None si no hay clima desde la fecha de siembra."""
    c, params, reglas = preparada["cultivo"], preparada["params"], preparada["reglas"]
    mes, dia = preparada["mes"], preparada["dia"]
    anio = clima.index[0].year
    siembra = pd.Timestamp(anio, mes, dia)
    if siembra < clima.index[0]:
        siembra = pd.Timestamp(anio + 1, mes, dia)
    if siembra > clima.index[-1]:
        return None  # no hay suficiente clima real desde la proxima fecha de siembra

    fechas = simular(clima, siembra, lat, c)
    if c.etapas[-1][0] not in fechas:
        return {"apta": False, "metodo": "simulacion_real", "siembra_simulada": str(siembra.date()),
                "razones": [f"no alcanza a completar el ciclo fenologico sembrando el {siembra.date()} "
                            "con el clima disponible (puede ser que el rango de clima ingerido sea corto, "
                            "no necesariamente que el sitio sea inviable)"]}

    agua = balance_del_cultivo(clima, lat, siembra, fechas, c, params, cap_mm, riego, et0_factores, prof_suelo_m)
    resultado = evaluar(clima, agua, siembra, fechas, c, reglas)
    razones = []
    if resultado["estado"] == "perdido":
        razones.append(f"la simulacion real pierde el cultivo sembrando el {siembra.date()} -- "
                       "ver por que en regla_dano_especie (fase y peligro que gatillo efecto 'total')")
    elif resultado["perdida"] > 0.5:
        razones.append(f"perdida simulada alta ({resultado['perdida'] * 100:.0f}%) sembrando el {siembra.date()}")
    return {"apta": len(razones) == 0, "razones": razones, "metodo": "simulacion_real",
            "siembra_simulada": str(siembra.date()), "perdida_simulada": resultado["perdida"],
            "estado_simulado": resultado["estado"], "ciclo_dias": (fechas[c.etapas[-1][0]] - siembra).days,
            "modelo_agua": "fao56" if params else "balde_perfil",
            "cap_mm_usado": cap_mm if cap_mm else f"{AWC_POR_DEFECTO_MM if params else 100.0} (supuesto, sin dato real de sitio)"}


async def calcular_idoneidad(sitio: dict, especies: list[tuple[str, str | None]], repo: RepositorioEspecies,
                              clima: pd.DataFrame | None = None, lat: float | None = None) -> list[dict]:
    """La funcion de analisis de terreno que el plan (Fase 6) asigna a este nivel de
    madurez: solo necesita requisitos_especie (perfil_generico), no umbral_fenologico_config
    -- por eso puede correr para una especie que EspecieSinPerfilFenologico todavia no
    deja simular con construir_cultivo().

    especies: [(especie, variedad_local), ...] -- BUG REAL corregido: antes esto era
    list[str] y pasaba variedad_local=None fijo en toda la cadena (requisitos(),
    nivel_madurez(), construir_cultivo(), construir_reglas()), aunque requisitos_especie
    y regla_dano_especie SI tienen columna variedad_local -- el dia que exista una fila
    calibrada para una variedad especifica (ej. via caracteristica_variedad_aportada),
    esta funcion la habria ignorado igual. Mismo patron que construir_catalogo(), que
    siempre acepto tuplas -- calcular_idoneidad() era la excepcion, no construir_catalogo.

    sitio: {'ph': float|None, 'tmin': float|None, 'tmax': float|None, 'awc_mm': float|None}
    -- valores REALES del sitio (ej. ph/awc de SoilGrids/CLSoilMaps, tmin/tmax promedio
    real de CR2MET/POWER para el predio), nunca inventados. Ausencia de un dato de
    sitio (None) NUNCA descarta una especie -- "no sabemos" no es "no sirve", mismo
    principio que el resto del proyecto (ver advertencia de nivel_madurez).

    clima/lat opcionales: si se pasan (serie diaria real, no solo el promedio de `sitio`)
    y la especie llega a perfil_fenologico_regional o superior, se intenta
    _idoneidad_simulada() primero -- la comparacion real por fase, no el promedio ciego
    de tb/tc. El chequeo generico de abajo queda como respaldo para perfil_generico puro
    (la mayoria de EcoCrop, sin umbral_fenologico_config) o si la simulacion no corrio."""
    out = []
    for especie, variedad_local in especies:
        nombre = especie if variedad_local is None else f"{especie}:{variedad_local}"
        req = await repo.requisitos(especie, variedad_local)
        if req is None:
            out.append({"especie": nombre, "apta": None, "razones": ["sin_perfil (sin requisitos_especie)"]})
            continue
        nivel = await nivel_madurez(especie, variedad_local, repo)

        resultado = None
        if clima is not None and lat is not None and nivel in ("perfil_fenologico_regional", "perfil_calibrado"):
            resultado = await _idoneidad_simulada(especie, variedad_local, repo, clima, lat, sitio.get("awc_mm"))

        if resultado is None:
            razones = []
            ph = sitio.get("ph")
            if ph is not None and req.get("ph_suelo_min") is not None and ph < req["ph_suelo_min"]:
                razones.append(f"pH del sitio ({ph}) bajo el minimo tolerado por la especie ({req['ph_suelo_min']})")
            if ph is not None and req.get("ph_suelo_max") is not None and ph > req["ph_suelo_max"]:
                razones.append(f"pH del sitio ({ph}) sobre el maximo tolerado por la especie ({req['ph_suelo_max']})")
            tmin = sitio.get("tmin")
            if tmin is not None and req.get("tb") is not None and tmin < req["tb"]:
                razones.append(f"temperatura minima real del sitio ({tmin}) bajo la base termica de la especie ({req['tb']})")
            tmax = sitio.get("tmax")
            if tmax is not None and req.get("tc") is not None and tmax > req["tc"]:
                razones.append(f"temperatura maxima real del sitio ({tmax}) sobre el techo termico de la especie ({req['tc']})")
            # BUG REAL corregido: habia columnas humedad_suelo_minima/maxima en
            # requisitos_especie que esta funcion nunca leia -- el agua disponible del
            # sitio (awc_mm, CLSoilMaps) solo entraba como insumo del balance de agua en
            # el camino simulado, nunca se comparaba directo contra el requisito de la
            # especie. Hoy (verificado) ninguna fila tiene esta columna poblada todavia
            # -- esto no cambia ningun resultado actual, deja el mecanismo listo para
            # cuando se poblar con datos de lluvia real (ej. EcoCrop RMIN/RMAX) o de
            # ground truth de agricultores.
            awc = sitio.get("awc_mm")
            if awc is not None and req.get("humedad_suelo_minima") is not None and awc < req["humedad_suelo_minima"]:
                razones.append(f"agua disponible del sitio ({awc} mm) bajo el minimo tolerado por la especie ({req['humedad_suelo_minima']} mm)")
            if awc is not None and req.get("humedad_suelo_maxima") is not None and awc > req["humedad_suelo_maxima"]:
                razones.append(f"agua disponible del sitio ({awc} mm) sobre el maximo tolerado por la especie ({req['humedad_suelo_maxima']} mm)")
            resultado = {"apta": len(razones) == 0, "razones": razones, "metodo": "generico_tb_tc_promedio"}

        out.append({"especie": nombre, "fuente_requisitos": req.get("fuente"), "nivel_madurez": nivel, **resultado})
    return out


# ---------------------------------------------------------------- idoneidad de predio (metodo EcoCrop)
# Metodo publicado, no propio: paquete Recocrop 0.4-2 (Hijmans), basado en Hackett (1991).
# Cada variable da una respuesta 0-1 en forma de meseta; la respuesta conjunta es la del
# factor mas limitante (ley del minimo); una temporada vale lo que su peor mes; el sitio
# vale lo que su mejor temporada entre las doce fechas de inicio posibles. Tres diferencias
# con Recocrop, las tres deliberadas:
#   - paso mensual, no quincenal interpolado;
#   - la helada letal se compara contra la minima diaria real mas baja del mes;
#   - la lluvia se compara como media mensual de la temporada, no mes a mes. Recocrop
#     corre sobre normales de 30 anos; aca el clima es UN ano observado, y exigir el
#     minimo en cada mes hacia que un solo mes seco descartara cientos de especies
#     (verificado en Quemchi: 31 mm en nov-2025). El umbral es el mismo de Recocrop.
#
# La radiacion NO es parte del metodo EcoCrop (Recocrop ignora las categorias de luz):
# entra aparte, con la equivalencia sin validar de la tabla equivalencia_luz_ghi, y solo
# puede bajar el puntaje hasta PESO_LUZ -- nunca vuelve 'no apta' a una especie.
PESO_LUZ = 0.3

# Debajo de este puntaje una especie es posible pero no se recomienda: un puntaje de 0,02 solo
# dice que el factor limitante no llega a cero. Queda con apta=False y marginal=True, y sale
# en la lista solo si se piden las no aptas.
PUNTAJE_MINIMO_APTA = 0.2

# Un suelo mas acido que el minimo de la especie se puede corregir con cal. El factor de pH no
# baja de PH_PISO_ENCALADO mientras el suelo este a menos de MARGEN_ENCALADO unidades de pH
# del minimo, y la salida trae la correccion. Un suelo alcalino no tiene correccion practica.
PH_PISO_ENCALADO = 0.5
MARGEN_ENCALADO = 1.0

# Fraccion sobre la altitud maxima de la especie en que el factor de altitud baja de 1 a 0.
MARGEN_ALTITUD = 0.10

# Textura: puntos de arcilla o arena de error que se le suponen al dato del suelo, y respuesta
# de una clase que la especie tolera pero no es la optima. El dato es un modelo de 250 m a
# 0-5 cm, el mas flojo de los factores del suelo: por eso la penalizacion es leve.
MARGEN_TEXTURA_PCT = 5.0
TEXTURA_TOLERADA = 0.75

# Suelo que declara el agricultor (el predio no tiene esos datos medidos). Respuesta de lo que la
# especie solo tolera, de menos a mas costosa de corregir: la fertilidad se mejora con abono (piso
# 0,5, nunca descarta); la profundidad y el drenaje no; la sal baja el rendimiento a la mitad.
DRENAJE_TOLERADO = 0.75
SALINIDAD_TOLERADA = 0.5
PROFUNDIDAD_TOLERADA = 0.75
FERTILIDAD_TOLERADA = 0.75
PISO_FERTILIDAD = 0.5
ORDEN_SALINIDAD = {"none": 0, "low": 1, "medium": 2, "high": 3}
ORDEN_PROFUNDIDAD = {"very_shallow": 0, "shallow": 1, "medium": 2, "deep": 3}
ORDEN_FERTILIDAD = {"low": 0, "moderate": 1, "high": 2}
CAMPOS_SUELO = ("drenaje", "salinidad", "profundidad", "fertilidad")

# Temperatura: -6,5 C por km de subida (gradiente estandar de la atmosfera) para pasar de la altura
# media de la celda de CR2MET a la del predio. Tope de seguridad si un dato viene malo.
GRADIENTE_TEMPERATURA_C_POR_M = 0.0065
CORRECCION_TEMPERATURA_MAX_C = 5.0

# Categorias de EcoCrop que no son cultivo. Una especie se deja fuera del ranking por
# defecto solo si TODAS sus categorias estan aca; sin categoria (ej. maiz) se conserva.
CATEGORIAS_NO_CULTIVO = frozenset({"forest/wood", "ornamentals/turf", "environmental", "weed"})

FUENTE_ECOCROP = "FAO_EcoCrop_opinion_experta"

# Categorias de EcoCrop que un agricultor reconoce como comida. Solo desempatan el orden:
# con el mismo puntaje salen antes que forrajes, medicinales y plantas silvestres.
CATEGORIAS_ALIMENTO = frozenset({"vegetables", "roots/tubers", "pulses (grain legumes)",
                                 "cereals & pseudocereals", "fruits & nuts"})


def respuesta_meseta(x, minimo, opt_min, opt_max, maximo) -> float | None:
    """0 bajo `minimo` y sobre `maximo`, 1 entre los optimos, lineal entre medio. Un
    umbral ausente (None) deja abierta esa cola. None si falta el dato del sitio o los
    cuatro umbrales -- 'no sabemos' nunca se convierte en 0."""
    if x is None or all(v is None for v in (minimo, opt_min, opt_max, maximo)):
        return None
    bajo = opt_min if opt_min is not None else minimo
    alto = opt_max if opt_max is not None else maximo
    if bajo is not None and x < bajo:
        piso = minimo if minimo is not None else bajo
        return 0.0 if x <= piso else (x - piso) / (bajo - piso)
    if alto is not None and x > alto:
        techo = maximo if maximo is not None else alto
        return 0.0 if x >= techo else (techo - x) / (techo - alto)
    return 1.0


def duracion_temporada_meses(ciclo_min_dias, ciclo_max_dias) -> int:
    """Regla de Recocrop ('duration'): ciclo minimo mas un mes, salvo que minimo y maximo
    coincidan -- la temporada corta es la que decide si el sitio sirve. Sin dato de ciclo
    (arboles y perennes en EcoCrop) se evalua el ano completo."""
    if not ciclo_min_dias:
        return 12
    dias = ciclo_min_dias if ciclo_max_dias == ciclo_min_dias else ciclo_min_dias + 30
    return max(1, min(12, round(dias / 30)))


def normales_mensuales(clima: pd.DataFrame | None, min_dias: int = 20) -> dict:
    """Clima diario (tmin, tmax, lluvia) -> doce valores por mes calendario, indice 0 =
    enero: temperatura media, minima diaria mas baja y lluvia acumulada. Una variable
    queda en None completa si a algun mes le faltan datos -- una temporada evaluada con
    meses sin dato ganaria por tener menos factores, no por ser mejor."""
    vacio = {"tmedia": None, "tmin_extrema": None, "lluvia": None}
    if clima is None or clima.empty:
        return vacio
    tmedia, tmin_extrema, lluvia = [None] * 12, [None] * 12, [None] * 12
    for mes, g in clima.groupby(clima.index.month):
        t = g.dropna(subset=["tmin", "tmax"])
        if len(t) >= min_dias:
            tmedia[mes - 1] = float(((t["tmin"] + t["tmax"]) / 2).mean())
            tmin_extrema[mes - 1] = float(t["tmin"].min())
        ll = g["lluvia"].dropna()
        if len(ll) >= min_dias:
            lluvia[mes - 1] = float(ll.mean() * g.index[0].days_in_month)
    completa = lambda v: v if all(x is not None for x in v) else None
    return {"tmedia": completa(tmedia), "tmin_extrema": completa(tmin_extrema), "lluvia": completa(lluvia)}


def _categoria_luz(ghi: float, luz: list[dict]) -> dict | None:
    """luz: filas de equivalencia_luz_ghi ordenadas por `orden` (1 = mas luz)."""
    return next((f for f in luz if ghi >= f["ghi_min_kwh_m2_dia"]), None)


def _respuesta_luz(req: dict, orden_sitio: int, luz: list[dict]) -> float | None:
    orden = {f["categoria"]: f["orden"] for f in luz}
    absoluto = [orden[c] for c in (req.get("luz_min"), req.get("luz_max")) if c in orden]
    optimo = [orden[c] for c in (req.get("luz_opt_min"), req.get("luz_opt_max")) if c in orden]
    if not absoluto and not optimo:
        return None
    if optimo and min(optimo) <= orden_sitio <= max(optimo):
        return 1.0
    if absoluto and min(absoluto) <= orden_sitio <= max(absoluto):
        return 0.5
    return 0.0


def clase_textura(arcilla_pct: float | None, arena_pct: float | None) -> str | None:
    """Clase de textura al estilo FAO/EcoCrop a partir de arcilla y arena (% en peso):
    heavy = arcilloso (arcilla, arcillo-arenoso, arcillo-limoso), light = arenoso (arena,
    arena franca, franco arenoso), medium = el resto. Aproxima el triangulo USDA con cortes
    simples, no lo reproduce. None si falta alguno de los dos datos."""
    if arcilla_pct is None or arena_pct is None:
        return None
    if arcilla_pct >= 40 or (arcilla_pct >= 35 and arena_pct >= 45):
        return "heavy"
    if arena_pct >= 52 and arcilla_pct < 20:
        return "light"
    return "medium"


def clases_textura_posibles(arcilla_pct: float | None, arena_pct: float | None,
                            margen: float = MARGEN_TEXTURA_PCT) -> list[str]:
    """La clase de textura del sitio y las vecinas que caben dentro del error del dato (+-margen
    puntos de arcilla y de arena). Primero la clase central. Vacia si falta un dato. SoilGrids
    no distingue 5 puntos: sin esto, un sitio en el borde entre dos clases cambia de veredicto
    por una decima."""
    central = clase_textura(arcilla_pct, arena_pct)
    if central is None:
        return []
    clases = [central]
    for da in (-margen, margen):
        for ds in (-margen, margen):
            vecina = clase_textura(max(arcilla_pct + da, 0.0), min(max(arena_pct + ds, 0.0), 100.0))
            if vecina not in clases:
                clases.append(vecina)
    return clases


def _respuesta_textura(req: dict, clases: list[str]) -> float | None:
    """Por cada clase posible del sitio: 1 si es optima para la especie, TEXTURA_TOLERADA si solo la
    tolera, 0 si no; vale la mejor. Sin dato del sitio o de la especie, None: no filtra."""
    rango = req.get("textura_rango")
    optima = req.get("textura_opt") or rango
    if not clases or not (optima or rango):
        return None
    return max(1.0 if optima and c in optima else (TEXTURA_TOLERADA if rango and c in rango else 0.0) for c in clases)


def _respuesta_drenaje(req: dict, clase: str | None) -> float | None:
    """Clase de drenaje que declara el agricultor: 'poorly' = se inunda (saturado mas de la mitad del
    ano), 'well', 'excessive' = se seca muy rapido. Un encharcamiento pasajero NO es 'poorly': se
    corrige con zanjas o camellones, y por eso la pregunta es por inundacion. 1 si la clase es
    optima para la especie, DRENAJE_TOLERADO si solo la tolera, 0 si no."""
    rango = req.get("drenaje_rango")
    optima = req.get("drenaje_opt") or rango
    if clase is None or not (optima or rango):
        return None
    if optima and clase in optima:
        return 1.0
    return DRENAJE_TOLERADO if rango and clase in rango else 0.0


def _respuesta_salinidad(req: dict, clase: str | None) -> float | None:
    """Sal del suelo que declara el agricultor. Una escala: bajo el optimo de la especie responde
    1, hasta el maximo que tolera SALINIDAD_TOLERADA (la sal baja el rendimiento), mas alla 0."""
    maximo = ORDEN_SALINIDAD.get(req.get("salinidad_max") or req.get("salinidad_opt"))
    optimo = ORDEN_SALINIDAD.get(req.get("salinidad_opt"), maximo)
    nivel = ORDEN_SALINIDAD.get(clase)
    if nivel is None or maximo is None:
        return None
    maximo = max(maximo, optimo)
    if nivel <= optimo:
        return 1.0
    return SALINIDAD_TOLERADA if nivel <= maximo else 0.0


def _respuesta_profundidad(req: dict, clase: str | None) -> float | None:
    """Profundidad del suelo que declara el agricultor. Es un minimo: un suelo mas profundo que lo
    optimo no perjudica. Al menos lo optimo responde 1, al menos lo minimo que tolera
    PROFUNDIDAD_TOLERADA, menos que eso 0."""
    nivel = ORDEN_PROFUNDIDAD.get(clase)
    optima = ORDEN_PROFUNDIDAD.get(req.get("profundidad_opt"))
    minima = ORDEN_PROFUNDIDAD.get(req.get("profundidad_min"))
    if nivel is None or (optima is None and minima is None):
        return None
    optima = minima if optima is None else optima
    minima = optima if minima is None else min(minima, optima)
    if nivel >= optima:
        return 1.0
    return PROFUNDIDAD_TOLERADA if nivel >= minima else 0.0


def _respuesta_fertilidad(req: dict, clase: str | None) -> tuple[float | None, dict | None]:
    """Fertilidad que declara el agricultor. Se puede mejorar con abono o compost: por eso nunca baja
    de PISO_FERTILIDAD y, si el suelo no llega a lo optimo, la salida trae la correccion."""
    nivel = ORDEN_FERTILIDAD.get(clase)
    optima = ORDEN_FERTILIDAD.get(req.get("fertilidad_opt"))
    minima = ORDEN_FERTILIDAD.get(req.get("fertilidad_min"))
    if nivel is None or (optima is None and minima is None):
        return None, None
    optima = minima if optima is None else optima
    minima = optima if minima is None else min(minima, optima)
    if nivel >= optima:
        return 1.0, None
    correccion = {"tipo": "fertilizacion", "fertilidad_sitio": clase,
                  "fertilidad_requerida": req.get("fertilidad_opt") or req.get("fertilidad_min")}
    return (FERTILIDAD_TOLERADA if nivel >= minima else PISO_FERTILIDAD), correccion


def suelo_sin_declarar(sitio: dict) -> list[str]:
    """Las preguntas sobre el suelo que el agricultor todavia no respondio."""
    suelo = sitio.get("suelo") or {}
    return [campo for campo in CAMPOS_SUELO if suelo.get(campo) is None]


# Un puntaje alto con el suelo sin conocer promete lo que no se midio: factores sin dato no puntuan, asi que una
# especie buena en clima daba 100 % sin saber nada del suelo. Con el suelo incompleto el puntaje tiene un maximo.
TOPE_SUELO_SIN_DECLARAR = 0.90   # falta alguna de las cuatro respuestas del agricultor (CAMPOS_SUELO)
TOPE_SUELO_SIN_SATELITE = 0.80   # no hay ni pH ni textura de SoilGrids: falta la base del suelo
_CAMPOS_PUNTAJE = ("puntaje", "puntaje_ano_dificil")


def tope_por_suelo(sitio: dict) -> tuple[float, str] | None:
    """(tope, motivo) del puntaje segun lo que se sabe del suelo, o None si esta completo: pH o textura de satelite
    y las cuatro respuestas del agricultor. Sin pH ni textura manda el tope menor, aunque el agricultor haya
    respondido todo."""
    if sitio.get("ph") is None and not sitio.get("textura") and not sitio.get("textura_posibles"):
        return TOPE_SUELO_SIN_SATELITE, "sin_suelo_de_satelite"
    if suelo_sin_declarar(sitio):
        return TOPE_SUELO_SIN_DECLARAR, "suelo_sin_declarar"
    return None


def aplicar_tope_suelo(ranking: list[dict], sitio: dict) -> list[dict]:
    """Limita `puntaje` y `puntaje_ano_dificil` de cada especie al tope de tope_por_suelo() y lo informa en
    `tope_suelo` ({'tope', 'motivo'}; 'puntaje_sin_tope' solo si el tope lo bajo). El orden no se pierde: el
    puntaje sin tope desempata. Con el suelo completo no toca nada."""
    nivel = tope_por_suelo(sitio)
    if nivel is None:
        return ranking
    tope, motivo = nivel
    for r in ranking:
        r["tope_suelo"] = {"tope": tope, "motivo": motivo}
        if r.get("puntaje") is not None and r["puntaje"] > tope:
            r["tope_suelo"]["puntaje_sin_tope"] = r["puntaje"]
        for campo in _CAMPOS_PUNTAJE:
            if r.get(campo) is not None:
                r[campo] = min(r[campo], tope)
    ranking.sort(key=lambda r: (r["apta"] is True, r["puntaje"] if r["puntaje"] is not None else -1.0,
                                r["tope_suelo"].get("puntaje_sin_tope", r["puntaje"] or 0.0)), reverse=True)
    return ranking


def delta_temperatura_por_altitud(altitud_parcela_m: float | None, altitud_celda_m: float | None) -> float:
    """Grados a sumar a la temperatura de la celda de 5 km de CR2MET para llevarla a la altura del
    predio: la temperatura baja GRADIENTE_TEMPERATURA_C_POR_M por metro de subida. Con el
    predio mas alto que la altura media de su celda da negativo. 0 si falta algun dato, y
    nunca mas de CORRECCION_TEMPERATURA_MAX_C en valor absoluto."""
    if altitud_parcela_m is None or altitud_celda_m is None:
        return 0.0
    delta = -GRADIENTE_TEMPERATURA_C_POR_M * (altitud_parcela_m - altitud_celda_m)
    return max(-CORRECCION_TEMPERATURA_MAX_C, min(CORRECCION_TEMPERATURA_MAX_C, delta))


def corregir_temperatura(clima: pd.DataFrame | None, delta: float) -> pd.DataFrame | None:
    """Copia del clima diario con tmin y tmax desplazadas `delta` grados."""
    if clima is None or not delta:
        return clima
    corregido = clima.copy()
    corregido["tmin"] = corregido["tmin"] + delta
    corregido["tmax"] = corregido["tmax"] + delta
    return corregido


def _respuesta_altitud(req: dict, altitud_m: float | None) -> float | None:
    """EcoCrop solo publica un maximo de altitud, y son cifras redondas de opinion experta: hasta el
    maximo responde 1; por encima baja en recta hasta 0 a MARGEN_ALTITUD sobre el maximo."""
    maximo = req.get("altitud_max_m")
    if altitud_m is None or maximo is None:
        return None
    if altitud_m <= maximo:
        return 1.0
    return max(0.0, 1 - (altitud_m - maximo) / (maximo * MARGEN_ALTITUD))


def _respuesta_ph(req: dict, ph: float | None) -> tuple[float | None, dict | None]:
    """Respuesta 0-1 del pH del sitio. Bajo el minimo de la especie (suelo mas acido) no cae a
    cero de golpe: el encalado lo sube, asi que el piso baja de PH_PISO_ENCALADO a 0 a lo
    largo de MARGEN_ENCALADO unidades de pH. Si el piso es lo que decide, devuelve tambien la
    correccion. Un suelo alcalino sigue yendo a cero: no hay correccion practica."""
    minimo, opt_min = req.get("ph_suelo_min"), req.get("ph_opt_min")
    respuesta = respuesta_meseta(ph, minimo, opt_min, req.get("ph_opt_max"), req.get("ph_suelo_max"))
    referencia = opt_min if opt_min is not None else minimo
    if respuesta is None or minimo is None or ph >= referencia:
        return respuesta, None
    piso = PH_PISO_ENCALADO * min(1.0, max(0.0, (ph - (minimo - MARGEN_ENCALADO)) / MARGEN_ENCALADO))
    if piso <= respuesta:
        return respuesta, None
    return piso, {"tipo": "encalado", "ph_sitio": ph, "ph_minimo": minimo}


def puntuar_especie(req: dict, sitio: dict, luz: list[dict], riego: bool = False) -> dict:
    """req: fila de requisitos_especie. sitio: {'normales': normales_mensuales(...),
    'ph': float|None, 'ghi_mensual': [12 valores kWh/m2/dia]|None}. luz: filas de
    equivalencia_luz_ghi. Devuelve el puntaje de la mejor temporada y el factor que la
    limita; `apta` es None si no hay ni un factor evaluable. `riego`: la falta de lluvia
    no cuenta (el agricultor la repone), pero el exceso de lluvia si."""
    normales = sitio.get("normales") or {}
    duracion = duracion_temporada_meses(req.get("ciclo_min_dias"), req.get("ciclo_max_dias"))
    t_opt_min = req.get("t_opt_min") if req.get("t_opt_min") is not None else req.get("t_optima")
    t_opt_max = req.get("t_opt_max") if req.get("t_opt_max") is not None else req.get("t_optima")
    # EcoCrop publica lluvia ANUAL; Recocrop la lleva a umbral mensual dividiendo por la
    # duracion de la temporada (en meses) mas uno. Con riego se sueltan los dos umbrales de
    # abajo (minimo y optimo minimo): una cola abierta no limita.
    lluvia_mes = [None if v is None or (riego and i < 2) else v / (duracion + 1) for i, v in enumerate((
        req.get("lluvia_anual_min"), req.get("lluvia_anual_opt_min"),
        req.get("lluvia_anual_opt_max"), req.get("lluvia_anual_max")))]
    letal = req.get("temperatura_letal")

    def mensual(variable, *umbrales):
        serie = normales.get(variable)
        return None if serie is None else [respuesta_meseta(x, *umbrales) for x in serie]

    por_mes = {
        "temperatura": mensual("tmedia", req.get("tb"), t_opt_min, t_opt_max, req.get("tc")),
        # Recocrop: muere bajo KTMP-1, sin dano sobre KTMP+1.
        "helada": None if letal is None else mensual("tmin_extrema", letal - 1, letal + 1, None, None),
    }
    por_mes = {k: v for k, v in por_mes.items() if v is not None and v[0] is not None}
    lluvia = normales.get("lluvia")
    ph, correccion_ph = _respuesta_ph(req, sitio.get("ph"))
    suelo = sitio.get("suelo") or {}
    fertilidad, correccion_fertilidad = _respuesta_fertilidad(req, suelo.get("fertilidad"))
    correcciones = [c for c in (correccion_ph, correccion_fertilidad) if c]
    # Factores del sitio que no cambian con la temporada, como el pH. Los cuatro ultimos los
    # declara el agricultor: sin respuesta (None), no filtran.
    fijos = {nombre: valor for nombre, valor in (
        ("ph", ph), ("altitud", _respuesta_altitud(req, sitio.get("altitud_m"))),
        ("textura", _respuesta_textura(
            req, sitio.get("textura_posibles") or ([sitio["textura"]] if sitio.get("textura") else []))),
        ("drenaje", _respuesta_drenaje(req, suelo.get("drenaje"))),
        ("salinidad", _respuesta_salinidad(req, suelo.get("salinidad"))),
        ("profundidad", _respuesta_profundidad(req, suelo.get("profundidad"))),
        ("fertilidad", fertilidad)) if valor is not None}

    mejor = None
    for inicio in range(12):
        meses = [(inicio + i) % 12 for i in range(duracion)]
        factores = {nombre: min(serie[m] for m in meses) for nombre, serie in por_mes.items()}
        if lluvia is not None:
            humedad = respuesta_meseta(sum(lluvia[m] for m in meses) / duracion, *lluvia_mes)
            if humedad is not None:
                factores["humedad"] = humedad
        factores.update(fijos)
        if not factores:
            break
        limitante = min(factores, key=factores.get)
        # Desempate entre temporadas con el mismo peor mes: la de mejor promedio mensual.
        promedio = sum(min(serie[m] for serie in por_mes.values()) for m in meses) / duracion if por_mes else 0.0
        clave = (factores[limitante], promedio)
        if mejor is None or clave > mejor["clave"]:
            mejor = {"clave": clave, "inicio": inicio, "meses": meses, "factores": factores, "limitante": limitante}

    base = {"duracion_temporada_meses": duracion, "ciclo_conocido": bool(req.get("ciclo_min_dias")),
            "metodo": "ecocrop_mensual"}
    if mejor is None:
        return {**base, "apta": None, "puntaje": None, "factores": {}, "correcciones": [],
                "razones": ["sin datos de sitio o de especie suficientes para evaluar"]}

    limite = mejor["factores"][mejor["limitante"]]
    factores = {k: round(v, 3) for k, v in mejor["factores"].items()}
    puntaje, categoria = limite, None
    ghi = sitio.get("ghi_mensual")
    if ghi and luz:
        categoria = _categoria_luz(sum(ghi[m] for m in mejor["meses"]) / duracion, luz)
        respuesta = _respuesta_luz(req, categoria["orden"], luz) if categoria else None
        if respuesta is not None:
            factores["radiacion"] = respuesta
            puntaje = limite * (1 - PESO_LUZ * (1 - respuesta))
    return {**base, "apta": limite > 0, "puntaje": round(puntaje, 3), "factores": factores,
            "factor_limitante": mejor["limitante"], "mes_inicio_temporada": mejor["inicio"] + 1,
            "categoria_luz_temporada": categoria["categoria"] if categoria else None,
            "correcciones": correcciones}


def datos_faltantes(sitio: dict) -> list[str]:
    """Factores del sitio que no se pudieron medir. Sin un dato, ese factor no filtra: la lista
    puede incluir especies que el terreno no tolera. Quien la muestre debe decirlo."""
    normales = sitio.get("normales") or {}
    faltan = []
    if normales.get("tmedia") is None:
        faltan.append("temperatura")
    if normales.get("tmin_extrema") is None:
        faltan.append("helada")
    if normales.get("lluvia") is None:
        faltan.append("lluvia")
    if sitio.get("ph") is None:
        faltan.append("ph")
    if not sitio.get("ghi_mensual"):
        faltan.append("radiacion")
    if sitio.get("awc_mm") is None:
        faltan.append("agua_suelo")
    if sitio.get("altitud_m") is None:
        faltan.append("altitud")
    if sitio.get("textura") is None:
        faltan.append("textura")
    return faltan


def seleccionar_candidatas(ranking: list[dict], limite: int, incluir_no_aptas: bool = False,
                           especie: str | None = None) -> list[dict]:
    """Lo que el endpoint devuelve del ranking ya ordenado. `especie` (claves separadas por
    coma) trae solo esas, aptas o no, sin limite. Si no, las aptas (y las demas si
    `incluir_no_aptas`) recortadas a `limite`."""
    if especie:
        pedidas = {e.strip() for e in especie.split(",") if e.strip()}
        return [r for r in ranking if r["especie"] in pedidas]
    lista = ranking if incluir_no_aptas else [r for r in ranking if r["apta"]]
    return lista[:limite]


def _slug(nombre_cientifico: str) -> str:
    """Misma regla que database/importar_ecocrop.slug(): asi el nombre cientifico de una
    especie curada ('Solanum tuberosum') apunta a su fila de EcoCrop ('solanum_tuberosum')."""
    s = re.sub(r"[^a-z0-9\s]", "", nombre_cientifico.strip().lower())
    return re.sub(r"\s+", "_", s).strip("_")


def _clima_ciclico(clima: pd.DataFrame | None) -> pd.DataFrame | None:
    """El ultimo ano de clima repetido una vez, para que la simulacion fenologica tenga
    donde completar un ciclo que empieza cerca del final de la serie. Es el mismo supuesto
    que ya hace el metodo mensual (el ano observado como referencia), no una proyeccion.
    None si quedan huecos de mas de 3 dias -- simular() se niega a correr sobre huecos."""
    if clima is None or clima.empty:
        return None
    diario = clima.asfreq("D").interpolate(limit=3)
    if diario[["tmin", "tmax", "lluvia"]].isna().any().any():
        return None
    siguiente = diario.copy()
    siguiente.index = siguiente.index + pd.DateOffset(years=1)
    ciclico = pd.concat([diario, siguiente])
    return ciclico[~ciclico.index.duplicated()].sort_index()


_INFRAESPECIE = re.compile(r"\s(var|ssp|subsp|f|cv)\.?\s+(.+)$", re.IGNORECASE)
_RANGO = {"var": "variedad", "ssp": "subespecie", "subsp": "subespecie", "f": "forma", "cv": "cultivar"}


def _binomio(nombre_cientifico: str) -> str:
    """Genero y especie ('Beta vulgaris var. cicla' -> 'beta vulgaris'); el hibrido conserva su 'x'."""
    palabras = re.sub(r"[^a-z\s\-]", "", nombre_cientifico.lower().replace("×", " x ")).split()
    return " ".join(palabras[:3] if len(palabras) >= 3 and palabras[1] == "x" else palabras[:2])


def _rango_y_nombre(nombre_cientifico: str) -> tuple[str | None, str | None]:
    """('var. cicla' -> ('variedad', 'cicla')); (None, None) si es la especie sin variedad."""
    m = _INFRAESPECIE.search(f" {nombre_cientifico}")
    return (_RANGO[m.group(1).lower()], m.group(2).strip()) if m else (None, None)


def _unir_variedades(resultados: list[dict], unir: bool = True) -> list[dict]:
    """EcoCrop trae como filas aparte las variedades y subespecies de una misma especie (Beta vulgaris, var. cicla y
    var. flavescens son tres 'Acelga'). Para quien elige que sembrar son la misma especie: con `unir` queda una fila por
    especie, la de mejor puntaje (a igual puntaje, la especie sin variedad). Cada fila de una especie con variedades
    trae `variedades` (todas, de la que mas conviene a la que menos, con su puntaje) y `variedad_recomendada`: la que
    mas conviene, aunque no sea la conocida. Sin `unir` salen todas las filas (para pedir una variedad puntual)."""
    grupos: dict[str, list[dict]] = {}
    for r in resultados:
        cientifico = r.get("nombre_cientifico")
        grupos.setdefault(_binomio(cientifico) if cientifico else r["especie"], []).append(r)
    salida = []
    for filas in grupos.values():
        if len(filas) == 1:
            salida.append(filas[0])
            continue
        orden = sorted(filas, key=lambda r: (r["apta"] is True, r["puntaje"] if r["puntaje"] is not None else -1.0,
                                             _rango_y_nombre(r["nombre_cientifico"])[0] is None), reverse=True)
        mejor = orden[0]
        variedades = []
        for r in orden:
            rango, nombre = _rango_y_nombre(r["nombre_cientifico"])
            variedades.append({"nombre_cientifico": r["nombre_cientifico"], "rango": rango, "nombre": nombre,
                               "puntaje": r["puntaje"], "apta": r["apta"], "mejor": r is mejor})
        rango, nombre = _rango_y_nombre(mejor["nombre_cientifico"])
        recomendada = {"rango": rango, "nombre": nombre} if rango else None
        for r in ([mejor] if unir else filas):
            salida.append({**r, "variedades": variedades, "variedad_recomendada": recomendada})
    return salida


# ---------------------------------------------------------------- buscador de especies
def _sin_tildes(texto: str | None) -> str:
    """Minusculas y sin tildes, para que "ají" encuentre "aji" y "Quínoa" a "quinoa"."""
    import unicodedata
    base = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in base if unicodedata.category(c) != "Mn")


def buscar_especies(identidades: dict[str, dict], fuentes: dict[str, str | None], con_fenologia: set[str],
                    consulta: str, limite: int = 12) -> list[dict]:
    """Las especies del catalogo cuyo nombre (en espanol, en ingles, comun o cientifico) contiene la consulta, de la
    que mejor coincide a la que menos. Solo lo que se puede sembrar: las mismas exclusiones que el ranking por defecto
    (malezas, forestales, ornamentales y las filas de EcoCrop que no son cultivos reconocidos). Cada una trae
    `seguimiento`: si tiene calendario por etapa. Una consulta de menos de 2 letras no devuelve nada."""
    q = _sin_tildes(consulta).strip()
    if len(q) < 2:
        return []
    # La fila de EcoCrop de una especie con calendario (solanum_tuberosum de la papa) no se ofrece aparte.
    gemelas = {_slug(identidades[c]["nombre_cientifico"]) for c in con_fenologia if (identidades.get(c) or {}).get("nombre_cientifico")}
    puntuadas = []
    for clave, ident in identidades.items():
        if clave in gemelas and clave not in con_fenologia:
            continue
        cats = set(ident.get("categorias") or [])
        if "weed" in cats or (cats and cats <= CATEGORIAS_NO_CULTIVO):
            continue
        if (fuentes.get(clave) == FUENTE_ECOCROP and clave not in con_fenologia
                and not es_cultivo_reconocido(ident.get("nombre_cientifico"))):
            continue
        campos = [_sin_tildes(ident.get(k)) for k in ("nombre_es", "nombre_en", "nombre_cientifico")]
        campos += [_sin_tildes(n) for n in (ident.get("nombres_comunes") or "").replace(";", ",").split(",")]
        campos.append(_sin_tildes(clave.replace("_", " ")))
        campos = [c.strip() for c in campos if c and c.strip()]
        if not any(q in c for c in campos):
            continue
        # 0: un nombre empieza igual; 1: alguna palabra de un nombre empieza igual; 2: lo contiene
        rango = 0 if any(c.startswith(q) for c in campos) else \
            1 if any(p.startswith(q) for c in campos for p in c.split()) else 2
        con_seguimiento = clave in con_fenologia
        puntuadas.append((rango, not con_seguimiento, len(campos[0]), clave, {
            "especie": clave, "nombre_es": ident.get("nombre_es"), "nombre_en": ident.get("nombre_en"),
            "nombre_cientifico": ident.get("nombre_cientifico"), "nombres_comunes": ident.get("nombres_comunes"),
            "seguimiento": con_seguimiento}))
    puntuadas.sort(key=lambda t: t[:4])
    return [t[4] for t in puntuadas[:limite]]


async def ranking_idoneidad(sitio: dict, repo: RepositorioEspecies, clima: pd.DataFrame | None = None,
                             lat: float | None = None, categorias: set[str] | None = None,
                             riego: bool = False, incluir_silvestres: bool = False,
                             unir_variedades: bool = True, solo: set[str] | None = None) -> list[dict]:
    """Todo el catalogo contra un predio, ordenado de mas a menos idoneo. Una consulta
    por tabla (no por especie). sitio: lo que espera puntuar_especie() mas 'awc_mm'.

    categorias: si se pasa, solo especies con alguna de esas categorias; si no, se dejan
    fuera las que son unicamente CATEGORIAS_NO_CULTIVO.

    solo: si se pasa, se evaluan unicamente esas claves de especie (para consultar una puntual sin simular las
    demas); el resultado de cada una es el mismo que en el ranking completo. Pensado para `unir_variedades=False`.

    Las que EcoCrop marca como maleza ('weed') no se recomiendan aunque tengan otra categoria
    de uso (avena silvestre, quelite, chufa salian en "Comida" porque tambien son 'cereals' o
    'vegetables'): solo entran con `incluir_silvestres` (para consultar una especie puntual) o si
    `categorias` pide 'weed' de forma expresa.

    Las filas de EcoCrop que no estan en cultivos_reconocidos (algodoncillo, cenizo, cebada bulbosa:
    EcoCrop las etiqueta como 'vegetables' o 'forage/pasture' igual que a un cultivo, y no marca
    cuales se siembran) tambien quedan fuera, salvo con `incluir_silvestres`. No afecta a las
    especies curadas ni a las de otra fuente.

    Una especie curada con perfil fenologico (papa) y su fila de EcoCrop (solanum_tuberosum)
    salen una sola vez, con el nombre curado. Si la simulacion por fase del perfil curado
    corre, el puntaje es el menor entre (1 - perdida simulada) y el de EcoCrop, y la salida
    trae ambos (`puntaje_simulacion`, `puntaje_ecocrop`). Si no corre, queda el de EcoCrop.
    `riego`: la falta de lluvia no cuenta, ni en EcoCrop ni en la simulacion por fase.

    Una excepcion: la simulacion no puede declarar apta a una especie que queda fuera de
    los rangos absolutos de EcoCrop. Las reglas de dano curadas se escribieron para una
    zona (ajo chilote y haba no tienen regla de sequia porque Chiloe es de exceso de agua)
    y fuera de ella no ven lo que falta: BUG REAL, en Copiapo (74 mm de lluvia al ano)
    ambas salian con puntaje 1,0."""
    requisitos = await repo.requisitos_genericos()
    identidades = await repo.identidades()
    luz = await repo.equivalencias_luz()
    con_fenologia = await repo.especies_con_fenologia()
    por_especie = {r["especie"]: r for r in requisitos}

    gemelo = {}  # slug de EcoCrop -> especie curada que lo representa
    for curada in con_fenologia:
        cientifico = (identidades.get(curada) or {}).get("nombre_cientifico")
        if cientifico and _slug(cientifico) in por_especie:
            gemelo[_slug(cientifico)] = curada
    con_gemelo = set(gemelo.values())
    ciclico = _clima_ciclico(clima) if lat is not None else None
    binomios_solo = {_binomio(identidades[n]["nombre_cientifico"]) for n in (solo or ())
                     if (identidades.get(n) or {}).get("nombre_cientifico")}

    out = []
    for req in requisitos:
        clave = req["especie"]
        if clave in con_gemelo:
            continue  # se evalua al pasar por su fila de EcoCrop
        nombre = gemelo.get(clave, clave)
        identidad = identidades.get(nombre) or identidades.get(clave) or {}
        if solo is not None and nombre not in solo and not (
                identidad.get("nombre_cientifico") and _binomio(identidad["nombre_cientifico"]) in binomios_solo):
            continue   # las variedades de una especie pedida se evaluan: `variedades` lista a todas las del grupo
        cats = set(identidad.get("categorias") or [])
        if "weed" in cats and not incluir_silvestres and "weed" not in (categorias or ()):
            continue
        if (not incluir_silvestres and req.get("fuente") == FUENTE_ECOCROP and nombre not in con_fenologia
                and not es_cultivo_reconocido(identidad.get("nombre_cientifico"))):
            continue  # silvestre o de uso local que EcoCrop mezcla con los cultivos (ver cultivos_reconocidos)
        if categorias is not None:
            if not cats & categorias:
                continue
        elif cats and cats <= CATEGORIAS_NO_CULTIVO:
            continue

        resultado = puntuar_especie(req, sitio, luz, riego)
        nivel = "perfil_generico"
        if nombre in con_fenologia:
            nivel = await nivel_madurez(nombre, None, repo)
            simulacion = None
            if ciclico is not None:
                try:
                    simulacion = await _idoneidad_simulada(
                        nombre, None, repo, ciclico, lat, sitio.get("awc_mm"), riego, sitio.get("et0_factor_mensual"),
                        PROFUNDIDAD_SUELO_M.get((sitio.get("suelo") or {}).get("profundidad")))
                except ClimaIncompleto:
                    simulacion = None
            if simulacion is not None:
                fuera_de_rango = resultado["apta"] is False
                # Sin 'perdida_simulada' la simulacion no completo el ciclo: puntaje 0. El puntaje
                # es el menor entre la simulacion y EcoCrop: asi la cifra de arriba nunca supera a
                # la peor de las barras que se muestran debajo (la simulacion sola ignoraba, por
                # ejemplo, un pH o una temperatura en el limite).
                puntaje_sim = round(1 - simulacion.get("perdida_simulada", 1.0), 3)
                puntaje_eco = resultado["puntaje"]
                resultado.update(
                    simulacion=simulacion, metodo="simulacion_por_fase",
                    apta=simulacion["apta"] and not fuera_de_rango,
                    fuera_de_rangos_ecocrop=fuera_de_rango,
                    puntaje_simulacion=puntaje_sim, puntaje_ecocrop=puntaje_eco,
                    puntaje=0.0 if fuera_de_rango else (puntaje_sim if puntaje_eco is None else min(puntaje_sim, puntaje_eco)))
        if resultado["apta"] and resultado["puntaje"] < PUNTAJE_MINIMO_APTA:
            resultado.update(apta=False, marginal=True)

        out.append({"especie": nombre, "especie_ecocrop": clave if clave != nombre else None,
                    "nombre_cientifico": identidad.get("nombre_cientifico"),
                    "nombres_comunes": identidad.get("nombres_comunes"),
                    "nombre_es": identidad.get("nombre_es"), "nombre_en": identidad.get("nombre_en"),
                    "categorias": sorted(cats), "forma_vida": identidad.get("forma_vida"),
                    "nivel_madurez": nivel, "fuente_requisitos": req.get("fuente"), **resultado})

    # Orden: aptas primero, por puntaje. Con el mismo puntaje, las de perfil fenologico (las
    # que tienen seguimiento por etapa) antes que las demas, luego la comida antes que la
    # maleza y el forraje, y al final el nombre, para que el orden no dependa de la base.
    def prioridad(r: dict) -> tuple:
        cats = set(r["categorias"])
        return (r["nivel_madurez"] != "perfil_generico", bool(cats & CATEGORIAS_ALIMENTO) and "weed" not in cats)

    out = _unir_variedades(out, unir_variedades)

    out.sort(key=lambda r: r["especie"])
    out.sort(key=lambda r: (r["apta"] is True, r["puntaje"] if r["puntaje"] is not None else -1.0, *prioridad(r)),
             reverse=True)
    return out


# ---------------------------------------------------------------- seguimiento de un cultivo sembrado
def _perdida_de(eventos: list[dict]) -> float:
    """Misma combinacion que motor_estres.evaluar(): por (fase, peligro) cuenta la regla
    mas grave, entre fases se multiplican; un efecto 'total' es perdida completa."""
    if any(e["efecto"] == "total" for e in eventos):
        return 1.0
    peor = {}
    for e in eventos:
        if e["efecto"] == "parcial":
            clave = (e["fase"], e["peligro"])
            peor[clave] = max(peor.get(clave, 0.0), e["valor"])
    perdida = 1.0
    for v in peor.values():
        perdida *= 1 - v
    return round(1 - perdida, 2)


# Que etapa del calendario confirma cada reporte de campo. Solo las que significan lo mismo en cualquier especie:
# "brote" es la emergencia (BBCH09) y "flor" la floracion (BBCH65). Las demas (hojas, fruto o raiz, amarilla, cosecha)
# no tienen una etapa propia en el reloj termico de estas especies: se anotan pero no mueven el calendario.
ETAPA_DE_REPORTE = {"brote": "emergencia", "flor": "floracion"}

# Especies con etapas derivadas de FAO-56 (inicial, desarrollo, media, madurez): ahi "desarrollo" termina con la
# cobertura plena (lo que se ve como flor) y "media" al empezar la senescencia (hojas amarillas). El brote y el resto
# no coinciden con ningun corte. Sin validar con datos de campo. En las especies de abajo la flor no marca el fin de
# "desarrollo" (raiz, tuberculo, hortaliza de hoja o inflorescencia que se cosecha antes de florecer).
ETAPA_DE_REPORTE_FAO = {"flor": "desarrollo", "amarilla": "media"}
ESPECIES_FAO_SIN_FLOR = frozenset({
    "beta_vulgaris", "daucus_carota", "ipomoea_batatas", "raphanus_sativus_var_radicula",
    "brassica_oleracea_var_botrytis", "brassica_oleracea_var_capitata", "brassica_oleracea_var_italica"})
FASES_QUE_REANCLAN = tuple(dict.fromkeys([*ETAPA_DE_REPORTE, *ETAPA_DE_REPORTE_FAO]))


def etapa_de_reporte(fase: str, c: Cultivo) -> str | None:
    """Etapa del calendario de `c` que confirma un reporte de `fase`, o None si ese reporte no mueve nada."""
    etapa = ETAPA_DE_REPORTE.get(fase)
    nombres = [n for n, _ in c.etapas]
    if etapa in nombres:
        return etapa
    if "desarrollo" in nombres and "media" in nombres:
        if fase == "flor" and c.nombre.split(":")[0] in ESPECIES_FAO_SIN_FLOR:
            return None
        return ETAPA_DE_REPORTE_FAO.get(fase)
    return None


def calendario_con_reportes(clima: pd.DataFrame, fechas: dict, c: Cultivo, siembra, lat: float,
                            reportes: list[dict]) -> tuple[dict, dict]:
    """Reancla el calendario simulado a lo que el agricultor vio (ver pheno_engine.actualizar_calendario_con_confirmacion).
    `reportes`: [{'fase', 'fecha'}]. De cada etapa cuenta el reporte mas reciente (asi se puede corregir uno
    equivocado reportando de nuevo). Las etapas confirmadas toman la fecha del reporte; las anteriores, la simulada
    o la del reporte si la simulada cae despues; las posteriores a la ultima confirmada se vuelven a calcular desde
    esa fecha. Devuelve (fechas nuevas, {etapa: fecha confirmada}); sin reportes que apliquen, las mismas fechas."""
    nombres = [n for n, _ in c.etapas]
    siembra = pd.Timestamp(siembra)
    confirmadas: dict[str, pd.Timestamp] = {}
    for r in sorted(reportes, key=lambda r: r["fecha"]):
        etapa = etapa_de_reporte(r["fase"], c)
        fecha = pd.Timestamp(r["fecha"])
        if etapa in nombres and siembra <= fecha <= clima.index[-1]:
            confirmadas[etapa] = fecha
    if not confirmadas:
        return fechas, {}
    ultima = max(confirmadas, key=nombres.index)
    nuevas: dict[str, pd.Timestamp] = {}
    try:
        posteriores = actualizar_calendario_con_confirmacion(clima, ultima, confirmadas[ultima], lat, c)
    except (ValueError, KeyError):
        return fechas, {}
    for nombre in nombres[: nombres.index(ultima) + 1]:
        if nombre in confirmadas:
            nuevas[nombre] = confirmadas[nombre]
        elif nombre in fechas:
            nuevas[nombre] = min(fechas[nombre], confirmadas[ultima])
    nuevas.update(posteriores)
    return nuevas, {n: f for n, f in confirmadas.items()}


async def seguimiento_cultivo(especie: str, variedad_local: str | None, repo: RepositorioEspecies,
                               clima: pd.DataFrame, siembra, lat: float, cap_mm: float | None, hoy,
                               manejo: tuple = (), et0_factores: list | None = None,
                               prof_suelo_m: float | None = None, reportes: tuple = ()) -> dict:
    """Un cultivo ya sembrado (o con siembra planeada) contra la serie diaria del predio:
    en que fecha llega a cada etapa, en que fase esta hoy, y que condiciones y eventos de
    dano toca cada fase -- separando lo que ya se observo, lo que viene en el pronostico y
    lo que solo es estimacion con el ano anterior.

    clima: repositorio_clima.leer_clima_diario() (tmin, tmax, lluvia, rh, fuente,
    horizonte). Levanta EspecieSinPerfilFenologico si la especie no tiene reloj de GDD,
    y ValueError si la serie no cubre la fecha de siembra.

    Las reglas se evaluan tres veces: con la serie cortada en el ultimo dia observado,
    cortada en el ultimo dia de pronostico, y completa. Un evento es 'observado' si la
    regla ya se cumple solo con lo observado, 'pronostico' si hace falta el pronostico
    para que se cumpla, y 'estimado' si solo aparece al sumar el ano anterior -- asi una
    lluvia acumulada que depende de dias que aun no ocurren no cuenta como dano ocurrido."""
    c = await construir_cultivo(especie, variedad_local, repo)
    reglas = await construir_reglas(especie, variedad_local, repo)
    siembra, hoy = pd.Timestamp(siembra), pd.Timestamp(hoy)
    if siembra < clima.index[0] or siembra > clima.index[-1]:
        raise ValueError("la serie de clima del predio no cubre la fecha de siembra")

    numerico = clima[["tmin", "tmax", "lluvia", "rh"]].astype(float)
    horizonte = clima["horizonte"]
    fechas = simular(numerico, siembra, lat, c)
    fechas, confirmadas = calendario_con_reportes(numerico, fechas, c, siembra, lat, list(reportes))
    params = await construir_parametros_agua(especie, repo)
    riegos = tuple(pd.Timestamp(m["fecha"]) for m in manejo if m["tipo_labor"] == "riego")
    agua = balance_del_cultivo(numerico, lat, siembra, fechas, c, params, cap_mm, False, et0_factores, prof_suelo_m,
                               riegos=riegos)
    resultado = evaluar(numerico, agua, siembra, fechas, c, reglas, manejo=manejo)

    dia = lambda t: t.date().isoformat()
    ultimo_dia = lambda h: horizonte.index[horizonte == h].max() if (horizonte == h).any() else None
    fin_observado = ultimo_dia("observado")
    fin_pronostico = ultimo_dia("pronostico") or fin_observado

    def eventos_hasta(fin) -> list[dict]:
        if fin is None:
            return []
        return evaluar(numerico.loc[:fin], agua.loc[:fin], siembra, fechas, c, reglas, manejo=manejo)["eventos"]

    clave = lambda e: (e["fase"], e["peligro"], e["efecto"], e["valor"])
    observados, con_pronostico = eventos_hasta(fin_observado), eventos_hasta(fin_pronostico)
    ya_observado, ya_pronosticado = {clave(e) for e in observados}, {clave(e) for e in con_pronostico}
    eventos = [{**e, "valor": float(e["valor"]),
                "horizonte": "observado" if clave(e) in ya_observado
                             else "pronostico" if clave(e) in ya_pronosticado else "estimado",
                "primer_dia": dia(e["primer_dia"]), "ultimo_dia": dia(e["ultimo_dia"])}
               for e in resultado["eventos"]]

    etapas = [{"etapa": nombre, "fecha": dia(fechas[nombre]) if nombre in fechas else None,
               "horizonte": horizonte.get(fechas[nombre]) if nombre in fechas else None,
               "confirmada": nombre in confirmadas}
              for nombre, _ in c.etapas]

    tramos = [(nombre, ini, fin, False) for nombre, ini, fin in fases(siembra, fechas, c)]
    if not resultado["ciclo_completo"]:
        # La etapa siguiente no se alcanza dentro de la serie: fase abierta hasta su ultimo dia.
        alcanzadas = [n for n, _ in c.etapas if n in fechas]
        previa = alcanzadas[-1] if alcanzadas else "siembra"
        tramos.append((f"{previa}->{c.etapas[len(alcanzadas)][0]}",
                       fechas[previa] if alcanzadas else siembra, clima.index[-1], True))

    fases_out, fase_actual = [], None
    for nombre, ini, fin, abierta in tramos:
        tramo, etiquetas = numerico.loc[ini:fin], horizonte.loc[ini:fin]
        estado = "terminada" if fin < hoy else "futura" if ini > hoy else "en_curso"
        if estado == "en_curso":
            fase_actual = nombre
        fases_out.append({
            "fase": nombre, "inicio": dia(ini), "fin": None if abierta else dia(fin), "estado": estado,
            "dias_por_horizonte": {h: int(n) for h, n in etiquetas.value_counts().items()},
            "condiciones": None if tramo.empty else {
                "tmin_mas_baja": round(float(tramo["tmin"].min()), 1),
                "tmax_mas_alta": round(float(tramo["tmax"].max()), 1),
                "lluvia_mm": round(float(tramo["lluvia"].sum()), 1),
                "humedad_relativa_media": None if tramo["rh"].isna().all() else round(float(tramo["rh"].mean()), 1),
                "agua_suelo_minima": round(float(agua.loc[ini:fin, "agua"].min()), 2),
            },
            "eventos": [e for e in eventos if e["fase"] == nombre],
        })

    ultimo = lambda h: dia(ultimo_dia(h)) if ultimo_dia(h) is not None else None
    if resultado["fecha_perdida"] is not None:
        estado_cultivo = "perdido"
    elif not resultado["ciclo_completo"]:
        estado_cultivo = "ciclo_sin_completar_en_la_serie"
    else:
        estado_cultivo = resultado["estado"]
    if params is None:
        riego_hoy = {"disponible": False, "motivo": "especie_sin_parametros_de_agua"}
    else:
        taw, raw = zona_raices_mm(cap_mm if cap_mm else AWC_POR_DEFECTO_MM, params, prof_suelo_m)
        hechos = [r for r in riegos if r <= hoy]
        riego_hoy = {**recomendar_riego(agua, taw, raw, horizonte, hoy, siembra, fechas.get(c.etapas[-1][0]),
                                        max(hechos) if hechos else None),
                     "suelo_medido": bool(cap_mm)}
    return {
        "cultivo": c.nombre, "siembra": dia(siembra), "hoy": dia(hoy),
        "horizontes": {"observado_hasta": ultimo("observado"), "pronostico_hasta": ultimo("pronostico"),
                       "estimado_hasta": ultimo("estimado")},
        "etapas": etapas, "fase_actual": fase_actual, "fases": fases_out,
        "calendario_aproximado": await calendario_aproximado(especie, variedad_local, repo),
        "estado": estado_cultivo, "riego": riego_hoy,
        "perdida_observada": _perdida_de(observados),
        "perdida_con_pronostico": _perdida_de(con_pronostico),
        "perdida_proyectada": _perdida_de(eventos) if resultado["ciclo_completo"] else None,
        "atraso_dias": int(resultado["atraso_dias"]),
        "reglas_evaluadas": len(reglas),
        # Reglas cuya fase no existe entre las etapas de esta especie: nunca se cumplen.
        "reglas_con_fase_desconocida": sorted({r.fase for r in reglas} - fases_validas(c)),
        "capacidad_agua_mm": cap_mm if cap_mm else (AWC_POR_DEFECTO_MM if params else 100.0),
        "modelo_agua": "fao56" if params else "balde_perfil",
        "humedad_relativa_disponible": bool(numerico["rh"].notna().any()),
    }


# ---------------------------------------------------------------- curva optica del satelite
# Contraste independiente de la simulacion: cuando reverdece de verdad el poligono, segun
# el NDVI de Sentinel-2, contra la fecha en que el motor dice que el cultivo emerge.
# Los cuatro numeros son criterio propio, sin validar contra cultivos con fecha conocida:
# el umbral del 20 % de la amplitud es de uso comun en fenologia satelital, no un
# estandar calibrado para estas especies.
AMPLITUD_NDVI_MIN = 0.2    # con menos subida que esto no hay senal de un cultivo creciendo
UMBRAL_VERDOR = 0.2        # el verdor "empieza" al cruzar base + 20 % de la amplitud
SALTO_RUIDO_NDVI = 0.15    # una caida mayor que esta respecto de sus dos vecinos es nube residual
DIAS_BASE_ANTES, DIAS_BASE_DESPUES = 30, 10   # ventana alrededor de la siembra que define la linea de base


def _sin_ruido(obs: list[dict]) -> list[dict]:
    """Quita las caidas aisladas: una nube o una sombra que la mascara dejo pasar baja el
    NDVI de un intervalo, nunca lo sube (visto en datos reales: 0,03 entre dos 0,33)."""
    return [o for i, o in enumerate(obs)
            if not (0 < i < len(obs) - 1
                    and obs[i - 1]["ndvi"] - o["ndvi"] > SALTO_RUIDO_NDVI
                    and obs[i + 1]["ndvi"] - o["ndvi"] > SALTO_RUIDO_NDVI)]


def curva_optica(observaciones: list[dict], siembra: date, emergencia_simulada: date | None = None) -> dict:
    """observaciones: repositorio_clima.leer_ndvi() -- [{'fecha', 'ndvi', 'visible'}].

    Devuelve en que estado esta la senal ('con_senal', 'sin_senal_de_crecimiento',
    'sin_linea_de_base', 'sin_observaciones_tras_la_siembra') y, si hay senal, la fecha
    en que empezo el verdor y su distancia en dias a la emergencia simulada.

    Dos cosas que este numero NO es: no es un error del modelo (el verdor se ve desde el
    satelite cuando el follaje ya cubre parte del suelo, dias o semanas despues de emerger:
    un desfase positivo moderado es lo esperable) y no es mas preciso que el hueco entre
    las dos observaciones que lo encierran (`incertidumbre_dias`)."""
    obs = _sin_ruido(sorted(observaciones, key=lambda o: o["fecha"]))
    previas = [o for o in obs if siembra - timedelta(days=DIAS_BASE_ANTES) <= o["fecha"]
               <= siembra + timedelta(days=DIAS_BASE_DESPUES)]
    posteriores = [o for o in obs if o["fecha"] > siembra]
    out = {"observaciones_validas": len(obs), "metodo": "umbral_20pct_de_amplitud_sin_validar"}
    if not posteriores:
        return {**out, "estado": "sin_observaciones_tras_la_siembra"}
    if not previas:
        return {**out, "estado": "sin_linea_de_base"}

    base = median(o["ndvi"] for o in previas)
    pico = max(posteriores, key=lambda o: o["ndvi"])
    amplitud = pico["ndvi"] - base
    out.update(ndvi_base=round(base, 3), ndvi_maximo=round(pico["ndvi"], 3), fecha_maximo=pico["fecha"].isoformat(),
               amplitud=round(amplitud, 3),
               # Si el maximo es la ultima observacion, la curva sigue subiendo: la amplitud
               # real sera mayor y la fecha de inicio puede correrse.
               provisional=pico is obs[-1])
    if amplitud < AMPLITUD_NDVI_MIN:
        return {**out, "estado": "sin_senal_de_crecimiento"}

    umbral = base + UMBRAL_VERDOR * amplitud
    cruce = next(o for o in posteriores if o["ndvi"] >= umbral)
    anterior = next((o for o in reversed(obs) if o["fecha"] < cruce["fecha"]), None)
    if anterior is None or anterior["ndvi"] >= umbral:
        inicio, incertidumbre = cruce["fecha"], None
    else:
        fraccion = (umbral - anterior["ndvi"]) / (cruce["ndvi"] - anterior["ndvi"])
        dias = (cruce["fecha"] - anterior["fecha"]).days
        inicio, incertidumbre = anterior["fecha"] + timedelta(days=round(fraccion * dias)), dias
    out.update(estado="con_senal", inicio_verdor=inicio.isoformat(), incertidumbre_dias=incertidumbre,
               verdor_anterior_a_la_siembra=inicio < siembra,
               desfase_con_emergencia_dias=(inicio - emergencia_simulada).days if emergencia_simulada else None)
    return out


async def construir_cultivo(especie: str, variedad_local: str | None, repo: RepositorioEspecies) -> Cultivo:
    req = await repo.requisitos(especie, variedad_local)
    umbrales = await repo.umbrales_fenologicos(especie, variedad_local)
    if not umbrales:
        if req:
            raise EspecieSinPerfilFenologico(
                f"{especie}/{variedad_local}: hay requisitos_especie (sirve para idoneidad "
                "de sitio) pero no umbral_fenologico_config -- no se puede simular calendario."
            )
        raise EspecieSinPerfil(f"{especie}/{variedad_local}: sin ningun dato registrado.")
    if not req or req.get("tb") is None:
        raise EspecieSinPerfilFenologico(
            f"{especie}/{variedad_local}: hay umbral_fenologico_config pero faltan tb/to/tc "
            "en requisitos_especie -- no se puede calcular el reloj termico."
        )

    filas = elegir_etapas(umbrales, variedad_local)
    if not filas:
        raise EspecieSinPerfilFenologico(f"{especie}/{variedad_local}: sin etapas para esta variedad ni genericas.")
    etapas = tuple((u["etapa"], (u["gdd_minimo"] + u["gdd_maximo"]) / 2) for u in filas)
    # Una etapa con horas_luz_criticas avanza mas lento bajo ese fotoperiodo. Cultivo
    # admite un solo fotoperiodo critico: si hay varias etapas moduladas, manda la ultima.
    moduladas = tuple(u["etapa"] for u in filas if u.get("horas_luz_criticas"))
    horas_luz = next((u["horas_luz_criticas"] for u in reversed(filas) if u.get("horas_luz_criticas")), None)

    return Cultivo(
        nombre=f"{especie}:{variedad_local or 'generica'}",
        tb=req["tb"], to=req["t_optima"], tc=req["tc"],
        etapas=etapas,
        moduladas=moduladas,
        foto_critico=horas_luz or 0,
        foto_sens=req.get("foto_sens") or (0.05 if horas_luz else 0),
        vern_req=req.get("vern_req") or 0,
    )


def elegir_etapas(umbrales: list[dict], variedad_local: str | None) -> list[dict]:
    """Las etapas de una especie son datos, no codigo: cada fila de umbral_fenologico_config
    es una etapa con su nombre (`etapa`), su posicion (`orden`) y los grados-dia que la
    separan de la anterior. Cada especie define cuantas tiene y como se llaman (papa:
    emergencia, tuberizacion, madurez; ajo: emergencia, bulbificacion, madurez).

    Si la variedad pedida tiene etapas propias se usan solo esas, completas -- una variedad
    puede tener otro numero de etapas que la especie generica, no se mezclan fila a fila."""
    propias = [u for u in umbrales if variedad_local is not None and u["variedad_local"] == variedad_local]
    filas = propias or [u for u in umbrales if u["variedad_local"] is None]
    return sorted(filas, key=lambda u: u["orden"])


def fases_validas(c: Cultivo) -> set[str]:
    """Nombres de fase que una regla de dano puede usar para este cultivo -- los mismos
    que arma motor_estres.fases(). Una regla con otra fase nunca se evalua."""
    nombres = ["siembra", *(n for n, _ in c.etapas)]
    return {f"{a}->{b}" for a, b in zip(nombres, nombres[1:])} | {"cosecha", "*"}


async def construir_perfil(especie: str, repo: RepositorioEspecies) -> dict:
    rasgos = await repo.rasgos_rotacion(especie)
    if not rasgos:
        raise EspecieSinPerfil(f"{especie}: sin rasgos_rotacion_especie -- no se puede ubicar en una rotacion.")
    perfil = dict(
        familia=rasgos["familia_botanica"],
        legum=rasgos["fija_nitrogeno"],
        exigente=bool(rasgos.get("exigente")),
        intervalo=rasgos.get("intervalo_rotacion") if rasgos.get("intervalo_rotacion") is not None else 1,
        perenne=bool(rasgos.get("perenne")),
    )
    if not perfil["perenne"]:
        perfil["siembra"] = (rasgos.get("siembra_mes") or 1, rasgos.get("siembra_dia") or 1)
    return perfil


async def construir_reglas(especie: str, variedad_local: str | None, repo: RepositorioEspecies) -> tuple[Regla, ...]:
    """Tupla vacia si no hay filas -- y eso es correcto: motor_rotacion.evaluar_cultivos()
    ya trata 'sin reglas' como 'no modelado', no como 'sin riesgo'. No hay que fingir
    reglas aqui para evitar una tupla vacia."""
    filas = await repo.reglas_dano(especie, variedad_local)
    return tuple(Regla(
        f["fase"], f["peligro"], f["umbral"], f["minimo"], f["efecto"], f.get("valor", 0),
        f.get("mitigado_por"), f.get("factor_mitigacion") or 0.0, f.get("ventana_mitigacion_dias") or 0,
    ) for f in filas)


# ---------------------------------------------------------------- orquestacion para motor_rotacion
@dataclass
class Catalogo:
    cultivos: dict       # {nombre: Cultivo} -- solo las que se pudieron construir
    perfiles: dict       # {nombre: dict} -- todas las que tienen rasgos_rotacion_especie
    reglas: dict         # {nombre: tuple[Regla,...]} -- vacia si no hay, nunca ausente
    sin_perfil: list     # nombres que ni siquiera llegaron a perfil_generico


async def construir_catalogo(especies: list[tuple[str, str | None]], repo: RepositorioEspecies) -> Catalogo:
    """especies: [(especie, variedad_local), ...].

    Un cultivo que falla construir_cultivo (perfil_generico nada mas, o sin_perfil) NO
    se agrega a `cultivos` -- motor_rotacion.evaluar_cultivos() ya sabe tratar un nombre
    ausente de `cultivos` igual que uno sin reglas: no modelado, relleno neutro. No hace
    falta propagar el error hacia arriba para que el resto del catalogo funcione.

    Las especies se construyen en secuencia, no con asyncio.gather -- son pocas por
    predio (3-8 especies tipico) y el paralelismo no vale la complejidad de manejar
    errores parciales de gather aqui. Si esto escala a decenas de especies por consulta,
    reconsiderar."""
    cultivos, perfiles, reglas, sin_perfil = {}, {}, {}, []
    for especie, variedad_local in especies:
        nombre = especie if variedad_local is None else f"{especie}:{variedad_local}"
        try:
            perfiles[nombre] = await construir_perfil(especie, repo)
        except EspecieSinPerfil:
            sin_perfil.append(nombre)
            continue
        reglas[nombre] = await construir_reglas(especie, variedad_local, repo)
        if not perfiles[nombre].get("perenne"):
            try:
                cultivos[nombre] = await construir_cultivo(especie, variedad_local, repo)
            except (EspecieSinPerfil, EspecieSinPerfilFenologico):
                pass  # queda sin Cultivo -- evaluar_cultivos() lo trata como no modelado
    return Catalogo(cultivos, perfiles, reglas, sin_perfil)


# ---------------------------------------------------------------- repositorio de prueba
@dataclass
class RepositorioEnMemoria:
    """Implementacion minima de RepositorioEspecies sobre listas de dict, para probar
    la logica de arriba sin una base de datos real. Las filas tienen la misma forma
    que las columnas de database/schema.sql."""
    requisitos_rows: list[dict]
    umbrales_rows: list[dict]
    rasgos_rows: list[dict]
    reglas_rows: list[dict]
    especie_rows: list[dict] = field(default_factory=list)
    luz_rows: list[dict] = field(default_factory=list)
    parametros_agua_rows: list[dict] = field(default_factory=list)

    async def requisitos_genericos(self):
        return [r for r in self.requisitos_rows if r["variedad_local"] is None]

    async def especies_con_fenologia(self):
        return {u["especie"] for u in self.umbrales_rows if u["variedad_local"] is None}

    async def identidades(self):
        return {e["especie"]: e for e in self.especie_rows}

    async def equivalencias_luz(self):
        return sorted(self.luz_rows, key=lambda f: f["orden"])

    async def parametros_agua(self, especie):
        return next((r for r in self.parametros_agua_rows if r["especie"] == especie), None)

    async def requisitos(self, especie, variedad_local):
        for r in self.requisitos_rows:
            if r["especie"] == especie and r["variedad_local"] in (variedad_local, None):
                return r
        return None

    async def umbrales_fenologicos(self, especie, variedad_local):
        return [u for u in self.umbrales_rows
                if u["especie"] == especie and u["variedad_local"] in (variedad_local, None)]

    async def rasgos_rotacion(self, especie):
        return next((r for r in self.rasgos_rows if r["especie"] == especie), None)

    async def especies_con_rasgos_rotacion(self):
        return sorted({r["especie"] for r in self.rasgos_rows})

    async def reglas_dano(self, especie, variedad_local):
        return [f for f in self.reglas_rows
                if f["especie"] == especie and f["variedad_local"] in (variedad_local, None)]

    async def listar_especies(self):
        vistos, out = set(), []
        for r in self.requisitos_rows:
            clave = (r["especie"], r["variedad_local"])
            if clave not in vistos:
                vistos.add(clave)
                out.append(clave)
        return out
