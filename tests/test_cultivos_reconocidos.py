"""Las filas de EcoCrop que no son cultivo (algodoncillo, cenizo) no salen como cultivables,
aunque vengan etiquetadas como hortaliza o forraje (catalogo_especies.ranking_idoneidad)."""
import catalogo_especies as ce
from catalogo_prueba import correr, repo_prueba, req, sitio_de
from cultivos_reconocidos import es_cultivo_reconocido

BASE = dict(tb=4, topt=(12, 20), tc=30, letal=-4, lluvia=(300, 500, 1400, 2200), ph=(5.0, 5.2, 7.5, 8.0), ciclo=(100, 140))
ECOCROP = "FAO_EcoCrop_opinion_experta"


def salen(**opciones):
    extra = [
        (req("lechuga_e", **BASE, fuente=ECOCROP), ["vegetables"], "Lactuca sativa L."),
        (req("algodoncillo_e", **BASE, fuente=ECOCROP), ["vegetables", "materials"], "Asclepias speciosa"),
        (req("cenizo_e", **BASE, fuente=ECOCROP), ["forage/pasture", "vegetables"], "Chenopodium album ssp. album"),
        (req("local_t", **BASE, fuente="INIA_prueba"), ["vegetables"], "Especie local sin listar"),
    ]
    repo = repo_prueba(con_luz=False, extra=extra)
    return {r["especie"] for r in correr(ce.ranking_idoneidad(sitio_de("chiloe"), repo, **opciones))}


def test_un_cultivo_reconocido_sale_y_la_silvestre_de_ecocrop_no():
    resultado = salen()
    assert "lechuga_e" in resultado
    assert not resultado & {"algodoncillo_e", "cenizo_e"}


def test_tampoco_salen_con_un_grupo_de_comida():
    resultado = salen(categorias={"vegetables", "forage/pasture"})
    assert "lechuga_e" in resultado and not resultado & {"algodoncillo_e", "cenizo_e"}


def test_se_pueden_pedir_las_silvestres():
    assert {"lechuga_e", "algodoncillo_e", "cenizo_e"} <= salen(incluir_silvestres=True)


def test_una_especie_de_otra_fuente_no_se_filtra_por_la_lista():
    assert "local_t" in salen()


def test_el_binomio_ignora_autor_variedad_y_mayusculas():
    assert es_cultivo_reconocido("Lactuca sativa L.")
    assert es_cultivo_reconocido("Prunus persica var. nucipersica")
    assert es_cultivo_reconocido("Fragaria × ananassa Duchesne")
    assert not es_cultivo_reconocido("Asclepias speciosa") and not es_cultivo_reconocido(None)


def test_cultivos_que_un_contador_de_nombres_habria_dejado_fuera():
    for nombre in ("Cichorium endivia", "Rheum rhaponticum", "Raphanus sativus", "Triticum compactum",
                   "Echinochloa frumentacea", "Solanum tuberosum", "Vicia faba", "Chenopodium quinoa"):
        assert es_cultivo_reconocido(nombre), nombre
