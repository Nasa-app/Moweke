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


def balance_agua(clima, lat, capacidad_mm):
    """Balde diario. capacidad_mm = agua aprovechable del perfil (dato de suelo del usuario,
    o SoilGrids/CHLSOC/GAEZ mientras no haya dato local — ver seccion 10 del modelo conceptual).
    ET0 por Hargreaves; la extraccion cae linealmente bajo el 50% de la capacidad.
    Devuelve fraccion de agua disponible y exceso diario (mm que no caben)."""
    ra = radiacion_extraterrestre(lat, clima.index.dayofyear.values)
    tmed = (clima.tmin.values + clima.tmax.values) / 2
    et0 = 0.0023 * ra * (tmed + 17.8) * np.sqrt(np.clip(clima.tmax.values - clima.tmin.values, 0, None))
    et0 = np.clip(et0, 0, None)
    w, frac, exceso = capacidad_mm, np.empty(len(clima)), np.empty(len(clima))
    for i, lluvia in enumerate(clima.lluvia.values):
        w += lluvia
        exceso[i] = max(0.0, w - capacidad_mm)
        w = min(w, capacidad_mm)
        w = max(0.0, w - et0[i] * min(1.0, w / (0.5 * capacidad_mm)))
        frac[i] = w / capacidad_mm
    return pd.DataFrame({"agua": frac, "exceso": exceso, "et0": et0}, index=clima.index)


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


def evaluar(clima, agua, siembra, fechas, c, reglas, externos=(), manejo=()):
    """Aplica las reglas al clima tal como viene (eventos naturales o inyectados).
    externos: [(fecha, peligro)] para eventos que no estan en el clima (ceniza, granizo).
    manejo: [{'tipo_labor', 'fecha'}] -- aplicaciones reales sobre el predio (manejo_predio),
    para que una regla con mitigado_por reduzca su dano si corresponde (ver Regla).
    manejo=() (default) -- comportamiento identico a cuando esto no existia: pensado para
    motor_rotacion.evaluar_cultivos(), que trabaja con anos sinteticos sin manejo real que
    registrar. Quien evalue un cultivo real de una parcela real (calcular_fenologia_cultivo,
    Fase 6) es quien debe leer manejo_predio y pasarlo aqui."""
    danos, eventos, fecha_perdida, atraso = [], [], None, 0
    ciclo_completo = c.etapas[-1][0] in fechas
    for nombre, ini, fin in fases(siembra, fechas, c):
        p, a = clima.loc[ini:fin], agua.loc[ini:fin]
        for r in reglas:
            if r.fase not in (nombre, "*"):
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
