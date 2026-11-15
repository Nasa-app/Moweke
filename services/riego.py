"""
Cuando regar -- lo que el balance de agua del cultivo (motor_estres.balance_agua_fao56) dice del
agua del suelo hoy y de los proximos dias.

El balance lleva el agotamiento de la zona de raices (Dr). El cultivo no sufre mientras Dr no pase
RAW = p * TAW; pasado ese punto empieza a transpirar menos (Ks < 1). Regar cuando Dr llega a RAW es la
regla de FAO-56 (cap. 8): aca se busca el primer dia, desde hoy y dentro de lo observado y del
pronostico, en que eso ocurre, y cuantos milimetros hacen falta para volver a llenar la zona.

Es una estimacion, no una medicion: no hay sensor de humedad. Los limites reales son los del
balance -- agua aprovechable del suelo (medida por CLSoilMaps o un valor por defecto), lluvia y
ET0 de modelo, riegos que el agricultor declaro, sin escorrentia ni intercepcion. Lo que viene mas
alla del pronostico (el 'estimado' del ano anterior) no entra: no es una referencia para decidir.
"""
from __future__ import annotations

import pandas as pd

HORIZONTES_VALIDOS = ("observado", "pronostico")
_TOLERANCIA_MM = 1e-6


def recomendar_riego(agua: pd.DataFrame, taw_mm: float, raw_mm: float, horizonte: pd.Series, hoy,
                     siembra, madurez=None, ultimo_riego=None) -> dict:
    """agua: la salida del balance (columnas `agua`, fraccion de TAW disponible, y `ks`), con el mismo
    indice diario que `horizonte` ('observado' | 'pronostico' | 'estimado' por dia). `madurez`: la fecha
    de la ultima etapa, o None si la serie no la alcanza. Devuelve siempre un dict con `estado`:

      sin_sembrar     la siembra es futura: no hay nada que regar
      fuera_de_ciclo  el cultivo ya llego a madurez
      regar_ya        hoy el agotamiento ya llego a RAW
      proximos_dias   llega a RAW dentro del pronostico (`fecha_limite`, `dias_para_riego`)
      sin_necesidad   no llega a RAW en lo que cubre el pronostico (`dias_revisados`)

    `disponible` es False (con `motivo`) si no hay clima observado o de pronostico para hoy."""
    hoy, siembra = pd.Timestamp(hoy).normalize(), pd.Timestamp(siembra).normalize()
    if hoy < siembra:
        return {"disponible": True, "estado": "sin_sembrar"}
    if madurez is not None and hoy > pd.Timestamp(madurez).normalize():
        return {"disponible": True, "estado": "fuera_de_ciclo"}
    validos = horizonte.index[horizonte.isin(HORIZONTES_VALIDOS)]
    if len(validos) == 0 or hoy not in agua.index or hoy > validos.max():
        return {"disponible": False, "motivo": "sin_clima_para_hoy"}

    fin = validos.max() if madurez is None else min(validos.max(), pd.Timestamp(madurez).normalize())
    tramo = agua.loc[hoy:fin]
    agotamiento = (1.0 - tramo["agua"]) * taw_mm
    llega = agotamiento >= raw_mm - _TOLERANCIA_MM

    resultado = {
        "disponible": True, "estado": "sin_necesidad",
        "agua_pct": round(float(tramo["agua"].iloc[0]) * 100), "umbral_pct": round((1.0 - raw_mm / taw_mm) * 100),
        "ks_hoy": round(float(tramo["ks"].iloc[0]), 2), "capacidad_zona_raices_mm": round(taw_mm),
        "lamina_mm": None, "fecha_limite": None, "dias_para_riego": None,
        "dias_revisados": int((fin - hoy).days),
        "ultimo_riego": None if ultimo_riego is None else pd.Timestamp(ultimo_riego).date().isoformat(),
    }
    if llega.any():
        dia = llega.index[llega.to_numpy().argmax()]
        resultado.update(estado="regar_ya" if dia == hoy else "proximos_dias",
                         lamina_mm=round(float(agotamiento.loc[dia])),
                         fecha_limite=dia.date().isoformat(), dias_para_riego=int((dia - hoy).days))
    return resultado
