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

from pheno_engine import Cultivo
from motor_estres import Regla


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
    return tuple(Regla(f["fase"], f["peligro"], f["umbral"], f["minimo"], f["efecto"], f.get("valor", 0)) for f in filas)


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
