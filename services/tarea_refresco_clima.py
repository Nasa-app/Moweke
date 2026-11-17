"""
Tarea programada -- refresca el clima de los predios sin que nadie tenga que consultar.

Recorre todos los predios y vuelve a correr, por cada uno, solo las fuentes que hagan
falta (services/ingesta_predio.encolar decide cuales: nunca corridas, vencidas,
interrumpidas o con error):

  - predios con un cultivo activo (sembrado en el ultimo ano, o con siembra planeada):
    todas las fuentes, incluidas las diarias (POWER y pronostico de Open-Meteo);
  - el resto: solo las de sitio -- en la practica CR2MET, que vence una vez al mes
    cuando la ventana de doce meses se corre. Sin esto, el dia 1 de cada mes el ranking
    de especies se quedaria sin el mes recien terminado.

Las fuentes que fallan se reintentan al final de la pasada, con espera creciente
(`--espera` segundos, luego el doble, ...) hasta `--intentos` pasadas. AppEEARS se
congestiono 40+ minutos en una sesion real: un reintento inmediato no sirve.

Uso (necesita DATABASE_URL en el entorno):

    python -m services.tarea_refresco_clima [--intentos 3] [--espera 120] [--pausa 1]

Pensada para un cron diario, por ejemplo `0 9 * * *` (09:00 UTC, 06:00 en Chile):
POWER publica con ~3 dias de atraso y Open-Meteo renueva su pronostico varias veces al
dia, asi que una corrida diaria basta. Correrla dos veces seguidas no repite descargas.

Codigo de salida: 0 si todo quedo al dia, 1 si alguna fuente siguio con error tras los
reintentos, 2 si falta configuracion -- para que el cron pueda alertar.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from sqlalchemy import text

from services import db
from services.ingesta_predio import FUENTES, FUENTES_DE_SITIO, encolar, estado_ingesta, ingerir_predio

log = logging.getLogger("tarea_refresco_clima")

DIAS_CULTIVO_ACTIVO = 365


async def _predios() -> list[tuple[int, bool]]:
    """[(id_parcela, tiene_cultivo_activo)]."""
    async with db.SessionLocal() as session:
        filas = (await session.execute(text("""
            SELECT p.id, EXISTS (
                SELECT 1 FROM predio_cultivos c
                WHERE c.id_parcela = p.id
                  AND c.fecha_siembra >= current_date - make_interval(days => CAST(:dias AS integer))
            ) AS activo
            FROM parcela p ORDER BY p.id
        """), {"dias": DIAS_CULTIVO_ACTIVO})).all()
    return [(f.id, f.activo) for f in filas]


async def _refrescar_predio(id_parcela: int, fuentes: tuple[str, ...], reintento: bool) -> tuple[list[str], list[str]]:
    """Corre lo que haga falta y devuelve (fuentes corridas, fuentes que quedaron con error)."""
    async with db.SessionLocal() as session:
        jobs = await encolar(session, id_parcela, fuentes, reintentar_errores_ya=reintento)
    if jobs:
        await ingerir_predio(id_parcela, jobs)
    async with db.SessionLocal() as session:
        estado = await estado_ingesta(session, id_parcela)
    return list(jobs), [f for f in fuentes if estado[f]["con_error"]]


async def refrescar(intentos: int = 3, espera_s: float = 120, pausa_s: float = 1) -> dict:
    """Devuelve {'predios', 'fuentes_corridas', 'con_error': {id_parcela: [fuentes]}}."""
    pendientes = await _predios()
    resumen = {"predios": len(pendientes), "fuentes_corridas": 0, "con_error": {}}
    for intento in range(1, intentos + 1):
        fallidos = []
        for id_parcela, activo in pendientes:
            fuentes = FUENTES if activo else FUENTES_DE_SITIO
            try:
                corridas, con_error = await _refrescar_predio(id_parcela, fuentes, reintento=intento > 1)
            except Exception:
                # Un predio que revienta (base caida a mitad de camino) no detiene a los demas.
                log.exception("predio %s: la pasada %s fallo entera", id_parcela, intento)
                corridas, con_error = [], ["(pasada interrumpida)"]
            resumen["fuentes_corridas"] += len(corridas)
            if corridas or con_error:
                log.info("predio %s (%s): corridas %s, con error %s", id_parcela,
                         "cultivo activo" if activo else "sin cultivo activo", corridas or "ninguna",
                         con_error or "ninguna")
            if con_error:
                fallidos.append((id_parcela, activo))
                resumen["con_error"][id_parcela] = con_error
            else:
                resumen["con_error"].pop(id_parcela, None)
            if corridas:
                await asyncio.sleep(pausa_s)  # no encadenar predios sin respiro contra las APIs externas
        if not fallidos:
            break
        pendientes = fallidos
        if intento < intentos:
            espera = espera_s * 2 ** (intento - 1)
            log.info("%s predio(s) con error; reintento %s de %s en %.0f s", len(fallidos), intento + 1, intentos, espera)
            await asyncio.sleep(espera)
    return resumen


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresca el clima de los predios (tarea para cron).")
    parser.add_argument("--intentos", type=int, default=3, help="pasadas como maximo (default 3)")
    parser.add_argument("--espera", type=float, default=120, help="segundos antes del primer reintento; luego se duplica")
    parser.add_argument("--pausa", type=float, default=1, help="segundos entre un predio y el siguiente")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    if db.SessionLocal is None:
        log.error("DATABASE_URL no esta definida en el entorno")
        return 2
    resumen = asyncio.run(refrescar(max(1, args.intentos), max(0.0, args.espera), max(0.0, args.pausa)))
    log.info("listo: %s predios, %s fuentes corridas, %s predios con error", resumen["predios"],
             resumen["fuentes_corridas"], len(resumen["con_error"]))
    return 1 if resumen["con_error"] else 0


if __name__ == "__main__":
    sys.exit(main())
