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

from datetime import date

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
