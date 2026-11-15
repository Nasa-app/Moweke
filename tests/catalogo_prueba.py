"""Catalogo y sitios inventados para probar el motor sin base de datos. Las especies son
sinteticas a proposito: las pruebas fijan el comportamiento del motor, no el valor de los
datos de EcoCrop. Los sitios imitan cuatro climas extremos."""
import asyncio

import pandas as pd

from catalogo_especies import RepositorioEnMemoria
from pheno_engine import clima_sintetico

LAT = -42.5

LUZ = [
    {"categoria": "sol pleno", "orden": 1, "ghi_min_kwh_m2_dia": 5.0},
    {"categoria": "luminoso", "orden": 2, "ghi_min_kwh_m2_dia": 3.5},
    {"categoria": "sombra parcial", "orden": 3, "ghi_min_kwh_m2_dia": 0.0},
]

_COLUMNAS = ("tb", "t_optima", "tc", "t_opt_min", "t_opt_max", "temperatura_letal",
             "lluvia_anual_min", "lluvia_anual_opt_min", "lluvia_anual_opt_max", "lluvia_anual_max",
             "ph_suelo_min", "ph_opt_min", "ph_opt_max", "ph_suelo_max",
             "luz_min", "luz_opt_min", "luz_opt_max", "luz_max",
             "ciclo_min_dias", "ciclo_max_dias", "humedad_suelo_minima", "humedad_suelo_maxima",
             "altitud_max_m", "textura_opt", "textura_rango", "drenaje_opt", "drenaje_rango",
             "salinidad_opt", "salinidad_max", "profundidad_opt", "profundidad_min", "fertilidad_opt", "fertilidad_min")


def req(especie, *, tb, topt, tc, letal, lluvia, ph, ciclo, **extra):
    """Una fila de requisitos_especie. topt = (min, max); lluvia y ph = (min, opt_min, opt_max, max)."""
    fila = dict.fromkeys(_COLUMNAS)
    fila.update(especie=especie, variedad_local=None, fuente="prueba",
                tb=tb, t_opt_min=topt[0], t_opt_max=topt[1], t_optima=sum(topt) / 2, tc=tc, temperatura_letal=letal,
                lluvia_anual_min=lluvia[0], lluvia_anual_opt_min=lluvia[1],
                lluvia_anual_opt_max=lluvia[2], lluvia_anual_max=lluvia[3],
                ph_suelo_min=ph[0], ph_opt_min=ph[1], ph_opt_max=ph[2], ph_suelo_max=ph[3],
                luz_min="sombra parcial", luz_opt_min="sol pleno", luz_opt_max="luminoso", luz_max="sol pleno",
                ciclo_min_dias=ciclo[0], ciclo_max_dias=ciclo[1])
    fila.update(extra)
    return fila


def identidad(especie, categorias, cientifico=None):
    return {"especie": especie, "nombre_cientifico": cientifico or f"{especie} prueba",
            "nombres_comunes": especie, "categorias": categorias, "forma_vida": "herb"}


# Cada especie tolera un clima distinto: la prueba es que el motor las separe por terreno.
ESPECIES = [
    (req("trigo_t", tb=4, topt=(12, 20), tc=30, letal=-4, lluvia=(300, 500, 1400, 2200), ph=(5.2, 6.0, 7.0, 7.5), ciclo=(100, 140)),
     ["cereals & pseudocereals"]),
    (req("cacao_t", tb=15, topt=(24, 30), tc=38, letal=8, lluvia=(1200, 1800, 2800, 3800), ph=(5.0, 5.5, 7.0, 7.5), ciclo=(150, 180)),
     ["fruits & nuts"]),
    (req("quinoa_t", tb=0, topt=(6, 14), tc=24, letal=-10, lluvia=(150, 250, 600, 900), ph=(5.5, 6.0, 8.0, 8.5), ciclo=(140, 200)),
     ["cereals & pseudocereals"]),
    (req("salicornia_t", tb=8, topt=(18, 30), tc=42, letal=-2, lluvia=(40, 100, 200, 300), ph=(6.0, 6.5, 8.5, 9.0), ciclo=(90, 150)),
     ["vegetables"]),
    (req("arandano_t", tb=3, topt=(10, 20), tc=30, letal=-15, lluvia=(500, 800, 2000, 3000), ph=(4.0, 4.5, 5.5, 6.0), ciclo=(150, 200)),
     ["fruits & nuts"]),
    (req("pino_t", tb=4, topt=(10, 20), tc=30, letal=-10, lluvia=(500, 800, 2000, 3000), ph=(4.5, 5.0, 6.5, 7.5), ciclo=(300, 365)),
     ["forest/wood"]),
]

SITIOS = {
    "chiloe": dict(
        tmedia=[14, 14, 12.5, 10.5, 9, 7.5, 7, 7.5, 8.5, 10, 11.5, 13],
        tmin=[4, 4, 2, 0, -2, -3, -4, -3, -2, -1, 1, 3],
        lluvia=[90, 80, 110, 170, 250, 300, 270, 230, 170, 140, 110, 100],
        ph=5.5, ghi=[6.2, 5.4, 4.0, 2.6, 1.7, 1.3, 1.5, 2.2, 3.3, 4.5, 5.7, 6.3], awc=140),
    "desierto": dict(
        tmedia=[22, 22, 20, 17, 15, 13, 12.5, 13, 14.5, 16.5, 18.5, 20.5],
        tmin=[10, 10, 8, 5, 3, 1, 0, 1, 3, 5, 7, 9],
        lluvia=[0, 0, 0, 2, 6, 18, 22, 14, 6, 4, 2, 0],
        ph=7.8, ghi=[8.5, 7.6, 6.4, 5, 3.9, 3.3, 3.6, 4.5, 5.7, 7, 8, 8.7], awc=60),
    "altiplano": dict(
        tmedia=[9, 9, 8.5, 7.5, 5.5, 4, 3.5, 4.5, 6, 7.5, 8.5, 9],
        tmin=[-1, -1, -3, -6, -9, -11, -12, -10, -8, -6, -4, -2],
        lluvia=[90, 100, 60, 10, 2, 1, 1, 2, 4, 5, 10, 40],
        ph=6.5, ghi=[7.0, 6.6, 6.0, 5.6, 4.8, 4.4, 4.7, 5.4, 6.2, 6.9, 7.3, 7.3], awc=80),
    "tropico": dict(
        tmedia=[27] * 12, tmin=[21] * 12, lluvia=[200] * 12,
        ph=5.0, ghi=[4.8] * 12, awc=150),
}


def sitio_de(nombre, *, ph=None, tmin_delta=0.0, lluvia=None, **cambios):
    """Un sitio en el formato que espera ranking_idoneidad. `ph=False` lo deja sin dato."""
    d = SITIOS[nombre]
    valor_ph = d["ph"] if ph is None else (None if ph is False else ph)
    sitio = {"normales": {"tmedia": list(d["tmedia"]), "tmin_extrema": [x + tmin_delta for x in d["tmin"]],
                          "lluvia": list(d["lluvia"]) if lluvia is None else lluvia},
             "ph": valor_ph, "ghi_mensual": list(d["ghi"]), "awc_mm": d["awc"],
             "altitud_m": 100, "textura": "medium"}
    sitio.update(cambios)
    return sitio


def repo_prueba(*, con_luz=True, curada=False, lluvia_curada=(300, 500, 1400, 2200), extra=()):
    """Catalogo en memoria. `curada` agrega una especie con perfil fenologico (papa_t) y su fila
    de EcoCrop ('solanum_prueba'), igual que papa y solanum_tuberosum en el catalogo real."""
    requisitos = [r for r, _ in ESPECIES]
    identidades = [identidad(r["especie"], cats) for r, cats in ESPECIES]
    umbrales, rasgos, reglas = [], [], []
    for r, cats, *cientifico in extra:
        requisitos.append(r)
        identidades.append(identidad(r["especie"], cats, *cientifico))
    if curada:
        base = dict(tb=4, topt=(12, 20), tc=28, letal=-4, lluvia=lluvia_curada, ph=(5.2, 6.0, 7.0, 7.5), ciclo=(100, 140))
        requisitos.append(req("solanum_prueba", **base))
        requisitos.append(req("papa_t", **base, fuente="INIA_prueba"))
        identidades.append(identidad("solanum_prueba", ["roots/tubers"], "Solanum prueba"))
        identidades.append(identidad("papa_t", ["roots/tubers"], "Solanum prueba"))
        umbrales = [
            {"especie": "papa_t", "variedad_local": None, "orden": i, "etapa": e, "gdd_minimo": a, "gdd_maximo": b,
             "horas_luz_criticas": None, "fuente": "INIA_prueba"}
            for i, (e, a, b) in enumerate([("emergencia", 100, 140), ("tuberizacion", 300, 380), ("madurez", 500, 600)], 1)
        ]
        rasgos = [{"especie": "papa_t", "fija_nitrogeno": False, "familia_botanica": "Solanaceae",
                   "siembra_mes": 10, "siembra_dia": 15, "perenne": False}]
        reglas = [
            {"especie": "papa_t", "variedad_local": None, "fase": "emergencia->tuberizacion", "peligro": "helada",
             "umbral": -4, "minimo": 1, "efecto": "total", "valor": 0},
            {"especie": "papa_t", "variedad_local": None, "fase": "tuberizacion->madurez", "peligro": "sequia",
             "umbral": 0.4, "minimo": 0, "efecto": "parcial", "valor": 0.4},
        ]
    return RepositorioEnMemoria(requisitos, umbrales, rasgos, reglas, identidades, LUZ if con_luz else [])


def clima_prueba(lluvia_factor=1.0) -> pd.DataFrame:
    """Un ano de clima diario continuo, con la forma que entrega leer_sitio()."""
    clima = clima_sintetico("2024-11-01", "2025-10-31", tmedia=12, amp=4, rango=7, seed=1)
    clima["lluvia"] = clima["lluvia"] * lluvia_factor
    return clima


def correr(corrutina):
    return asyncio.run(corrutina)
