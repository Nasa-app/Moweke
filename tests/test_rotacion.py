"""Motor de rotacion: reglas duras, busqueda con tope y el plan que compara estrategias para un predio."""
import numpy as np
import pytest
from fastapi import HTTPException

import main
import motor_rotacion as mr
from catalogo_prueba import clima_prueba, correr, repo_prueba, req, sitio_de
from services import plan_rotacion as pr
from test_multianual import historia_sintetica

SUELO = {"drenaje": "well", "salinidad": "none", "profundidad": "deep", "fertilidad": "moderate"}
HISTORIA = historia_sintetica(range(1991, 2026), tmedia=12.0, lluvia_mes=120)
BASE = dict(tb=4, topt=(12, 20), tc=30, letal=-4, lluvia=(300, 500, 1400, 2200), ph=(5.2, 6.0, 7.0, 7.5))


def perfil_de(familia, legum=False, perenne=False, intervalo=1, exigente=False):
    p = dict(familia=familia, legum=legum, exigente=exigente, intervalo=intervalo, perenne=perenne)
    if not perenne:
        p["siembra"] = (10, 15)
    return p


PERFIL = {
    "papa": perfil_de("solanaceas", intervalo=3, exigente=True),
    "tomate": perfil_de("Solanaceae", intervalo=2, exigente=True),
    "haba": perfil_de("fabaceas", legum=True, intervalo=2),
    "trigo": perfil_de("Poaceae", intervalo=1),
    "pradera": perfil_de("pradera", legum=True, perenne=True, intervalo=0),
    "sin_rasgos_x": None,
}
PERFIL.pop("sin_rasgos_x")


def tabla_plana(perdida=0.2, anos=15, **cada):
    """Una tabla de motor_rotacion donde todas las especies rinden igual, salvo las de `cada` {nombre: perdida}."""
    t = {}
    for n, p in PERFIL.items():
        t[n] = dict(viable=True, dur=300 if p["perenne"] else 140, perdidas=np.full(anos, cada.get(n, perdida)),
                    cierra=1.0, p_perdido=0.0, modelado=True)
    return t


# ---------------------------------------------------------------- reglas duras (funciones puras)
@pytest.mark.parametrize("a, b, esperado", [
    ("papa", "tomate", True),        # 'solanaceas' (seed) con 'Solanaceae' (EcoCrop)
    ("papa", "papa", True),
    ("papa", "haba", False),
    ("haba", "trigo", False),
    ("papa", "desconocida", False),  # sin perfil no se juzga
])
def test_par_prohibido(a, b, esperado):
    assert mr.par_prohibido(a, b, PERFIL) is esperado


def test_la_familia_se_compara_sin_tildes_ni_mayusculas():
    perfil = {"a": perfil_de("Solanáceas"), "b": perfil_de("SOLANACEAE")}
    assert mr.par_prohibido("a", "b", perfil)


def test_solanaceas_seguidas_se_detectan_tambien_al_cerrar_el_ciclo():
    assert not mr.sin_familia_seguida(("papa", "tomate", "haba"), PERFIL)      # papa y tomate, una tras otra
    assert not mr.sin_familia_seguida(("tomate", "haba", "papa"), PERFIL)      # papa -> tomate al volver a empezar
    assert mr.sin_familia_seguida(("papa", "haba", "tomate", "trigo"), PERFIL)


def test_historial_no_deja_empezar_con_una_solanacea_tras_una_solanacea():
    assert not mr.cumple_historial(("tomate", "haba", "trigo"), ["trigo", "papa"], PERFIL)
    assert mr.cumple_historial(("haba", "tomate", "trigo"), ["trigo", "papa"], PERFIL)


def test_historial_respeta_el_intervalo_contra_la_siembra_previa_mas_reciente():
    # haba pide 2 temporadas de por medio: sembrada hace 2 temporadas (una de por medio), solo puede volver en la 2a
    previos = ["trigo", "haba", "trigo"]
    assert not mr.cumple_historial(("haba", "trigo", "pradera"), previos, PERFIL)
    assert mr.cumple_historial(("pradera", "haba", "trigo"), previos, PERFIL)
    assert not mr.cumple_historial(("papa", "trigo", "haba"), ["papa"], PERFIL)         # papa pide 3 de por medio


def test_un_previo_sin_perfil_no_se_juzga():
    assert mr.cumple_historial(("papa", "haba", "trigo"), ["algo_sin_perfil"], PERFIL)
    assert mr.cumple_historial(("papa", "haba", "trigo"), [], PERFIL)


def test_inicio_desde_historial_gira_el_ciclo_hasta_que_cumple():
    seq = ("papa", "haba", "trigo")
    assert mr.inicio_desde_historial(seq, ["haba"], PERFIL) == ("trigo", "papa", "haba")
    assert mr.inicio_desde_historial(("papa", "tomate", "haba"), [], PERFIL) == ("papa", "tomate", "haba")
    assert mr.inicio_desde_historial(("papa", "papa"), ["papa"], PERFIL) is None


# ---------------------------------------------------------------- buscar
def buscar(tablas=None, **kw):
    return mr.buscar(tablas or {"reciente": tabla_plana()}, PERFIL, **kw)


def test_buscar_nunca_pone_solanaceas_seguidas_y_cuenta_los_descartes():
    top, info = buscar(top=500)
    assert top and all(mr.sin_familia_seguida(r["seq"], PERFIL) for r in top)
    assert info["familia"] > 0


def test_buscar_gira_el_ciclo_para_no_empezar_con_una_solanacea_tras_otra():
    top, _ = buscar(top=500, previos=("papa",))
    assert top and all(r["seq"][0] not in ("papa", "tomate") for r in top)


def test_buscar_descarta_por_historial_lo_que_ningun_giro_cumple():
    # tres cultivos de intervalo 2 sembrados en el orden a, b, c: el ciclo solo puede seguir en ese mismo orden
    perfil = {n: perfil_de(n, intervalo=2) for n in "abc"}
    tabla = {n: dict(viable=True, dur=100, perdidas=np.full(5, 0.2), cierra=1.0, p_perdido=0.0, modelado=True)
             for n in perfil}
    top, info = mr.buscar({"r": tabla}, perfil, largos=(3,), previos=("a", "b", "c"), top=50)
    assert info["historial"] == 1 and [r["seq"] for r in top] == [("a", "b", "c")]


def test_el_tope_de_especies_recorta_las_peores_y_lo_informa():
    tabla = tabla_plana(papa=0.5, tomate=0.4, trigo=0.3, haba=0.2, pradera=0.1)
    top, info = buscar({"r": tabla}, max_especies=3)
    assert info["viables"] == ["pradera", "haba", "trigo"]                  # las de menor riesgo medio
    assert info["recortadas"] == ["tomate", "papa"]
    assert {n for r in top for n in r["seq"]} <= set(info["viables"])


def test_el_tope_acota_el_producto_cartesiano():
    _, info = buscar(max_especies=2, largos=(5,), top=1)
    assert info["evaluadas"] + info["intervalo"] + info["familia"] + info["historial"] + info["calendario"] <= 2 ** 5


def test_el_peor_escenario_manda():
    buena, mala = tabla_plana(0.1), tabla_plana(0.1, haba=0.9)
    top, _ = buscar({"reciente": buena, "proyectado": mala}, top=500)
    con_haba = next(r for r in top if "haba" in r["seq"])
    assert con_haba["peor_escenario"] == "proyectado"


# ---------------------------------------------------------------- fertilidad
def test_los_pesos_de_fertilidad_baja_suman_uno():
    assert sum(mr.PESOS_FERTILIDAD_BAJA.values()) == pytest.approx(1.0)
    assert sum(mr.PESOS.values()) == pytest.approx(1.0)


def test_el_criterio_de_fertilidad_es_la_fraccion_de_temporadas_que_reponen():
    t = tabla_plana()
    p = lambda seq: mr.puntuar(seq, t, PERFIL, mr.PESOS_FERTILIDAD_BAJA)["fertilidad"]
    assert p(("trigo", "papa", "tomate")) == 0.0
    assert p(("haba", "trigo", "trigo", "papa")) == pytest.approx(0.5)      # 1 de 4: la mitad del credito
    assert p(("haba", "pradera", "trigo")) == 1.0                           # desde la mitad, credito completo
    assert "fertilidad" not in mr.puntuar(("haba", "trigo", "papa"), t, PERFIL, mr.PESOS)


def test_fertilidad_baja_sube_las_rotaciones_con_leguminosa_o_pradera():
    def reponen(top):
        return np.mean([np.mean([PERFIL[n]["legum"] or PERFIL[n]["perenne"] for n in r["seq"]]) for r in top])
    # con un trigo algo mejor que el resto, sin el criterio la rotacion lo repetiria; con fertilidad baja gana la que repone
    t = tabla_plana(trigo=0.05)
    normal = mr.buscar({"r": t}, PERFIL, top=10)[0]
    baja = mr.buscar({"r": t}, PERFIL, top=10, pesos=mr.PESOS_FERTILIDAD_BAJA)[0]
    assert reponen(baja) > reponen(normal)


# ---------------------------------------------------------------- no modelados
def test_un_cultivo_no_modelado_recibe_el_riesgo_medio_y_nunca_cero():
    tabla = {"a": dict(viable=True, modelado=True, perdidas=np.array([0.2, 0.4])),
             "b": dict(viable=True, modelado=False, perdidas=np.zeros(2))}
    assert mr.rellenar_no_modelados(tabla)["b"]["perdidas"].tolist() == pytest.approx([0.2, 0.4])
    tabla["a"]["perdidas"] = np.zeros(2)
    tabla["b"]["perdidas"] = np.zeros(2)
    assert (mr.rellenar_no_modelados(tabla, piso=0.1)["b"]["perdidas"] >= 0.1).all()


def test_sin_ningun_modelado_se_usa_el_valor_por_defecto():
    tabla = {"b": dict(viable=True, modelado=False, perdidas=np.zeros(3))}
    assert mr.rellenar_no_modelados(tabla, por_defecto=0.5)["b"]["perdidas"].tolist() == [0.5] * 3


# ---------------------------------------------------------------- el plan sobre un catalogo en memoria
def anual(nombre, familia, *, legum=False, intervalo=1, ciclo=(100, 140), mes=10, **suelo):
    """(fila de EcoCrop, identidad, rasgos) de una especie anual curada sin simulacion por fase."""
    fila = req(nombre, **BASE, ciclo=ciclo, **suelo)
    ident = {"especie": nombre, "nombre_cientifico": f"{nombre} prueba", "nombres_comunes": nombre,
             "categorias": ["vegetables"], "forma_vida": "herb"}
    rasgos = {"especie": nombre, "fija_nitrogeno": legum, "familia_botanica": familia, "exigente": False,
              "intervalo_rotacion": intervalo, "siembra_mes": mes, "siembra_dia": 15, "perenne": False}
    return fila, ident, rasgos


def repo_plan(*extra, papa=True, pradera=True):
    """papa_t es curada (con simulacion por fase y regla de dano sin validar); el resto, solo EcoCrop. Siempre trae
    una leguminosa, un cereal y una solanacea mas; `pradera` agrega una perenne sin fila de EcoCrop."""
    repo = repo_prueba(curada=papa)
    if papa:
        repo.rasgos_rows[0].update(intervalo_rotacion=3, exigente=True, familia_botanica="Solanaceae")
        repo.reglas_rows[0]["fuente"] = "placeholder_sin_validar"
    base = [anual("tomate_t", "solanaceas", intervalo=2), anual("haba_t", "fabaceas", legum=True, intervalo=2),
            anual("cebada_t", "Poaceae", intervalo=1)]
    for fila, ident, rasgos in [*base, *extra]:
        repo.requisitos_rows.append(fila)
        repo.especie_rows.append(ident)
        repo.rasgos_rows.append(rasgos)
    if pradera:
        repo.rasgos_rows.append({"especie": "pradera_t", "fija_nitrogeno": True, "familia_botanica": "pradera",
                                 "exigente": False, "intervalo_rotacion": 0, "siembra_mes": None,
                                 "siembra_dia": None, "perenne": True})
    return repo


def plan(repo=None, previos=(), suelo=None, historia=HISTORIA, **kw):
    sitio = sitio_de("chiloe", suelo={**SUELO, **(suelo or {})})
    return correr(pr.plan_rotacion(sitio, repo or repo_plan(), historia, -42.5, list(previos), **kw))


def secuencias(p, tipo="rotacion"):
    return [e["secuencia"] for e in p["estrategias"] if e["tipo"] == tipo]


def seguidas(seq, a="papa_t", b="tomate_t"):
    L = len(seq)
    return any({seq[i], seq[(i + 1) % L]} == {a, b} or seq[i] == seq[(i + 1) % L] == a for i in range(L))


def test_el_plan_trae_al_menos_tres_estrategias_con_lo_que_pide_el_contrato():
    p = plan(previos=["cebada_t"])
    assert p["estado"] == "ok" and len(p["estrategias"]) >= 3
    base, *rotaciones = p["estrategias"]
    assert base["tipo"] == "base" and base["secuencia"] == ["cebada_t"] * 3
    for e in p["estrategias"]:
        assert {"puntaje", "peor_escenario", "criterios", "perdida_media", "perdida_ano_dificil",
                "cumple_reglas", "advertencias", "secuencia"} <= set(e)
    assert all(e["cumple_reglas"] for e in rotaciones) and not base["cumple_reglas"]   # repetir viola el intervalo
    assert [e["puntaje"] for e in rotaciones] == sorted((e["puntaje"] for e in rotaciones), reverse=True)
    assert p["aviso"] and "no predice rendimiento" in p["aviso"]


def test_las_estrategias_salen_aunque_el_limite_sea_uno():
    assert len(plan(previos=["cebada_t"], limite=1)["estrategias"]) >= 3
    assert len(plan(limite=1)["estrategias"]) >= 3                                    # sin historial no hay base


def test_papa_seguida_de_otra_solanacea_queda_descartada():
    p = plan(limite=8)
    assert secuencias(p) and not any(seguidas(s) for s in secuencias(p))
    assert p["descartes"]["rotaciones"]["familia"] > 0


def test_una_solanacea_no_puede_seguir_a_la_ultima_siembra_del_predio():
    for ultimo in ("papa_t", "tomate_t"):
        p = plan(previos=["cebada_t", ultimo], limite=8)
        assert secuencias(p) and all(s[0] not in ("papa_t", "tomate_t") for s in secuencias(p))
    base = plan(previos=["tomate_t"])["estrategias"][0]
    assert not base["cumple_reglas"] and any("solanáceas" in a for a in base["advertencias"])


def test_el_intervalo_se_respeta_contra_el_historial():
    p = plan(previos=["haba_t", "cebada_t"], limite=8)        # haba pide 2 temporadas de por medio: ya paso 1
    assert secuencias(p) and all("haba_t" not in s[:1] for s in secuencias(p))


@pytest.mark.parametrize("suelo, campo, causa", [
    ({"drenaje": "poorly"}, dict(drenaje_opt=["well"], drenaje_rango=["well"]), "inundacion"),
    ({"salinidad": "high"}, dict(salinidad_opt="none", salinidad_max="low"), "salinidad"),
    ({"profundidad": "shallow"}, dict(profundidad_opt="deep", profundidad_min="medium"), "profundidad"),
])
def test_el_suelo_declarado_excluye_la_especie_y_se_nombra_la_causa(suelo, campo, causa):
    repo = repo_plan(anual("sensible_t", "Brassicaceae", **campo))
    p = plan(repo, suelo=suelo, limite=8)
    assert {"especie": "sensible_t", "causa": "suelo", "detalle": causa} in p["descartes"]["especies"]
    assert not any("sensible_t" in s for s in secuencias(p))
    fila = next(e for e in p["especies"] if e["especie"] == "sensible_t")
    assert fila["incluida"] is False and fila["motivo_exclusion"]["detalle"] == causa


def test_sin_el_suelo_que_la_excluye_la_especie_entra():
    repo = repo_plan(anual("sensible_t", "Brassicaceae", drenaje_opt=["well"], drenaje_rango=["well"]))
    p = plan(repo, suelo={"drenaje": "well"}, limite=8)
    assert next(e for e in p["especies"] if e["especie"] == "sensible_t")["incluida"]


def test_la_fertilidad_baja_activa_el_criterio_y_sube_las_rotaciones_que_reponen():
    def reponen(p):
        top = p["estrategias"][:]
        return np.mean([np.mean([s in ("haba_t", "pradera_t") for s in e["secuencia"]]) for e in top if e["tipo"] == "rotacion"])
    normal, baja = plan(limite=8), plan(suelo={"fertilidad": "low"}, limite=8)
    assert baja["criterio_fertilidad"] and not normal["criterio_fertilidad"]
    assert all("fertilidad" in e["criterios"] for e in baja["estrategias"] if e["tipo"] == "rotacion")
    assert reponen(baja) >= reponen(normal)
    assert max(e["criterios"]["fertilidad"] for e in baja["estrategias"] if e["tipo"] == "rotacion") == 1.0


def test_el_tope_de_especies_recorta_e_informa():
    extra = [anual(f"cultivo{i}_t", f"Familia{i}", intervalo=1) for i in range(5)]
    p = plan(repo_plan(*extra), limite=8)
    d = p["descartes"]
    assert d["max_especies"] == mr.MAX_ESPECIES and len(d["recortadas"]) > 0
    assert not {n for s in secuencias(p) for n in s} & set(d["recortadas"])


def test_las_especies_sin_simulacion_salen_marcadas_y_nunca_con_riesgo_cero():
    p = plan(previos=["cebada_t"], limite=8)
    assert {"tomate_t", "haba_t", "cebada_t", "pradera_t"} <= set(p["no_modeladas"]) and "papa_t" not in p["no_modeladas"]
    modelada = {e["especie"]: e for e in p["especies"]}
    assert modelada["papa_t"]["modelada"] and not modelada["cebada_t"]["modelada"]
    assert modelada["papa_t"]["reglas_placeholder"] and not modelada["cebada_t"]["reglas_placeholder"]
    sin_papa = [e for e in p["estrategias"] if "papa_t" not in e["secuencia"]]
    assert sin_papa and all(e["perdida_media"] > 0 and e["perdida_ano_dificil"] > 0 for e in sin_papa)
    assert any("valor neutro" in a for e in sin_papa for a in e["advertencias"])


def test_el_relleno_de_un_no_modelado_tiene_piso_aunque_las_modeladas_no_pierdan_nada():
    datos = correr(pr.multianual.perdidas_anuales(
        sitio_de("chiloe", suelo=SUELO), repo_plan(), HISTORIA, -42.5, ["papa_t", "cebada_t"]))
    perfiles = {"papa_t": PERFIL["papa"], "cebada_t": PERFIL["trigo"]}
    esc = datos["escenarios"]["reciente"]
    esc["puntaje"][:, 0] = 1.0                                           # la unica modelada, sin una sola perdida
    t = pr.tabla_de_escenario(esc, {"papa_t": 0, "cebada_t": 1}, {"papa_t": True, "cebada_t": False}, perfiles,
                              {"cebada_t": 120.0})
    assert t["papa_t"]["modelado"] and not t["cebada_t"]["modelado"]
    assert (t["cebada_t"]["perdidas"] >= pr.PISO_RIESGO_NO_MODELADO).all()


def test_el_ciclo_de_la_especie_simulada_viene_de_la_simulacion():
    datos = correr(pr.multianual.perdidas_anuales(
        sitio_de("chiloe", suelo=SUELO), repo_plan(), HISTORIA, -42.5, ["papa_t", "cebada_t", "no_existe"]))
    assert datos["anios"] == list(range(2011, 2026)) and set(datos["escenarios"]) == {"reciente", "proyectado"}
    assert datos["especies"]["papa_t"]["simulada"] and not datos["especies"]["cebada_t"]["simulada"]
    assert datos["especies"]["no_existe"]["indice"] is None
    for esc in datos["escenarios"].values():
        assert esc["puntaje"].shape == (15, 3) == esc["ciclo_dias"].shape
        assert np.isnan(esc["puntaje"][:, 2]).all() and np.isnan(esc["ciclo_dias"][:, 1]).all()
    ciclo = datos["escenarios"]["reciente"]["ciclo_dias"][:, 0]
    assert np.isfinite(ciclo).any() and (ciclo[np.isfinite(ciclo)] > 0).all()


def test_sin_historia_suficiente_no_hay_plan():
    p = plan(historia=historia_sintetica(range(2010, 2026)))               # 16 anos: faltan 7
    assert p["estado"] == "historia_insuficiente" and p["estrategias"] == []
    assert p["vacios"][0]["codigo"] == "historia_insuficiente"
    assert plan(historia={})["estado"] == "historia_insuficiente"


def test_los_vacios_de_informacion_se_listan():
    p = plan(repo_plan(), previos=["algo_sin_perfil"], suelo={"fertilidad": None, "profundidad": None})
    codigos = {v["codigo"] for v in p["vacios"]}
    assert {"cultivos_previos_sin_perfil", "fertilidad_sin_declarar", "suelo_sin_declarar"} <= codigos
    assert "historial_vacio" in {v["codigo"] for v in plan()["vacios"]}
    assert plan(previos=["algo_sin_perfil"])["estrategias"][0]["tipo"] == "rotacion"     # sin base: no hay perfil


def test_con_pocas_especies_lo_dice():
    repo = repo_plan(papa=False, pradera=False)
    for lista in (repo.rasgos_rows, repo.requisitos_rows, repo.especie_rows):
        lista[:] = [r for r in lista if r["especie"] not in ("haba_t", "cebada_t")]
    p = plan(repo)
    assert "pocas_especies" in {v["codigo"] for v in p["vacios"]}


def test_el_plan_no_cambia_el_ranking_multianual():
    from services import multianual as ma
    repo = repo_plan()
    antes, _ = correr(ma.ranking_multianual(sitio_de("chiloe", suelo=SUELO), repo, HISTORIA, None, -42.5))
    plan(repo)
    despues, _ = correr(ma.ranking_multianual(sitio_de("chiloe", suelo=SUELO), repo, HISTORIA, None, -42.5))
    assert antes and [(r["especie"], r["puntaje"]) for r in antes] == [(r["especie"], r["puntaje"]) for r in despues]


# ---------------------------------------------------------------- el endpoint (funcion llamada con una sesion falsa)
class Resultado:
    def __init__(self, fila=None, filas=()):
        self._fila, self._filas = fila, list(filas)

    def mappings(self):
        return self

    def first(self):
        return self._fila

    def all(self):
        return self._filas


class SesionFalsa:
    def __init__(self, respuestas=()):
        self.respuestas, self.sentencias = list(respuestas), []

    async def execute(self, sentencia, parametros=None):
        self.sentencias.append((str(sentencia), parametros))
        return self.respuestas.pop(0)


AGRICULTOR = {"id": 1, "rol": "agricultor"}


def sitio_leido(clima=True):
    return {"altitud_dem_m": 100.0, "altitud_celda_m": 100.0, "clima": clima_prueba() if clima else clima_prueba().iloc[0:0],
            "arcilla_pct": 25.0, "arena_pct": 40.0, "ph": 5.5, "ghi_mensual": [5.0] * 12, "awc_mm": 120.0,
            "periodo_clima": None}


@pytest.fixture
def api(monkeypatch):
    estado = {"historia": HISTORIA, "sitio": sitio_leido()}

    async def parcela(id_parcela, usuario, session):
        return {"id": id_parcela, "altitud_msnm": 100.0, "lat": -42.5, "suelo": dict(SUELO)}

    async def leer_sitio(session, id_parcela):
        return estado["sitio"]

    async def leer_historia(session, id_parcela):
        return estado["historia"]

    async def estado_ingesta(session, id_parcela):
        return {}

    monkeypatch.setattr(main, "_parcela_autorizada", parcela)
    monkeypatch.setattr(main, "leer_sitio", leer_sitio)
    monkeypatch.setattr(main, "leer_historia", leer_historia)
    monkeypatch.setattr(main.ingesta_predio, "estado_ingesta", estado_ingesta)
    monkeypatch.setattr(main, "RepositorioPostgres", lambda session: repo_plan())
    monkeypatch.setattr(main, "_ALMACEN_CATALOGO", {})
    monkeypatch.setattr(main, "_ROTACION_POR_USUARIO", main.LimiteIntentos(1000, 60))
    return estado


def comparar(sesion=None, usuario=AGRICULTOR, **kw):
    kw = {"riego": False, "escenario": "observado", "largo_max": 5, "limite": 5, **kw}
    sesion = sesion or SesionFalsa([Resultado(filas=[{"especie": "cebada_t"}])])
    return correr(main.comparar_rotaciones(7, session=sesion, usuario=usuario, **kw)), sesion


def test_el_endpoint_responde_con_las_estrategias(api):
    cuerpo, sesion = comparar()
    assert cuerpo["parcela"] == 7 and cuerpo["estado"] == "ok" and cuerpo["cultivos_previos"] == ["cebada_t"]
    assert len(cuerpo["estrategias"]) >= 3 and cuerpo["estrategias"][0]["tipo"] == "base"
    assert cuerpo["aviso"] and cuerpo["escenario"] == "observado"


def test_los_cultivos_previos_llegan_del_mas_antiguo_al_mas_reciente_y_la_consulta_va_parametrizada(api):
    sesion = SesionFalsa([Resultado(filas=[{"especie": "tomate_t"}, {"especie": "haba_t"}, {"especie": "cebada_t"}])])
    cuerpo, _ = comparar(sesion)
    assert cuerpo["cultivos_previos"] == ["cebada_t", "haba_t", "tomate_t"]       # la consulta trae lo mas nuevo primero
    sql, parametros = sesion.sentencias[0]
    assert "predio_cultivos" in sql and ":p" in sql and ":n" in sql and "ORDER BY fecha_siembra" in sql
    assert parametros == {"p": 7, "n": pr.MAX_PREVIOS}


def test_una_parcela_ajena_responde_404_sin_calcular_nada(monkeypatch):
    sesion = SesionFalsa([Resultado(fila={"id": 7, "id_usuario": 99, "rol": "x"})])
    with pytest.raises(HTTPException) as e:
        correr(main.comparar_rotaciones(7, riego=False, escenario="observado", largo_max=5, limite=5,
                                        session=sesion, usuario=AGRICULTOR))
    assert e.value.status_code == 404 and len(sesion.sentencias) == 1


def test_sin_clima_del_predio_responde_409(api):
    api["sitio"] = sitio_leido(clima=False)
    with pytest.raises(HTTPException) as e:
        comparar()
    assert e.value.status_code == 409 and "estado_ingesta" in e.value.detail


def test_sin_historia_suficiente_responde_409(api):
    api["historia"] = historia_sintetica(range(2015, 2026))
    with pytest.raises(HTTPException) as e:
        comparar()
    assert e.value.status_code == 409 and e.value.detail["estado"] == "historia_insuficiente"


def test_el_endpoint_se_frena_por_usuario(api, monkeypatch):
    monkeypatch.setattr(main, "_ROTACION_POR_USUARIO", main.LimiteIntentos(1, 60))
    comparar()
    with pytest.raises(HTTPException) as e:
        comparar()
    assert e.value.status_code == 429
    comparar(usuario={"id": 2, "rol": "agricultor"})


def test_los_parametros_estan_acotados_en_el_contrato_de_la_api():
    ruta = main.app.openapi()["paths"]["/api/parcelas/{id_parcela}/rotacion/comparar"]["get"]
    p = {x["name"]: x["schema"] for x in ruta["parameters"]}
    assert (p["largo_max"]["minimum"], p["largo_max"]["maximum"]) == (3, 5)
    assert (p["limite"]["minimum"], p["limite"]["maximum"]) == (1, 8)
    assert p["escenario"]["enum"] == ["observado", "moderado", "fuerte"] and p["riego"]["type"] == "boolean"
    assert set(p) == {"id_parcela", "riego", "escenario", "largo_max", "limite"}      # ninguna entrada libre
    assert ruta.get("security"), "el endpoint exige sesion"


def test_el_escenario_de_calentamiento_llega_al_plan(api, monkeypatch):
    vistos = []
    original = main.plan_rotacion.plan_rotacion

    async def espia(*a, **kw):
        vistos.append(kw["calentamiento_c_por_decada"])
        return await original(*a, **kw)
    monkeypatch.setattr(main.plan_rotacion, "plan_rotacion", espia)
    comparar(escenario="fuerte")
    assert vistos == [main.ESCENARIOS_CALENTAMIENTO["fuerte"]]
