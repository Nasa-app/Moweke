"""Cambios fuertes de clima en el predio, mirando de hoy hacia adelante (pronostico incluido).

Es independiente del cultivo: avisa que el tiempo va a cambiar o a ser extremo, no que algo se dañe (eso lo dicen
los eventos de dano de la fenologia). Los umbrales son una primera referencia para Chiloe, NO estan calibrados con
datos del predio ni con las tolerancias de cada especie: ajustarlos con la comunidad antes de tratarlos como oficiales.

Cada alerta junta los dias seguidos con la misma condicion: {tipo, primer_dia, ultimo_dia, valor, horizonte}.
`valor` es el extremo del tramo (minima mas baja, maxima mas alta, lluvia mas fuerte o el salto mayor entre dos dias)."""
from __future__ import annotations

import pandas as pd

HELADA_C = 0.0              # minima igual o menor: helada
HELADA_FUERTE_C = -3.0      # minima igual o menor: helada fuerte
CALOR_C = 27.0              # maxima igual o mayor: calor fuerte para el sur de Chile
SALTO_C = 7.0               # cambio de la maxima de un dia al siguiente: calentamiento o enfriamiento brusco
LLUVIA_FUERTE_MM = 30.0     # lluvia de un dia igual o mayor

TIPOS = ("helada", "calor", "lluvia_fuerte", "calentamiento_brusco", "enfriamiento_brusco")


def _tramos(dias: pd.Series) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Los dias en que `dias` es verdadero, juntando los consecutivos en tramos (primero, ultimo)."""
    tramos: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    for fecha in dias.index[dias.to_numpy(dtype=bool)]:
        if tramos and fecha - tramos[-1][1] == pd.Timedelta(days=1):
            tramos[-1] = (tramos[-1][0], fecha)
        else:
            tramos.append((fecha, fecha))
    return tramos


def cambios_fuertes(clima: pd.DataFrame, hoy: str) -> list[dict]:
    """`clima`: un dia por fila (indice de fechas) con tmin, tmax, lluvia y horizonte ('observado' | 'pronostico').
    Devuelve las alertas desde `hoy` (el dia anterior solo sirve para medir el salto de la maxima), ordenadas por
    fecha. Los dias sin dato no alertan."""
    if clima is None or clima.empty:
        return []
    clima = clima.sort_index()
    salto = clima["tmax"].diff()
    desde = pd.Timestamp(hoy)
    condiciones = {
        "helada": (clima["tmin"] <= HELADA_C, clima["tmin"], "min"),
        "calor": (clima["tmax"] >= CALOR_C, clima["tmax"], "max"),
        "lluvia_fuerte": (clima["lluvia"] >= LLUVIA_FUERTE_MM, clima["lluvia"], "max"),
        "calentamiento_brusco": (salto >= SALTO_C, salto, "max"),
        "enfriamiento_brusco": (salto <= -SALTO_C, salto, "min"),
    }
    alertas = []
    for tipo, (cumple, medida, extremo) in condiciones.items():
        cumple = (cumple & (clima.index >= desde)).fillna(False)
        for primero, ultimo in _tramos(cumple):
            valores = medida.loc[primero:ultimo]
            alertas.append({
                "tipo": tipo,
                "primer_dia": primero.date().isoformat(), "ultimo_dia": ultimo.date().isoformat(),
                "valor": round(float(valores.min() if extremo == "min" else valores.max()), 1),
                "horizonte": str(clima.loc[primero, "horizonte"]),
                "fuerte": bool(tipo == "helada" and valores.min() <= HELADA_FUERTE_C),
            })
    return sorted(alertas, key=lambda a: (a["primer_dia"], a["tipo"]))
