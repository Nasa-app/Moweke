"""
Componente de datos v0.1 — implementacion real de RepositorioEspecies sobre Postgres.

Esto es lo que reemplaza a catalogo_especies.RepositorioEnMemoria en produccion. Implementa
el mismo Protocol (RepositorioEspecies) con las mismas cuatro firmas -- por eso
services/catalogo_especies.py, motor_estres.py y motor_rotacion.py no necesitan saber que
existe este archivo: consumen la interfaz, no esta clase.

NO VERIFICADO POR EJECUCION: este entorno no tiene sqlalchemy/asyncpg instalados ni un
Postgres corriendo. La logica (que tablas, que columnas, que filtros) esta revisada contra
database/schema.sql columna por columna, pero no se probo end-to-end como el resto del
codigo de este proyecto. Correrlo contra una base real antes de confiar en el.

Patron de acceso: async, una conexion (o pool) por request de FastAPI, inyectada por
dependencia -- nunca una conexion global compartida entre requests concurrentes.
"""
from __future__ import annotations

from sqlalchemy import select
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
)


class RepositorioPostgres:
    """Implementa el Protocol RepositorioEspecies (services/catalogo_especies.py) sobre
    una sesion async de SQLAlchemy. No guarda estado propio -- la sesion la maneja quien
    construye este objeto (ver dependencia de FastAPI mas abajo)."""

    def __init__(self, session: AsyncSession):
        self._s = session

    async def requisitos(self, especie: str, variedad_local: str | None) -> dict | None:
        # variedad_local especifica primero; si no hay fila para esa variedad, cae a la
        # fila generica de la especie (variedad_local IS NULL) -- mismo principio de
        # "revisar el nivel mas especifico antes de asumir sin informacion" que en el
        # resto del proyecto (ver jerarquia de confianza).
        q = select(requisitos_especie).where(
            requisitos_especie.c.especie == especie,
            requisitos_especie.c.variedad_local.in_([variedad_local, None]),
        ).order_by(requisitos_especie.c.variedad_local.is_(None))  # no-nulo primero
        fila = (await self._s.execute(q)).mappings().first()
        return dict(fila) if fila else None

    async def umbrales_fenologicos(self, especie: str, variedad_local: str | None) -> list[dict]:
        q = select(umbral_fenologico_config).where(
            umbral_fenologico_config.c.especie == especie,
            umbral_fenologico_config.c.variedad_local.in_([variedad_local, None]),
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
            regla_dano_especie.c.variedad_local.in_([variedad_local, None]),
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
