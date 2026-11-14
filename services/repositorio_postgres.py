"""
Componente de datos v0.1 — implementacion real de RepositorioEspecies sobre Postgres.

Esto es lo que reemplaza a catalogo_especies.RepositorioEnMemoria en produccion. Implementa
el mismo Protocol (RepositorioEspecies) con las mismas cuatro firmas -- por eso
services/catalogo_especies.py, motor_estres.py y motor_rotacion.py no necesitan saber que
existe este archivo: consumen la interfaz, no esta clase.

VERIFICADO (Fase 3 del plan de MVP) contra Postgres+PostGIS real en Railway. Se encontró
y corrigió un bug real: ver `_coincide_variedad` más abajo.

Patron de acceso: async, una conexion (o pool) por request de FastAPI, inyectada por
dependencia -- nunca una conexion global compartida entre requests concurrentes.
"""
from __future__ import annotations

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

# Tablas declaradas con SQLAlchemy Core, columna por columna igual que database/schema.sql.
# No se usa un ORM declarativo (modelos de clase) a proposito: este componente solo lee
# cuatro tablas con consultas simples, un ORM completo seria una capa de mas para esto.
from sqlalchemy import MetaData, Table, Column, Integer, String, Float, Boolean, Date

metadata = MetaData()

requisitos_especie = Table(
    "requisitos_especie", metadata,
    Column("id", Integer, primary_key=True),
    Column("especie", String), Column("variedad_local", String),
    Column("humedad_suelo_minima", Float), Column("humedad_suelo_maxima", Float),
    Column("horas_luz_criticas", Float), Column("radiacion_solar_minima", Float),
    Column("ph_suelo_min", Float), Column("ph_suelo_max", Float),
    Column("tb", Float), Column("t_optima", Float), Column("tc", Float),
    Column("foto_critico", Float), Column("foto_sens", Float), Column("vern_req", Float),
    Column("fuente", String),
)

umbral_fenologico_config = Table(
    "umbral_fenologico_config", metadata,
    Column("id", Integer, primary_key=True),
    Column("especie", String), Column("variedad_local", String), Column("transicion", String),
    Column("gdd_minimo", Float), Column("gdd_maximo", Float),
    Column("horas_luz_criticas", Float), Column("fuente", String),
    Column("fecha_ultima_calibracion", Date),
)

rasgos_rotacion_especie = Table(
    "rasgos_rotacion_especie", metadata,
    Column("especie", String, primary_key=True),
    Column("fija_nitrogeno", Boolean), Column("familia_botanica", String),
    Column("demanda_hidrica_relativa", String), Column("profundidad_raiz_relativa", String),
    Column("exigente", Boolean), Column("intervalo_rotacion", Integer),
    Column("siembra_mes", Integer), Column("siembra_dia", Integer), Column("perenne", Boolean),
)

regla_dano_especie = Table(
    "regla_dano_especie", metadata,
    Column("id", Integer, primary_key=True),
    Column("especie", String), Column("variedad_local", String), Column("fase", String),
    Column("peligro", String), Column("umbral", Float), Column("minimo", Integer),
    Column("efecto", String), Column("valor", Float), Column("fuente", String),
    # Mitigacion por manejo real (ver services/motor_estres.Regla) -- NULL/0/0 para toda
    # regla que no sea biotica (helada/calor/sequia/anegamiento/ceniza no se mitigan).
    Column("mitigado_por", String), Column("factor_mitigacion", Float),
    Column("ventana_mitigacion_dias", Integer),
)


class RepositorioPostgres:
    """Implementa el Protocol RepositorioEspecies (services/catalogo_especies.py) sobre
    una sesion async de SQLAlchemy. No guarda estado propio -- la sesion la maneja quien
    construye este objeto (ver dependencia de FastAPI mas abajo)."""

    def __init__(self, session: AsyncSession):
        self._s = session

    @staticmethod
    def _coincide_variedad(columna, variedad_local: str | None):
        """BUG REAL encontrado al probar contra Postgres: `columna.in_([variedad_local, None])`
        con variedad_local=None genera `IN (NULL, NULL)`, que en SQL no matchea nunca -- NULL
        nunca es igual a NULL vía IN/=. Se verificó: requisitos("papa", None) devolvía None
        con la versión anterior, aunque la fila genérica de papa sí existe.
        La forma correcta: coincide si la columna es NULL (fila genérica) O si coincide
        exactamente con variedad_local (cuando se pide una variedad específica)."""
        if variedad_local is None:
            return columna.is_(None)
        return or_(columna == variedad_local, columna.is_(None))

    async def requisitos(self, especie: str, variedad_local: str | None) -> dict | None:
        # variedad_local especifica primero; si no hay fila para esa variedad, cae a la
        # fila generica de la especie (variedad_local IS NULL) -- mismo principio de
        # "revisar el nivel mas especifico antes de asumir sin informacion" que en el
        # resto del proyecto (ver jerarquia de confianza).
        q = select(requisitos_especie).where(
            requisitos_especie.c.especie == especie,
            self._coincide_variedad(requisitos_especie.c.variedad_local, variedad_local),
        ).order_by(requisitos_especie.c.variedad_local.is_(None))  # no-nulo primero
        fila = (await self._s.execute(q)).mappings().first()
        return dict(fila) if fila else None

    async def umbrales_fenologicos(self, especie: str, variedad_local: str | None) -> list[dict]:
        q = select(umbral_fenologico_config).where(
            umbral_fenologico_config.c.especie == especie,
            self._coincide_variedad(umbral_fenologico_config.c.variedad_local, variedad_local),
        )
        filas = (await self._s.execute(q)).mappings().all()
        return [dict(f) for f in filas]

    async def rasgos_rotacion(self, especie: str) -> dict | None:
        q = select(rasgos_rotacion_especie).where(rasgos_rotacion_especie.c.especie == especie)
        fila = (await self._s.execute(q)).mappings().first()
        return dict(fila) if fila else None

    async def reglas_dano(self, especie: str, variedad_local: str | None) -> list[dict]:
        q = select(regla_dano_especie).where(
            regla_dano_especie.c.especie == especie,
            self._coincide_variedad(regla_dano_especie.c.variedad_local, variedad_local),
        )
        filas = (await self._s.execute(q)).mappings().all()
        return [dict(f) for f in filas]


# ---------------------------------------------------------------- dependencia de FastAPI
"""
Como se conecta con los endpoints (docs/arquitectura-flujos-mogewe.md):

    from fastapi import Depends
    from sqlalchemy.ext.asyncio import AsyncSession
    import catalogo_especies as ce

    async def obtener_repo(session: AsyncSession = Depends(obtener_sesion_bd)) -> RepositorioPostgres:
        return RepositorioPostgres(session)

    @app.get("/api/parcelas/{id}/rotacion/comparar")
    async def comparar_rotacion(id: int, repo: RepositorioPostgres = Depends(obtener_repo)):
        especies = await especies_a_evaluar(id, session)   # que especies tiene sentido
                                                              # evaluar para ESTA parcela --
                                                              # decision de la capa de API,
                                                              # no de catalogo_especies.
        cat = await ce.construir_catalogo(especies, repo)
        ...
"""
