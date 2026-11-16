"""Reportes de campo por cultivo: la etapa en que el agricultor ve su cultivo (fenologia_observada)."""
import asyncio
from datetime import date, datetime, timedelta, timezone

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
    monkeypatch.setattr(main, "_REPORTES_POR_USUARIO", main.LimiteIntentos(1000, 60))

    async def autorizado(id_cultivo, usuario, session):
        return {"id": id_cultivo, "id_parcela": 1, "fecha_siembra": HOY - timedelta(days=10)}
    monkeypatch.setattr(main, "_cultivo_autorizado", autorizado)


def reportar(fase, fecha, respuestas, capturado=None):
    sesion, respuesta = SesionFalsa(respuestas), Response()
    datos = main.ReporteDeCampo(fase=fase, fecha=fecha, capturado=capturado)
    return sesion, respuesta, correr(main.declarar_reporte(5, datos, respuesta, sesion, USUARIO))


def test_solo_se_aceptan_las_seis_etapas_del_reporte():
    for fase in ("brote", "hojas", "flor", "fruto", "amarilla", "cosecha"):
        main.ReporteDeCampo(fase=fase, fecha=HOY)
    for fase in ("Hojas", "BBCH09", "x'; DROP TABLE fenologia_observada;--"):
        with pytest.raises(ValidationError):
            main.ReporteDeCampo(fase=fase, fecha=HOY)


def test_guarda_un_reporte_nuevo_con_la_hora_del_telefono_sin_zona():
    capturado = datetime(2026, 11, 16, 21, 30, tzinfo=timezone.utc)
    sesion, _, r = reportar("hojas", HOY, [Resultado(), Resultado(escalar=2), Resultado()], capturado)
    assert r == {"registrado": True} and sesion.confirmado
    sentencia, parametros = sesion.sentencias[-1]
    assert "INSERT INTO fenologia_observada" in sentencia
    assert parametros == {"c": 5, "f": "hojas", "d": HOY, "t": datetime(2026, 11, 16, 21, 30)}


def test_reenviar_el_mismo_reporte_no_lo_duplica():
    sesion, respuesta, r = reportar("flor", HOY, [Resultado(filas=[{"x": 1}])])
    assert r == {"registrado": False} and respuesta.status_code == 200 and not sesion.confirmado


@pytest.mark.parametrize("fecha", [HOY + timedelta(days=2), HOY - timedelta(days=11)])
def test_la_fecha_debe_estar_entre_la_siembra_y_hoy(fecha):
    with pytest.raises(HTTPException) as error:
        reportar("brote", fecha, [])
    assert error.value.status_code == 422


def test_un_dia_de_margen_por_la_zona_horaria_del_telefono():
    reportar("brote", HOY + timedelta(days=1), [Resultado(), Resultado(escalar=0), Resultado()])


def test_hay_un_tope_de_reportes_por_cultivo():
    with pytest.raises(HTTPException) as error:
        reportar("brote", HOY, [Resultado(), Resultado(escalar=main.REPORTES_MAX_POR_CULTIVO)])
    assert error.value.status_code == 409


def test_se_acota_por_usuario(monkeypatch):
    monkeypatch.setattr(main, "_REPORTES_POR_USUARIO", main.LimiteIntentos(1, 60))
    reportar("brote", HOY, [Resultado(), Resultado(escalar=0), Resultado()])
    with pytest.raises(HTTPException) as error:
        reportar("hojas", HOY, [])
    assert error.value.status_code == 429


def test_lista_los_reportes_del_mas_reciente_al_mas_antiguo():
    filas = [{"fase": "flor", "fecha": HOY}, {"fase": "hojas", "fecha": HOY - timedelta(days=3)}]
    sesion = SesionFalsa([Resultado(filas=filas)])
    r = correr(main.listar_reportes(5, sesion, USUARIO))
    assert r == {"reportes": [{"fase": "flor", "fecha": HOY.isoformat()},
                              {"fase": "hojas", "fecha": (HOY - timedelta(days=3)).isoformat()}]}
    assert "ORDER BY fecha_observada DESC" in sesion.sentencias[0][0]
