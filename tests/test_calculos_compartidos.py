"""Calculos compartidos: una sola ejecucion para solicitudes iguales (services.calculos_compartidos)."""
import asyncio

import pytest

from services.calculos_compartidos import CalculosCompartidos


class Reloj:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def correr(c):
    return asyncio.run(c)


def test_el_segundo_pedido_usa_el_guardado():
    llamadas = []

    async def calcular():
        llamadas.append(1)
        return "ranking"

    async def prueba():
        c = CalculosCompartidos(reloj=Reloj())
        return await c.obtener("k", calcular), await c.obtener("k", calcular)

    assert correr(prueba()) == ("ranking", "ranking") and len(llamadas) == 1


def test_pedidos_simultaneos_esperan_el_mismo_calculo():
    llamadas = []

    async def calcular():
        llamadas.append(1)
        await asyncio.sleep(0.05)
        return "ranking"

    async def prueba():
        c = CalculosCompartidos(reloj=Reloj())
        return await asyncio.gather(*(c.obtener("k", calcular) for _ in range(5)))

    assert correr(prueba()) == ["ranking"] * 5 and len(llamadas) == 1


def test_claves_distintas_se_calculan_por_separado():
    async def prueba():
        c = CalculosCompartidos(reloj=Reloj())

        async def uno():
            return 1

        async def dos():
            return 2
        return await c.obtener("a", uno), await c.obtener("b", dos)

    assert correr(prueba()) == (1, 2)


def test_vence_pasada_la_vigencia():
    reloj, llamadas = Reloj(), []

    async def calcular():
        llamadas.append(1)
        return len(llamadas)

    async def prueba():
        c = CalculosCompartidos(vigencia_s=10, reloj=reloj)
        a = await c.obtener("k", calcular)
        reloj.t = 9
        b = await c.obtener("k", calcular)
        reloj.t = 11
        d = await c.obtener("k", calcular)
        return a, b, d

    assert correr(prueba()) == (1, 1, 2)


def test_un_calculo_que_falla_no_se_guarda_y_se_reintenta():
    intentos = []

    async def calcular():
        intentos.append(1)
        if len(intentos) == 1:
            raise RuntimeError("se cayo la base")
        return "ok"

    async def prueba():
        c = CalculosCompartidos(reloj=Reloj())
        with pytest.raises(RuntimeError):
            await c.obtener("k", calcular)
        return await c.obtener("k", calcular)

    assert correr(prueba()) == "ok" and len(intentos) == 2


def test_quien_pide_puede_cancelarse_sin_cancelar_el_calculo():
    async def calcular():
        await asyncio.sleep(0.05)
        return "ranking"

    async def prueba():
        c = CalculosCompartidos(reloj=Reloj())
        primero = asyncio.ensure_future(c.obtener("k", calcular))
        await asyncio.sleep(0.01)
        segundo = asyncio.ensure_future(c.obtener("k", calcular))
        await asyncio.sleep(0.01)
        primero.cancel()
        return await segundo

    assert correr(prueba()) == "ranking"


def test_el_tope_descarta_lo_mas_viejo():
    reloj = Reloj()

    async def prueba():
        c = CalculosCompartidos(vigencia_s=1000, maximo=2, reloj=reloj)
        for i, k in enumerate("abc"):
            reloj.t = i

            async def f(i=i):
                return i
            await c.obtener(k, f)
        return sorted(c._listos)

    assert correr(prueba()) == ["b", "c"]


def test_la_precarga_del_catalogo_no_tumba_el_arranque(monkeypatch):
    import main

    class SesionRota:
        async def __aenter__(self):
            raise RuntimeError("base caida")

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(main.base_de_datos, "SessionLocal", lambda: SesionRota())
    correr(main._precargar_catalogo())                       # no lanza
    monkeypatch.setattr(main.base_de_datos, "SessionLocal", None)
    correr(main._precargar_catalogo())                       # sin base configurada tampoco
