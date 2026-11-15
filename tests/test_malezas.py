"""Las especies que EcoCrop marca como maleza no se recomiendan (catalogo_especies.ranking_idoneidad)."""
import catalogo_especies as ce
from catalogo_prueba import correr, repo_prueba, req, sitio_de

BASE = dict(tb=4, topt=(12, 20), tc=30, letal=-4, lluvia=(300, 500, 1400, 2200), ph=(5.0, 5.2, 7.5, 8.0), ciclo=(100, 140))


def nombres(**opciones):
    extra = [
        (req("lechuga_t", **BASE), ["vegetables"]),
        (req("quelite_t", **BASE), ["vegetables", "weed"]),        # comestible, pero EcoCrop la marca maleza
        (req("avena_silvestre_t", **BASE), ["cereals & pseudocereals", "forage/pasture", "weed"]),
        (req("cizana_t", **BASE), ["weed"]),
    ]
    ranking = correr(ce.ranking_idoneidad(sitio_de("chiloe"), repo_prueba(con_luz=False, extra=extra), **opciones))
    return {r["especie"] for r in ranking}


def test_con_un_grupo_de_comida_no_salen_las_malezas_aunque_tengan_categoria_de_comida():
    salen = nombres(categorias={"vegetables", "cereals & pseudocereals"})
    assert "lechuga_t" in salen
    assert not salen & {"quelite_t", "avena_silvestre_t", "cizana_t"}


def test_sin_grupo_tampoco_salen_las_malezas():
    salen = nombres()
    assert "lechuga_t" in salen and not salen & {"quelite_t", "avena_silvestre_t", "cizana_t"}


def test_se_puede_pedir_expresamente_la_categoria_maleza():
    assert {"quelite_t", "avena_silvestre_t", "cizana_t"} <= nombres(categorias={"weed"})


def test_consultar_una_especie_puntual_la_devuelve_aunque_sea_maleza():
    assert {"quelite_t", "avena_silvestre_t"} <= nombres(incluir_malezas=True)


def test_el_resto_del_catalogo_no_cambia():
    sin_extras = {r["especie"] for r in correr(ce.ranking_idoneidad(sitio_de("chiloe"), repo_prueba(con_luz=False)))}
    assert sin_extras <= nombres()


def test_el_ranking_multianual_respeta_la_exclusion_y_el_permiso():
    from services import multianual as ma
    extra = [(req("lechuga_t", **BASE), ["vegetables"]), (req("quelite_t", **BASE), ["vegetables", "weed"])]
    repo = repo_prueba(con_luz=False, extra=extra)
    sitio = sitio_de("chiloe")
    sin, _ = correr(ma.ranking_multianual(sitio, repo, None, None, None, categorias={"vegetables"}))
    con, _ = correr(ma.ranking_multianual(sitio, repo, None, None, None, categorias={"vegetables"}, incluir_malezas=True))
    assert "quelite_t" not in {r["especie"] for r in sin} and "quelite_t" in {r["especie"] for r in con}
