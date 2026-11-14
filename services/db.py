"""
Sesion de base de datos — Fase 3 del plan de MVP.

Lee la cadena de conexion de la variable de entorno DATABASE_URL (en Railway, la
inyecta el servicio PostGIS; en local, viene de `railway run` o de un .env no
versionado — ver docs/arquitectura-flujos-mogewe.md, "Secretos y configuracion").

Railway entrega DATABASE_URL con el esquema `postgres://`, que SQLAlchemy async
con asyncpg no acepta tal cual -- necesita `postgresql+asyncpg://`. La conversion
se hace aqui, una sola vez, no en cada archivo que use la sesion.
"""
from __future__ import annotations

import os

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession


def _url_async(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


_DATABASE_URL = os.environ.get("DATABASE_URL", "")

engine = create_async_engine(_url_async(_DATABASE_URL), pool_pre_ping=True) if _DATABASE_URL else None
SessionLocal = async_sessionmaker(engine, expire_on_commit=False) if engine else None


async def obtener_sesion() -> AsyncSession:
    """Dependencia de FastAPI: una sesion por request, nunca compartida entre requests."""
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL no esta definida en el entorno.")
    async with SessionLocal() as session:
        yield session
