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

import unicodedata
from itertools import product

import numpy as np
import pandas as pd

from motor_estres import balance_agua, contingencia, evaluar
from pheno_engine import simular

PESOS = dict(riesgo=0.35, peor_ano=0.20, diversidad=0.15, precedente=0.15, cobertura=0.15)
# Con la fertilidad declarada 'low' entra un sexto criterio: cuanto de la rotacion repone nitrogeno o cubre el suelo.
PESOS_FERTILIDAD_BAJA = dict(riesgo=0.30, peor_ano=0.15, diversidad=0.10, precedente=0.15, cobertura=0.10, fertilidad=0.20)
DIAS_COSECHA, MAX_BARBECHO = 14, 270
# Familias que no pueden ir una tras otra porque consumen lo mismo y comparten plagas y enfermedades. Se compara el
# comienzo del nombre, sin tildes ni mayusculas: cubre 'solanaceas' (seed) y 'Solanaceae' (EcoCrop).
FAMILIAS_SIN_SEGUIDAS = ("solanac",)
MAX_ESPECIES = 6      # tope de especies que entran a buscar(): 6 ** 5 = 7.776 secuencias como maximo


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
    return rellenar_no_modelados(tabla)


def rellenar_no_modelados(tabla, piso=0.0, por_defecto=None):
    """Da a cada cultivo no modelado el riesgo medio, ano a ano, de los modelados y viables. `piso`: perdida minima
    del relleno (un cultivo sin modelar nunca queda con riesgo cero); `por_defecto`: perdida constante para cuando no
    hay ningun modelado y viable que promediar (None deja lo que traia)."""
    ref = [v["perdidas"] for v in tabla.values() if v["modelado"] and v["viable"]]
    for v in tabla.values():
        if v["modelado"]:
            continue
        if ref:
            v["perdidas"] = np.maximum(np.mean(ref, axis=0), piso)
        elif por_defecto is not None:
            v["perdidas"] = np.full(len(v["perdidas"]), max(por_defecto, piso))
        elif piso:
            v["perdidas"] = np.maximum(v["perdidas"], piso)
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


def _sin_tildes(texto):
    base = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in base if not unicodedata.combining(c)).lower().strip()


def _grupo_sin_seguidas(familia):
    f = _sin_tildes(familia)
    return next((g for g in FAMILIAS_SIN_SEGUIDAS if f.startswith(g)), None)


def par_prohibido(a, b, perfil):
    """True si `a` y `b` son de la misma familia de FAMILIAS_SIN_SEGUIDAS (solanaceas con solanaceas). Un cultivo sin
    perfil no se juzga."""
    if a not in perfil or b not in perfil:
        return False
    grupo = _grupo_sin_seguidas(perfil[a].get("familia"))
    return grupo is not None and grupo == _grupo_sin_seguidas(perfil[b].get("familia"))


def sin_familia_seguida(seq, perfil):
    """Ninguna temporada de la rotacion va seguida de una de su misma familia restringida. Es ciclica: tras la ultima
    temporada vuelve la primera."""
    L = len(seq)
    return not any(par_prohibido(seq[i], seq[(i + 1) % L], perfil) for i in range(L))


def cumple_historial(seq, previos, perfil, extra=None):
    """`previos`: lo sembrado hasta ahora, del mas antiguo al mas reciente; `seq` empieza en la temporada siguiente.
    Respeta el intervalo contra la siembra previa mas reciente de cada cultivo y la regla de familias contra el ultimo
    previo. Un previo sin perfil no se juzga."""
    previos = list(previos)
    if not previos:
        return True
    if par_prohibido(previos[-1], seq[0], perfil):
        return False
    for n in set(seq):
        if n not in perfil:
            continue
        ultimo = max((i for i, p in enumerate(previos) if p == n), default=None)
        if ultimo is None:
            continue
        req = perfil[n]["intervalo"] + (extra or {}).get(n, 0)
        entre = (len(previos) - 1 - ultimo) + seq.index(n)     # temporadas entre esa siembra y la de la rotacion
        if entre < req:
            return False
    return True


def inicio_desde_historial(seq, previos, perfil, extra=None):
    """La primera rotacion del ciclo (el mismo ciclo empezando en otra temporada) que cumple el historial, o None."""
    seq = tuple(seq)
    for i in range(len(seq)):
        giro = seq[i:] + seq[:i]
        if cumple_historial(giro, previos, perfil, extra):
            return giro
    return None


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
    if "fertilidad" in pesos:
        repone = np.mean([bool(perfil[n]["legum"] or perfil[n].get("perenne")) for n in seq])
        crit["fertilidad"] = min(1.0, float(repone) / 0.5)    # credito completo desde la mitad de las temporadas
    crit["total"] = sum(pesos[k] * crit[k] for k in pesos)
    crit["anos"], crit["max_barbecho"] = round(total / 365, 1), max_gap
    return crit


def buscar(tablas, perfil, largos=(3, 4, 5), pesos=PESOS, extra_intervalo=None, top=5, previos=(),
           max_especies=MAX_ESPECIES):
    """tablas {escenario: tabla}. Una rotacion vale lo que vale en su peor escenario. Descarta por intervalo
    sanitario, por familias seguidas, por historial (`previos`) y por calendario; `seq` sale empezando en la primera
    temporada del ciclo que cumple el historial. Las viables se ordenan por riesgo medio y solo entran `max_especies`:
    las demas quedan en `recortadas` (el tope acota el producto cartesiano a max_especies ** largo)."""
    previos = tuple(previos)
    viables = [n for n in perfil if all(t[n]["viable"] for t in tablas.values())]
    riesgo = lambda n: float(np.mean([np.mean(t[n]["perdidas"]) for t in tablas.values()]))
    viables.sort(key=lambda n: (riesgo(n), n))
    recortadas = viables[max_especies:]
    viables = viables[:max_especies]
    vistos, res = set(), []
    descartes = dict(intervalo=0, familia=0, historial=0, calendario=0)
    for L in largos:
        for seq in product(viables, repeat=L):
            seq = canonica(seq)
            if seq in vistos:
                continue
            vistos.add(seq)
            if not cumple_intervalo(seq, perfil, extra_intervalo):
                descartes["intervalo"] += 1
                continue
            if not sin_familia_seguida(seq, perfil):
                descartes["familia"] += 1
                continue
            seq = inicio_desde_historial(seq, previos, perfil, extra_intervalo)
            if seq is None:
                descartes["historial"] += 1
                continue
            por_esc = {e: puntuar(seq, t, perfil, pesos) for e, t in tablas.items()}
            if any(c["max_barbecho"] > MAX_BARBECHO for c in por_esc.values()):
                descartes["calendario"] += 1
                continue
            peor = min(por_esc, key=lambda e: por_esc[e]["total"])
            res.append(dict(rotacion=" > ".join(seq), seq=seq, puntaje=round(por_esc[peor]["total"], 3),
                            peor_escenario=peor, **{k: round(v, 2) for k, v in por_esc[peor].items() if k != "total"}))
    res.sort(key=lambda r: (-r["puntaje"], r["seq"]))
    return res[:top], dict(viables=viables, recortadas=recortadas, evaluadas=len(res), **descartes)


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
