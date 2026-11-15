"""Sesion anonima: la app pide sola una cuenta sin telefono ni contrasena al abrirse."""
import asyncio
import sys
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

import main

auth = sys.modules["services.auth"]        # el modulo que usa main (no una segunda copia importada plana)


def correr(corrutina):
    return asyncio.run(corrutina)


class SesionFalsa:
    def __init__(self, respuestas):
        self.respuestas, self.sentencias, self.confirmado = list(respuestas), [], False

    async def execute(self, sentencia, parametros=None):
        self.sentencias.append((str(sentencia), parametros))
        return self.respuestas.pop(0)

    async def commit(self):
        self.confirmado = True


class Resultado:
    def __init__(self, fila=None):
        self._fila = fila

    def first(self):
        return self._fila

    def mappings(self):
        return self


def pedido(ip="10.0.0.1"):
    return Request({"type": "http", "method": "POST", "path": "/api/auth/anonimo", "headers": [], "client": (ip, 5000)})


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    monkeypatch.setattr(auth, "SECRET_KEY", "secreto-de-prueba")
    monkeypatch.setattr(main, "_ANONIMOS_POR_IP", main.LimiteIntentos(1000, 60))
    monkeypatch.setattr(main, "_ANONIMOS_GLOBAL", main.LimiteIntentos(1000, 60))


def crear(ip="10.0.0.1", id_usuario=41):
    sesion = SesionFalsa([Resultado(SimpleNamespace(id=id_usuario))])
    return sesion, correr(main.sesion_anonima(pedido(ip), sesion))


def test_crea_una_cuenta_sin_telefono_ni_contrasena_y_devuelve_su_token():
    sesion, token = crear(id_usuario=41)
    sentencia, parametros = sesion.sentencias[0]
    assert "INSERT INTO usuarios" in sentencia and sesion.confirmado
    assert "telefono" not in sentencia and "password_hash" not in sentencia and "email" not in sentencia
    assert "'agricultor'" in sentencia and "'admin'" not in sentencia
    assert parametros == main._PUNTO_ANONIMO
    datos = auth.decodificar_token(token.access_token)
    assert datos["sub"] == "41" and datos["rol"] == "agricultor"


def test_el_token_dura_un_ano_porque_no_hay_otra_forma_de_volver_a_entrar():
    _, token = crear()
    exp = datetime.fromtimestamp(auth.decodificar_token(token.access_token)["exp"], timezone.utc)
    dias = (exp - datetime.now(timezone.utc)).days
    assert 360 <= dias <= 365
    # los tokens de login normal siguen durando un dia
    normal = auth.decodificar_token(auth.crear_token(1, "agricultor"))["exp"]
    assert (datetime.fromtimestamp(normal, timezone.utc) - datetime.now(timezone.utc)).days == 0


def test_se_acota_por_ip(monkeypatch):
    monkeypatch.setattr(main, "_ANONIMOS_POR_IP", main.LimiteIntentos(2, 60))
    crear("10.0.0.1")
    crear("10.0.0.1")
    with pytest.raises(HTTPException) as error:
        crear("10.0.0.1")
    assert error.value.status_code == 429 and "Retry-After" in error.value.headers
    crear("10.0.0.2")                                     # otra IP no se ve afectada


def test_se_acota_en_total_aunque_se_reparta_entre_ips(monkeypatch):
    monkeypatch.setattr(main, "_ANONIMOS_GLOBAL", main.LimiteIntentos(2, 60))
    crear("10.0.0.1")
    crear("10.0.0.2")
    with pytest.raises(HTTPException) as error:
        crear("10.0.0.3")
    assert error.value.status_code == 429


def test_una_cuenta_anonima_no_puede_iniciar_sesion_con_telefono_y_contrasena(monkeypatch):
    # no tiene password_hash: ni una contrasena vacia ni cualquier otra sirve
    monkeypatch.setattr(main, "_LOGINS_POR_IP", main.LimiteIntentos(1000, 60))
    monkeypatch.setattr(main, "_LOGINS_POR_CUENTA", main.LimiteIntentos(1000, 60))
    sesion = SesionFalsa([Resultado({"id": 41, "password_hash": None, "rol": "agricultor"})])
    with pytest.raises(HTTPException) as error:
        correr(main.login_agricultor(main.LoginAgricultor(telefono="", password=""), pedido(), sesion))
    assert error.value.status_code == 401


def test_el_rol_sale_de_la_base_y_no_del_token():
    """Un token que dice 'admin' para una cuenta que en la base es agricultor no da acceso de admin."""
    token = auth.crear_token(41, "admin")
    sesion = SesionFalsa([Resultado({"id": 41, "nombre": "Anónimo", "rol": "agricultor"})])
    usuario = correr(main.usuario_actual(token, sesion))
    assert usuario["rol"] == "agricultor"
    with pytest.raises(HTTPException) as error:
        correr(main.requerir_admin(usuario))
    assert error.value.status_code == 403


def test_la_ruta_anonima_no_exige_sesion_y_los_endpoints_de_admin_si():
    ruta = next(r for r in main.app.routes if getattr(r, "path", "") == "/api/auth/anonimo")
    assert main.usuario_actual not in {d.call for d in ruta.dependant.dependencies}
    admin = [r for r in main.app.routes if getattr(r, "path", "").startswith("/api/admin/")]
    assert admin and all(main.requerir_admin in {d.call for d in r.dependant.dependencies} for r in admin)


def test_crear_predios_se_acota_por_ip(monkeypatch):
    """Con cuentas anonimas baratas, el tope por usuario no basta: cada predio dispara descargas externas."""
    monkeypatch.setattr(main, "_PARCELAS_POR_IP", main.LimiteIntentos(2, 60))
    fuera_de_chile = main.ParcelaNueva(lat=10.0, lon=-70.0, hectareas=1.0)     # se rechaza antes de tocar la base
    usuario = {"id": 1, "nombre": "x", "rol": "agricultor"}

    def intentar(ip):
        return correr(main.crear_parcela(fuera_de_chile, SimpleNamespace(), pedido(ip), None, usuario))

    for _ in range(2):
        with pytest.raises(HTTPException) as error:
            intentar("10.0.0.1")
        assert error.value.status_code == 422
    with pytest.raises(HTTPException) as error:
        intentar("10.0.0.1")
    assert error.value.status_code == 429
    with pytest.raises(HTTPException) as error:
        intentar("10.0.0.2")                               # otra IP sigue pudiendo intentar
    assert error.value.status_code == 422
