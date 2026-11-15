"""Las variedades y subespecies de EcoCrop salen como una sola especie en el ranking (catalogo_especies._unir_variedades)."""
import catalogo_especies as ce
from catalogo_prueba import correr, repo_prueba, req, sitio_de

BASE = dict(tb=4, topt=(12, 20), tc=30, letal=-4, lluvia=(300, 500, 1400, 2200), ph=(5.0, 5.2, 7.5, 8.0), ciclo=(100, 140))
DEBIL = dict(BASE, tb=15, topt=(28, 32), tc=40)   # no le sirve el clima frio de Chiloe


def candidatas(extra, **opciones):
    repo = repo_prueba(con_luz=False, extra=extra)
    return {r["especie"]: r for r in correr(ce.ranking_idoneidad(sitio_de("chiloe"), repo, **opciones))}


def test_la_especie_y_sus_variedades_salen_una_sola_vez_con_el_mejor_puntaje():
    extra = [
        (req("acelga_base", **DEBIL), ["vegetables"], "Beta vulgaris"),
        (req("acelga_cicla", **BASE), ["vegetables"], "Beta vulgaris var. cicla"),
        (req("acelga_flav", **DEBIL), ["vegetables"], "Beta vulgaris var. flavescens"),
    ]
    r = candidatas(extra)
    acelgas = [x for x in r.values() if x["nombre_cientifico"].startswith("Beta vulgaris")]
    assert len(acelgas) == 1
    assert acelgas[0]["nombre_cientifico"] == "Beta vulgaris var. cicla"
    assert acelgas[0]["variedad_recomendada"] == {"rango": "variedad", "nombre": "cicla"}
    assert [v["nombre_cientifico"] for v in acelgas[0]["variedades"]][0] == "Beta vulgaris var. cicla"
    assert acelgas[0]["variedades"][0]["mejor"] is True and len(acelgas[0]["variedades"]) == 3


def test_a_igual_puntaje_gana_la_especie_sin_variedad():
    extra = [
        (req("apio_var", **BASE), ["vegetables"], "Apium graveolens var. dulce"),
        (req("apio_base", **BASE), ["vegetables"], "Apium graveolens"),
    ]
    r = candidatas(extra)
    apios = [x for x in r.values() if x["nombre_cientifico"].startswith("Apium")]
    assert [x["nombre_cientifico"] for x in apios] == ["Apium graveolens"]


def test_especies_distintas_no_se_unen_aunque_sean_del_mismo_genero():
    extra = [
        (req("allium_a", **BASE), ["vegetables"], "Allium fistulosum"),
        (req("allium_b", **BASE), ["vegetables"], "Allium schoenoprasum"),
    ]
    r = candidatas(extra)
    assert {"allium_a", "allium_b"} <= set(r)


def test_el_hibrido_conserva_su_x_y_no_se_une_con_su_genero():
    extra = [
        (req("fresa_h", **BASE), ["fruits & nuts"], "Fragaria x ananassa"),
        (req("fresa_v", **BASE), ["fruits & nuts"], "Fragaria vesca"),
    ]
    r = candidatas(extra)
    assert {"fresa_h", "fresa_v"} <= set(r)


def test_si_la_especie_base_gana_no_hay_variedad_recomendada_pero_se_listan_todas():
    extra = [
        (req("apio_base2", **BASE), ["vegetables"], "Apium graveolens"),
        (req("apio_dulce", **DEBIL), ["vegetables"], "Apium graveolens var. dulce"),
    ]
    apio = [x for x in candidatas(extra).values() if x["nombre_cientifico"].startswith("Apium")][0]
    assert apio["variedad_recomendada"] is None and len(apio["variedades"]) == 2


def test_se_puede_pedir_una_variedad_puntual_sin_unir():
    extra = [
        (req("cicla", **BASE), ["vegetables"], "Beta vulgaris var. cicla"),
        (req("flav", **DEBIL), ["vegetables"], "Beta vulgaris var. flavescens"),
    ]
    repo = repo_prueba(con_luz=False, extra=extra)
    r = {x["especie"]: x for x in correr(ce.ranking_idoneidad(sitio_de("chiloe"), repo, unir_variedades=False))}
    assert {"cicla", "flav"} <= set(r)
    assert r["flav"]["variedad_recomendada"] == {"rango": "variedad", "nombre": "cicla"}
