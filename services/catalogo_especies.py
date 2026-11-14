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
  perfil_calibrado            -> umbral_fenologico_config.fuente != 'placeholder_sin_validar'.

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
from typing import Protocol

import pandas as pd

from pheno_engine import ClimaIncompleto, Cultivo, simular
from motor_estres import Regla, balance_agua, evaluar, fases


class EspecieSinPerfil(Exception):
    """No hay ningun dato (ni siquiera generico) para esta especie/variedad."""


class EspecieSinPerfilFenologico(Exception):
    """Hay requisitos_especie (sirve para idoneidad de sitio) pero no
    umbral_fenologico_config -- no se puede construir un reloj de GDD todavia."""


class RepositorioEspecies(Protocol):
    async def requisitos(self, especie: str, variedad_local: str | None) -> dict | None: ...
    async def umbrales_fenologicos(self, especie: str, variedad_local: str | None) -> list[dict]: ...
    async def rasgos_rotacion(self, especie: str) -> dict | None: ...
    async def reglas_dano(self, especie: str, variedad_local: str | None) -> list[dict]: ...
    async def listar_especies(self) -> list[tuple[str, str | None]]: ...
    async def requisitos_genericos(self) -> list[dict]: ...
    async def especies_con_fenologia(self) -> set[str]: ...
    async def identidades(self) -> dict[str, dict]: ...
    async def equivalencias_luz(self) -> list[dict]: ...


async def nivel_madurez(especie: str, variedad_local: str | None, repo: RepositorioEspecies) -> str:
    umbrales = await repo.umbrales_fenologicos(especie, variedad_local)
    if umbrales:
        sin_validar = any(u["fuente"] == "placeholder_sin_validar" for u in umbrales)
        return "perfil_fenologico_regional" if sin_validar else "perfil_calibrado"
    if await repo.requisitos(especie, variedad_local):
        return "perfil_generico"
    return "sin_perfil"


async def _idoneidad_simulada(especie: str, variedad_local: str | None, repo: RepositorioEspecies,
                               clima: pd.DataFrame, lat: float, cap_mm: float | None) -> dict | None:
    """Corre el mismo camino real que motor_rotacion.evaluar_cultivos() usa (simular +
    evaluar), para que la supervivencia ante un evento dependa de EN QUE FASE ocurre
    (regla_dano_especie.fase), no de si el promedio anual de temperatura cruza tb/tc en
    algun momento -- eso es lo que el chequeo generico de mas abajo no puede ver (BUG
    REAL encontrado: papa daba 'no apta' por una helada puntual que en la simulacion real
    solo le causa un atraso de 14 dias, no la mata).

    None si no se puede simular (sin perfil fenologico, perenne, sin fecha de siembra en
    rasgos_rotacion_especie, o el clima disponible no alcanza para esa fecha) -- quien
    llama cae al chequeo generico en ese caso, nunca inventa un resultado."""
    try:
        c = await construir_cultivo(especie, variedad_local, repo)
    except (EspecieSinPerfil, EspecieSinPerfilFenologico):
        return None
    rasgos = await repo.rasgos_rotacion(especie)
    if not rasgos or rasgos.get("perenne") or rasgos.get("siembra_mes") is None:
        return None  # pradera/perenne no se siembra una vez al ano -- no aplica este chequeo

    mes, dia = rasgos["siembra_mes"], rasgos.get("siembra_dia") or 1
    anio = clima.index[0].year
    siembra = pd.Timestamp(anio, mes, dia)
    if siembra < clima.index[0]:
        siembra = pd.Timestamp(anio + 1, mes, dia)
    if siembra > clima.index[-1]:
        return None  # no hay suficiente clima real desde la proxima fecha de siembra

    reglas = await construir_reglas(especie, variedad_local, repo)
    fechas = simular(clima, siembra, lat, c)
    if c.etapas[-1][0] not in fechas:
        return {"apta": False, "metodo": "simulacion_real", "siembra_simulada": str(siembra.date()),
                "razones": [f"no alcanza a completar el ciclo fenologico sembrando el {siembra.date()} "
                            "con el clima disponible (puede ser que el rango de clima ingerido sea corto, "
                            "no necesariamente que el sitio sea inviable)"]}

    agua = balance_agua(clima, lat, cap_mm if cap_mm else 100.0)
    resultado = evaluar(clima, agua, siembra, fechas, c, reglas)
    razones = []
    if resultado["estado"] == "perdido":
        razones.append(f"la simulacion real pierde el cultivo sembrando el {siembra.date()} -- "
                        "ver por que en regla_dano_especie (fase y peligro que gatillo efecto 'total')")
    elif resultado["perdida"] > 0.5:
        razones.append(f"perdida simulada alta ({resultado['perdida'] * 100:.0f}%) sembrando el {siembra.date()}")
    return {"apta": len(razones) == 0, "razones": razones, "metodo": "simulacion_real",
            "siembra_simulada": str(siembra.date()), "perdida_simulada": resultado["perdida"],
            "estado_simulado": resultado["estado"],
            "cap_mm_usado": cap_mm if cap_mm else "100.0 (placeholder, sin dato real de sitio)"}


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
    real de CR2MET/POWER para la parcela), nunca inventados. Ausencia de un dato de
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

# Categorias de EcoCrop que no son cultivo. Una especie se deja fuera del ranking por
# defecto solo si TODAS sus categorias estan aca; sin categoria (ej. maiz) se conserva.
CATEGORIAS_NO_CULTIVO = frozenset({"forest/wood", "ornamentals/turf", "environmental", "weed"})


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


def puntuar_especie(req: dict, sitio: dict, luz: list[dict]) -> dict:
    """req: fila de requisitos_especie. sitio: {'normales': normales_mensuales(...),
    'ph': float|None, 'ghi_mensual': [12 valores kWh/m2/dia]|None}. luz: filas de
    equivalencia_luz_ghi. Devuelve el puntaje de la mejor temporada y el factor que la
    limita; `apta` es None si no hay ni un factor evaluable."""
    normales = sitio.get("normales") or {}
    duracion = duracion_temporada_meses(req.get("ciclo_min_dias"), req.get("ciclo_max_dias"))
    t_opt_min = req.get("t_opt_min") if req.get("t_opt_min") is not None else req.get("t_optima")
    t_opt_max = req.get("t_opt_max") if req.get("t_opt_max") is not None else req.get("t_optima")
    # EcoCrop publica lluvia ANUAL; Recocrop la lleva a umbral mensual dividiendo por la
    # duracion de la temporada (en meses) mas uno.
    lluvia_mes = [None if v is None else v / (duracion + 1) for v in (
        req.get("lluvia_anual_min"), req.get("lluvia_anual_opt_min"),
        req.get("lluvia_anual_opt_max"), req.get("lluvia_anual_max"))]
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
    ph = respuesta_meseta(sitio.get("ph"), req.get("ph_suelo_min"), req.get("ph_opt_min"),
                           req.get("ph_opt_max"), req.get("ph_suelo_max"))

    mejor = None
    for inicio in range(12):
        meses = [(inicio + i) % 12 for i in range(duracion)]
        factores = {nombre: min(serie[m] for m in meses) for nombre, serie in por_mes.items()}
        if lluvia is not None:
            humedad = respuesta_meseta(sum(lluvia[m] for m in meses) / duracion, *lluvia_mes)
            if humedad is not None:
                factores["humedad"] = humedad
        if ph is not None:
            factores["ph"] = ph
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
        return {**base, "apta": None, "puntaje": None, "factores": {},
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
            "categoria_luz_temporada": categoria["categoria"] if categoria else None}


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


async def ranking_idoneidad(sitio: dict, repo: RepositorioEspecies, clima: pd.DataFrame | None = None,
                             lat: float | None = None, categorias: set[str] | None = None) -> list[dict]:
    """Todo el catalogo contra un predio, ordenado de mas a menos idoneo. Una consulta
    por tabla (no por especie). sitio: lo que espera puntuar_especie() mas 'awc_mm'.

    categorias: si se pasa, solo especies con alguna de esas categorias; si no, se dejan
    fuera las que son unicamente CATEGORIAS_NO_CULTIVO.

    Una especie curada con perfil fenologico (papa) y su fila de EcoCrop (solanum_tuberosum)
    salen una sola vez, con el nombre curado. Si la simulacion por fase del perfil curado
    corre, manda ella (es el nivel mas especifico): puntaje = 1 - perdida simulada, y los
    factores de EcoCrop quedan como referencia. Si no corre, queda el puntaje de EcoCrop."""
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

    out = []
    for req in requisitos:
        clave = req["especie"]
        if clave in con_gemelo:
            continue  # se evalua al pasar por su fila de EcoCrop
        nombre = gemelo.get(clave, clave)
        identidad = identidades.get(nombre) or identidades.get(clave) or {}
        cats = set(identidad.get("categorias") or [])
        if categorias is not None:
            if not cats & categorias:
                continue
        elif cats and cats <= CATEGORIAS_NO_CULTIVO:
            continue

        resultado = puntuar_especie(req, sitio, luz)
        nivel = "perfil_generico"
        if nombre in con_fenologia:
            nivel = await nivel_madurez(nombre, None, repo)
            simulacion = None
            if ciclico is not None:
                try:
                    simulacion = await _idoneidad_simulada(nombre, None, repo, ciclico, lat, sitio.get("awc_mm"))
                except ClimaIncompleto:
                    simulacion = None
            if simulacion is not None:
                resultado.update(
                    simulacion=simulacion, apta=simulacion["apta"], metodo="simulacion_por_fase",
                    # Sin 'perdida_simulada' la simulacion no completo el ciclo: puntaje 0.
                    puntaje=round(1 - simulacion.get("perdida_simulada", 1.0), 3))

        out.append({"especie": nombre, "especie_ecocrop": clave if clave != nombre else None,
                    "nombre_cientifico": identidad.get("nombre_cientifico"),
                    "nombres_comunes": identidad.get("nombres_comunes"),
                    "categorias": sorted(cats), "forma_vida": identidad.get("forma_vida"),
                    "nivel_madurez": nivel, "fuente_requisitos": req.get("fuente"), **resultado})

    out.sort(key=lambda r: (r["apta"] is True, r["puntaje"] if r["puntaje"] is not None else -1.0), reverse=True)
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


async def seguimiento_cultivo(especie: str, variedad_local: str | None, repo: RepositorioEspecies,
                               clima: pd.DataFrame, siembra, lat: float, cap_mm: float | None, hoy,
                               manejo: tuple = ()) -> dict:
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
    agua = balance_agua(numerico, lat, cap_mm if cap_mm else 100.0)
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
               "horizonte": horizonte.get(fechas[nombre]) if nombre in fechas else None}
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
    return {
        "cultivo": c.nombre, "siembra": dia(siembra), "hoy": dia(hoy),
        "horizontes": {"observado_hasta": ultimo("observado"), "pronostico_hasta": ultimo("pronostico"),
                       "estimado_hasta": ultimo("estimado")},
        "etapas": etapas, "fase_actual": fase_actual, "fases": fases_out,
        "estado": estado_cultivo,
        "perdida_observada": _perdida_de(observados),
        "perdida_con_pronostico": _perdida_de(con_pronostico),
        "perdida_proyectada": _perdida_de(eventos) if resultado["ciclo_completo"] else None,
        "atraso_dias": int(resultado["atraso_dias"]),
        "reglas_evaluadas": len(reglas),
        # Reglas cuya fase no existe entre las etapas de esta especie: nunca se cumplen.
        "reglas_con_fase_desconocida": sorted({r.fase for r in reglas} - fases_validas(c)),
        "capacidad_agua_mm": cap_mm if cap_mm else 100.0,
        "humedad_relativa_disponible": bool(numerico["rh"].notna().any()),
    }


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
    parcela (3-8 especies tipico) y el paralelismo no vale la complejidad de manejar
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

    async def requisitos_genericos(self):
        return [r for r in self.requisitos_rows if r["variedad_local"] is None]

    async def especies_con_fenologia(self):
        return {u["especie"] for u in self.umbrales_rows if u["variedad_local"] is None}

    async def identidades(self):
        return {e["especie"]: e for e in self.especie_rows}

    async def equivalencias_luz(self):
        return sorted(self.luz_rows, key=lambda f: f["orden"])

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
