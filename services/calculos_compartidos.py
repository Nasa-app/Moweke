"""Un calculo caro que muchas solicitudes piden igual (el ranking de especies de una parcela) se hace una vez.

- Si ya se calculo hace menos de `vigencia_s`, se devuelve el guardado.
- Si se esta calculando ahora, las demas solicitudes iguales esperan ese mismo calculo en vez de lanzar otro: un
  agricultor que toca varios filtros seguidos, o varios a la vez, no apila calculos de varios segundos.
- Un calculo que falla no se guarda: la siguiente solicitud lo intenta de nuevo.
- Quien pide no cancela el calculo si se desconecta: otros pueden estar esperandolo.
Vive en la memoria del proceso: al desplegar o reiniciar se vacia."""
from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable, Hashable


class CalculosCompartidos:
    def __init__(self, vigencia_s: float = 900, maximo: int = 64, reloj: Callable[[], float] = time.monotonic):
        self._vigencia, self._maximo, self._reloj = vigencia_s, maximo, reloj
        self._listos: dict[Hashable, tuple[float, object]] = {}
        self._en_curso: dict[Hashable, asyncio.Future] = {}

    async def obtener(self, clave: Hashable, calcular: Callable[[], Awaitable[object]]):
        guardado = self._listos.get(clave)
        if guardado and self._reloj() - guardado[0] < self._vigencia:
            return guardado[1]
        tarea = self._en_curso.get(clave)
        if tarea is None:
            tarea = asyncio.ensure_future(calcular())
            self._en_curso[clave] = tarea
            tarea.add_done_callback(lambda t: self._terminado(clave, t))
        return await asyncio.shield(tarea)

    def _terminado(self, clave: Hashable, tarea: asyncio.Future) -> None:
        self._en_curso.pop(clave, None)
        if tarea.cancelled() or tarea.exception() is not None:
            return
        if len(self._listos) >= self._maximo:
            vencidas = [k for k, (momento, _) in self._listos.items() if self._reloj() - momento >= self._vigencia]
            for k in vencidas or [min(self._listos, key=lambda k: self._listos[k][0])]:
                del self._listos[k]
        self._listos[clave] = (self._reloj(), tarea.result())

    def olvidar(self) -> None:
        self._listos.clear()
