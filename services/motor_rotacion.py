"""
Motor de rotacion v0.1  (se apoya en pheno_engine.py y motor_estres.py)
========================================================================
1. Evalua cada cultivo en cada escenario: cierra ciclo, duracion, perdida ano a ano.
2. Genera todas las secuencias de 3 a 5 temporadas.
3. Descarta las que rompen una regla dura (viabilidad, intervalo sanitario, calendario).
4. Puntua el resto con cinco criterios y se queda con el puntaje del PEOR escenario.
5. Plan B: si un cultivo de la rotacion se pierde, que alcanza a sembrarse en su lugar.

ADVERTENCIA: parametros de cultivos, reglas de dano, intervalos sanitarios, bonificaciones
y pesos son valores de partida NO VERIFICADOS. Sin rendimientos, el puntaje ORDENA
rotaciones; no dice cuanto mas producen.

Este archivo NO conoce ninguna especie por nombre ni tiene PERFIL/CULTIVOS/REGLAS
hardcodeados. Todas las funciones reciben `cultivos` ({nombre: Cultivo}), `perfil`
({nombre: dict}) y `reglas` ({nombre: tuple[Regla,...]}) ya construidos por el llamador
-- normalmente via services/catalogo_especies.construir_catalogo() sobre la base de
datos (database/seed_especies.sql). Ver services/catalogo_especies.py.

Correccion sobre el borrador original: evaluar_cultivos() ya NO asume riesgo cero para
un cultivo sin entrada en `reglas`. Antes, solo "pradera" (perenne=True) recibia el relleno
neutro (riesgo medio de los cultivos modelados); cualquier otro cultivo sin reglas
quedaba con perdidas=[0,0,...] siempre, lo que le daria ventaja artificial en buscar()
frente a un cultivo que si tiene su riesgo modelado. Ahora "sin reglas" se trata igual
que "perenne": modelado=False, relleno neutro. Esto importaba en la practica: ajo_chilote
y haba no tenian entrada en reglas hasta que se agrego en database/seed_especies.sql.
"""
from __future__ import annotations

from itertools import product

import numpy as np
import pandas as pd

from motor_estres import balance_agua, contingencia, evaluar
from pheno_engine import simular

PESOS = dict(riesgo=0.35, peor_ano=0.20, diversidad=0.15, precedente=0.15, cobertura=0.15)
DIAS_COSECHA, MAX_BARBECHO = 14, 270


# ---------------------------------------------------------------- 1. Evaluacion por cultivo
def evaluar_cultivos(clima, anos, lat, cap, cultivos, perfil, reglas, max_ciclo=330):
    """cultivos/perfil/reglas: diccionarios ya construidos (ver catalogo_especies).
    Un nombre en `perfil` sin entrada correspondiente en `cultivos` (perenne, o especie
    sin umbral_fenologico_config todavia) no se simula -- recibe el relleno neutro."""
    agua = balance_agua(clima, lat, cap)
    tabla = {}
    for n, p in perfil.items():
        sin_reglas = len(reglas.get(n, ())) == 0
        if p.get("perenne") or n not in cultivos or sin_reglas:
            # No modelado (perenne sin riesgo de clima definido, sin Cultivo construible
            # todavia, o sin reglas de dano): se rellena abajo con el riesgo medio de los
            # modelados y viables, nunca con cero -- cero seria una ventaja artificial.
            tabla[n] = dict(viable=True, dur=365 - DIAS_COSECHA if p.get("perenne") else np.nan,
                            perdidas=np.zeros(len(anos)), cierra=1.0, p_perdido=0.0, modelado=False)
            continue
        c, durs, perd = cultivos[n], [], []
        for a in anos:
            s = pd.Timestamp(a, *p["siembra"])
            fechas = simular(clima, s, lat, c)
            fin = fechas.get(c.etapas[-1][0])
            if fin is None or (fin - s).days > max_ciclo:
                durs.append(np.nan)
                perd.append(1.0)
                continue
            durs.append((fin - s).days)
            perd.append(evaluar(clima, agua, s, fechas, c, reglas.get(n, ()))["perdida"])
        durs, perd = np.array(durs), np.array(perd)
        cierra, p_perdido = float(np.mean(~np.isnan(durs))), float(np.mean(perd >= 1.0))
        tabla[n] = dict(viable=cierra >= 0.8 and p_perdido <= 0.3,
                        dur=float(np.nanpercentile(durs, 80)) if cierra > 0 else np.nan,
                        perdidas=perd, cierra=cierra, p_perdido=p_perdido, modelado=True)
    ref = [v["perdidas"] for v in tabla.values() if v["modelado"] and v["viable"]]
    for v in tabla.values():
        if not v["modelado"] and ref:
            v["perdidas"] = np.mean(ref, axis=0)
    return tabla


# ---------------------------------------------------------------- 2. Reglas duras
def canonica(seq):
    return min(tuple(seq[i:] + seq[:i]) for i in range(len(seq)))


def cumple_intervalo(seq, perfil, extra=None):
    """extra {cultivo: temporadas adicionales} por inoculo declarado en el historial del predio."""
    L = len(seq)
    for n in set(seq):
        req = perfil[n]["intervalo"] + (extra or {}).get(n, 0)
        pos = [i for i, x in enumerate(seq) if x == n]
        for k, i in enumerate(pos):
            j = pos[(k + 1) % len(pos)]
            sep = (j - i) % L or L
            if sep - 1 < req:
                return False
    return True


def _prox_fecha(md, desde):
    f = pd.Timestamp(desde.year, *md)
    return f if f >= desde else pd.Timestamp(desde.year + 1, *md)


def linea_tiempo(seq, tabla, perfil, ano0=2001):
    """Encadena siembras y cosechas. El siguiente cultivo se siembra en su primera fecha
    posible despues de la cosecha del anterior. Devuelve tramos, dias totales y mayor barbecho."""
    seq = list(seq)
    k = next((i for i, n in enumerate(seq) if not perfil[n].get("perenne")), 0)
    seq = seq[k:] + seq[:k]
    tramos, t, max_gap, dias_cultivo = [], None, 0, 0
    for n in seq + [seq[0]]:
        p = perfil[n]
        if p.get("perenne"):
            s = t if t is not None else pd.Timestamp(ano0, 1, 1)
        else:
            s = _prox_fecha(p["siembra"], t) if t is not None else pd.Timestamp(ano0, *p["siembra"])
        if t is not None:
            max_gap = max(max_gap, (s - t).days)
        if len(tramos) == len(seq):
            total = (s - tramos[0][1]).days
            break
        ocup = int(tabla[n]["dur"]) + DIAS_COSECHA
        t = s + pd.Timedelta(days=ocup)
        dias_cultivo += ocup
        tramos.append((n, s, t))
    return tramos, total, max_gap, dias_cultivo


# ---------------------------------------------------------------- 3. Puntaje
def puntuar(seq, tabla, perfil, pesos=PESOS):
    perd = np.array([tabla[n]["perdidas"] for n in seq])
    tramos, total, max_gap, dias_cultivo = linea_tiempo(seq, tabla, perfil)
    L, trans = len(seq), []
    for i in range(L):
        a, b = perfil[seq[i]], perfil[seq[(i + 1) % L]]
        trans.append(1 if a["legum"] and b["exigente"] else -1 if a["familia"] == b["familia"] else 0)
    crit = dict(
        riesgo=1 - float(perd.mean()),
        peor_ano=1 - float(perd.mean(axis=0).max()),   # como si cada fase estuviera presente cada ano
        diversidad=len(set(seq)) / L,
        precedente=(float(np.mean(trans)) + 1) / 2,
        cobertura=min(1.0, dias_cultivo / total),
    )
    crit["total"] = sum(pesos[k] * crit[k] for k in pesos)
    crit["anos"], crit["max_barbecho"] = round(total / 365, 1), max_gap
    return crit


def buscar(tablas, perfil, largos=(3, 4, 5), pesos=PESOS, extra_intervalo=None, top=5):
    """tablas {escenario: tabla}. Una rotacion vale lo que vale en su peor escenario."""
    viables = [n for n in perfil if all(t[n]["viable"] for t in tablas.values())]
    vistos, res, descartes = set(), [], dict(intervalo=0, calendario=0)
    for L in largos:
        for seq in product(viables, repeat=L):
            seq = canonica(seq)
            if seq in vistos:
                continue
            vistos.add(seq)
            if not cumple_intervalo(seq, perfil, extra_intervalo):
                descartes["intervalo"] += 1
                continue
            por_esc = {e: puntuar(seq, t, perfil, pesos) for e, t in tablas.items()}
            if any(c["max_barbecho"] > MAX_BARBECHO for c in por_esc.values()):
                descartes["calendario"] += 1
                continue
            peor = min(por_esc, key=lambda e: por_esc[e]["total"])
            res.append(dict(rotacion=" > ".join(seq), seq=seq, puntaje=round(por_esc[peor]["total"], 3),
                            peor_escenario=peor, **{k: round(v, 2) for k, v in por_esc[peor].items() if k != "total"}))
    res.sort(key=lambda r: -r["puntaje"])
    return res[:top], dict(viables=viables, evaluadas=len(res), **descartes)


# ---------------------------------------------------------------- 4. Plan B por posicion
def plan_b(seq, clima, tabla, lat, cap, cultivos, perfil, reglas, ano0=2019):
    """Para cada cultivo de la rotacion: si se pierde a mitad de ciclo, que alcanza a madurar
    antes de la siembra del cultivo siguiente. No revisa el intervalo sanitario del reemplazo."""
    tramos = linea_tiempo(seq, tabla, perfil, ano0)[0]
    cand = {n: c for n, c in cultivos.items() if not perfil.get(n, {}).get("perenne")}
    out = []
    for i, (n, s, h) in enumerate(tramos):
        if perfil[n].get("perenne"):
            continue
        sig = tramos[(i + 1) % len(tramos)][0]
        if perfil[sig].get("perenne"):   # la siembra de pradera se puede postergar
            limite = h + pd.Timedelta(days=90)
        else:
            limite = _prox_fecha(perfil[sig]["siembra"], h) - pd.Timedelta(days=DIAS_COSECHA)
        golpe = s + (h - s) / 2
        if limite > clima.index[-1]:
            continue
        r = contingencia(clima, golpe.normalize(), limite, lat, cand, reglas, cap)
        caben = r[r.cabe].cultivo.tolist()
        out.append(dict(cultivo=n, perdida_el=golpe.date(), limite=limite.date(), alcanzan=caben or ["ninguno"]))
    return pd.DataFrame(out)
