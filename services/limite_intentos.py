"""
Limite de intentos por clave -- ventana deslizante en memoria, sin dependencias.

Para los endpoints que se pueden llamar sin token (registro y login): acota cuantas
veces una misma clave (una IP, un telefono) puede intentar dentro de una ventana.

Limitaciones reales:
  - Vive en la memoria del proceso: se borra con cada despliegue o reinicio y no se
    comparte entre procesos. Con mas de una replica, cada una cuenta por separado y el
    limite efectivo se multiplica por el numero de replicas.
  - No distingue un intento fallido de uno correcto: cuenta todos.
"""
from __future__ import annotations

import time
from collections import deque

# Tope de claves recordadas por limite. Al llegar, primero se sueltan las claves cuya
# ventana ya paso; si aun asi no hay espacio se olvida todo: ante una inundacion de
# claves distintas se prefiere perder la cuenta a crecer sin limite.
CLAVES_MAX = 20_000


class LimiteIntentos:
    def __init__(self, maximo: int, ventana_s: float, reloj=time.monotonic):
        self._maximo, self._ventana, self._reloj = maximo, ventana_s, reloj
        self._marcas: dict[str, deque[float]] = {}

    def registrar(self, clave: str) -> float | None:
        """Anota un intento de `clave`. Devuelve None si cabe en la ventana, o los
        segundos que faltan para que se permita el siguiente (ese intento no se anota)."""
        ahora = self._reloj()
        marcas = self._marcas.get(clave)
        if marcas is None:
            if len(self._marcas) >= CLAVES_MAX:
                self._soltar_vencidas(ahora)
            marcas = self._marcas[clave] = deque()
        while marcas and marcas[0] <= ahora - self._ventana:
            marcas.popleft()
        if len(marcas) >= self._maximo:
            return marcas[0] + self._ventana - ahora
        marcas.append(ahora)
        return None

    def _soltar_vencidas(self, ahora: float) -> None:
        vencidas = [c for c, m in self._marcas.items() if not m or m[-1] <= ahora - self._ventana]
        for clave in vencidas:
            del self._marcas[clave]
        if len(self._marcas) >= CLAVES_MAX:
            self._marcas.clear()
