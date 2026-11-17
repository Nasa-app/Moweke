"""
Motor fenologico v0.1
=====================
Reloj de desarrollo de cultivos + integracion de indicadores fenologicos locales.

Un mismo motor sirve a dos modos:
  - operativo  : clima observado + pronostico  -> etapa actual, fechas proyectadas, alertas
  - estrategico: series diarias de escenario   -> calendario futuro, sincronia con indicadores

Entrada de clima: DataFrame con indice de fechas diario y columnas tmin, tmax (C), lluvia (mm),
y opcionalmente rh (humedad relativa %, de POWER RH2M) para el riesgo de tizon.

Este archivo NO conoce ninguna especie por nombre ni tiene parametros de cultivo
hardcodeados -- Cultivo se construye en tiempo de ejecucion desde la base de datos
(services/catalogo_especies.py, sobre database/seed_especies.sql). Las funciones de
abajo solo trabajan con el objeto Cultivo que les pasen.

Cubre el nucleo biofisico y de calibracion con indicadores. No integra satelite
(HLS/EVI), no corre el dispatcher por bioma, y no tiene I/O con la base de datos mas
alla de lo que catalogo_especies le entrega ya construido — eso vive en la capa que
llama a este motor (docs/arquitectura-flujos-mogen.md, Flujo 4).
`actualizar_calendario_con_confirmacion`, mas abajo, es el punto de enganche para
reanclar el reloj a la ultima etapa confirmada por el agricultor.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- 1. Biofisica base
_H = (np.arange(8) + 0.5) / 8  # 8 pasos de 3 horas


def tiempo_termico_diario(tmin, tmax, tb, to, tc):
    """Grados-dia efectivos con tres temperaturas cardinales (base, optima, critica).
    Se integra sobre 8 temperaturas subdiarias para no subestimar dias que cruzan tb u to."""
    tmin = np.asarray(tmin, float)[:, None]
    tmax = np.asarray(tmax, float)[:, None]
    t = tmin + (tmax - tmin) * 0.5 * (1 + np.cos(2 * np.pi * (_H - 0.6)))
    te = np.where(t <= to, t - tb, (to - tb) * (tc - t) / (tc - to))
    return np.clip(te, 0, None).mean(axis=1)


def fotoperiodo(lat, doy, crepusculo=-6.0):
    """Horas de luz incluyendo crepusculo civil. Depende solo de latitud y dia del ano:
    no cambia con el clima, por eso limita el traslado de cultivos entre latitudes."""
    decl = np.radians(23.45 * np.sin(np.radians(360 * (284 + np.asarray(doy)) / 365)))
    lat_r = np.radians(lat)
    cos_h = (np.sin(np.radians(crepusculo)) - np.sin(lat_r) * np.sin(decl)) / (
        np.cos(lat_r) * np.cos(decl)
    )
    return 2 * np.degrees(np.arccos(np.clip(cos_h, -1, 1))) / 15


@dataclass(frozen=True)
class Cultivo:
    nombre: str
    tb: float
    to: float
    tc: float
    etapas: tuple            # ((nombre, grados-dia desde la etapa anterior), ...)
    moduladas: tuple = ()    # etapas cuya tasa se frena por fotoperiodo / vernalizacion
    foto_critico: float = 0  # h; bajo este valor una planta de dia largo se retrasa
    foto_sens: float = 0     # fraccion de tasa perdida por hora bajo el critico
    vern_req: float = 0      # dias de frio efectivo requeridos (0 = sin requerimiento)
    ventanas: tuple = ()     # ((etapa_ini, etapa_fin|None, peligro, umbral), ...)


def _tasas(df, lat, c, delta):
    tt = tiempo_termico_diario(df.tmin + delta, df.tmax + delta, c.tb, c.to, c.tc)
    f = np.ones(len(df))
    if c.foto_sens:
        luz = fotoperiodo(lat, df.index.dayofyear.values)
        f *= np.clip(1 - c.foto_sens * (c.foto_critico - luz), 0.1, 1)
    if c.vern_req:
        tmed = (df.tmin + df.tmax).values / 2 + delta
        frio = np.interp(tmed, [-1, 3, 10, 15], [0, 1, 1, 0]).cumsum()
        f *= np.clip(frio / c.vern_req, 0.1, 1)
    return tt, f


class ClimaIncompleto(ValueError):
    """tmin/tmax tienen NaN en el rango simulado. Sin esto, un solo dia sin dato (POWER
    devuelve -999 en huecos -- ver services/cliente_power.py) hace que `acum` se vuelva
    NaN para siempre y la etapa nunca se alcance, en silencio, sin ningun error. Rellenar
    el hueco es responsabilidad de quien llama (interpolacion, o lo que corresponda segun
    cuanto dura el hueco) -- este motor no decide eso por su cuenta, solo se niega a
    simular sobre un hueco sin rellenar en vez de producir una fecha equivocada callada."""


def simular(clima, siembra, lat, c, delta=0.0):
    """Fechas de cada etapa. delta = correccion de microclima (C) sobre la grilla."""
    df = clima.loc[pd.Timestamp(siembra):]
    if df[["tmin", "tmax"]].isna().any().any():
        dias_con_hueco = df.index[df[["tmin", "tmax"]].isna().any(axis=1)]
        raise ClimaIncompleto(
            f"{len(dias_con_hueco)} dia(s) sin tmin/tmax entre {dias_con_hueco[0].date()} y "
            f"{dias_con_hueco[-1].date()} -- rellenar antes de llamar a simular()."
        )
    tt, f = _tasas(df, lat, c, delta)
    fechas, i, acum = {}, 0, 0.0
    for d in range(len(df)):
        nombre, meta = c.etapas[i]
        acum += tt[d] * (f[d] if nombre in c.moduladas else 1.0)
        if acum >= meta:
            fechas[nombre] = df.index[d]
            acum -= meta
            i += 1
            if i == len(c.etapas):
                break
    return fechas


# ---------------------------------------------------------------- 2. Indicador local
@dataclass(frozen=True)
class Indicador:
    """Evento observado por la comunidad (floracion de una planta, etc.).
    Si termico=True se modela como suma termica desde `inicio` (mes, dia)."""
    nombre: str
    inicio: tuple = (6, 21)
    tb: float = 0.0
    theta: float | None = None
    termico: bool = True


def _suma_indicador(clima, ano, ind, delta):
    ini = pd.Timestamp(ano, *ind.inicio)
    s = clima.loc[ini: ini + pd.Timedelta(days=300)]
    return np.clip((s.tmin + s.tmax) / 2 + delta - ind.tb, 0, None).cumsum()


def fecha_indicador(clima, ano, ind, delta=0.0):
    s = _suma_indicador(clima, ano, ind, delta)
    k = int(np.searchsorted(s.values, ind.theta))
    return s.index[k] if k < len(s) else pd.NaT


def ajustar_indicador(clima, observaciones, ind, tbs=np.arange(0, 8.5, 0.5), min_n=3):
    """Estima tb y theta desde fechas observadas {ano: fecha}.
    Debe hacerse donde la temperatura esta MEDIDA (estacion cercana). Si se ajusta con
    la grilla del mismo predio, theta absorbe el sesgo de microclima y la via 1 no sirve."""
    if len(observaciones) < min_n:
        raise ValueError(f"se requieren al menos {min_n} anos de observaciones")
    mejor = None
    for tb in tbs:
        cand = replace(ind, tb=float(tb))
        sumas = [
            _suma_indicador(clima, a, cand, 0.0).loc[pd.Timestamp(f)]
            for a, f in observaciones.items()
        ]
        cand = replace(cand, theta=float(np.mean(sumas)))
        err = [
            (fecha_indicador(clima, a, cand) - pd.Timestamp(f)).days
            for a, f in observaciones.items()
        ]
        rmse = float(np.sqrt(np.mean(np.square(err))))
        if mejor is None or rmse < mejor[1]:
            mejor = (cand, rmse)
    return mejor


# ---- via 1: corrector de microclima
def delta_microclima(clima_grilla, ano, fecha_obs, ind, rango=(-6.0, 6.0)):
    """Ajuste de temperatura que hace coincidir la suma termica de la grilla con la fecha
    en que la comunidad observo el indicador. El indicador actua como termometro biologico.

    Reemplaza al "sesgo_parcela_dias" del modelo conceptual: un delta de temperatura se
    traslada correctamente al evaluar cualquier otro cultivo en el mismo predio, porque
    entra directo al calculo de GDD. Un offset fijo de dias no se traslada entre cultivos
    con sensibilidad termica distinta."""
    f = pd.Timestamp(fecha_obs)
    lo, hi = rango
    for _ in range(40):
        mid = (lo + hi) / 2
        if _suma_indicador(clima_grilla, ano, ind, mid).loc[f] < ind.theta:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 2)


# ---- via 2: punto de partida del reloj
def simular_desde_indicador(clima, fecha_indicador_obs, lat, c, dias_despues=0, delta=0.0):
    """Regla tradicional 'se siembra cuando ocurre X'. Vale para cualquier indicador,
    termico o no (aves, luna, estrellas)."""
    siembra = pd.Timestamp(fecha_indicador_obs) + pd.Timedelta(days=dias_despues)
    return siembra, simular(clima, siembra, lat, c, delta)


# ---- via 3: senal de como viene la temporada
def senal_estacional(historial, estado_actual, min_n=10):
    """historial: [(estado_indicador, tipo_temporada), ...] de anos pasados.
    Devuelve P(tipo | estado_actual) con suavizado de Laplace. Con menos de min_n anos
    devuelve la frecuencia base y usable=False: la senal se muestra, no se usa."""
    tipos = sorted({t for _, t in historial})
    base = {t: sum(1 for _, x in historial if x == t) / len(historial) for t in tipos}
    sub = [t for e, t in historial if e == estado_actual]
    if len(historial) < min_n or not sub:
        return {"p": base, "n": len(sub), "usable": False}
    p = {t: (sub.count(t) + 1) / (len(sub) + len(tipos)) for t in tipos}
    return {"p": p, "n": len(sub), "usable": True}


# ---- via 4: ajuste de la variedad local
def ajustar_variedad(clima, siembras, observadas, lat, c, delta=0.0):
    """Recalcula los grados-dia por etapa con fechas observadas por el usuario.
    siembras {ano: fecha}; observadas {ano: {etapa: fecha}}. Usa la mediana entre anos."""
    acum = {n: [] for n, _ in c.etapas}
    for ano, siembra in siembras.items():
        df = clima.loc[pd.Timestamp(siembra):]
        tt, f = _tasas(df, lat, c, delta)
        prev = pd.Timestamp(siembra) - pd.Timedelta(days=1)
        for n, _ in c.etapas:
            if n not in observadas[ano]:
                break
            fin = pd.Timestamp(observadas[ano][n])
            m = (df.index > prev) & (df.index <= fin)
            acum[n].append(float((tt[m] * (f[m] if n in c.moduladas else 1.0)).sum()))
            prev = fin
    nuevas = tuple((n, float(np.median(acum[n])) if acum[n] else t) for n, t in c.etapas)
    return replace(c, etapas=nuevas)


# ---- via 5: sincronia bajo escenarios
def sincronia(clima, anos, ind, c, lat, siembra_md, etapa, delta=0.0):
    """Desfase (dias) entre la etapa del cultivo y el indicador, ano por ano."""
    out = {}
    for a in anos:
        fi = fecha_indicador(clima, a, ind, delta)
        fc = simular(clima, pd.Timestamp(a, *siembra_md), lat, c, delta).get(etapa)
        if fc is not None and fi is not pd.NaT:
            out[a] = (fc - fi).days
    return out


def fuera_de_rango(desfases_esc, desfases_hist):
    lo, hi = min(desfases_hist.values()), max(desfases_hist.values())
    v = list(desfases_esc.values())
    return sum(1 for x in v if x < lo or x > hi) / len(v), (lo, hi)


# ---------------------------------------------------------------- 3. Alertas y confianza
def alertas(clima_dias, fechas, c, dias_cosecha=14):
    """Cruza clima diario (pronostico) con las ventanas sensibles del cultivo.

    'peligro' admite 'helada' (tmin), 'calor' (tmax), 'lluvia' (lluvia) y 'tizon'
    (humedad relativa sostenida, columna 'rh' en clima_dias — RH2M de NASA POWER).
    tizon no es booleano de un solo dia: se dispara si rh se mantiene >= umbral
    durante 'horas_consecutivas' dias seguidos dentro de la ventana, porque el riesgo
    real es de humectacion foliar sostenida, no de un pico aislado."""
    out = []
    for ventana in c.ventanas:
        ini, fin, peligro, umbral = ventana[:4]
        horas_consecutivas = ventana[4] if len(ventana) > 4 else 1
        if ini not in fechas:
            continue
        a = fechas[ini]
        b = fechas.get(fin, a + pd.Timedelta(days=dias_cosecha)) if fin else a + pd.Timedelta(days=dias_cosecha)
        p = clima_dias.loc[a:b]
        if peligro == "tizon":
            if "rh" not in p.columns:
                continue
            m = (p.rh >= umbral).rolling(horas_consecutivas, min_periods=horas_consecutivas).sum() >= horas_consecutivas
        else:
            m = {"helada": p.tmin <= umbral, "calor": p.tmax >= umbral, "lluvia": p.lluvia >= umbral}[peligro]
        for d in p.index[m.fillna(False) if hasattr(m, "fillna") else m]:
            out.append((d.date(), peligro, f"{ini}->{fin or 'cosecha'}"))
    return out


def confianza(componentes):
    """componentes {nombre: 0..1}. Manda el mas debil, y se informa cual es.

    Esto es la implementacion real de lo que el modelo conceptual describia como
    cuatro escalones categoricos (sin_referencia/referencia_local/calibrado_comunal/
    calibrado_predio). Las etiquetas A/B/C se derivan de este calculo continuo, no al
    reves — permite decir cual componente especifico es el limitante (anos de indicador,
    parametro de variedad, dato de suelo), no solo un nivel general."""
    nombre = min(componentes, key=componentes.get)
    v = componentes[nombre]
    return {"nivel": "A" if v >= 0.75 else "B" if v >= 0.5 else "C", "limitante": nombre, "valor": v}


# ---------------------------------------------------------------- 4. Reanclaje a confirmacion de campo
# Los parametros de cultivo (antes un diccionario CULTIVOS hardcodeado aqui) ahora se
# construyen en tiempo de ejecucion desde la base de datos -- ver services/catalogo_especies.py
# y database/seed_especies.sql. Este archivo no conoce ninguna especie por nombre.
def actualizar_calendario_con_confirmacion(clima, etapa_confirmada, fecha_confirmada, lat, c, delta=0.0):
    """Punto de enganche con Flujo 3/4 (docs/arquitectura-flujos-mogen.md): cuando llega
    un reporte de campo confirmando una etapa, el reloj se reancla a esa fecha real en vez
    de seguir acumulando desde la siembra original. Devuelve las fechas proyectadas para
    las etapas que quedan despues de la confirmada.

    No modifica `simular` — simplemente la vuelve a llamar desde el punto confirmado con
    las etapas restantes, que es la forma correcta de reanclar sin duplicar la logica del
    reloj."""
    idx = [n for n, _ in c.etapas].index(etapa_confirmada)
    restantes = c.etapas[idx + 1:]
    if not restantes:
        return {}
    c_restante = replace(c, etapas=restantes)
    return simular(clima, fecha_confirmada, lat, c_restante, delta)


# ---------------------------------------------------------------- 5. Utilidad de prueba
def clima_sintetico(inicio, fin, tmedia=10.5, amp=4.5, rango=7.0, calentamiento=0.0, seed=0):
    """Clima inventado, hemisferio sur templado. Solo para probar el codigo —
    usado por services/motor_estres.py y services/motor_rotacion.py en sus demos."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(inicio, fin, freq="D")
    doy = idx.dayofyear.values
    ruido = np.zeros(len(idx))
    for i in range(1, len(idx)):
        ruido[i] = 0.7 * ruido[i - 1] + rng.normal(0, 1.4)
    tmed = tmedia + calentamiento + amp * np.cos(2 * np.pi * (doy - 20) / 365) + ruido
    p_lluvia = 0.38 - 0.15 * np.cos(2 * np.pi * (doy - 20) / 365)
    lluvia = np.where(rng.random(len(idx)) < p_lluvia, rng.gamma(0.8, 9, len(idx)), 0.0)
    return pd.DataFrame({"tmin": tmed - rango / 2, "tmax": tmed + rango / 2, "lluvia": lluvia}, index=idx)
