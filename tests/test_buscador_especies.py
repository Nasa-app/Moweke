"""Buscador de especies para agregar un cultivo (catalogo_especies.buscar_especies)."""
import catalogo_especies as ce

ID = {
    "papa": {"nombre_es": "Papa", "nombre_en": "Potato", "nombre_cientifico": "Solanum tuberosum", "nombres_comunes": "patata", "categorias": ["roots/tubers"]},
    "solanum_tuberosum": {"nombre_es": "Papa", "nombre_en": "Potato", "nombre_cientifico": "Solanum tuberosum", "nombres_comunes": "potato", "categorias": ["roots/tubers"]},
    "capsicum_annuum": {"nombre_es": "Ají", "nombre_en": "Pepper", "nombre_cientifico": "Capsicum annuum", "nombres_comunes": "pimiento, chile", "categorias": ["vegetables"]},
    "chenopodium_quinoa": {"nombre_es": "Quinoa", "nombre_en": "Quinoa", "nombre_cientifico": "Chenopodium quinoa", "nombres_comunes": "quinua", "categorias": ["cereals & pseudocereals"]},
    "chenopodium_album": {"nombre_es": "Quelite", "nombre_en": "Fat hen", "nombre_cientifico": "Chenopodium album", "nombres_comunes": "bledo", "categorias": ["vegetables", "weed"]},
    "pinus_radiata": {"nombre_es": "Pino", "nombre_en": "Pine", "nombre_cientifico": "Pinus radiata", "nombres_comunes": "pino insigne", "categorias": ["forest/wood"]},
    "rosa_x": {"nombre_es": "Rosa", "nombre_en": "Rose", "nombre_cientifico": "Rosa x", "nombres_comunes": "", "categorias": ["vegetables"]},
}
FUENTES = {k: ce.FUENTE_ECOCROP for k in ID} | {"papa": "INIA"}


def buscar(q, **kw):
    return [r["especie"] for r in ce.buscar_especies(ID, FUENTES, {"papa"}, q, **kw)]


def test_encuentra_por_nombre_en_espanol_ingles_comun_o_cientifico():
    assert buscar("papa") == ["papa"]
    assert buscar("potato") == ["papa"]
    assert buscar("patata") == ["papa"]
    assert buscar("tuberosum") == ["papa"]


def test_no_distingue_tildes_ni_mayusculas():
    assert buscar("AJI") == ["capsicum_annuum"] and buscar("ají") == ["capsicum_annuum"]
    assert buscar("quínoa") == ["chenopodium_quinoa"]


def test_la_fila_de_ecocrop_de_una_especie_con_calendario_no_sale_aparte():
    assert "solanum_tuberosum" not in buscar("solanum")


def test_no_ofrece_malezas_forestales_ni_cultivos_no_reconocidos():
    assert buscar("quelite") == [] and buscar("bledo") == []   # maleza
    assert buscar("pino") == []                                # forestal
    assert buscar("rosa") == []                                # EcoCrop que no es cultivo reconocido


def test_marca_cuales_tienen_seguimiento_y_trae_los_nombres():
    r = ce.buscar_especies(ID, FUENTES, {"papa"}, "papa")[0]
    assert r["seguimiento"] is True and r["nombre_en"] == "Potato" and r["nombre_cientifico"] == "Solanum tuberosum"
    assert ce.buscar_especies(ID, FUENTES, {"papa"}, "quinoa")[0]["seguimiento"] is False


def test_primero_las_que_empiezan_igual_y_con_seguimiento_antes():
    ID2 = {**ID, "otra": {"nombre_es": "Semilla de papa dulce", "nombre_en": "x", "nombre_cientifico": "Otra otra", "nombres_comunes": "", "categorias": ["vegetables"]}}
    f = FUENTES | {"otra": "INIA"}
    assert [r["especie"] for r in ce.buscar_especies(ID2, f, {"papa"}, "papa")] == ["papa", "otra"]


def test_una_consulta_de_menos_de_dos_letras_no_devuelve_nada_y_se_respeta_el_limite():
    assert buscar("p") == [] and buscar("  ") == []
    muchas = {f"sp_{i}": {"nombre_es": f"Tomate {i}", "nombre_en": "", "nombre_cientifico": f"Lycopersicon {i}", "nombres_comunes": "", "categorias": ["vegetables"]} for i in range(30)}
    assert len(ce.buscar_especies(muchas, {k: "INIA" for k in muchas}, set(), "tomate", limite=5)) == 5
