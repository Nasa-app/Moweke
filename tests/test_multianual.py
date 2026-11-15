"""Idoneidad multianual (services/multianual.py): puntaje vectorizado, periodos, tendencia y categorias."""
import numpy as np
import pandas as pd
import pytest

import catalogo_especies as ce
from catalogo_prueba import LUZ
from services import multianual as ma

COLUMNAS = ("tb", "t_optima", "tc", "t_opt_min", "t_opt_max", "temperatura_letal", "lluvia_anual_min",
            "lluvia_anual_opt_min", "lluvia_anual_opt_max", "lluvia_anual_max", "ph_suelo_min", "ph_opt_min",
            "ph_opt_max", "ph_suelo_max", "luz_min", "luz_opt_min", "luz_opt_max", "luz_max", "ciclo_min_dias",
            "ciclo_max_dias", "altitud_max_m", "textura_opt", "textura_rango", "drenaje_opt", "drenaje_rango",
            "salinidad_opt", "salinidad_max", "profundidad_opt", "profundidad_min", "fertilidad_opt", "fertilidad_min")
CATEGORIAS_LUZ = [f["categoria"] for f in LUZ]


def especie_al_azar(rng, i):
    """Una fila de requisitos con umbrales ordenados y huecos al azar (EcoCrop no los trae todos)."""
    tb = rng.uniform(-2, 12)
    t1 = tb + rng.uniform(2, 8)
    t2 = t1 + rng.uniform(1, 8)
    tc = t2 + rng.uniform(3, 12)
    ll = np.sort(rng.uniform(100, 3000, 4))
    ph = np.sort(rng.uniform(4, 9, 4))
    fila = dict.fromkeys(COLUMNAS)
    fila.update(especie=f"e{i}", variedad_local=None, tb=tb, t_opt_min=t1, t_opt_max=t2, t_optima=(t1 + t2) / 2, tc=tc,
                temperatura_letal=rng.uniform(-8, 6), lluvia_anual_min=ll[0], lluvia_anual_opt_min=ll[1],
                lluvia_anual_opt_max=ll[2], lluvia_anual_max=ll[3], ph_suelo_min=ph[0], ph_opt_min=ph[1],
                ph_opt_max=ph[2], ph_suelo_max=ph[3], altitud_max_m=int(rng.uniform(500, 4000)),
                luz_min=rng.choice(CATEGORIAS_LUZ), luz_opt_min=rng.choice(CATEGORIAS_LUZ),
                luz_opt_max=rng.choice(CATEGORIAS_LUZ), luz_max=rng.choice(CATEGORIAS_LUZ),
                ciclo_min_dias=int(rng.uniform(40, 330)), ciclo_max_dias=int(rng.uniform(40, 400)),
                textura_opt=["medium"], textura_rango=["light", "medium", "heavy"],
                drenaje_opt=["well"], drenaje_rango=["well", "moderate"], salinidad_opt="none", salinidad_max="low",
                profundidad_opt="deep", profundidad_min="shallow", fertilidad_opt="high", fertilidad_min="low")
    for campo in COLUMNAS:                                  # huecos al azar, salvo lo que define la especie
        if campo not in ("especie",) and rng.random() < 0.15:
            fila[campo] = None
    if rng.random() < 0.1:
        fila["ciclo_min_dias"] = fila["ciclo_max_dias"] = None
    if rng.random() < 0.1:
        fila.update(tb=None, t_opt_min=None, t_opt_max=None, t_optima=None, tc=None)
    return fila


def sitio_al_azar(rng):
    base = rng.uniform(0, 20)
    amp = rng.uniform(1, 10)
    tmedia = [float(base + amp * np.cos(2 * np.pi * (m - 0.5) / 12 - np.pi)) for m in range(12)]
    sitio = {"normales": {"tmedia": tmedia, "tmin_extrema": [t - rng.uniform(2, 12) for t in tmedia],
                          "lluvia": [float(x) for x in rng.uniform(0, 400, 12)]},
             "ph": float(rng.uniform(4, 9)) if rng.random() > 0.2 else None,
             "altitud_m": float(rng.uniform(0, 4500)) if rng.random() > 0.2 else None,
             "ghi_mensual": [float(x) for x in rng.uniform(1, 8, 12)] if rng.random() > 0.2 else None,
             "textura": "medium" if rng.random() > 0.3 else None}
    if rng.random() > 0.3:
        sitio["suelo"] = {"drenaje": str(rng.choice(["well", "moderate", "poor"])),
                          "salinidad": str(rng.choice(["none", "low", "high"])),
                          "profundidad": str(rng.choice(["shallow", "medium", "deep"])),
                          "fertilidad": str(rng.choice(["low", "high"]))}
    for variable in ("tmin_extrema", "lluvia"):
        if rng.random() < 0.15:
            sitio["normales"][variable] = None
    if rng.random() < 0.1:
        sitio["normales"]["tmedia"] = None
    return sitio


@pytest.mark.parametrize("riego", [False, True])
def test_el_puntaje_vectorizado_es_igual_al_de_cada_especie(riego):
    rng = np.random.default_rng(42)
    requisitos = [especie_al_azar(rng, i) for i in range(150)]
    cat = ma.CatalogoVectorial(requisitos, LUZ)
    comparados = 0
    for _ in range(40):
        sitio = sitio_al_azar(rng)
        limite, puntaje = cat.calcular_matriz(sitio["normales"], cat.factores_fijos(sitio), sitio["ghi_mensual"], riego)
        for i, req in enumerate(requisitos):
            esperado = ce.puntuar_especie(req, sitio, LUZ, riego)
            if esperado["puntaje"] is None:
                assert np.isnan(puntaje[i]) and np.isnan(limite[i]), (req["especie"], sitio)
            else:
                assert puntaje[i] == pytest.approx(esperado["puntaje"], abs=1.5e-3), (req["especie"], sitio)
                assert (limite[i] > 0) == esperado["apta"]
                comparados += 1
    assert comparados > 2000


def test_theil_sen_ignora_los_valores_extremos():
    assert ma.theil_sen([1, 2, 3, 4, 5], [2, 4, 6, 8, 10]) == pytest.approx(2.0)
    assert ma.theil_sen([1, 2, 3, 4, 5, 6, 7], [1, 1, 1, 1, 1, 1, 90]) == 0.0
    assert ma.theil_sen([1], [1]) == 0.0


def historia_sintetica(anios, calentamiento=0.0, lluvia_mes=100.0, tmedia=12.0, amp=5.0, sd=0.0, seed=0):
    rng = np.random.default_rng(seed)
    historia = {}
    for k, anio in enumerate(anios):
        idx = pd.date_range(f"{anio}-01-01", f"{anio}-12-31", freq="D")
        t = tmedia + calentamiento * k + rng.normal(0, sd) - amp * np.cos(2 * np.pi * (idx.day_of_year - 15) / 365.25)
        historia[anio] = pd.DataFrame({"tmin": t - 4, "tmax": t + 4, "lluvia": lluvia_mes * 12 / len(idx)}, index=idx)
    return historia


def test_la_tendencia_recupera_el_calentamiento_y_se_acota():
    h = historia_sintetica(range(1991, 2026), calentamiento=0.03)
    t = ma.tendencia_clima(h)
    assert t["temp_c_por_anio"] == pytest.approx(0.03, abs=1e-3) and t["anios"] == 35
    loco = ma.tendencia_clima(historia_sintetica(range(1991, 2026), calentamiento=0.5))
    assert loco["temp_c_por_anio"] == ma.LIMITE_TEMP_C_POR_ANIO[1]
    assert loco["temp_c_por_decada_observada"] == pytest.approx(5.0, abs=0.05)         # lo observado se informa sin acotar


def test_un_enfriamiento_observado_no_se_proyecta_pero_se_informa():
    t = ma.tendencia_clima(historia_sintetica(range(1991, 2026), calentamiento=-0.03))
    assert t["temp_c_por_anio"] == 0.0 and t["temp_c_por_decada_observada"] == pytest.approx(-0.3, abs=0.01)


def test_periodos_reciente_son_los_ultimos_anios_completos():
    reciente, historico = ma.periodos(historia_sintetica(range(1991, 2026)))
    assert reciente == list(range(2011, 2026)) and historico == list(range(1991, 2011))


def test_proyectar_suma_la_tendencia_por_los_anos_que_faltan_y_acota_la_lluvia():
    h = historia_sintetica([2025], lluvia_mes=100.0)[2025]
    t = {"temp_c_por_anio": 0.04, "lluvia_rel_por_anio": -0.05}
    p = ma.proyectar(h, 2025, t, 2040)
    assert (p["tmax"] - h["tmax"]).round(6).eq(0.6).all()
    assert p["lluvia"].sum() == pytest.approx(h["lluvia"].sum() * ma.LIMITE_FACTOR_LLUVIA[0])     # -75 % se acota a -40 %
    assert ma.proyectar(h, 2045, t, 2040)["tmax"].equals(h["tmax"])                                  # un ano pasado el horizonte no se mueve


def periodo(tipico, dificil):
    return {"tipico": tipico, "dificil": dificil}


def test_categorias_de_clima():
    m = ce.PUNTAJE_MINIMO_APTA
    bien, mal = periodo(0.8, m + 0.3), periodo(0.1, m - 0.15)        # lejos del minimo, de un lado y del otro
    assert ma.categoria_clima(bien, bien, bien) == "tradicional"
    assert ma.categoria_clima(mal, bien, bien) == "emergente"
    assert ma.categoria_clima(mal, mal, bien) == "emergente"          # todavia no es apta, pero lo sera
    assert ma.categoria_clima(bien, bien, mal) == "en_riesgo"
    assert ma.categoria_clima(mal, bien, mal) == "en_riesgo"          # apta ahora, ni antes ni a futuro
    assert ma.categoria_clima(bien, mal, mal) == "en_riesgo"          # lo era y ya no
    assert ma.categoria_clima(mal, mal, mal) is None


def test_un_cambio_chico_no_hace_nueva_ni_pone_en_riesgo_a_una_especie():
    m = ce.PUNTAJE_MINIMO_APTA
    # el ano dificil cruza el minimo, pero la compatibilidad tipica casi no se mueve
    assert ma.categoria_clima(periodo(0.35, m - 0.15), periodo(0.35, m + 0.1), periodo(0.38, m + 0.2)) == "tradicional"
    assert ma.categoria_clima(periodo(0.35, m + 0.1), periodo(0.35, m + 0.05), periodo(0.35, m - 0.02)) == "tradicional"
    assert ma.categoria_clima(periodo(0.35, m + 0.1), periodo(0.35, m - 0.01), periodo(0.35, m - 0.03)) is None
    assert ma.categoria_clima(periodo(None, None), periodo(None, None), periodo(None, None)) is None


# ---------------------------------------------------------------- ranking multianual
from catalogo_prueba import correr, repo_prueba, req, sitio_de  # noqa: E402

ESPECIES_EXTRA = [
    # empieza a servir cuando el clima sube: el minimo termico queda por encima de lo que da la serie al comienzo
    (req("calida_t", tb=11.5, topt=(15, 24), tc=32, letal=-3, lluvia=(300, 500, 2500, 3500), ph=(4.5, 5, 7, 7.5),
         ciclo=(100, 140)), ["vegetables"]),
    # sirve en el frio y deja de servir cuando sube: su techo termico queda cerca
    (req("fria_t", tb=0, topt=(5, 8.5), tc=12.5, letal=-8, lluvia=(300, 500, 2500, 3500), ph=(4.5, 5, 7, 7.5),
         ciclo=(100, 140)), ["vegetables"]),
]


def ranking(historia, repo=None, riego=False, **kw):
    repo = repo or repo_prueba(extra=ESPECIES_EXTRA)
    return correr(ma.ranking_multianual(kw.pop("sitio", sitio_de("chiloe")), repo, historia, None, None, riego=riego, **kw))


def fila(rk, nombre):
    return next(r for r in rk if r["especie"] == nombre)


def test_una_especie_que_el_clima_en_cambio_vuelve_posible_sale_como_emergente():
    rk, resumen = ranking(historia_sintetica(range(1991, 2026), calentamiento=0.05, tmedia=9.0, lluvia_mes=120))
    r = fila(rk, "calida_t")
    assert r["clima"]["categoria"] == "emergente" and r["apta"]                # apta hoy por su ano dificil reciente
    assert r["clima"]["historico"]["dificil"] < ce.PUNTAJE_MINIMO_APTA <= r["clima"]["reciente"]["dificil"]
    assert r["clima"]["proyectado"]["tipico"] > r["clima"]["reciente"]["tipico"] > r["clima"]["historico"]["tipico"]
    assert resumen["temp_c_por_decada_observada"] == pytest.approx(0.5, abs=0.01)
    assert resumen["periodo_historico"] == [1991, 2010] and resumen["periodo_reciente"] == [2011, 2025]


def test_una_especie_que_el_calentamiento_saca_sale_en_riesgo():
    rk, _ = ranking(historia_sintetica(range(1991, 2026), calentamiento=0.05, tmedia=12.0, lluvia_mes=120))
    r = fila(rk, "fria_t")
    assert r["clima"]["categoria"] == "en_riesgo"
    assert r["clima"]["proyectado"]["dificil"] < r["clima"]["historico"]["dificil"]


def test_sin_tendencia_lo_que_sirve_es_tradicional_y_nada_es_emergente():
    rk, resumen = ranking(historia_sintetica(range(1991, 2026), calentamiento=0.0, tmedia=9.0, lluvia_mes=120))
    categorias = {r["clima"]["categoria"] for r in rk if "clima" in r}
    assert "emergente" not in categorias and "en_riesgo" not in categorias and "tradicional" in categorias
    assert resumen["temp_c_por_decada_usada"] == 0.0


def test_un_escenario_de_calentamiento_reemplaza_la_tendencia_observada():
    h = historia_sintetica(range(1991, 2026), calentamiento=0.0, tmedia=9.0, lluvia_mes=120)
    observado, r0 = ranking(h)
    fuerte, r1 = ranking(h, calentamiento_c_por_decada=0.6)
    assert fila(observado, "calida_t")["clima"]["categoria"] != "emergente"
    assert fila(fuerte, "calida_t")["clima"]["categoria"] == "emergente"
    assert r0["escenario"] == "observado" and r1["escenario"] == "supuesto" and r1["temp_c_por_decada_usada"] == 0.6
    # el periodo historico y el reciente no cambian con el escenario: solo el proyectado
    assert fila(observado, "calida_t")["clima"]["reciente"] == fila(fuerte, "calida_t")["clima"]["reciente"]


def test_un_ano_malo_entre_quince_no_descarta_pero_tres_si():
    def con_heladas(anios_malos):
        h = historia_sintetica(range(1991, 2026), tmedia=12.0, lluvia_mes=120)
        for a in anios_malos:
            h[a] = h[a].assign(tmin=h[a]["tmin"] - 30.0)                     # un ano con helada fuera de toda tolerancia
        return h
    uno, _ = ranking(con_heladas([2015]))
    tres, _ = ranking(con_heladas([2013, 2015, 2019]))
    assert fila(uno, "trigo_t")["apta"] and fila(uno, "trigo_t")["puntaje_ano_dificil"] > 0.2
    assert not fila(tres, "trigo_t")["apta"] and fila(tres, "trigo_t")["puntaje_ano_dificil"] < 0.2
    # la compatibilidad tipica es la misma: la mediana no ve la helada
    assert fila(tres, "trigo_t")["puntaje"] == pytest.approx(fila(uno, "trigo_t")["puntaje"])
    assert fila(tres, "trigo_t")["marginal"] and not fila(tres, "trigo_t")["apta"]


def test_los_periodos_dependen_solo_de_los_anos_de_cada_uno():
    h = historia_sintetica(range(1991, 2026), tmedia=12.0, lluvia_mes=120)
    for a in range(1991, 2011):                                               # solo el periodo historico tiene heladas
        h[a] = h[a].assign(tmin=h[a]["tmin"] - 30.0)
    r = fila(ranking(h)[0], "trigo_t")
    assert r["clima"]["historico"]["dificil"] == 0.0 and r["clima"]["reciente"]["dificil"] > 0.2
    assert r["apta"]                                                           # el decil que cuenta es el reciente


def test_con_poca_historia_queda_el_ranking_de_un_ano_sin_campos_nuevos():
    rk, resumen = ranking(historia_sintetica(range(2010, 2026)))               # 16 anos: no alcanza para dos periodos
    assert resumen is None and all("clima" not in r for r in rk)
    rk, resumen = ranking(None)
    assert resumen is None


def test_el_orden_es_aptas_primero_y_por_compatibilidad_tipica():
    rk, _ = ranking(historia_sintetica(range(1991, 2026), calentamiento=0.02, tmedia=9.0, lluvia_mes=120))
    aptas = [r for r in rk if r["apta"]]
    assert aptas and rk[:len(aptas)] == aptas
    assert [r["puntaje"] for r in aptas] == sorted((r["puntaje"] for r in aptas), reverse=True)
    for r in rk:
        if "clima" in r:
            assert r["puntaje_ano_dificil"] <= r["puntaje"] + 1e-9             # un ano dificil nunca rinde mas que el tipico
            assert r["apta"] == (r["puntaje_ano_dificil"] >= ce.PUNTAJE_MINIMO_APTA)


def test_con_riego_la_falta_de_lluvia_no_descarta_en_ningun_periodo():
    h = historia_sintetica(range(1991, 2026), tmedia=12.0, lluvia_mes=5.0)
    seco, _ = ranking(h)
    regado, _ = ranking(h, riego=True)
    assert not fila(seco, "trigo_t")["apta"] and fila(regado, "trigo_t")["apta"]


def test_la_correccion_por_altitud_se_aplica_a_cada_ano():
    h = historia_sintetica(range(1991, 2026), tmedia=12.0, lluvia_mes=120)
    frio, _ = ranking(h, delta_temp=-12.0)
    assert fila(frio, "trigo_t")["puntaje"] < ranking(h)[0][[r["especie"] for r in ranking(h)[0]].index("trigo_t")]["puntaje"]


# ---------------------------------------------------------------- especies con seguimiento por etapa
def test_la_especie_curada_se_simula_ano_por_ano_y_los_anos_secos_bajan_su_ano_dificil():
    lluvioso = historia_sintetica(range(1991, 2026), tmedia=12.0, lluvia_mes=140)
    seco = {a: (d.assign(lluvia=0.0) if a in (2012, 2015, 2018, 2021) else d) for a, d in lluvioso.items()}
    repo = repo_prueba(curada=True)
    kw = dict(repo=repo, sitio=sitio_de("chiloe"), lat=-42.5)
    bien, _ = correr(ma.ranking_multianual(kw["sitio"], repo, lluvioso, None, -42.5))
    mal, _ = correr(ma.ranking_multianual(kw["sitio"], repo, seco, None, -42.5))
    papa_bien, papa_mal = fila(bien, "papa_t"), fila(mal, "papa_t")
    assert papa_bien["clima"]["categoria"] is not None
    assert papa_mal["puntaje_ano_dificil"] < papa_bien["puntaje_ano_dificil"]


# ---------------------------------------------------------------- catalogo en memoria
def test_el_repositorio_cacheado_lee_el_catalogo_una_vez_hasta_que_vence():
    repo = repo_prueba()
    lecturas = []
    original = repo.requisitos_genericos

    async def contado():
        lecturas.append(1)
        return await original()
    repo.requisitos_genericos = contado
    reloj = {"t": 0.0}
    almacen = {}
    uno = ma.RepositorioCacheado(repo, almacen, ahora=lambda: reloj["t"])
    correr(uno.requisitos_genericos()), correr(ma.RepositorioCacheado(repo, almacen, ahora=lambda: reloj["t"]).requisitos_genericos())
    assert len(lecturas) == 1
    reloj["t"] = ma.RepositorioCacheado.VIGENCIA_S + 1
    correr(uno.requisitos_genericos())
    assert len(lecturas) == 2
    assert uno.listar_especies is not None                                      # lo que no se cachea pasa al repositorio
    pedidos = []
    original_rasgos = repo.rasgos_rotacion

    async def rasgos(especie):
        pedidos.append(especie)
        return await original_rasgos(especie)
    repo.rasgos_rotacion = rasgos
    correr(uno.rasgos_rotacion("papa_t")), correr(uno.rasgos_rotacion("papa_t"))
    assert pedidos == ["papa_t"]
    v1 = correr(uno.catalogo_vectorial())
    assert correr(uno.catalogo_vectorial()) is v1
