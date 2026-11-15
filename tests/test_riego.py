"""Cuando regar: el riego declarado en el balance, la recomendacion y su cableado en seguimiento_cultivo."""
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest
from fastapi import HTTPException, Response

import catalogo_especies as ce
import main
from catalogo_prueba import LAT, clima_prueba, correr, repo_prueba
from motor_estres import ParametrosAgua, balance_agua_fao56, zona_raices_mm
from riego import recomendar_riego

PARAMS = ParametrosAgua(zr_m=0.5, p=0.35, kc_ini=0.5, kc_med=1.15, kc_fin=0.75, ky=1.1)
AWC = 400.0                                            # TAW = 100 mm, RAW = 35 mm con PARAMS
HOY = pd.Timestamp("2025-01-05")


def balance(dias=40, lluvia=0.0, et0=4.0, riegos=()):
    idx = pd.date_range("2025-01-01", periods=dias, freq="D")
    clima = pd.DataFrame({"tmin": 8.0, "tmax": 18.0, "lluvia": float(lluvia)}, index=idx)
    agua = balance_agua_fao56(clima, np.full(dias, et0), pd.Series(1.0, index=idx), AWC, PARAMS, riegos=riegos)
    return clima, agua


def horizontes(idx, observado_hasta, pronostico_hasta):
    return pd.Series(["observado" if d <= observado_hasta else "pronostico" if d <= pronostico_hasta else "estimado"
                      for d in idx], index=idx)


# ---------------------------------------------------------------- zona de raices y riego en el balance
def test_zona_de_raices_reparte_el_agua_y_el_suelo_somero_la_limita():
    assert zona_raices_mm(AWC, PARAMS) == pytest.approx((100.0, 35.0))
    assert zona_raices_mm(AWC, PARAMS, prof_suelo_m=0.25) == pytest.approx((50.0, 17.5))


def test_un_riego_declarado_deja_la_zona_llena_ese_dia():
    _, sin = balance(riegos=())
    _, con = balance(riegos=[date(2025, 1, 15)])
    assert con["agua"].iloc[13] == pytest.approx(sin["agua"].iloc[13])                 # antes del riego, igual
    assert sin["agua"].iloc[14] < 0.7
    assert con["agua"].iloc[14] == pytest.approx(1.0 - 4.0 / 100.0)                    # lleno + ET de ese dia (Kc = 1)
    assert con["agua"].iloc[-1] > sin["agua"].iloc[-1]


def test_un_riego_fuera_de_la_serie_no_cambia_nada():
    _, sin = balance()
    _, con = balance(riegos=[date(2024, 6, 1), date(2026, 6, 1)])
    assert np.allclose(sin["agua"], con["agua"])


# ---------------------------------------------------------------- recomendacion
def recomendar(dias=40, lluvia=0.0, observado_hasta="2025-01-04", pronostico_hasta="2025-01-20", hoy=HOY, **kw):
    clima, agua = balance(dias, lluvia)
    hz = horizontes(clima.index, pd.Timestamp(observado_hasta), pd.Timestamp(pronostico_hasta))
    return recomendar_riego(agua, 100.0, 35.0, hz, hoy, kw.pop("siembra", "2025-01-01"), **kw)


def test_sin_necesidad_si_llueve_lo_que_el_cultivo_gasta():
    r = recomendar(lluvia=6.0)
    assert r["estado"] == "sin_necesidad" and r["fecha_limite"] is None and r["lamina_mm"] is None
    assert r["dias_revisados"] == 15 and r["umbral_pct"] == 65 and r["agua_pct"] >= 90


def test_proximos_dias_da_la_fecha_y_la_lamina():
    r = recomendar()                                       # sin lluvia: gasta 4 mm al dia desde el 1 de enero
    assert r["estado"] == "proximos_dias" and r["fecha_limite"] == "2025-01-09"   # 36 mm >= RAW (35 mm)
    assert r["lamina_mm"] == 36 and r["dias_para_riego"] == 4 and r["agua_pct"] == 80 and r["umbral_pct"] == 65


def test_regar_ya_cuando_hoy_ya_paso_el_umbral():
    r = recomendar(hoy=pd.Timestamp("2025-01-20"), observado_hasta="2025-01-19")
    assert r["estado"] == "regar_ya" and r["dias_para_riego"] == 0 and r["ks_hoy"] < 1.0
    assert r["lamina_mm"] > 35 and r["agua_pct"] < r["umbral_pct"]


def test_lo_estimado_con_el_ano_anterior_no_entra_a_la_recomendacion():
    # el pronostico llega solo hasta el 7: el umbral se cruza el 9, pero eso ya es estimado y no se avisa
    r = recomendar(pronostico_hasta="2025-01-07")
    assert r["estado"] == "sin_necesidad" and r["dias_revisados"] == 2


def test_el_ultimo_riego_se_informa():
    assert recomendar(ultimo_riego=date(2025, 1, 5))["ultimo_riego"] == "2025-01-05"


def test_fuera_del_ciclo_y_sin_sembrar_no_recomiendan_nada():
    assert recomendar(siembra="2025-02-01")["estado"] == "sin_sembrar"
    assert recomendar(madurez="2025-01-03")["estado"] == "fuera_de_ciclo"


def test_sin_clima_para_hoy_no_inventa():
    r = recomendar(observado_hasta="2024-12-31", pronostico_hasta="2025-01-03")
    assert r == {"disponible": False, "motivo": "sin_clima_para_hoy"}


def test_la_recomendacion_se_corta_en_la_madurez():
    r = recomendar(madurez="2025-01-07")                   # el umbral se cruza el 9: el ciclo ya termino
    assert r["estado"] == "sin_necesidad" and r["dias_revisados"] == 2


# ---------------------------------------------------------------- cableado en seguimiento_cultivo
SIEMBRA, HOY_SEG = date(2024, 12, 1), date(2025, 1, 10)


def seguimiento(manejo=(), con_parametros=True, lluvia_factor=0.0, cap_mm=140.0):
    repo = repo_prueba(curada=True)
    if con_parametros:
        repo.parametros_agua_rows = [{"especie": "papa_t", "zr_m": 0.5, "p_agotamiento": 0.35, "kc_ini": 0.5,
                                      "kc_med": 1.15, "kc_fin": 0.75, "ky": 1.1}]
    clima = clima_prueba(lluvia_factor).loc["2024-11-01":"2025-03-31"].copy()
    clima["rh"] = 80.0
    clima["horizonte"] = horizontes(clima.index, pd.Timestamp("2025-01-07"), pd.Timestamp("2025-01-26"))
    return correr(ce.seguimiento_cultivo("papa_t", None, repo, clima, SIEMBRA, LAT, cap_mm, HOY_SEG, manejo=tuple(manejo)))


def test_seguimiento_entrega_la_recomendacion_de_riego():
    r = seguimiento()["riego"]
    assert r["disponible"] and r["estado"] in ("regar_ya", "proximos_dias") and r["suelo_medido"] is True
    assert r["ultimo_riego"] is None and 0 <= r["agua_pct"] <= 100


def test_seguimiento_sin_dato_de_suelo_lo_dice():
    assert seguimiento(cap_mm=None)["riego"]["suelo_medido"] is False


def test_declarar_un_riego_cambia_la_recomendacion():
    sin = seguimiento()["riego"]
    con = seguimiento(manejo=[{"tipo_labor": "riego", "fecha": HOY_SEG}])["riego"]
    assert con["agua_pct"] > sin["agua_pct"] and con["ultimo_riego"] == HOY_SEG.isoformat()
    assert con["estado"] == "proximos_dias" and con["dias_para_riego"] > 0


def test_otras_labores_no_cuentan_como_riego():
    base = seguimiento()["riego"]
    otra = seguimiento(manejo=[{"tipo_labor": "fungicida", "fecha": HOY_SEG}])["riego"]
    assert otra["agua_pct"] == base["agua_pct"] and otra["ultimo_riego"] is None


def test_una_especie_sin_parametros_de_agua_no_recibe_recomendacion():
    assert seguimiento(con_parametros=False)["riego"] == {"disponible": False, "motivo": "especie_sin_parametros_de_agua"}


# ---------------------------------------------------------------- endpoints
AGRICULTOR = {"id": 7, "nombre": "x", "rol": "agricultor"}


class SesionFalsa:
    """Una sesion que responde lo que el test dicta, en el orden en que el endpoint pregunta."""
    def __init__(self, respuestas):
        self.respuestas, self.sentencias, self.confirmado = list(respuestas), [], False

    async def execute(self, sentencia, parametros=None):
        self.sentencias.append((str(sentencia), parametros))
        return self.respuestas.pop(0)

    async def commit(self):
        self.confirmado = True


class Resultado:
    def __init__(self, fila=None, escalar=None, filas=()):
        self._fila, self._escalar, self._filas = fila, escalar, list(filas)

    def mappings(self):
        return self

    def first(self):
        return self._fila

    def scalar_one(self):
        return self._escalar

    def all(self):
        return self._filas


@pytest.fixture
def autorizado(monkeypatch):
    async def parcela(id_parcela, usuario, session):
        return {}
    monkeypatch.setattr(main, "_parcela_autorizada", parcela)
    monkeypatch.setattr(main, "_RIEGOS_POR_USUARIO", main.LimiteIntentos(1000, 60))


def cultivo_de(siembra):
    return Resultado(fila={"id": 3, "id_parcela": 9, "fecha_siembra": siembra})


def declarar(sesion, fecha, usuario=AGRICULTOR):
    respuesta = Response()
    cuerpo = correr(main.declarar_riego(3, main.RiegoDeclarado(fecha=fecha), respuesta, sesion, usuario))
    return respuesta, cuerpo


def test_declarar_riego_nuevo_se_inserta(autorizado):
    hoy = date.today()
    sesion = SesionFalsa([cultivo_de(hoy - timedelta(days=60)), Resultado(fila=None), Resultado(escalar=2), Resultado()])
    _, cuerpo = declarar(sesion, hoy)
    assert cuerpo == {"registrado": True} and sesion.confirmado
    assert "INSERT INTO manejo_predio" in sesion.sentencias[-1][0] and sesion.sentencias[-1][1] == {"c": 3, "f": hoy}


def test_declarar_el_mismo_dia_otra_vez_responde_200_sin_insertar(autorizado):
    hoy = date.today()
    sesion = SesionFalsa([cultivo_de(hoy - timedelta(days=60)), Resultado(fila={"x": 1})])
    respuesta, cuerpo = declarar(sesion, hoy)
    assert respuesta.status_code == 200 and cuerpo == {"registrado": False} and not sesion.confirmado


@pytest.mark.parametrize("dias", [-1, 31])
def test_fecha_futura_o_muy_vieja_es_422(autorizado, dias):
    hoy = date.today()
    sesion = SesionFalsa([cultivo_de(hoy - timedelta(days=90))])
    with pytest.raises(HTTPException) as error:
        declarar(sesion, hoy - timedelta(days=dias))
    assert error.value.status_code == 422 and not sesion.confirmado


def test_no_se_acepta_un_riego_anterior_a_la_siembra(autorizado):
    hoy = date.today()
    sesion = SesionFalsa([cultivo_de(hoy - timedelta(days=5))])
    with pytest.raises(HTTPException) as error:
        declarar(sesion, hoy - timedelta(days=10))
    assert error.value.status_code == 422


def test_cultivo_ajeno_o_inexistente_es_404(autorizado, monkeypatch):
    async def ajena(id_parcela, usuario, session):
        raise HTTPException(404)
    monkeypatch.setattr(main, "_parcela_autorizada", ajena)
    with pytest.raises(HTTPException) as error:
        declarar(SesionFalsa([cultivo_de(date.today())]), date.today())
    assert error.value.status_code == 404
    with pytest.raises(HTTPException) as error:
        declarar(SesionFalsa([Resultado(fila=None)]), date.today())
    assert error.value.status_code == 404


def test_tope_de_riegos_por_cultivo(autorizado):
    hoy = date.today()
    sesion = SesionFalsa([cultivo_de(hoy - timedelta(days=60)), Resultado(fila=None), Resultado(escalar=main.RIEGOS_MAX_POR_CULTIVO)])
    with pytest.raises(HTTPException) as error:
        declarar(sesion, hoy)
    assert error.value.status_code == 409 and not sesion.confirmado


def test_los_riegos_se_acotan_por_usuario(autorizado, monkeypatch):
    monkeypatch.setattr(main, "_RIEGOS_POR_USUARIO", main.LimiteIntentos(1, 60))
    hoy = date.today()
    declarar(SesionFalsa([cultivo_de(hoy - timedelta(days=60)), Resultado(fila={"x": 1})]), hoy)
    with pytest.raises(HTTPException) as error:
        declarar(SesionFalsa([cultivo_de(hoy - timedelta(days=60)), Resultado(fila={"x": 1})]), hoy)
    assert error.value.status_code == 429


def test_anular_riego_borra_solo_ese_dia(autorizado):
    hoy = date.today()
    sesion = SesionFalsa([cultivo_de(hoy), Resultado(filas=[(1,)])])
    cuerpo = correr(main.anular_riego(3, main.RiegoDeclarado(fecha=hoy), sesion, AGRICULTOR))
    assert cuerpo == {"anulado": True} and sesion.confirmado
    sentencia, parametros = sesion.sentencias[-1]
    assert "DELETE FROM manejo_predio" in sentencia and "tipo_labor = 'riego'" in sentencia
    assert parametros == {"c": 3, "f": hoy}
    vacia = SesionFalsa([cultivo_de(hoy), Resultado(filas=[])])
    assert correr(main.anular_riego(3, main.RiegoDeclarado(fecha=hoy), vacia, AGRICULTOR)) == {"anulado": False}


def test_las_rutas_de_riego_exigen_sesion():
    rutas = [r for r in main.app.routes if getattr(r, "path", "").startswith("/api/cultivos/{id_cultivo}/riegos")]
    assert len(rutas) == 2 and all(main.usuario_actual in {d.call for d in r.dependant.dependencies} for r in rutas)
