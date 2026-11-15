"""Indicadores locales: la logica de senales, el contrato con database/ y los endpoints.

Los endpoints se llaman como funciones (sin servidor ni base): las consultas SQL de
services/indicadores_locales.py se reemplazan por dobles, asi que esto prueba la
autorizacion, las validaciones y las respuestas, no el SQL."""
import asyncio
import re
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException, Response

import main

# El modulo que usa main (`services.indicadores_locales`), no una segunda copia importada
# plana: los dobles de abajo tienen que reemplazar lo que main llama de verdad.
il = main.indicadores_locales

RAIZ = Path(__file__).resolve().parent.parent
HOY = date.today()


def correr(corrutina):
    return asyncio.run(corrutina)


# ---------------------------------------------------------------- limpiar_texto
def test_limpiar_texto_normaliza_espacios_y_quita_control():
    assert il.limpiar_texto("  Floración \t del\n ulmo\x00 ") == "Floración del ulmo"


@pytest.mark.parametrize("malo", ["", "   ", "\x00\x07", "<script>alert(1)</script>", "a > b"])
def test_limpiar_texto_rechaza_vacio_y_signos(malo):
    with pytest.raises(ValueError):
        il.limpiar_texto(malo)


# ---------------------------------------------------------------- ventana y estado
@pytest.mark.parametrize("mes, desde, hasta, esperado", [
    (9, 9, 11, True), (11, 9, 11, True), (8, 9, 11, False), (12, 9, 11, False),
    (12, 11, 2, True), (1, 11, 2, True), (2, 11, 2, True), (3, 11, 2, False), (10, 11, 2, False),
    (5, 5, 5, True), (6, 5, 5, False),
])
def test_mes_en_ventana(mes, desde, hasta, esperado):
    assert il.mes_en_ventana(date(2026, mes, 15), desde, hasta) is esperado


@pytest.mark.parametrize("observadores, umbral, esperado", [
    (0, 3, "sin_reportes"), (1, 3, "en_observacion"), (2, 3, "en_observacion"),
    (3, 3, "confirmada"), (9, 3, "confirmada"), (1, 1, "confirmada"),
])
def test_estado_senal(observadores, umbral, esperado):
    assert il.estado_senal(observadores, umbral) == esperado


def test_resumen_solo_cuenta_confirmadas():
    resumen = il.resumen_por_significado([
        {"nombre": "Ulmo", "significado": "helada", "estado": "confirmada"},
        {"nombre": "Zarapito", "significado": "helada", "estado": "confirmada"},
        {"nombre": "Chucao", "significado": "precipitacion_alta", "estado": "en_observacion"},
        {"nombre": "Notro", "significado": "precipitacion_tardia", "estado": "sin_reportes"},
    ])
    assert resumen == {"helada": ["Ulmo", "Zarapito"]}


# ---------------------------------------------------------------- contrato con la base
def _valores_check(sql: str, columna: str) -> set[str]:
    bloque = re.search(rf"{columna}\s+VARCHAR NOT NULL CHECK \({columna} IN\s*\(([^)]*)\)", sql)
    assert bloque, f"no encontre el CHECK de {columna}"
    return set(re.findall(r"'([^']+)'", bloque.group(1)))


@pytest.mark.parametrize("archivo", ["database/schema.sql", "database/migracion_indicadores_locales.sql"])
def test_los_check_de_sql_coinciden_con_el_codigo(archivo):
    sql = (RAIZ / archivo).read_text(encoding="utf-8")
    assert _valores_check(sql, "categoria") == set(il.CATEGORIAS)
    assert _valores_check(sql, "significado") == set(il.SIGNIFICADOS)


# ---------------------------------------------------------------- esquemas del cuerpo
def _indicador(**cambios):
    base = dict(id_zona=1, categoria="floracion", nombre="Ulmo", evento="primera floración",
                significado="precipitacion_tardia", mes_desde=1, mes_hasta=3)
    return main.IndicadorNuevo(**{**base, **cambios})


def test_indicador_limpia_el_texto_libre():
    ind = _indicador(nombre="  Ulmo  ", nota="  en   flor ")
    assert ind.nombre == "Ulmo" and ind.nota == "en flor"
    assert ind.umbral_reportes == 3 and ind.vigencia_dias == 90


@pytest.mark.parametrize("cambios", [
    {"nombre": "<b>Ulmo</b>"}, {"nota": "   "}, {"categoria": "insectos"}, {"significado": "sequia"},
    {"mes_desde": 0}, {"mes_hasta": 13}, {"umbral_reportes": 0}, {"umbral_reportes": 51},
    {"vigencia_dias": 6}, {"vigencia_dias": 366},
])
def test_indicador_rechaza_valores_fuera_de_contrato(cambios):
    with pytest.raises(ValueError):
        _indicador(**cambios)


def test_zona_limpia_el_nombre():
    assert main.ZonaNueva(nombre="  Quemchi  ", perimetro={}).nombre == "Quemchi"
    with pytest.raises(ValueError):
        main.ZonaNueva(nombre="<x>", perimetro={})


# ---------------------------------------------------------------- autorizacion de rutas
def _dependencias(ruta):
    return {d.call for d in ruta.dependant.dependencies}


def test_todas_las_rutas_de_administracion_exigen_admin():
    rutas = [r for r in main.app.routes
             if getattr(r, "path", "").startswith(("/api/admin/zonas-indicadores", "/api/admin/indicadores-locales"))]
    assert len(rutas) == 5
    assert all(main.requerir_admin in _dependencias(r) for r in rutas)


def test_las_rutas_del_agricultor_exigen_sesion():
    rutas = [r for r in main.app.routes
             if getattr(r, "path", "") in ("/api/parcelas/{id_parcela}/indicadores",
                                           "/api/indicadores/{id_indicador}/observaciones")]
    assert len(rutas) == 2
    assert all(main.usuario_actual in _dependencias(r) for r in rutas)


def test_requerir_admin_rechaza_agricultor():
    with pytest.raises(HTTPException) as error:
        correr(main.requerir_admin({"id": 1, "nombre": "x", "rol": "agricultor"}))
    assert error.value.status_code == 403


# ---------------------------------------------------------------- reportar un indicador
AGRICULTOR = {"id": 7, "nombre": "x", "rol": "agricultor"}


@pytest.fixture
def base(monkeypatch):
    """Un indicador de enero a marzo, visible para el usuario, y un registro que cuenta las llamadas."""
    estado = {"indicador": {"id": 5, "mes_desde": 1, "mes_hasta": 3}, "nueva": True, "registros": []}

    async def para_reportar(session, id_indicador, id_usuario):
        return estado["indicador"]

    async def registrar(session, id_indicador, id_usuario, fecha):
        estado["registros"].append((id_indicador, id_usuario, fecha))
        return estado["nueva"]

    monkeypatch.setattr(il, "indicador_para_reportar", para_reportar)
    monkeypatch.setattr(il, "registrar_observacion", registrar)
    monkeypatch.setattr(main, "_OBSERVACIONES_POR_USUARIO", main.LimiteIntentos(1000, 60))
    return estado


def reportar(fecha, usuario=AGRICULTOR):
    respuesta = Response()
    cuerpo = correr(main.reportar_indicador(5, main.ObservacionNueva(fecha_observada=fecha), respuesta, None, usuario))
    return respuesta, cuerpo


def _fecha_en_ventana(dias_atras=0):
    """Una fecha reciente que cae en enero-marzo: la ultima de ese tramo que no es futura."""
    fecha = HOY - timedelta(days=dias_atras)
    while fecha.month not in (1, 2, 3):
        fecha -= timedelta(days=1)
    return fecha


def test_reporte_nuevo_responde_201_y_se_guarda(base):
    fecha = _fecha_en_ventana()
    _, cuerpo = reportar(fecha)
    assert cuerpo == {"registrada": True}
    assert base["registros"] == [(5, 7, fecha)]


def test_reporte_repetido_responde_200_sin_duplicar(base):
    base["nueva"] = False
    respuesta, cuerpo = reportar(_fecha_en_ventana())
    assert respuesta.status_code == 200 and cuerpo == {"registrada": False}


def test_indicador_de_otra_zona_o_apagado_es_404(base):
    base["indicador"] = None
    with pytest.raises(HTTPException) as error:
        reportar(_fecha_en_ventana())
    assert error.value.status_code == 404 and not base["registros"]


@pytest.mark.parametrize("fecha", [HOY + timedelta(days=1), HOY - timedelta(days=il.OBSERVACION_DIAS_ATRAS_MAX + 1)])
def test_fecha_futura_o_muy_vieja_es_422(base, fecha):
    with pytest.raises(HTTPException) as error:
        reportar(fecha)
    assert error.value.status_code == 422 and not base["registros"]


def test_fecha_fuera_de_la_ventana_del_indicador_es_422(base):
    fecha = HOY
    while fecha.month in (1, 2, 3) or HOY - fecha > timedelta(days=il.OBSERVACION_DIAS_ATRAS_MAX):
        fecha -= timedelta(days=1)
    with pytest.raises(HTTPException) as error:
        reportar(fecha)
    assert error.value.status_code == 422 and not base["registros"]


def test_el_reporte_se_acota_por_usuario(base, monkeypatch):
    monkeypatch.setattr(main, "_OBSERVACIONES_POR_USUARIO", main.LimiteIntentos(2, 60))
    fecha = _fecha_en_ventana()
    reportar(fecha)
    reportar(fecha)
    with pytest.raises(HTTPException) as error:
        reportar(fecha)
    assert error.value.status_code == 429
    reportar(fecha, usuario={**AGRICULTOR, "id": 8})   # otro usuario, otra cuenta


# ---------------------------------------------------------------- lectura de senales
def test_indicadores_del_predio_incluye_resumen_y_marca_sin_validar(monkeypatch):
    async def parcela(id_parcela, usuario, session):
        return {}

    async def senales(session, id_parcela, id_usuario, hoy):
        return [{"id": 1, "nombre": "Ulmo", "significado": "helada", "estado": "confirmada"},
                {"id": 2, "nombre": "Chucao", "significado": "precipitacion_alta", "estado": "en_observacion"}]

    monkeypatch.setattr(main, "_parcela_autorizada", parcela)
    monkeypatch.setattr(il, "senales_del_predio", senales)
    cuerpo = correr(main.indicadores_parcela(1, None, AGRICULTOR))
    assert cuerpo["resumen"] == {"helada": ["Ulmo"]} and cuerpo["validado"] is False
    assert [i["id"] for i in cuerpo["indicadores"]] == [1, 2]
