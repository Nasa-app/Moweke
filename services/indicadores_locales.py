"""
Indicadores locales -- lo que una comunidad observa en su zona (aves, floracion de
especies) y lo que, segun ella, anuncia (precipitacion alta o baja, helada, lluvia
temprana o tardia).

Un administrador carga la definicion de cada indicador para una zona (un poligono); los
agricultores cuyo predio cae dentro de la zona reportan cuando lo ven; la senal sale como
'confirmada' cuando agricultores distintos la reportaron dentro de su vigencia.

Es conocimiento local sin validar: aca no se compara con datos de estacion, y nada de esto
entra a la simulacion de fechas ni de perdidas (services/pheno_engine.py). Lo que se le
muestra al agricultor lo marca asi. Un reporte aislado no confirma nada: hacen falta
`umbral_reportes` agricultores distintos, igual que el resto del diseno (ver
docs/arquitectura-flujos-mogen.md, "por que un solo reporte no mueve nada grande").

La logica de arriba no toca la base y se prueba sola (tests/test_indicadores_locales.py);
las funciones async de abajo son el SQL.
"""
from __future__ import annotations

import unicodedata
from datetime import date
from typing import Literal, get_args

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Unica fuente de estas listas: main.py las usa para validar el cuerpo de la peticion y
# database/schema.sql las repite en sus CHECK (tests/test_indicadores_locales.py lo comprueba).
Categoria = Literal["aves", "floracion"]
Significado = Literal["precipitacion_alta", "precipitacion_baja", "helada",
                      "precipitacion_temprana", "precipitacion_tardia"]
CATEGORIAS = get_args(Categoria)
SIGNIFICADOS = get_args(Significado)

# Una zona mas chica que esto es un clic de mas; una mas grande que la comuna mas extensa
# de Chile (Natales, ~4,9 millones de ha) es un poligono equivocado, no una zona.
ZONA_HECTAREAS_MIN = 1.0
ZONA_HECTAREAS_MAX = 10_000_000.0
# Hasta cuantos dias atras se acepta la fecha de un reporte.
OBSERVACION_DIAS_ATRAS_MAX = 365


# ---------------------------------------------------------------- logica sin base
def limpiar_texto(valor: str) -> str:
    """Texto libre de la comunidad listo para guardar y mostrar a otros usuarios: sin
    caracteres de control, con los espacios normalizados y sin `<` ni `>`. Levanta
    ValueError si queda vacio o trae esos signos. Escapar al mostrarlo sigue siendo
    trabajo de quien lo muestra; esto es la segunda capa."""
    sustituido = "".join(" " if unicodedata.category(c)[0] == "C" else c for c in valor)
    limpio = " ".join(unicodedata.normalize("NFC", sustituido).split())
    if not limpio:
        raise ValueError("no puede quedar vacío")
    if "<" in limpio or ">" in limpio:
        raise ValueError("no puede llevar los signos < ni >")
    return limpio


def mes_en_ventana(fecha: date, mes_desde: int, mes_hasta: int) -> bool:
    """Si el mes de `fecha` cae dentro de la ventana. La ventana puede cruzar el fin de
    ano: de noviembre (11) a febrero (2) incluye diciembre y enero."""
    if mes_desde <= mes_hasta:
        return mes_desde <= fecha.month <= mes_hasta
    return fecha.month >= mes_desde or fecha.month <= mes_hasta


def estado_senal(observadores: int, umbral: int) -> str:
    """'confirmada' con `umbral` agricultores distintos o mas; 'en_observacion' con al
    menos uno; 'sin_reportes' sin ninguno."""
    if observadores >= umbral:
        return "confirmada"
    return "en_observacion" if observadores > 0 else "sin_reportes"


def resumen_por_significado(indicadores: list[dict]) -> dict[str, list[str]]:
    """Que anuncian hoy las senales confirmadas: significado -> nombres de los
    indicadores que lo dicen. Solo entran las confirmadas y solo los significados que
    tienen alguna."""
    resumen: dict[str, list[str]] = {}
    for ind in indicadores:
        if ind["estado"] == "confirmada":
            resumen.setdefault(ind["significado"], []).append(ind["nombre"])
    return resumen


# ---------------------------------------------------------------- lectura para el agricultor
async def senales_del_predio(session: AsyncSession, id_parcela: int, id_usuario: int, hoy: date) -> list[dict]:
    """Los indicadores activos de las zonas que contienen el centro del predio, cada uno con
    cuantos agricultores distintos lo reportaron dentro de su vigencia y si `id_usuario` ya
    lo reportó. No devuelve quien reporto: solo cuentas."""
    filas = (await session.execute(text("""
        SELECT i.id, i.categoria, i.nombre, i.evento, i.significado, i.nota,
               i.mes_desde, i.mes_hasta, i.umbral_reportes, i.vigencia_dias,
               z.nombre AS zona,
               count(DISTINCT o.id_usuario) AS observadores,
               max(o.fecha_observada) AS ultima_observacion,
               COALESCE(bool_or(o.id_usuario = :u), false) AS ya_reportaste
        FROM parcela p
        JOIN zona_indicadores z ON ST_Contains(z.geometria, ST_Centroid(p.geometria))
        JOIN indicador_local i ON i.id_zona = z.id AND i.activo
        LEFT JOIN observacion_indicador o
               ON o.id_indicador = i.id
              AND o.fecha_observada >= CAST(:hoy AS date) - i.vigencia_dias
              AND o.fecha_observada <= CAST(:hoy AS date)
        WHERE p.id = :p
        GROUP BY i.id, z.nombre
        ORDER BY i.categoria, i.nombre, i.id
    """), {"p": id_parcela, "u": id_usuario, "hoy": hoy})).mappings().all()
    return [{**dict(f), "estado": estado_senal(f["observadores"], f["umbral_reportes"])} for f in filas]


# ---------------------------------------------------------------- reporte del agricultor
async def indicador_para_reportar(session: AsyncSession, id_indicador: int, id_usuario: int) -> dict | None:
    """El indicador, solo si esta activo y el usuario tiene un predio dentro de su zona.
    Si no, None: un indicador inexistente, apagado o de otra zona se ven igual."""
    fila = (await session.execute(text("""
        SELECT i.id, i.mes_desde, i.mes_hasta
        FROM indicador_local i JOIN zona_indicadores z ON z.id = i.id_zona
        WHERE i.id = :i AND i.activo
          AND EXISTS (SELECT 1 FROM parcela p
                      WHERE p.id_usuario = :u AND ST_Contains(z.geometria, ST_Centroid(p.geometria)))
    """), {"i": id_indicador, "u": id_usuario})).mappings().first()
    return dict(fila) if fila else None


async def registrar_observacion(session: AsyncSession, id_indicador: int, id_usuario: int, fecha: date) -> bool:
    """Guarda el reporte. True si es nuevo; False si ese usuario ya lo habia reportado ese
    dia (un reintento del telefono sin senal no cuenta dos veces)."""
    nuevo = (await session.execute(text("""
        INSERT INTO observacion_indicador (id_indicador, id_usuario, fecha_observada)
        VALUES (:i, :u, :f)
        ON CONFLICT (id_indicador, id_usuario, fecha_observada) DO NOTHING
        RETURNING id
    """), {"i": id_indicador, "u": id_usuario, "f": fecha})).first()
    await session.commit()
    return nuevo is not None


# ---------------------------------------------------------------- administracion
class ZonaInvalida(ValueError):
    """El poligono de la zona no sirve; el mensaje es para mostrarle al administrador."""


async def crear_zona(session: AsyncSession, nombre: str, geojson: str) -> int | None:
    """Inserta la zona. `geojson` ya paso la validacion de forma (main._validar_perimetro).
    Aca va la geometrica, en PostGIS. Devuelve el id, o None si ya hay una zona con ese nombre."""
    forma = (await session.execute(text("""
        SELECT ST_IsValid(g) AND ST_IsSimple(g) AS valido, ST_Area(g::geography) / 10000 AS hectareas
        FROM (SELECT ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326) AS g) x
    """), {"gj": geojson})).mappings().first()
    if not forma["valido"]:
        raise ZonaInvalida("El perímetro se cruza a sí mismo; debe ser un polígono simple")
    if not ZONA_HECTAREAS_MIN <= forma["hectareas"] <= ZONA_HECTAREAS_MAX:
        raise ZonaInvalida(f"La zona mide {forma['hectareas']:.2f} hectáreas; debe medir entre "
                           f"{ZONA_HECTAREAS_MIN:.0f} y {ZONA_HECTAREAS_MAX:.0f}")
    id_zona = (await session.execute(text("""
        INSERT INTO zona_indicadores (nombre, geometria)
        VALUES (:n, ST_ForcePolygonCCW(ST_Force2D(ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326))))
        ON CONFLICT (nombre) DO NOTHING
        RETURNING id
    """), {"n": nombre, "gj": geojson})).scalar_one_or_none()
    await session.commit()
    return id_zona


async def listar_zonas(session: AsyncSession) -> list[dict]:
    filas = (await session.execute(text("""
        SELECT z.id, z.nombre, round((ST_Area(z.geometria::geography) / 10000)::numeric, 1)::float AS hectareas,
               (SELECT count(*) FROM indicador_local i WHERE i.id_zona = z.id AND i.activo) AS indicadores_activos
        FROM zona_indicadores z ORDER BY z.nombre
    """))).mappings().all()
    return [dict(f) for f in filas]


async def zona_existe(session: AsyncSession, id_zona: int) -> bool:
    return (await session.execute(text("SELECT 1 FROM zona_indicadores WHERE id = :z"), {"z": id_zona})).first() is not None


async def crear_indicador(session: AsyncSession, datos: dict) -> int:
    id_indicador = (await session.execute(text("""
        INSERT INTO indicador_local (id_zona, categoria, nombre, evento, significado, nota,
                                     mes_desde, mes_hasta, umbral_reportes, vigencia_dias)
        VALUES (:id_zona, :categoria, :nombre, :evento, :significado, :nota,
                :mes_desde, :mes_hasta, :umbral_reportes, :vigencia_dias)
        RETURNING id
    """), datos)).scalar_one()
    await session.commit()
    return id_indicador


async def listar_indicadores(session: AsyncSession, hoy: date, id_zona: int | None = None) -> list[dict]:
    """Todos los indicadores, apagados incluidos, con cuantos agricultores distintos los
    reportaron dentro de su vigencia."""
    filas = (await session.execute(text("""
        SELECT i.id, i.id_zona, z.nombre AS zona, i.categoria, i.nombre, i.evento, i.significado, i.nota,
               i.mes_desde, i.mes_hasta, i.umbral_reportes, i.vigencia_dias, i.activo,
               (SELECT count(DISTINCT o.id_usuario) FROM observacion_indicador o
                 WHERE o.id_indicador = i.id
                   AND o.fecha_observada >= CAST(:hoy AS date) - i.vigencia_dias
                   AND o.fecha_observada <= CAST(:hoy AS date)) AS observadores
        FROM indicador_local i JOIN zona_indicadores z ON z.id = i.id_zona
        WHERE CAST(:z AS integer) IS NULL OR i.id_zona = CAST(:z AS integer)
        ORDER BY z.nombre, i.categoria, i.nombre, i.id
    """), {"hoy": hoy, "z": id_zona})).mappings().all()
    return [{**dict(f), "estado": estado_senal(f["observadores"], f["umbral_reportes"])} for f in filas]


async def cambiar_estado(session: AsyncSession, id_indicador: int, activo: bool) -> bool:
    """Enciende o apaga un indicador. False si no existe. Apagarlo lo saca de lo que ven los
    agricultores y deja guardados sus reportes; cambiar lo que significa se hace creando
    otro, para no reinterpretar reportes viejos."""
    fila = (await session.execute(text(
        "UPDATE indicador_local SET activo = :a WHERE id = :i RETURNING id"), {"a": activo, "i": id_indicador})).first()
    await session.commit()
    return fila is not None
