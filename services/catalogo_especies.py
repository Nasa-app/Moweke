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

from dataclasses import dataclass
from typing import Protocol

import pandas as pd

from pheno_engine import Cultivo, simular
from motor_estres import Regla, balance_agua, evaluar


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


TRANSICIONES_EN_ORDEN = ("siembra_BBCH09", "BBCH09_BBCH65", "BBCH65_BBCH97")
# Nombre de etapa que CIERRA cada transicion -- BBCH09/BBCH65/BBCH97 son los nombres
# canonicos del proyecto (ver schema.sql, umbral_fenologico_config.transicion); se
# traducen a nombres libres porque Cultivo.etapas no esta atado a esa nomenclatura.
NOMBRE_ETAPA = {"siembra_BBCH09": "emergencia", "BBCH09_BBCH65": "floracion", "BBCH65_BBCH97": "madurez"}


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


async def calcular_idoneidad(sitio: dict, especies: list[str], repo: RepositorioEspecies,
                              clima: pd.DataFrame | None = None, lat: float | None = None) -> list[dict]:
    """La funcion de analisis de terreno que el plan (Fase 6) asigna a este nivel de
    madurez: solo necesita requisitos_especie (perfil_generico), no umbral_fenologico_config
    -- por eso puede correr para una especie que EspecieSinPerfilFenologico todavia no
    deja simular con construir_cultivo().

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
    for especie in especies:
        req = await repo.requisitos(especie, None)
        if req is None:
            out.append({"especie": especie, "apta": None, "razones": ["sin_perfil (sin requisitos_especie)"]})
            continue
        nivel = await nivel_madurez(especie, None, repo)

        resultado = None
        if clima is not None and lat is not None and nivel in ("perfil_fenologico_regional", "perfil_calibrado"):
            resultado = await _idoneidad_simulada(especie, None, repo, clima, lat, sitio.get("awc_mm"))

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
            resultado = {"apta": len(razones) == 0, "razones": razones, "metodo": "generico_tb_tc_promedio"}

        out.append({"especie": especie, "fuente_requisitos": req.get("fuente"), "nivel_madurez": nivel, **resultado})
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

    por_transicion = {u["transicion"]: u for u in umbrales}
    etapas = tuple(
        (NOMBRE_ETAPA[t], (por_transicion[t]["gdd_minimo"] + por_transicion[t]["gdd_maximo"]) / 2)
        for t in TRANSICIONES_EN_ORDEN
        if t in por_transicion
    )
    if not etapas:
        raise EspecieSinPerfilFenologico(f"{especie}/{variedad_local}: umbral_fenologico_config vacio.")

    ultima_transicion = por_transicion.get("BBCH65_BBCH97")
    horas_luz = ultima_transicion.get("horas_luz_criticas") if ultima_transicion else None

    return Cultivo(
        nombre=f"{especie}:{variedad_local or 'generica'}",
        tb=req["tb"], to=req["t_optima"], tc=req["tc"],
        etapas=etapas,
        moduladas=("madurez",) if horas_luz else (),
        foto_critico=horas_luz or 0,
        foto_sens=req.get("foto_sens") or (0.05 if horas_luz else 0),
        vern_req=req.get("vern_req") or 0,
    )


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
