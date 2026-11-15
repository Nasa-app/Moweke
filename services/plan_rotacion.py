"""
Plan de rotacion
================
Compara estrategias de rotacion para una parcela con el MISMO modelo de agua y de riesgo del ranking de especies:
cada especie se puntua en cada uno de los ultimos 15 anos de la serie de la parcela, tal cual
multianual.perdidas_anuales(), y de ahi sale la tabla que consumen puntuar() y buscar() de motor_rotacion.

  perdida de un ano  = 1 - puntaje de ese ano (el menor entre la simulacion por fase y EcoCrop)
  viable             = ano dificil (p10) >= PUNTAJE_MINIMO_APTA, el ciclo cierra en >= 80 % de los anos y el cultivo
                       se pierde por completo en <= 30 %
  duracion           = percentil 80 de los dias de ciclo
  escenarios         = 'reciente' y 'proyectado' a 2040; una rotacion vale lo que vale en el peor

Las perennes y las especies sin simulacion por fase NO estan modeladas: reciben el riesgo medio de las modeladas y
viables (con un piso: nunca riesgo cero) y salen marcadas. Las que el suelo declarado excluye (inundacion, sal o poca
profundidad) no entran, y se nombra la causa.

Reglas duras: intervalo sanitario, solanaceas nunca una tras otra (tambien contra lo ya sembrado) y calendario. El
puntaje ordena opciones; no predice rendimiento. Los umbrales de dano y los pesos son valores de partida sin validar
agronomicamente.
"""
from __future__ import annotations

import numpy as np

import motor_rotacion as mr
from services import catalogo_especies as ce
from services import multianual

AVISO = ("El puntaje ordena las opciones entre sí; no predice rendimiento ni ingresos. Las reglas de daño, los "
         "intervalos entre cultivos y los pesos son valores de partida que todavía no tienen validación agronómica.")

PISO_RIESGO_NO_MODELADO = 0.10    # perdida minima del relleno de una especie no modelada
RIESGO_SIN_REFERENCIA = 0.50      # perdida del relleno cuando no hay ninguna especie modelada y viable que promediar
MIN_ESPECIES = 3                  # con menos especies viables no hay rotacion que comparar
LARGO_BASE = 3                    # temporadas con que se evalua "repetir el cultivo actual"
MAX_PREVIOS = 12                  # siembras previas que se miran
CIERRE_MINIMO, PERDIDA_TOTAL_MAXIMA = 0.8, 0.3
CRITERIOS = ("riesgo", "peor_ano", "diversidad", "precedente", "cobertura", "fertilidad")


# ---------------------------------------------------------------- suelo declarado
def causa_suelo(req: dict | None, suelo: dict | None) -> str | None:
    """'inundacion', 'salinidad' o 'profundidad' si el suelo declarado excluye a la especie segun su fila de EcoCrop
    (la respuesta es 0); None si no la excluye o falta el dato. La fertilidad nunca excluye: se corrige con abono."""
    if req is None:
        return None
    suelo = suelo or {}
    for causa, respuesta, campo in (("inundacion", ce._respuesta_drenaje, "drenaje"),
                                     ("salinidad", ce._respuesta_salinidad, "salinidad"),
                                     ("profundidad", ce._respuesta_profundidad, "profundidad")):
        valor = respuesta(req, suelo.get(campo))
        if valor is not None and valor <= 0:
            return causa
    return None


def _fila_ecocrop(nombre: str, identidades: dict, por_especie: dict) -> dict | None:
    cientifico = (identidades.get(nombre) or {}).get("nombre_cientifico")
    gemela = ce._slug(cientifico) if cientifico else None
    return por_especie.get(gemela) or por_especie.get(nombre)


def _ciclo_ecocrop(req: dict | None) -> float | None:
    if not req:
        return None
    dias = req.get("ciclo_max_dias") or req.get("ciclo_min_dias")
    return float(dias) if dias else None


# ---------------------------------------------------------------- de las matrices a la tabla del motor
def tabla_de_escenario(escenario: dict, columnas: dict, simuladas: dict, perfiles: dict, ciclo_ecocrop: dict) -> dict:
    """{especie: fila de la tabla de motor_rotacion} de un escenario de multianual.perdidas_anuales()."""
    tabla = {}
    for nombre, j in columnas.items():
        punto, ciclo = escenario["puntaje"][:, j], escenario["ciclo_dias"][:, j]
        perenne = bool(perfiles[nombre].get("perenne"))
        completo = bool(np.isfinite(punto).all())
        dificil = float(np.percentile(punto, multianual.DECIL_DIFICIL)) if completo else None
        modelado = bool(simuladas[nombre]) and not perenne and completo
        if modelado:
            perdidas = 1.0 - punto
            cierra = float(np.mean(~np.isnan(ciclo)))
            p_perdido = float(np.mean(perdidas >= 1.0))
            dur = float(np.nanpercentile(ciclo, 80)) if cierra > 0 else np.nan
            viable = (dificil >= ce.PUNTAJE_MINIMO_APTA and cierra >= CIERRE_MINIMO
                      and p_perdido <= PERDIDA_TOTAL_MAXIMA and not np.isnan(dur))
        else:
            perdidas = np.zeros(len(punto))
            cierra, p_perdido = 1.0, 0.0
            dur = 365 - mr.DIAS_COSECHA if perenne else ciclo_ecocrop.get(nombre, np.nan)
            viable = dificil is None or dificil >= ce.PUNTAJE_MINIMO_APTA
        tabla[nombre] = dict(viable=bool(viable), dur=dur, perdidas=perdidas, cierra=cierra, p_perdido=p_perdido,
                             modelado=modelado, dificil=dificil)
    return mr.rellenar_no_modelados(tabla, piso=PISO_RIESGO_NO_MODELADO, por_defecto=RIESGO_SIN_REFERENCIA)


# ---------------------------------------------------------------- reglas, para explicar una estrategia
def _incumplimientos(seq, previos, perfil, extra=None) -> list[str]:
    fallas = []
    if not mr.cumple_intervalo(seq, perfil, extra):
        fallas.append("No respeta el intervalo mínimo entre siembras de un mismo cultivo.")
    if not mr.sin_familia_seguida(seq, perfil):
        fallas.append("Pone solanáceas una tras otra: consumen lo mismo y comparten plagas y enfermedades.")
    if previos and not mr.cumple_historial(seq, previos, perfil, extra):
        fallas.append("Choca con lo ya sembrado en la parcela (intervalo o familia respecto del último cultivo).")
    return fallas


def _advertencias(seq, modeladas: dict, placeholder: dict, perfiles: dict) -> list[str]:
    avisos = []
    for n in dict.fromkeys(seq):
        if not modeladas.get(n):
            motivo = "es perenne" if perfiles[n].get("perenne") else "no tiene simulación por fase"
            avisos.append(f"{n}: {motivo}; su riesgo es un valor neutro, no un cálculo.")
        if placeholder.get(n):
            avisos.append(f"{n}: sus reglas de daño no están validadas (placeholder_sin_validar).")
    return avisos


def _estrategia(tipo, seq, r, modeladas, placeholder, perfiles, fallas):
    return {
        "tipo": tipo, "secuencia": list(seq), "temporadas": len(seq),
        "puntaje": r["puntaje"], "peor_escenario": r["peor_escenario"],
        "criterios": {k: r[k] for k in CRITERIOS if k in r},
        "perdida_media": round(1 - r["riesgo"], 2), "perdida_ano_dificil": round(1 - r["peor_ano"], 2),
        "anios_del_ciclo": r["anos"], "max_barbecho_dias": r["max_barbecho"],
        "cumple_reglas": not fallas,
        "advertencias": fallas + _advertencias(seq, modeladas, placeholder, perfiles),
    }


# ---------------------------------------------------------------- el plan
async def plan_rotacion(sitio: dict, repo, historia, lat: float | None, previos: list[str],
                        riego: bool = False, delta_temp: float = 0.0, calentamiento_c_por_decada: float | None = None,
                        largo_max: int = 5, limite: int = 5) -> dict:
    """Estrategias de rotacion de la parcela, desde la proxima temporada. `previos`: las especies ya sembradas, de la
    mas antigua a la mas reciente. `estado` es 'historia_insuficiente' si la serie no alcanza para evaluar anos (no hay
    plan), o 'ok'. La estrategia base es repetir el cultivo actual (el ultimo de `previos`). Siempre salen al menos
    MIN_ESPECIES estrategias si hay especies viables, aunque `limite` sea menor: base mas las mejores rotaciones."""
    nombres = await repo.especies_con_rasgos_rotacion()
    cat = await ce.construir_catalogo([(n, None) for n in nombres], repo)
    perfiles = cat.perfiles
    vacios_sitio = _vacios_de_sitio(sitio)
    datos = await multianual.perdidas_anuales(sitio, repo, historia, lat, list(perfiles), riego, delta_temp,
                                              calentamiento_c_por_decada)
    if datos is None:
        minimo = multianual.ANIOS_RECIENTE + multianual.MIN_ANIOS_PERIODO
        return {"estado": "historia_insuficiente", "aviso": AVISO, "estrategias": [], "especies": [],
                "descartes": {}, "no_modeladas": [],
                "vacios": [{"codigo": "historia_insuficiente", "mensaje":
                            f"Hacen falta al menos {minimo} años de clima de la parcela para evaluar rotaciones."},
                           *vacios_sitio]}

    identidades = await repo.identidades()
    por_especie = {r["especie"]: r for r in await repo.requisitos_genericos()}
    suelo = sitio.get("suelo") or {}
    columnas = {n: j for j, n in enumerate(datos["especies"])}
    simuladas = {n: d["simulada"] for n, d in datos["especies"].items()}

    excluidas, ciclo_ecocrop = {}, {}
    for n in perfiles:
        req = _fila_ecocrop(n, identidades, por_especie)
        causa = causa_suelo(req, suelo)
        if causa:
            excluidas[n] = {"especie": n, "causa": "suelo", "detalle": causa}
            continue
        if not perfiles[n].get("perenne") and not simuladas[n]:
            ciclo = _ciclo_ecocrop(req)
            if ciclo is None:
                excluidas[n] = {"especie": n, "causa": "sin_ciclo",
                                "detalle": "no tiene simulación ni duración de ciclo en el catálogo"}
                continue
            ciclo_ecocrop[n] = ciclo
    incluidas = {n: columnas[n] for n in perfiles if n not in excluidas}
    perfil_plan = {n: perfiles[n] for n in incluidas}
    tablas = {e: tabla_de_escenario(m, incluidas, simuladas, perfil_plan, ciclo_ecocrop)
              for e, m in datos["escenarios"].items()}

    for n in incluidas:
        if not all(t[n]["viable"] for t in tablas.values()):
            excluidas[n] = {"especie": n, "causa": "clima", "detalle": _detalle_clima(n, tablas)}

    modeladas = {n: all(t[n]["modelado"] for t in tablas.values()) for n in incluidas}
    placeholder, niveles = {}, {}
    for n in perfiles:
        niveles[n] = await ce.nivel_madurez(n, None, repo)
        placeholder[n] = any(f.get("fuente") == "placeholder_sin_validar" for f in await repo.reglas_dano(n, None))

    fertilidad_baja = suelo.get("fertilidad") == "low"
    pesos = mr.PESOS_FERTILIDAD_BAJA if fertilidad_baja else mr.PESOS
    previos = [p for p in previos if p]
    base = _estrategia_base(previos, perfiles, perfil_plan, tablas, pesos, modeladas, placeholder, excluidas)

    n_rot = max(limite, 2 if base is not None else MIN_ESPECIES)
    top, info = mr.buscar(tablas, perfil_plan, largos=tuple(range(3, largo_max + 1)), pesos=pesos, top=n_rot,
                          previos=tuple(previos))
    rotaciones = [_estrategia("rotacion", r["seq"], r, modeladas, placeholder, perfiles, []) for r in top]

    vacios = list(vacios_sitio)
    if not previos:
        vacios.append({"codigo": "historial_vacio", "mensaje":
                       "No hay cultivos declarados en la parcela: no se puede cuidar el intervalo ni comparar con "
                       "repetir el cultivo actual."})
    sin_perfil = sorted({p for p in previos if p not in perfiles})
    if sin_perfil:
        vacios.append({"codigo": "cultivos_previos_sin_perfil", "detalle": sin_perfil, "mensaje":
                       "Estos cultivos ya sembrados no tienen rasgos de rotación en el catálogo, así que no se "
                       "juzgan contra las reglas: " + ", ".join(sin_perfil) + "."})
    viables_total = len(info["viables"]) + len(info["recortadas"])
    if viables_total < MIN_ESPECIES:
        vacios.append({"codigo": "pocas_especies", "detalle": viables_total, "mensaje":
                       f"Solo {viables_total} especie(s) viable(s) en esta parcela: hay poco que combinar."})

    return {
        "estado": "ok", "aviso": AVISO,
        "estrategias": ([base] if base else []) + rotaciones,
        "especies": [{"especie": n, "familia": perfiles[n]["familia"], "perenne": perfiles[n]["perenne"],
                      "modelada": bool(modeladas.get(n, False)), "nivel_madurez": niveles[n],
                      "reglas_placeholder": placeholder[n], "incluida": n not in excluidas,
                      "motivo_exclusion": excluidas.get(n)} for n in perfiles],
        "no_modeladas": sorted(n for n in incluidas if not modeladas[n] and n not in excluidas),
        "descartes": {"especies": list(excluidas.values()),
                      "rotaciones": {k: info[k] for k in ("intervalo", "familia", "historial", "calendario")},
                      "recortadas": info["recortadas"], "max_especies": mr.MAX_ESPECIES,
                      "rotaciones_evaluadas": info["evaluadas"]},
        "vacios": vacios,
        "criterio_fertilidad": fertilidad_baja,
        "escenarios": list(tablas), "anios_evaluados": datos["anios"], "serie_climatica": datos["resumen"],
    }


def _vacios_de_sitio(sitio: dict) -> list[dict]:
    vacios = []
    suelo = sitio.get("suelo") or {}
    if suelo.get("fertilidad") is None:
        vacios.append({"codigo": "fertilidad_sin_declarar", "mensaje":
                       "La fertilidad del suelo no está declarada: no se premian las rotaciones que reponen nitrógeno."})
    faltan = ce.suelo_sin_declarar(sitio)
    if faltan:
        vacios.append({"codigo": "suelo_sin_declarar", "detalle": faltan, "mensaje":
                       "Falta declarar del suelo: " + ", ".join(faltan) + ". Sin eso no se descartan especies por ello."})
    return vacios


def _detalle_clima(n: str, tablas: dict) -> str:
    peor = min((t[n] for t in tablas.values()), key=lambda f: f["dificil"] if f["dificil"] is not None else 1.0)
    partes = []
    if peor["dificil"] is not None and peor["dificil"] < ce.PUNTAJE_MINIMO_APTA:
        partes.append(f"el año difícil llega a {peor['dificil']:.2f}, bajo el mínimo {ce.PUNTAJE_MINIMO_APTA}")
    if peor["cierra"] < CIERRE_MINIMO:
        partes.append(f"el ciclo cierra solo en {peor['cierra'] * 100:.0f} % de los años")
    if peor["p_perdido"] > PERDIDA_TOTAL_MAXIMA:
        partes.append(f"se pierde por completo en {peor['p_perdido'] * 100:.0f} % de los años")
    return "; ".join(partes) or "no es viable con el clima de la parcela"


def _estrategia_base(previos, perfiles, perfil_plan, tablas, pesos, modeladas, placeholder, excluidas):
    """'Repetir el cultivo actual': el ultimo sembrado, LARGO_BASE temporadas seguidas. Es la referencia contra la
    que se comparan las rotaciones. None si no hay cultivo actual o no tiene perfil."""
    if not previos or previos[-1] not in perfiles:
        return None
    n = previos[-1]
    seq = (n,) * LARGO_BASE
    fallas = _incumplimientos(seq, previos, perfiles)
    if n in excluidas or n not in perfil_plan:
        motivo = excluidas.get(n, {})
        fallas.append(f"{n} queda excluido en esta parcela ({motivo.get('causa', 'sin datos')}: "
                      f"{motivo.get('detalle', '')}).")
        return {"tipo": "base", "secuencia": list(seq), "temporadas": len(seq), "puntaje": None,
                "peor_escenario": None, "criterios": {}, "perdida_media": None, "perdida_ano_dificil": None,
                "anios_del_ciclo": None, "max_barbecho_dias": None, "cumple_reglas": False,
                "advertencias": fallas}
    por_esc = {e: mr.puntuar(seq, t, perfil_plan, pesos) for e, t in tablas.items()}
    peor = min(por_esc, key=lambda e: por_esc[e]["total"])
    r = dict(puntaje=round(por_esc[peor]["total"], 3), peor_escenario=peor,
             **{k: round(v, 2) for k, v in por_esc[peor].items() if k != "total"})
    return _estrategia("base", seq, r, modeladas, placeholder, perfiles, fallas)
