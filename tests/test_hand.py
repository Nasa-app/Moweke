"""HAND (altura sobre el cauce): url de baldosa, lectura de ventana y agrupado por celda."""
import numpy as np
import rasterio
from rasterio.transform import from_origin

import cliente_hand as ch
from services import ingesta_predio as ip

PERIMETRO = {"type": "Polygon", "coordinates": [[[-72.0, -35.0], [-71.9994, -35.0], [-71.9994, -35.0006],
                                                  [-72.0, -35.0006], [-72.0, -35.0]]]}
TRANSFORM = from_origin(-72.0, -35.0, 0.00028, 0.00028)
WGS84 = rasterio.crs.CRS.from_epsg(4326)


def test_url_de_baldosa_hemisferio_sur_y_oeste():
    url = ch._url_baldosa(-35, -72)
    assert url.endswith("Copernicus_DSM_COG_10_S35_00_W072_00_HAND.tif") and "glo-30-hand" in url


def test_url_de_baldosa_hemisferio_norte_y_este():
    assert ch._url_baldosa(4, 7).endswith("Copernicus_DSM_COG_10_N04_00_E007_00_HAND.tif")


def test_agrupa_el_hand_por_celda_y_descarta_pixeles_sin_dato():
    hand = np.array([[1.0, 3.0], [np.nan, 9.0]])
    por_celda = ip.relieve_por_celda([{"altitud": hand, "transform": TRANSFORM, "crs": WGS84}],
                                     PERIMETRO, 32718, 1000.0, campos=("altitud",))
    assert sum(v["pixeles"] for v in por_celda.values()) == 3
    assert all(set(v) == {"altitud", "pixeles"} for v in por_celda.values())
    media = sum(v["altitud"] * v["pixeles"] for v in por_celda.values()) / 3
    assert abs(media - 13 / 3) < 1e-9


def test_el_agrupado_de_relieve_sigue_dando_altitud_y_pendiente():
    b = {"altitud": np.full((2, 2), 100.0), "pendiente": np.full((2, 2), 5.0), "transform": TRANSFORM, "crs": WGS84}
    por_celda = ip.relieve_por_celda([b], PERIMETRO, 32718, 1000.0)
    assert por_celda and all(v["altitud"] == 100.0 and v["pendiente"] == 5.0 for v in por_celda.values())


def test_la_fuente_inundacion_esta_registrada_como_dato_de_sitio():
    assert "inundacion" in ip.FUENTES and "inundacion" in ip.FUENTES_DE_SITIO and "inundacion" in ip._INGESTAS
