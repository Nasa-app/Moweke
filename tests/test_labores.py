"""Registro del cultivo: labores anotadas (riego, fertilizacion, pesticida, fungicida) en manejo_predio."""
import asyncio
from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.responses import Response

import main


def correr(corrutina):
    return asyncio.run(corrutina)


class Resultado:
    def __init__(self, filas=None, escalar=None):
        self._filas, self._escalar = filas or [], escalar

    def first(self):
        return self._filas[0] if self._filas else None

    def all(self):
        return self._filas

    def mappings(self):
        return self

    def scalar_one(self):
        return self._escalar


class SesionFalsa:
    def __init__(self, respuestas):
        self.respuestas, self.sentencias, self.confirmado = list(respuestas), [], False

    async def execute(self, sentencia, parametros=None):
        self.sentencias.append((str(sentencia), parametros))
        return self.respuestas.pop(0)

    async def commit(self):
        self.confirmado = True


HOY = date.today()
USUARIO = {"id": 7, "rol": "agricultor"}


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    monkeypatch.setattr(main, "_RIEGOS_POR_USUARIO", main.LimiteIntentos(1000, 60))

    async def autorizado(id_cultivo, usuario, session):
        return {"id": id_cultivo, "id_parcela": 1, "fecha_siembra": HOY - timedelta(days=10)}
    monkeypatch.setattr(main, "_cultivo_autorizado", autorizado)


def declarar(tipo, fecha, respuestas):
    sesion = SesionFalsa(respuestas)
    respuesta = Response()
    resultado = correr(main.declarar_labor(5, main.LaborDeclarada(tipo=tipo, fecha=fecha), respuesta, sesion, USUARIO))
    return sesion, respuesta, resultado


def test_solo_se_anotan_las_cuatro_labores_del_registro():
    for tipo in ("riego", "fertilizacion", "pesticida", "fungicida"):
        main.LaborDeclarada(tipo=tipo, fecha=HOY)
    for tipo in ("aporque", "drenaje", "x'; DROP TABLE manejo_predio;--"):
        with pytest.raises(ValidationError):
            main.LaborDeclarada(tipo=tipo, fecha=HOY)


def test_anota_una_labor_nueva():
    sesion, _, r = declarar("fertilizacion", HOY, [Resultado(), Resultado(escalar=3), Resultado()])
    assert r == {"registrado": True} and sesion.confirmado
    sentencia, parametros = sesion.sentencias[-1]
    assert "INSERT INTO manejo_predio" in sentencia and parametros == {"c": 5, "t": "fertilizacion", "f": HOY}


def test_la_misma_labor_el_mismo_dia_no_se_duplica():
    sesion, respuesta, r = declarar("pesticida", HOY, [Resultado(filas=[{"x": 1}])])
    assert r == {"registrado": False} and respuesta.status_code == 200 and not sesion.confirmado


def test_otra_labor_el_mismo_dia_si_se_anota():
    # la consulta de duplicado filtra por tipo: fertilizar y regar el mismo dia son dos anotaciones
    sesion, _, r = declarar("riego", HOY, [Resultado(), Resultado(escalar=1), Resultado()])
    assert r["registrado"] is True and "tipo_labor = :t" in sesion.sentencias[0][0]


@pytest.mark.parametrize("fecha", [HOY + timedelta(days=1), HOY - timedelta(days=11)])
def test_la_fecha_debe_estar_entre_la_siembra_y_hoy(fecha):
    with pytest.raises(HTTPException) as error:
        declarar("fungicida", fecha, [])
    assert error.value.status_code == 422


def test_hay_un_tope_de_labores_por_cultivo():
    with pytest.raises(HTTPException) as error:
        declarar("riego", HOY, [Resultado(), Resultado(escalar=main.LABORES_MAX_POR_CULTIVO)])
    assert error.value.status_code == 409


def test_lista_el_cultivo_y_las_labores_de_la_mas_reciente_a_la_mas_antigua():
    cultivo = {"id": 5, "id_parcela": 1, "especie": "papa", "variedad_local": None, "fecha_siembra": HOY - timedelta(days=10)}
    labores = [{"tipo": "fungicida", "fecha": HOY}, {"tipo": "riego", "fecha": HOY - timedelta(days=2)}]
    sesion = SesionFalsa([Resultado(filas=[cultivo]), Resultado(filas=labores)])
    r = correr(main.listar_labores(5, sesion, USUARIO))
    assert r["cultivo"]["especie"] == "papa" and r["cultivo"]["fecha_siembra"] == (HOY - timedelta(days=10)).isoformat()
    assert r["labores"] == [{"tipo": "fungicida", "fecha": HOY.isoformat()},
                            {"tipo": "riego", "fecha": (HOY - timedelta(days=2)).isoformat()}]
    assert "ORDER BY fecha DESC" in sesion.sentencias[1][0]


def test_anular_borra_solo_esa_labor_ese_dia():
    sesion = SesionFalsa([Resultado(filas=[{"id": 1}])])
    r = correr(main.anular_labor(5, main.LaborDeclarada(tipo="pesticida", fecha=HOY), sesion, USUARIO))
    assert r == {"anulado": True}
    sentencia, parametros = sesion.sentencias[0]
    assert "DELETE FROM manejo_predio" in sentencia and parametros == {"c": 5, "t": "pesticida", "f": HOY}
