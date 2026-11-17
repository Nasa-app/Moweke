"""
Motor de estres v0.1  (se apoya en pheno_engine.py)
====================================================
1. Balance de agua del suelo (balde simple) -> sequia y anegamiento pasan a existir.
2. Reglas de dano por fase: evento -> sin efecto / perdida parcial / perdida total / atraso.
3. Inyeccion de eventos extremos en cada fase -> matriz de vulnerabilidad.
4. Contingencia: tras una perdida, que cultivos aun cierran ciclo en la temporada.

Este archivo NO conoce ninguna especie por nombre ni tiene reglas de dano hardcodeadas
-- las reglas (Regla, mas abajo) se construyen en tiempo de ejecucion desde la base de
datos (services/catalogo_especies.construir_reglas, sobre database/seed_especies.sql).
Las funciones de este archivo reciben siempre `reglas` (o `reglas_por_cultivo`) como
parametro explicito, nunca lo buscan en un diccionario global.

Una tupla de reglas vacia NO significa "sin riesgo" -- significa "no esta modelado
todavia". evaluar_cultivos() en motor_rotacion.py trata eso con el mismo relleno neutro
que usa para la pradera, nunca como riesgo cero. contingencia(), mas abajo, hace lo mismo
explicitamente (estado 'sin_modelo_riesgo').
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from pheno_engine import simular

# ---------------------------------------------------------------- 1. Agua en el suelo
def radiacion_extraterrestre(lat, doy):
    """Ra en mm/dia de evaporacion equivalente (FAO-56)."""
    phi = np.radians(lat)
    doy = np.asarray(doy)
    dr = 1 + 0.033 * np.cos(2 * np.pi * doy / 365)
    dec = 0.409 * np.sin(2 * np.pi * doy / 365 - 1.39)
    ws = np.arccos(np.clip(-np.tan(phi) * np.tan(dec), -1, 1))
    ra = (24 * 60 / np.pi) * 0.0820 * dr * (
        ws * np.sin(phi) * np.sin(dec) + np.cos(phi) * np.cos(dec) * np.sin(ws)
    )
    return 0.408 * ra


def et0_hargreaves(clima, lat):
    """ET0 diaria (mm) de Hargreaves-Samani con tmin y tmax. Sobrestima en climas costeros humedos
    (depende de la raiz del rango diurno): se calibra por predio contra Penman-Monteith, ver
    factores_et0() y la tabla de calibracion de repositorio_clima."""
    ra = radiacion_extraterrestre(lat, clima.index.dayofyear.values)
    tmed = (clima.tmin.values + clima.tmax.values) / 2
    et0 = 0.0023 * ra * (tmed + 17.8) * np.sqrt(np.clip(clima.tmax.values - clima.tmin.values, 0, None))
    return np.clip(et0, 0, None)


def balance_agua(clima, lat, capacidad_mm, et0=None):
    """Balde diario. capacidad_mm = agua aprovechable del perfil (dato de suelo del usuario,
    o SoilGrids/CHLSOC/GAEZ mientras no haya dato local — ver seccion 10 del modelo conceptual).
    ET0 por Hargreaves (o la serie `et0` si se pasa); la extraccion cae linealmente bajo el 50% de
    la capacidad. Devuelve fraccion de agua disponible y exceso diario (mm que no caben).
    Es el balance de TODO el perfil, sin coeficiente de cultivo: sirve para el anegamiento
    ('exceso'). La sequia de un cultivo se calcula con balance_agua_fao56()."""
    et0 = et0_hargreaves(clima, lat) if et0 is None else np.asarray(et0, float)
    w, frac, exceso = capacidad_mm, np.empty(len(clima)), np.empty(len(clima))
    for i, lluvia in enumerate(clima.lluvia.values):
        w += lluvia
        exceso[i] = max(0.0, w - capacidad_mm)
        w = min(w, capacidad_mm)
        w = max(0.0, w - et0[i] * min(1.0, w / (0.5 * capacidad_mm)))
        frac[i] = w / capacidad_mm
    return pd.DataFrame({"agua": frac, "exceso": exceso, "et0": et0}, index=clima.index)


# ---------------------------------------------------------------- 1b. Balance de agua FAO-56 (por cultivo)
@dataclass(frozen=True)
class ParametrosAgua:
    """Lo que el balance de un cultivo necesita (FAO-56 tablas 12 y 22; Ky de FAO-33 tabla 24):
    profundidad efectiva de raices, fraccion de agotamiento sin estres, coeficientes de cultivo
    inicial, medio y final, y respuesta estacional del rendimiento al deficit de agua."""
    zr_m: float
    p: float
    kc_ini: float
    kc_med: float
    kc_fin: float
    ky: float


PROFUNDIDAD_SUELO_M = {"very_shallow": 0.15, "shallow": 0.35, "medium": 1.0, "deep": 2.0}   # centro de cada clase
PROFUNDIDAD_PERFIL_AWC_M = 2.0     # el agua aprovechable de CLSoilMaps es la de 0 a 200 cm
FRACCION_KC_MEDIA = 0.6            # de la ultima fase, tanto va con Kc medio antes de bajar al final (FAO-56, tabla 11)
LIMITES_FACTOR_ET0 = (0.4, 1.6)    # un factor de calibracion fuera de esto es un dato malo, no un clima


def factores_et0(factores_mensuales, indice):
    """Serie diaria de factores a partir de 12 valores (enero = indice 0). None -> sin calibrar (1)."""
    if factores_mensuales is None:
        return np.ones(len(indice))
    tabla = np.asarray(factores_mensuales, float)
    return tabla[np.asarray(indice.month) - 1]


def calibrar_et0_mensual(clima, et0_referencia, lat, min_dias_mes=10):
    """12 factores (enero primero) que llevan la ET0 de Hargreaves de `clima` (tmin, tmax) al nivel de una ET0 de
    referencia (Penman-Monteith): suma de la referencia sobre suma de Hargreaves en los dias en comun de cada mes.
    Un mes con menos de `min_dias_mes` dias en comun usa el factor de todo el traslape; se suaviza con los
    meses vecinos (1-2-1, circular) y se acota a LIMITES_FACTOR_ET0. Es la calibracion local de Hargreaves que
    recomienda FAO-56, hecha una vez por predio."""
    comun = clima[["tmin", "tmax"]].join(pd.Series(et0_referencia, name="ref"), how="inner").dropna()
    hs = pd.Series(et0_hargreaves(comun, lat), index=comun.index)
    if comun.empty or hs.sum() <= 0:
        return [1.0] * 12
    total = float(comun["ref"].sum() / hs.sum())
    crudo = {}
    for mes in range(1, 13):
        m = comun.index.month == mes
        crudo[mes] = float(comun.loc[m, "ref"].sum() / hs[m].sum()) if m.sum() >= min_dias_mes and hs[m].sum() > 0 else total
    lo, hi = LIMITES_FACTOR_ET0
    return [min(hi, max(lo, (crudo[(mes - 2) % 12 + 1] + 2 * crudo[mes] + crudo[mes % 12 + 1]) / 4)) for mes in range(1, 13)]


def kc_diario(indice, siembra, fechas, c, params):
    """Coeficiente de cultivo de cada dia. Antes de sembrar y mientras no emerge: Kc inicial; de la
    emergencia a la segunda etapa sube en linea recta al medio; luego se mantiene (FRACCION_KC_MEDIA
    de lo que queda hasta la madurez) y baja en linea recta al final; despues de la madurez, el final.
    Una etapa que la serie no alcanza deja la curva abierta hasta el ultimo dia."""
    dias = pd.DatetimeIndex(indice).normalize()
    siembra = pd.Timestamp(siembra).normalize()
    ultimo = dias[-1]
    nombres = [n for n, _ in c.etapas]
    t1 = fechas.get(nombres[0], ultimo)
    t2 = fechas.get(nombres[1], ultimo) if len(nombres) > 1 else fechas.get(nombres[-1], ultimo)
    tm = fechas.get(nombres[-1], ultimo)
    t1, t2, tm = pd.Timestamp(t1).normalize(), pd.Timestamp(t2).normalize(), pd.Timestamp(tm).normalize()
    t3 = t2 + (tm - t2) * FRACCION_KC_MEDIA
    kc = np.full(len(dias), params.kc_ini, float)
    en = lambda a, b: (dias >= a) & (dias < b)
    f_dev = np.clip((dias - t1) / max((t2 - t1), pd.Timedelta(days=1)), 0, 1)
    f_fin = np.clip((dias - t3) / max((tm - t3), pd.Timedelta(days=1)), 0, 1)
    kc = np.where(en(t1, t2), params.kc_ini + (params.kc_med - params.kc_ini) * f_dev, kc)
    kc = np.where(en(t2, t3), params.kc_med, kc)
    kc = np.where(en(t3, tm), params.kc_med + (params.kc_fin - params.kc_med) * f_fin, kc)
    kc = np.where(dias >= tm, params.kc_fin, kc)
    return pd.Series(kc, index=indice)


def zona_raices_mm(awc_total_mm, params, prof_suelo_m=None):
    """(TAW, RAW) en mm de la zona de raices: el agua aprovechable total y la parte que el cultivo
    saca sin sufrir (p * TAW). El suelo somero limita las raices aunque la especie llegue mas hondo."""
    zr = min(params.zr_m, prof_suelo_m) if prof_suelo_m else params.zr_m
    taw = max(awc_total_mm * min(1.0, zr / PROFUNDIDAD_PERFIL_AWC_M), 1e-6)
    return taw, params.p * taw


def balance_agua_fao56(clima, et0, kc, awc_total_mm, params, prof_suelo_m=None, riego=False, lat=None, riegos=()):
    """Balance diario de la zona de raices (FAO-56, cap. 8). TAW = agua aprovechable de la zona de
    raices = AWC de 0-200 cm repartida en proporcion a la profundidad que alcanzan las raices
    (supone el agua aprovechable uniforme en el perfil). RAW = p * TAW. Con agotamiento Dr
    mayor que RAW el cultivo transpira solo la fraccion Ks = (TAW - Dr) / (TAW - RAW) de su demanda
    ETc = Kc * ET0. Sin escorrentia ni intercepcion; el drenaje profundo es lo que sobra sobre cero
    agotamiento. `riego`: el agricultor repone el agua (Ks = 1); el exceso de lluvia se conserva.
    `riegos`: fechas en que el agricultor rego; cada una deja la zona de raices llena al empezar ese
    dia (se supone un riego completo: no se conoce la lamina aplicada).

    Devuelve por dia: agua (fraccion de TAW disponible), ks, etc, eta, et0, ky y `exceso` (mm de
    drenaje que no cupieron en TODO el perfil: lo que usan las reglas de anegamiento)."""
    taw, raw = zona_raices_mm(awc_total_mm, params, prof_suelo_m)
    et0 = np.asarray(et0, float)
    etc = np.asarray(kc, float) * et0
    lluvia = clima.lluvia.values
    n = len(clima)
    ks, eta, agua = np.ones(n), np.empty(n), np.empty(n)
    dias_de_riego = {pd.Timestamp(f).normalize() for f in riegos}
    dr = 0.0
    for i in range(n):
        if clima.index[i].normalize() in dias_de_riego:
            dr = 0.0
        ks[i] = 1.0 if riego or dr <= raw else max(0.0, (taw - dr) / (taw - raw))
        eta[i] = ks[i] * etc[i]
        dr = min(taw, max(0.0, dr - lluvia[i] + eta[i]))
        agua[i] = 1.0 - dr / taw
    out = pd.DataFrame({"agua": agua, "ks": ks, "etc": etc, "eta": eta, "et0": et0, "ky": params.ky}, index=clima.index)
    perfil = balance_agua(clima, lat if lat is not None else 0.0, max(awc_total_mm, 1e-6), et0=et0)
    out["exceso"] = perfil["exceso"].values
    return out


# ---------------------------------------------------------------- 2. Reglas de dano
@dataclass(frozen=True)
class Regla:
    fase: str        # "ini->fin", "cosecha" o "*" (cualquiera)
    peligro: str     # helada | calor | sequia | anegamiento | lluvia_cosecha | ceniza | tizon
    umbral: float    # C | fraccion de dias con agua < 30% | mm de exceso diario | mm acumulados | %RH
    minimo: int      # dias minimos que deben cumplir el umbral (para tizon: dias CONSECUTIVOS)
    efecto: str      # parcial | total | atraso
    valor: float = 0 # fraccion perdida (parcial) o dias (atraso)
    # Mitigacion por manejo real del predio (manejo_predio) -- pensado para peligros
    # bioticos (plagas/enfermedades) donde una practica humana cambia el resultado, a
    # diferencia de helada/calor/anegamiento que ningun insumo evita. Por eso solo
    # tiene efecto sobre 'parcial'/'atraso': una 'total' no se reduce por mitigacion
    # aqui (ver _reduccion_mitigacion) -- no usar mitigado_por en una regla 'total'.
    mitigado_por: str | None = None   # tipo_labor de manejo_predio que atenua esta regla (ej. 'fungicida')
    factor_mitigacion: float = 0.0    # fraccion de reduccion de 'valor' si se aplico dentro de la ventana
    ventana_mitigacion_dias: int = 0  # dias previos al primer dia del evento en que la aplicacion protege


R = Regla
REGLAS = {  # NO VERIFICADO
    "trigo_primavera": (
        R("emergencia->encanado", "helada", -8, 1, "parcial", 0.3),
        R("encanado->antesis", "helada", -1, 1, "parcial", 0.5),
        R("encanado->antesis", "helada", -5, 1, "total"),
        R("antesis->madurez", "helada", -1, 1, "parcial", 0.4),
        R("encanado->antesis", "calor", 32, 2, "parcial", 0.2),
        R("antesis->madurez", "calor", 32, 3, "parcial", 0.3),
        R("encanado->antesis", "sequia", 0.5, 0, "parcial", 0.3),
        R("antesis->madurez", "sequia", 0.5, 0, "parcial", 0.3),
        R("siembra->emergencia", "anegamiento", 20, 3, "parcial", 0.3),
        R("cosecha", "lluvia_cosecha", 60, 0, "parcial", 0.15),
        R("*", "ceniza", 0, 0, "parcial", 0.3),
    ),
    "papa": (
        R("emergencia->tuberizacion", "helada", -1, 1, "atraso", 14),
        R("emergencia->tuberizacion", "helada", -4, 1, "total"),
        R("tuberizacion->madurez", "helada", -1, 1, "parcial", 0.3),
        R("tuberizacion->madurez", "calor", 28, 5, "parcial", 0.25),
        R("tuberizacion->madurez", "sequia", 0.4, 0, "parcial", 0.4),
        R("siembra->emergencia", "anegamiento", 20, 3, "total"),
        R("tuberizacion->madurez", "anegamiento", 20, 3, "parcial", 0.4),
        R("*", "ceniza", 0, 0, "parcial", 0.3),
    ),
    "maiz": (
        R("emergencia->floracion", "helada", -2, 1, "total"),
        R("floracion->madurez", "helada", -1, 1, "parcial", 0.4),
        R("emergencia->floracion", "calor", 35, 3, "parcial", 0.4),
        R("emergencia->floracion", "sequia", 0.4, 0, "parcial", 0.5),
        R("*", "ceniza", 0, 0, "parcial", 0.3),
    ),
    "ajo_chilote": (
        # Placeholder sin validar. INIA (ficha tecnica) da minima 7C, maxima 30C, sin
        # detalle de umbral de dano por fase -- estos valores son estimacion propia
        # por analogia con otros Allium de clima templado, no de la ficha.
        R("emergencia->bulbificacion", "helada", -3, 1, "parcial", 0.3),
        R("emergencia->bulbificacion", "helada", -6, 1, "total"),
        R("bulbificacion->madurez", "helada", -2, 1, "parcial", 0.3),
        R("bulbificacion->madurez", "calor", 30, 5, "parcial", 0.2),
        # Chiloé es de exceso de agua, no de sequia -- se deja la regla de sequia fuera
        # a proposito en vez de copiar un umbral generico sin sentido para esta zona.
        R("siembra->emergencia", "anegamiento", 20, 3, "parcial", 0.3),
        R("bulbificacion->madurez", "anegamiento", 20, 3, "parcial", 0.35),
        R("cosecha", "lluvia_cosecha", 50, 0, "parcial", 0.2),
        R("*", "ceniza", 0, 0, "parcial", 0.3),
    ),
    "haba": (
        # Placeholder sin validar. CIREN (Haba.pdf) da base 5C, optimo 15-20C, maximo 28C.
        # Umbrales de dano por fase: estimacion propia por analogia con leguminosas de
        # grano de clima frio-humedo, no de la ficha.
        R("emergencia->floracion", "helada", -3, 1, "parcial", 0.3),
        R("emergencia->floracion", "helada", -6, 1, "total"),
        R("floracion->madurez", "helada", -1, 1, "parcial", 0.5),
        R("floracion->madurez", "calor", 28, 3, "parcial", 0.3),
        R("siembra->emergencia", "anegamiento", 20, 3, "parcial", 0.3),
        R("floracion->madurez", "anegamiento", 20, 3, "parcial", 0.3),
        R("*", "ceniza", 0, 0, "parcial", 0.3),
    ),
}


def fases(siembra, fechas, c, dias_cosecha=14):
    """[(nombre, inicio, fin)] para las etapas alcanzadas, mas la ventana de cosecha."""
    out, prev_n, prev_f = [], "siembra", pd.Timestamp(siembra)
    for n, _ in c.etapas:
        if n not in fechas:
            break
        out.append((f"{prev_n}->{n}", prev_f, fechas[n]))
        prev_n, prev_f = n, fechas[n]
    if c.etapas[-1][0] in fechas:
        out.append(("cosecha", prev_f, prev_f + pd.Timedelta(days=dias_cosecha)))
    return out


def _reduccion_mitigacion(r, cuando, manejo):
    """Fraccion de reduccion de r.valor si hubo una aplicacion real de r.mitigado_por
    (fila de manejo_predio: {'tipo_labor', 'fecha'}) dentro de la ventana de proteccion
    antes del primer dia en que la regla se cumplio. Sin mitigado_por, sin manejo, o sin
    aplicacion dentro de la ventana -> 0.0 (comportamiento identico al de antes de esto
    existir). No actua sobre efecto 'total' -- ver comentario en Regla."""
    if not r.mitigado_por or not manejo:
        return 0.0
    primer_dia = pd.Timestamp(cuando[0])
    ventana_ini = primer_dia - pd.Timedelta(days=r.ventana_mitigacion_dias)
    for app in manejo:
        if app.get("tipo_labor") == r.mitigado_por and ventana_ini <= pd.Timestamp(app["fecha"]) <= primer_dia:
            return r.factor_mitigacion
    return 0.0


def _danos_hidricos(agua, siembra, fechas, c, ky):
    """Perdida por deficit de agua, repartida por fase. FAO-33: 1 - Ya/Ym = Ky * (1 - ETa/ETc) en toda la
    temporada; la parte de cada fase es Ky * (ETc - ETa de la fase) / ETc de la temporada, asi que las
    partes suman el total. [(fase, perdida, primer_dia, ultimo_dia, dias_con_estres)] solo donde pasa de 0,5 %."""
    tramos = [(n, ini, fin) for n, ini, fin in fases(siembra, fechas, c) if n != "cosecha"]
    if not tramos:
        return []
    total = sum(float(agua.loc[ini:fin, "etc"].sum()) for _, ini, fin in tramos)
    if total <= 0:
        return []
    out = []
    for nombre, ini, fin in tramos:
        a = agua.loc[ini:fin]
        valor = ky * float((a["etc"] - a["eta"]).sum()) / total
        con_estres = a.index[a["ks"] < 0.999]
        if valor >= 0.005 and len(con_estres):
            out.append((nombre, round(min(valor, 1.0), 4), pd.Timestamp(con_estres[0]), pd.Timestamp(con_estres[-1]), len(con_estres)))
    return out


def evaluar(clima, agua, siembra, fechas, c, reglas, externos=(), manejo=()):
    """Aplica las reglas al clima tal como viene (eventos naturales o inyectados).
    externos: [(fecha, peligro)] para eventos que no estan en el clima (ceniza, granizo).
    manejo: [{'tipo_labor', 'fecha'}] -- aplicaciones reales sobre el predio (manejo_predio),
    para que una regla con mitigado_por reduzca su dano si corresponde (ver Regla).
    manejo=() (default) -- comportamiento identico a cuando esto no existia: pensado para
    motor_rotacion.evaluar_cultivos(), que trabaja con anos sinteticos sin manejo real que
    registrar. Quien evalue un cultivo real de un predio real (calcular_fenologia_cultivo,
    Fase 6) es quien debe leer manejo_predio y pasarlo aqui."""
    danos, eventos, fecha_perdida, atraso = [], [], None, 0
    ciclo_completo = c.etapas[-1][0] in fechas
    # Con el balance FAO-56 (columna `ky`), la sequia es una perdida continua (FAO-33) y las reglas de
    # sequia del catalogo, que eran un umbral de dias con poca agua, no se aplican.
    ky = float(agua["ky"].iloc[0]) if "ky" in agua.columns and len(agua) else float("nan")
    hidrico = ky == ky
    for nombre, ini, fin in fases(siembra, fechas, c):
        p, a = clima.loc[ini:fin], agua.loc[ini:fin]
        for r in reglas:
            if r.fase not in (nombre, "*"):
                continue
            if hidrico and r.peligro == "sequia":
                continue
            if r.peligro == "helada":
                m = p.tmin <= r.umbral
                ok, cuando = m.sum() >= r.minimo, p.index[m]
            elif r.peligro == "calor":
                m = p.tmax >= r.umbral
                ok, cuando = m.sum() >= r.minimo, p.index[m]
            elif r.peligro == "sequia":
                m = a.agua < 0.3
                ok, cuando = len(a) > 0 and m.mean() >= r.umbral, a.index[m]
            elif r.peligro == "anegamiento":
                m = a.exceso >= r.umbral
                ok, cuando = m.sum() >= r.minimo, a.index[m]
            elif r.peligro == "lluvia_cosecha":
                ok, cuando = p.lluvia.sum() >= r.umbral, p.index
            elif r.peligro == "tizon":
                # Mismo criterio que pheno_engine.alertas(): no es un pico aislado de
                # humedad, es humectacion foliar sostenida -- 'minimo' dias CONSECUTIVOS
                # con rh >= umbral. BUG REAL encontrado al conectar esto con mitigacion:
                # esta rama no existia -- tizon caia al 'else' (externos) y nunca
                # disparaba, porque nada inyecta un externo 'tizon'. La alerta que ve el
                # agricultor (pheno_engine.alertas) si lo evaluaba; el puntaje de
                # rotacion (este archivo, via motor_rotacion) nunca penalizaba por tizon.
                if "rh" not in p.columns:
                    ok, cuando = False, p.index[:0]
                else:
                    m = (p.rh >= r.umbral).rolling(r.minimo, min_periods=r.minimo).sum().fillna(0) >= r.minimo
                    ok, cuando = bool(m.any()), p.index[m]
            else:
                ext = [pd.Timestamp(f) for f, pel in externos if pel == r.peligro and ini <= pd.Timestamp(f) <= fin]
                ok, cuando = bool(ext), ext
            if ok:
                reduccion = _reduccion_mitigacion(r, cuando, manejo)
                valor_ef = r.valor * (1 - reduccion)
                danos.append((nombre, r.peligro, r.efecto, valor_ef))
                # Lo mismo que `danos`, con las fechas en que la regla se cumplio --
                # quien sigue un cultivo real necesita saber si el evento ya ocurrio,
                # viene en el pronostico o es solo una estimacion.
                eventos.append({"fase": nombre, "peligro": r.peligro, "efecto": r.efecto, "valor": valor_ef,
                                "primer_dia": pd.Timestamp(cuando[0]), "ultimo_dia": pd.Timestamp(cuando[-1]),
                                "dias": len(cuando)})
                if r.efecto == "total":
                    f0 = pd.Timestamp(cuando[0])
                    fecha_perdida = f0 if fecha_perdida is None else min(fecha_perdida, f0)
                if r.efecto == "atraso":
                    atraso += int(valor_ef)
    if hidrico:
        for fase, valor, primero, ultimo, dias_con_estres in _danos_hidricos(agua, siembra, fechas, c, ky):
            danos.append((fase, "sequia", "parcial", valor))
            eventos.append({"fase": fase, "peligro": "sequia", "efecto": "parcial", "valor": valor,
                            "primer_dia": primero, "ultimo_dia": ultimo, "dias": dias_con_estres})
    if fecha_perdida is not None or not ciclo_completo:
        estado, perdida = "perdido", 1.0
    else:
        # por (fase, peligro) cuenta solo la regla mas grave; entre fases se multiplican
        peor = {}
        for n, pel, ef, v in danos:
            if ef == "parcial":
                peor[(n, pel)] = max(peor.get((n, pel), 0), v)
        perdida = 1 - float(np.prod([1 - v for v in peor.values()])) if peor else 0.0
        estado = "parcial" if perdida > 0 else "ok"
    return {"estado": estado, "perdida": round(perdida, 2), "atraso_dias": atraso,
            "danos": danos, "eventos": eventos, "fecha_perdida": fecha_perdida,
            "ciclo_completo": ciclo_completo}


# ---------------------------------------------------------------- 3. Inyeccion de eventos
@dataclass(frozen=True)
class Evento:
    nombre: str
    tipo: str     # helada | calor | sequia | lluvia | ceniza
    dias: int
    valor: float = 0


EVENTOS = (
    Evento("helada -3 C, 1 dia", "helada", 1, -3),
    Evento("helada -6 C, 1 dia", "helada", 1, -6),
    Evento("calor 34 C, 5 dias", "calor", 5, 34),
    Evento("sin lluvia 45 dias", "sequia", 45),
    Evento("60 mm/dia, 3 dias", "lluvia", 3, 60),
    Evento("ceniza", "ceniza", 1),
)


def inyectar(clima, fecha, ev):
    c = clima.copy()
    d = pd.date_range(pd.Timestamp(fecha), periods=ev.dias, freq="D").intersection(c.index)
    if ev.tipo == "helada":
        c.loc[d, "tmin"] = ev.valor
        c.loc[d, "tmax"] = np.minimum(c.loc[d, "tmax"], ev.valor + 12)
    elif ev.tipo == "calor":
        c.loc[d, "tmax"] = ev.valor
        c.loc[d, "tmin"] = np.maximum(c.loc[d, "tmin"], ev.valor - 14)
    elif ev.tipo == "sequia":
        c.loc[d, "lluvia"] = 0.0
    elif ev.tipo == "lluvia":
        c.loc[d, "lluvia"] = ev.valor
    return c


def _correr(clima, siembra, lat, c, reglas, cap, delta=0.0, externos=()):
    fechas = simular(clima, siembra, lat, c, delta)
    agua = balance_agua(clima, lat, cap)
    return fechas, evaluar(clima, agua, siembra, fechas, c, reglas, externos)


def matriz_estres(clima, siembra, lat, c, reglas, cap, eventos=EVENTOS, delta=0.0):
    """Inyecta cada evento centrado en cada fase y registra el dano ADICIONAL al de base.
    No depende de que el modelo climatico acierte la probabilidad del evento."""
    fechas0, base = _correr(clima, siembra, lat, c, reglas, cap, delta)
    filas = {}
    for nombre, ini, fin in fases(siembra, fechas0, c):
        fila = {}
        for ev in eventos:
            f = ini + (fin - ini) / 2 - pd.Timedelta(days=ev.dias // 2)
            f = max(f.normalize(), pd.Timestamp(siembra))
            ext = [(f, "ceniza")] if ev.tipo == "ceniza" else []
            _, r = _correr(inyectar(clima, f, ev), siembra, lat, c, reglas, cap, delta, ext)
            if r["estado"] == "perdido":
                fila[ev.nombre] = "TOTAL"
            else:
                extra = 1 - (1 - r["perdida"]) / (1 - base["perdida"]) if base["perdida"] < 1 else 0
                at = r["atraso_dias"] - base["atraso_dias"]
                fila[ev.nombre] = (f"-{extra:.0%}" if extra > 0.005 else "") + (f" +{at}d" if at else "") or "."
        filas[nombre] = fila
    return pd.DataFrame(filas).T, base, fechas0


def resumen_matriz(m):
    v = m.values.ravel()
    return {"celdas": len(v), "perdida_total": int((v == "TOTAL").sum()),
            "con_dano": int((v != ".").sum()), "sin_dano": int((v == ".").sum())}


# ---------------------------------------------------------------- 4. Contingencia
def contingencia(clima, fecha_perdida, limite, lat, cultivos, reglas, cap, dias_resiembra=7, delta=0.0):
    """Tras perder un cultivo: cuales alcanzan la madurez antes de `limite`
    y con que dano segun el clima que sigue.

    `cultivos`: {nombre: Cultivo} ya construidos por el llamador (via
    catalogo_especies.construir_cultivo) -- este archivo no sabe de donde vienen.
    `reglas`: {nombre: tuple[Regla,...]}, idem via construir_reglas.

    candidatos SIN entrada en `reglas` muestran perdida=None con estado 'sin_modelo_riesgo'
    en vez de perdida=0.0 -- no se puede ofrecer un cultivo como plan B solo porque no
    tiene reglas de dano todavia. Ver la advertencia del modulo."""
    siembra = pd.Timestamp(fecha_perdida) + pd.Timedelta(days=dias_resiembra)
    out = []
    for nombre, c in cultivos.items():
        reglas_cultivo = reglas.get(nombre, ())
        sin_modelo = len(reglas_cultivo) == 0
        fechas, r = _correr(clima, siembra, lat, c, reglas_cultivo, cap, delta)
        fin = fechas.get(c.etapas[-1][0])
        cabe = fin is not None and fin <= pd.Timestamp(limite)
        if not cabe:
            estado, perdida = "no cierra ciclo", None
        elif sin_modelo:
            estado, perdida = "sin_modelo_riesgo", None
        else:
            estado, perdida = r["estado"], r["perdida"]
        out.append({"cultivo": nombre, "siembra": siembra.date(), "madurez": fin.date() if fin is not None else None,
                    "cabe": cabe, "estado": estado, "perdida": perdida})
    return pd.DataFrame(out)
