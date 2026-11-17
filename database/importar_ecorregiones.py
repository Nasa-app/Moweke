"""
Importador de ecorregiones -> database/seed_ecorregiones.sql -- ETL de una sola vez,
igual que importar_ecocrop.py: no es un cliente que se llame en produccion.

Fuente real: "Biomes and Ecoregions 2017" (RESOLVE; Dinerstein et al. 2017, BioScience
67(6)), la version revisada del mapa de ecorregiones terrestres de WWF (Olson et al.
2001) que nombraba el diseno original. Licencia CC-BY 4.0 (campo LICENSE de cada
entidad) -- hay que citar la fuente donde se muestre el dato. Se consulta el servicio
publico de entidades de ArcGIS, sin cuenta ni clave; no hace falta bajar ni leer el
shapefile mundial.

Alcance: las ecorregiones que tocan la caja de Chile continental (la misma caja que
valida POST /api/parcelas). VERIFICADO en vivo: son 16, varias solo del lado argentino o
boliviano de la caja -- se cargan igual, no estorban. Quedan fuera Juan Fernandez, Rapa
Nui y las demas islas oceanicas.

Las geometrias llegan simplificadas a TOLERANCIA_GRADOS (~1 km): el limite entre dos
ecorregiones no es una linea medida en terreno. ST_MakeValid repara lo que la
simplificacion pueda haber cruzado.

De cada ecorregion solo se guardan los poligonos que tocan la caja de Chile. Sin eso
"Rock and Ice" llega como un unico multipoligono con todos los hielos del planeta
(Islandia incluida): pesaba casi todo el archivo y obligaba a medir distancias contra
una geometria que da la vuelta al mundo.

Solo se copia lo que la fuente trae: nombre, bioma (los 14 biomas de WWF) y reino
biogeografico. `bioma_tipo`, la clasificacion propia de cuatro valores del proyecto, NO
se llena aca: no hay una equivalencia publicada entre los biomas de WWF y esos cuatro.

El SQL generado es idempotente (ON CONFLICT por eco_id) y termina asignando la
ecorregion a los predios que todavia no la tienen.
"""
from __future__ import annotations

import json
import logging
import sys

import requests

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("importar_ecorregiones")

URL = "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/Resolve_Ecoregions/FeatureServer/0/query"
CAJA_CHILE = "-76,-56,-66,-17.4"   # lon_min, lat_min, lon_max, lat_max
_LON_MIN, _LAT_MIN, _LON_MAX, _LAT_MAX = (float(v) for v in CAJA_CHILE.split(","))
TOLERANCIA_GRADOS = 0.01
FUENTE = "RESOLVE_Ecoregions_2017_CC-BY-4.0"


def escapar(valor) -> str:
    if valor is None:
        return "NULL"
    return "'" + str(valor).replace("'", "''") + "'"


def _toca_chile(poligono: list) -> bool:
    """poligono: anillos de un Polygon de GeoJSON; se mira la caja del anillo exterior."""
    lons, lats = [p[0] for p in poligono[0]], [p[1] for p in poligono[0]]
    return min(lons) <= _LON_MAX and max(lons) >= _LON_MIN and min(lats) <= _LAT_MAX and max(lats) >= _LAT_MIN


def recortar_a_chile(geometria: dict) -> dict:
    """Deja solo los poligonos de la ecorregion que tocan la caja de Chile. No corta
    poligonos: uno que la toca se conserva entero aunque siga hacia Argentina."""
    partes = geometria["coordinates"] if geometria["type"] == "MultiPolygon" else [geometria["coordinates"]]
    return {"type": "MultiPolygon", "coordinates": [p for p in partes if _toca_chile(p)]}


def main(destino_sql: str) -> None:
    r = requests.get(URL, params={
        "geometry": CAJA_CHILE, "geometryType": "esriGeometryEnvelope", "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects", "outFields": "ECO_ID,ECO_NAME,BIOME_NAME,REALM",
        "outSR": "4326", "maxAllowableOffset": TOLERANCIA_GRADOS, "geometryPrecision": 4, "f": "geojson",
    }, timeout=300)
    r.raise_for_status()
    datos = r.json()
    if datos.get("exceededTransferLimit") or datos.get("properties", {}).get("exceededTransferLimit"):
        raise RuntimeError("el servicio corto la respuesta: faltarian ecorregiones")
    entidades = sorted(datos["features"], key=lambda f: f["properties"]["ECO_ID"])
    log.info("ecorregiones que tocan la caja de Chile: %d", len(entidades))

    filas = []
    for f in entidades:
        p = f["properties"]
        # 'N/A' es como la fuente marca lo que no tiene bioma ni reino (Rock and Ice).
        bioma = None if p["BIOME_NAME"] == "N/A" else p["BIOME_NAME"]
        reino = None if p["REALM"] == "N/A" else p["REALM"]
        geometria = recortar_a_chile(f["geometry"])
        if not geometria["coordinates"]:
            continue
        geojson = json.dumps(geometria, separators=(",", ":"))
        filas.append(
            f"({int(p['ECO_ID'])}, {escapar(p['ECO_NAME'])}, {escapar(bioma)}, {escapar(reino)}, '{FUENTE}',\n"
            f"  ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_SetSRID(ST_GeomFromGeoJSON({escapar(geojson)}), 4326)), 3)))"
        )
        log.info("  %4d  %s  (%s): %d de %d poligonos", p["ECO_ID"], p["ECO_NAME"], bioma, len(geometria["coordinates"]),
                 len(f["geometry"]["coordinates"]) if f["geometry"]["type"] == "MultiPolygon" else 1)

    with open(destino_sql, "w") as salida:
        salida.write(
            "-- Generado por database/importar_ecorregiones.py -- NO editar a mano, regenerar.\n"
            "-- Fuente: Biomes and Ecoregions 2017 (RESOLVE; Dinerstein et al. 2017), CC-BY 4.0.\n"
            "-- Idempotente: actualiza las ecorregiones existentes e inserta las que falten.\n\n"
            "BEGIN;\n\n"
            "INSERT INTO ecoregion_wwf (eco_id, eco_name, bioma_wwf, reino, fuente, geometria) VALUES\n"
            + ",\n".join(filas) + "\n"
            "ON CONFLICT (eco_id) DO UPDATE SET eco_name = EXCLUDED.eco_name, bioma_wwf = EXCLUDED.bioma_wwf,\n"
            "  reino = EXCLUDED.reino, fuente = EXCLUDED.fuente, geometria = EXCLUDED.geometria;\n\n"
            "-- Predios que todavia no tienen ecorregion: la que contiene su centroide o, si\n"
            "-- cae en un borde simplificado (costa), la mas cercana a menos de 5 km.\n"
            "UPDATE parcela p SET id_ecoregion = (\n"
            "  SELECT e.id FROM ecoregion_wwf e\n"
            "  WHERE ST_DWithin(e.geometria::geography, ST_Centroid(p.geometria)::geography, 5000)\n"
            "  ORDER BY ST_Distance(e.geometria::geography, ST_Centroid(p.geometria)::geography) LIMIT 1)\n"
            "WHERE p.id_ecoregion IS NULL;\n\n"
            "COMMIT;\n"
        )
    log.info("escrito %s: %d ecorregiones", destino_sql, len(filas))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "database/seed_ecorregiones.sql")
