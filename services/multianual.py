"""
Idoneidad multianual
====================
La lista de especies de un predio se calculaba con UN ano de clima: el veredicto de "apta" cambiaba de 10 a
36 % de las especies con una anomalia de 1 C (medido), y ademas no distinguia lo que ya se cultiva en la zona de lo
que el clima en cambio vuelve posible. Este modulo evalua cada ano de la serie historica del predio y resume:

  historico   los anos mas viejos (1991 a 2010 con la serie actual)
  reciente    los ultimos ANIOS_RECIENTE anos completos (2011 a 2025)
  proyectado  los anos recientes llevados al HORIZONTE_PROYECCION con la tendencia de la propia serie

De cada periodo salen dos cifras: la compatibilidad TIPICA (mediana de los anos) y la de un ano DIFICIL (el peor
decil: el puntaje que se supera en 9 de cada 10 anos). Una especie es apta si su ano dificil reciente llega al
minimo. La categoria de clima compara los periodos: 'tradicional' (funciona y seguira funcionando), 'emergente'
(antes no y a futuro si, con un salto de verdad) o 'en_riesgo' (funcionaba y la tendencia la saca).

La proyeccion NO es un modelo de clima: es la tendencia lineal robusta (Theil-Sen) de 35 anos del propio
predio, acotada (nunca se proyecta un enfriamiento), aplicada a los anos recientes. Dice que pasa si lo observado sigue igual, no que va a pasar.
El puntaje es de idoneidad de sitio, no un rendimiento.

El puntaje de cada especie por ano sale de calcular_matriz(), una version vectorizada de
catalogo_especies.puntuar_especie(): la misma cuenta, 50 anos de 2.000 especies en una fraccion de segundo. Una
prueba la compara con la version original sobre especies y sitios aleatorios.
"""
from __future__ import annotations

import asyncio
import time
import warnings

import numpy as np
import pandas as pd

from services import catalogo_especies as ce

HORIZONTE_PROYECCION = 2040
ANIOS_RECIENTE = 15
MIN_ANIOS_PERIODO = 8                      # con menos anos un periodo no da un decil que valga
CAMBIO_MATERIAL = 0.10                      # lo que debe moverse la compatibilidad tipica para llamar al cambio emergente o en riesgo
DECIL_DIFICIL = 10                          # percentil de "un ano dificil"
LIMITE_TEMP_C_POR_ANIO = (0.0, 0.06)        # tendencia que se proyecta: de 0 a +0,6 C por decada. Un enfriamiento de 35 anos
                                            # es ruido de una serie corta, y las proyecciones regionales para Chile son de alza
LIMITE_FACTOR_LLUVIA = (0.6, 1.2)           # cuanto puede cambiar la lluvia entre el ano reciente y el horizonte


# ---------------------------------------------------------------- tendencia y periodos
def theil_sen(x, y) -> float:
    """Pendiente robusta: la mediana de las pendientes entre todos los pares de puntos."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    dx = x[None, :] - x[:, None]
    dy = y[None, :] - y[:, None]
    arriba = dx > 0
    return float(np.median(dy[arriba] / dx[arriba])) if arriba.any() else 0.0


def tendencia_clima(historia: dict[int, pd.DataFrame]) -> dict:
    """Pendiente de la temperatura media anual (C por ano) y de la lluvia anual (fraccion por ano) de la serie, con
    la temperatura acotada a LIMITE_TEMP_C_POR_ANIO. La lluvia se acota despues, al aplicarla (ver proyectar())."""
    anios = sorted(historia)
    tmedia = [float(((d["tmin"] + d["tmax"]) / 2).mean()) for d in (historia[a] for a in anios)]
    lluvia = [float(historia[a]["lluvia"].sum()) for a in anios]
    pend_t = theil_sen(anios, tmedia) if len(anios) >= 2 else 0.0
    pend_ll = theil_sen(anios, lluvia) / (np.mean(lluvia) or 1.0) if len(anios) >= 2 else 0.0
    lo, hi = LIMITE_TEMP_C_POR_ANIO
    return {"anios": len(anios), "primer_anio": anios[0] if anios else None, "ultimo_anio": anios[-1] if anios else None,
            "temp_c_por_decada_observada": round(pend_t * 10, 2), "lluvia_pct_por_decada_observada": round(pend_ll * 1000, 1),
            "temp_c_por_anio": min(hi, max(lo, pend_t)), "lluvia_rel_por_anio": float(pend_ll)}


def periodos(historia: dict[int, pd.DataFrame]) -> tuple[list[int], list[int]]:
    """(anos recientes, anos historicos): los ultimos ANIOS_RECIENTE anos completos y los anteriores."""
    anios = sorted(historia)
    return anios[-ANIOS_RECIENTE:], anios[:-ANIOS_RECIENTE]


def proyectar(df: pd.DataFrame, anio: int, tendencia: dict, horizonte: int = HORIZONTE_PROYECCION) -> pd.DataFrame:
    """El ano `anio` llevado al `horizonte`: la temperatura sube lo que la tendencia por los anos que faltan y la
    lluvia se multiplica por el cambio relativo, acotado a LIMITE_FACTOR_LLUVIA."""
    anios_hasta = max(horizonte - anio, 0)
    out = df.copy()
    delta = tendencia["temp_c_por_anio"] * anios_hasta
    out["tmin"], out["tmax"] = out["tmin"] + delta, out["tmax"] + delta
    lo, hi = LIMITE_FACTOR_LLUVIA
    out["lluvia"] = out["lluvia"] * min(hi, max(lo, 1 + tendencia["lluvia_rel_por_anio"] * anios_hasta))
    return out


# ---------------------------------------------------------------- puntaje vectorizado
def _meseta(x, minimo, opt_min, opt_max, maximo):
    """respuesta_meseta() sobre arreglos. Un umbral NaN es un umbral ausente; NaN si falta el dato o los cuatro umbrales."""
    with np.errstate(divide="ignore", invalid="ignore"):
        ninguno = np.isnan(minimo) & np.isnan(opt_min) & np.isnan(opt_max) & np.isnan(maximo)
        bajo = np.where(np.isnan(opt_min), minimo, opt_min)
        alto = np.where(np.isnan(opt_max), maximo, opt_max)
        piso = np.where(np.isnan(minimo), bajo, minimo)
        techo = np.where(np.isnan(maximo), alto, maximo)
        x = np.broadcast_to(x, np.broadcast_shapes(np.shape(x), np.shape(bajo)))
        en_bajo = ~np.isnan(bajo) & (x < bajo)
        en_alto = ~np.isnan(alto) & (x > alto)
        res_bajo = np.where(x <= piso, 0.0, (x - piso) / (bajo - piso))
        res_alto = np.where(x >= techo, 0.0, (techo - x) / (techo - alto))
        res = np.where(en_bajo, res_bajo, np.where(en_alto, res_alto, 1.0))
        return np.where(np.isnan(x) | ninguno, np.nan, res)


class CatalogoVectorial:
    """Los requisitos de las especies como arreglos, para puntuar todas a la vez."""

    def __init__(self, requisitos: list[dict], luz: list[dict]):
        self.requisitos = requisitos
        self.especies = [r["especie"] for r in requisitos]
        self.indice = {e: i for i, e in enumerate(self.especies)}
        num = lambda k: np.array([np.nan if r.get(k) is None else float(r[k]) for r in requisitos], float)
        self.tb, self.tc, self.letal = num("tb"), num("tc"), num("temperatura_letal")
        # misma regla que puntuar_especie: el optimo es t_opt_min/max, y si faltan, el punto medio t_optima
        topt = num("t_optima")
        self.topt_min = np.where(np.isnan(num("t_opt_min")), topt, num("t_opt_min"))
        self.topt_max = np.where(np.isnan(num("t_opt_max")), topt, num("t_opt_max"))
        self.lluvia_anual = np.stack([num("lluvia_anual_min"), num("lluvia_anual_opt_min"),
                                      num("lluvia_anual_opt_max"), num("lluvia_anual_max")], axis=1)
        self.duracion = np.array([ce.duracion_temporada_meses(r.get("ciclo_min_dias"), r.get("ciclo_max_dias"))
                                  for r in requisitos], int)
        luz = sorted(luz, key=lambda f: f["orden"])
        self.luz_umbral = np.array([f["ghi_min_kwh_m2_dia"] for f in luz], float)
        self.luz_respuesta = np.array([[np.nan if (v := ce._respuesta_luz(r, f["orden"], luz)) is None else v for f in luz]
                                       for r in requisitos], float).reshape(len(requisitos), len(luz))

    def factores_fijos(self, sitio: dict) -> np.ndarray:
        """El menor de los factores del sitio que no cambian con la temporada (pH, altitud, textura, suelo declarado) de
        cada especie; NaN si ninguno se puede evaluar."""
        suelo = sitio.get("suelo") or {}
        clases = sitio.get("textura_posibles") or ([sitio["textura"]] if sitio.get("textura") else [])
        out = np.full(len(self.requisitos), np.nan)
        for i, req in enumerate(self.requisitos):
            valores = (ce._respuesta_ph(req, sitio.get("ph"))[0], ce._respuesta_altitud(req, sitio.get("altitud_m")),
                       ce._respuesta_textura(req, clases), ce._respuesta_drenaje(req, suelo.get("drenaje")),
                       ce._respuesta_salinidad(req, suelo.get("salinidad")),
                       ce._respuesta_profundidad(req, suelo.get("profundidad")),
                       ce._respuesta_fertilidad(req, suelo.get("fertilidad"))[0])
            validos = [v for v in valores if v is not None]
            if validos:
                out[i] = min(validos)
        return out

    def calcular_matriz(self, normales: dict, fijos: np.ndarray, ghi_mensual=None, riego: bool = False):
        """(limite, puntaje) de cada especie con las normales de un ano: lo mismo que puntuar_especie(), a la vez
        para todas. NaN donde no hay ni un factor que evaluar. `limite` es el factor que limita en la mejor de las
        12 fechas de inicio; `puntaje` es el limite con el descuento de la luz."""
        n = len(self.requisitos)
        serie = lambda k: None if normales.get(k) is None else np.asarray(normales[k], float)
        tmedia, tmin_ext, lluvia = serie("tmedia"), serie("tmin_extrema"), serie("lluvia")

        nan_col = np.full((n, 1), np.nan)
        T = (np.full((n, 12), np.nan) if tmedia is None else
             _meseta(tmedia[None, :], self.tb[:, None], self.topt_min[:, None], self.topt_max[:, None], self.tc[:, None]))
        H = (np.full((n, 12), np.nan) if tmin_ext is None else
             _meseta(tmin_ext[None, :], (self.letal - 1)[:, None], (self.letal + 1)[:, None], nan_col, nan_col))
        tiene_T, tiene_H = ~np.isnan(T[:, 0]), ~np.isnan(H[:, 0])
        # por mes, el menor de los factores de temperatura que hay (para desempatar entre fechas)
        M = np.fmin(T, H)

        limite_por_inicio = np.full((n, 12), np.nan)
        promedio_por_inicio = np.zeros((n, 12))
        ghi = None if ghi_mensual is None or len(ghi_mensual) == 0 else np.asarray(ghi_mensual, float)
        ghi_por_inicio = np.zeros((n, 12))
        umbral_lluvia = self.lluvia_anual.copy()
        if riego:
            umbral_lluvia[:, :2] = np.nan            # la falta de lluvia no cuenta; el exceso si
        for d in range(1, 13):
            idx = np.where(self.duracion == d)[0]
            if not len(idx):
                continue
            mensual = umbral_lluvia[idx] / (d + 1)
            for ini in range(12):
                meses = [(ini + k) % 12 for k in range(d)]
                factores = [np.where(tiene_T[idx], T[idx][:, meses].min(axis=1), np.nan),
                            np.where(tiene_H[idx], H[idx][:, meses].min(axis=1), np.nan), fijos[idx]]
                if lluvia is not None:
                    factores.append(_meseta(np.full(len(idx), lluvia[meses].mean()), mensual[:, 0], mensual[:, 1],
                                            mensual[:, 2], mensual[:, 3]))
                limite_por_inicio[idx, ini] = np.fmin.reduce(factores)
                m = M[idx][:, meses]
                promedio_por_inicio[idx, ini] = np.where(np.isnan(m).any(axis=1), 0.0, m.mean(axis=1))
                if ghi is not None:
                    ghi_por_inicio[idx, ini] = ghi[meses].mean()
        mejor = np.nanmax(np.where(np.isnan(limite_por_inicio), -np.inf, limite_por_inicio), axis=1)
        sin_factores = np.isneginf(mejor)
        empate = limite_por_inicio == mejor[:, None]
        inicio = np.argmax(np.where(empate, promedio_por_inicio, -np.inf), axis=1)
        limite = np.where(sin_factores, np.nan, mejor)

        puntaje = limite.copy()
        if ghi is not None and len(self.luz_umbral):
            ghi_elegido = ghi_por_inicio[np.arange(n), inicio]
            alcanza = ghi_elegido[:, None] >= self.luz_umbral[None, :]
            categoria = np.argmax(alcanza, axis=1)
            respuesta = np.where(alcanza.any(axis=1), self.luz_respuesta[np.arange(n), categoria], np.nan)
            puntaje = np.where(np.isnan(respuesta), limite, limite * (1 - ce.PESO_LUZ * (1 - respuesta)))
        return limite, puntaje


# ---------------------------------------------------------------- resumen por periodo
def estadisticos(matriz: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(mediana, ano dificil) por especie de una matriz [anos, especies]. NaN si no hay anos."""
    if matriz.shape[0] == 0:
        vacio = np.full(matriz.shape[1], np.nan)
        return vacio, vacio
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmedian(matriz, axis=0), np.nanpercentile(matriz, DECIL_DIFICIL, axis=0)


def categoria_clima(historico: dict, reciente: dict, proyectado: dict) -> str | None:
    """Cada periodo es {'tipico', 'dificil'}. Ser apta es que el ano dificil llegue al minimo; que el cambio sea de
    verdad es que la compatibilidad TIPICA se mueva al menos CAMBIO_MATERIAL (el ano dificil de un periodo de 20 anos y
    otro de 15 difiere por azar, y cruzar el minimo por una centesima no vuelve nueva a una especie que se comporta
    igual). 'emergente': no era apta antes y a futuro lo es, con una mejora real. 'en_riesgo': lo era antes o ahora y a
    futuro cae de verdad. 'tradicional': el resto de las aptas ahora o a futuro. None: no lo es, y no hay cambio."""
    minimo = ce.PUNTAJE_MINIMO_APTA
    apta = lambda periodo: (periodo["dificil"] or 0.0) >= minimo
    tipico = lambda periodo: periodo["tipico"] or 0.0
    h, r, p = apta(historico), apta(reciente), apta(proyectado)
    if p:
        mejora = tipico(proyectado) - tipico(historico) >= CAMBIO_MATERIAL
        return "emergente" if (not h and mejora) else "tradicional"
    if (h or r) and max(tipico(historico), tipico(reciente)) - tipico(proyectado) >= CAMBIO_MATERIAL:
        return "en_riesgo"
    return "tradicional" if r else None


# ---------------------------------------------------------------- catalogo en memoria
class RepositorioCacheado:
    """Envuelve un repositorio y guarda en `almacen` (un dict que vive lo que viva el proceso) las lecturas del
    catalogo, que casi no cambia y tardan segundos: requisitos, identidades, luz y especies con fenologia. Lo demas
    pasa directo. Tambien guarda el CatalogoVectorial armado con esas filas. Las filas guardadas se comparten entre
    solicitudes: quien las lea no las modifica."""

    VIGENCIA_S = 1800

    def __init__(self, repo, almacen: dict, ahora=None):
        self._repo, self._almacen = repo, almacen
        self._ahora = ahora or time.monotonic

    def __getattr__(self, nombre):
        return getattr(self._repo, nombre)

    async def _leer(self, clave, lector):
        guardado = self._almacen.get(clave)
        if guardado and self._ahora() - guardado[0] < self.VIGENCIA_S:
            return guardado[1]
        valor = await lector()
        self._almacen[clave] = (self._ahora(), valor)
        return valor

    async def requisitos_genericos(self):
        return await self._leer("requisitos", self._repo.requisitos_genericos)

    async def identidades(self):
        return await self._leer("identidades", self._repo.identidades)

    async def equivalencias_luz(self):
        return await self._leer("luz", self._repo.equivalencias_luz)

    async def especies_con_fenologia(self):
        return await self._leer("fenologia", self._repo.especies_con_fenologia)

    # Lo que se lee de una especie al simularla: tambien casi no cambia, y son decenas de consultas por solicitud.
    async def requisitos(self, especie, variedad_local):
        return await self._leer(("requisitos", especie, variedad_local), lambda: self._repo.requisitos(especie, variedad_local))

    async def umbrales_fenologicos(self, especie, variedad_local):
        return await self._leer(("umbrales", especie, variedad_local),
                                lambda: self._repo.umbrales_fenologicos(especie, variedad_local))

    async def rasgos_rotacion(self, especie):
        return await self._leer(("rasgos", especie), lambda: self._repo.rasgos_rotacion(especie))

    async def especies_con_rasgos_rotacion(self):
        return await self._leer("especies_rotacion", self._repo.especies_con_rasgos_rotacion)

    async def reglas_dano(self, especie, variedad_local):
        return await self._leer(("reglas", especie, variedad_local), lambda: self._repo.reglas_dano(especie, variedad_local))

    async def parametros_agua(self, especie):
        return await self._leer(("agua", especie), lambda: self._repo.parametros_agua(especie))

    async def catalogo_vectorial(self) -> CatalogoVectorial:
        guardado = self._almacen.get("vectorial")
        requisitos = await self.requisitos_genericos()
        if guardado and guardado[1][0] is requisitos:
            return guardado[1][1]
        vectorial = CatalogoVectorial(requisitos, await self.equivalencias_luz())
        self._almacen["vectorial"] = (self._ahora(), (requisitos, vectorial))
        return vectorial


# ---------------------------------------------------------------- evaluacion de todo el catalogo
def puntajes_por_anio(cat: CatalogoVectorial, sitio: dict, series: list[pd.DataFrame], fijos: np.ndarray,
                      riego: bool, ajustes: dict | None = None) -> np.ndarray:
    """Matriz [anios, especies] de puntajes. `ajustes`: {indice de especie: f(clima del ano) -> puntaje de la
    simulacion por fase o None}; la especie vale el menor entre su simulacion y EcoCrop, y 0 si EcoCrop la descarta."""
    ghi = sitio.get("ghi_mensual")
    filas = []
    for df in series:
        limite, puntaje = cat.calcular_matriz(ce.normales_mensuales(df), fijos, ghi, riego)
        for i, simular in (ajustes or {}).items():
            if np.isnan(puntaje[i]):
                continue
            sim = simular(df)
            if sim is not None:
                puntaje[i] = 0.0 if limite[i] <= 0 else min(puntaje[i], sim)
        filas.append(puntaje)
    return np.vstack(filas)


def resumen_periodo(tipico: float, dificil: float) -> dict:
    redondear = lambda v: None if v is None or np.isnan(v) else round(float(v), 3)
    return {"tipico": redondear(tipico), "dificil": redondear(dificil)}


async def ranking_multianual(sitio: dict, repo, historia: dict[int, pd.DataFrame] | None, clima: pd.DataFrame | None,
                             lat: float | None, categorias: set[str] | None = None, riego: bool = False,
                             delta_temp: float = 0.0, simular_curadas: bool = True,
                             calentamiento_c_por_decada: float | None = None,
                             incluir_silvestres: bool = False,
                             unir_variedades: bool = True, solo: set[str] | None = None) -> tuple[list[dict], dict | None]:
    """El ranking de ranking_idoneidad() con el criterio multianual: cada especie se puntua en cada ano de la serie
    historica del predio y `apta` pasa a ser su ano dificil reciente (el peor decil) >= PUNTAJE_MINIMO_APTA.
    `puntaje` queda como la compatibilidad tipica reciente y se agrega `puntaje_ano_dificil` y, en `clima`, los tres
    periodos y la categoria. Devuelve (ranking, resumen de la serie); sin al menos ANIOS_RECIENTE + MIN_ANIOS_PERIODO
    anos de historia devuelve el ranking de un ano y resumen None. `calentamiento_c_por_decada`: un escenario que
    reemplaza la tendencia observada de la temperatura (un supuesto, no un pronostico); None usa la observada."""
    base = await ce.ranking_idoneidad(sitio, repo, clima=clima, lat=lat, categorias=categorias, riego=riego,
                                      incluir_silvestres=incluir_silvestres, unir_variedades=unir_variedades, solo=solo)
    if not historia or len(historia) < ANIOS_RECIENTE + MIN_ANIOS_PERIODO:
        return ce.aplicar_tope_suelo(base, sitio), None

    cat = (await repo.catalogo_vectorial()) if hasattr(repo, "catalogo_vectorial") else \
        CatalogoVectorial(await repo.requisitos_genericos(), await repo.equivalencias_luz())
    corregida = {a: ce.corregir_temperatura(df, delta_temp) if delta_temp else df for a, df in historia.items()}
    reciente, historico = periodos(corregida)
    tendencia = tendencia_clima(corregida)
    if calentamiento_c_por_decada is not None:
        tendencia["temp_c_por_anio"] = calentamiento_c_por_decada / 10
    fijos = cat.factores_fijos(sitio)

    # las especies con seguimiento por etapa: su simulacion corre ano por ano sobre el mismo clima
    ajustes = {}
    if simular_curadas and lat is not None:
        for r in base:
            if r.get("simulacion") is None:
                continue
            preparada = await ce.preparar_simulacion(r["especie"], None, repo)
            if preparada is None or (r.get("especie_ecocrop") or r["especie"]) not in cat.indice:
                continue
            ajustes[cat.indice[r.get("especie_ecocrop") or r["especie"]]] = _simulador(
                preparada, lat, sitio, riego)

    # el mismo ano de cada periodo en las tres lineas de tiempo; la proyectada parte de los anos recientes
    series = {"historico": [corregida[a] for a in historico], "reciente": [corregida[a] for a in reciente],
              "proyectado": [proyectar(corregida[a], a, tendencia) for a in reciente]}
    # ~1 s de calculo: en un hilo aparte, para no frenar a los demas usuarios mientras corre
    est = await asyncio.to_thread(lambda: {nombre: estadisticos(puntajes_por_anio(cat, sitio, df, fijos, riego, ajustes))
                                           for nombre, df in series.items()})
    for r in base:
        i = cat.indice.get(r.get("especie_ecocrop") or r["especie"])
        if i is None or r["puntaje"] is None:
            continue
        por = {n: resumen_periodo(est[n][0][i], est[n][1][i]) for n in est}
        rec = por["reciente"]
        apta = (rec["dificil"] or 0.0) >= ce.PUNTAJE_MINIMO_APTA
        r["clima"] = {**por, "categoria": categoria_clima(por["historico"], por["reciente"], por["proyectado"]),
                      "cambio_tipico_hasta_horizonte": round((por["proyectado"]["tipico"] or 0.0) - (por["historico"]["tipico"] or 0.0), 3)}
        r.update(puntaje_ano_actual=r["puntaje"], puntaje=rec["tipico"] or 0.0, puntaje_ano_dificil=rec["dificil"] or 0.0,
                 apta=apta, marginal=(not apta) and (rec["tipico"] or 0.0) > 0.0, metodo_periodo="multianual")
    prioridad = lambda r: (r["nivel_madurez"] != "perfil_generico",
                           bool(set(r["categorias"]) & ce.CATEGORIAS_ALIMENTO) and "weed" not in r["categorias"])
    base.sort(key=lambda r: r["especie"])
    base.sort(key=lambda r: (r["apta"] is True, r["puntaje"] if r["puntaje"] is not None else -1.0,
                             r.get("puntaje_ano_dificil") or 0.0, *prioridad(r)), reverse=True)
    ce.aplicar_tope_suelo(base, sitio)
    resumen = {k: tendencia[k] for k in ("anios", "primer_anio", "ultimo_anio", "temp_c_por_decada_observada",
                                         "lluvia_pct_por_decada_observada")}
    resumen.update(periodo_historico=[historico[0], historico[-1]], periodo_reciente=[reciente[0], reciente[-1]],
                   horizonte=HORIZONTE_PROYECCION, temp_c_por_decada_usada=round(tendencia["temp_c_por_anio"] * 10, 2),
                   decil=DECIL_DIFICIL, escenario="observado" if calentamiento_c_por_decada is None else "supuesto")
    return base, resumen


def _simulacion_anual(preparada: dict, lat: float, sitio: dict, riego: bool, df: pd.DataFrame) -> dict | None:
    """La simulacion por fase de una especie sobre un ano de clima (repetido una vez para cerrar ciclos que cruzan el
    fin de ano); None si el clima tiene huecos o no hay desde la fecha de siembra."""
    ciclico = ce._clima_ciclico(df)
    if ciclico is None:
        return None
    try:
        return ce.simular_idoneidad(preparada, ciclico, lat, sitio.get("awc_mm"), riego, sitio.get("et0_factor_mensual"),
                                    ce.PROFUNDIDAD_SUELO_M.get((sitio.get("suelo") or {}).get("profundidad")))
    except ce.ClimaIncompleto:
        return None


def _simulador(preparada: dict, lat: float, sitio: dict, riego: bool):
    """f(clima de un ano) -> puntaje de la simulacion por fase (1 - perdida), 0 si no completa el ciclo, None si no corre."""
    def simular(df: pd.DataFrame):
        r = _simulacion_anual(preparada, lat, sitio, riego, df)
        return None if r is None else round(1 - r.get("perdida_simulada", 1.0), 3)
    return simular


# ---------------------------------------------------------------- matrices por ano para el motor de rotacion
async def perdidas_anuales(sitio: dict, repo, historia: dict[int, pd.DataFrame] | None, lat: float | None,
                           especies: list[str], riego: bool = False, delta_temp: float = 0.0,
                           calentamiento_c_por_decada: float | None = None) -> dict | None:
    """El puntaje de cada especie pedida en cada ano, sin tocar el resultado de ranking_multianual(): lo mismo que
    el ranking calcula, pero la matriz entera para que el motor de rotacion pueda encadenar temporadas.

    Devuelve {'anios': [...], 'especies': {nombre: {'indice', 'simulada'}}, 'escenarios': {'reciente': {'puntaje',
    'ciclo_dias'}, 'proyectado': {...}}, 'resumen': {...}}. Cada matriz es [anios, especies] en el orden de `especies`:
    'reciente' son los ultimos ANIOS_RECIENTE anos y 'proyectado' esos mismos anos llevados a HORIZONTE_PROYECCION con
    la tendencia (o `calentamiento_c_por_decada`). `puntaje` es NaN donde la especie no tiene fila de EcoCrop; `ciclo_dias`
    es NaN donde no se simulo la especie o no cerro el ciclo. El indice de EcoCrop es la fila gemela por nombre cientifico
    (como en ranking_idoneidad) y, si no la hay, la fila de la propia especie. None sin al menos ANIOS_RECIENTE +
    MIN_ANIOS_PERIODO anos de historia."""
    if not historia or len(historia) < ANIOS_RECIENTE + MIN_ANIOS_PERIODO:
        return None
    cat = (await repo.catalogo_vectorial()) if hasattr(repo, "catalogo_vectorial") else \
        CatalogoVectorial(await repo.requisitos_genericos(), await repo.equivalencias_luz())
    identidades = await repo.identidades()
    corregida = {a: ce.corregir_temperatura(df, delta_temp) if delta_temp else df for a, df in historia.items()}
    reciente, _ = periodos(corregida)
    tendencia = tendencia_clima(corregida)
    if calentamiento_c_por_decada is not None:
        tendencia["temp_c_por_anio"] = calentamiento_c_por_decada / 10
    fijos = cat.factores_fijos(sitio)

    indice, ajustes = {}, {}
    ciclos: dict[int, dict[int, float]] = {}      # indice de especie -> {ano: dias de ciclo}
    for nombre in especies:
        cientifico = (identidades.get(nombre) or {}).get("nombre_cientifico")
        gemela = ce._slug(cientifico) if cientifico else None
        i = cat.indice.get(gemela) if gemela in cat.indice else cat.indice.get(nombre)
        indice[nombre] = {"indice": i, "simulada": False}
        if i is None or lat is None:
            continue
        preparada = await ce.preparar_simulacion(nombre, None, repo)
        if preparada is None:
            continue
        indice[nombre]["simulada"] = True
        ajustes[i] = _simulador_con_ciclo(preparada, lat, sitio, riego, ciclos.setdefault(i, {}))

    series = {"reciente": [corregida[a] for a in reciente],
              "proyectado": [proyectar(corregida[a], a, tendencia) for a in reciente]}
    columnas = [indice[n]["indice"] for n in especies]

    def calcular():
        salida = {}
        for nombre, df in series.items():
            for c in ciclos.values():
                c.clear()
            m = puntajes_por_anio(cat, sitio, df, fijos, riego, ajustes)
            puntaje = np.full((len(df), len(columnas)), np.nan)
            ciclo = np.full((len(df), len(columnas)), np.nan)
            for j, i in enumerate(columnas):
                if i is None:
                    continue
                puntaje[:, j] = m[:, i]
                for k, a in enumerate(reciente):
                    ciclo[k, j] = ciclos.get(i, {}).get(a, np.nan)
            salida[nombre] = {"puntaje": puntaje, "ciclo_dias": ciclo}
        return salida

    escenarios = await asyncio.to_thread(calcular)    # ~1 s de calculo: en un hilo aparte
    resumen = {k: tendencia[k] for k in ("anios", "primer_anio", "ultimo_anio", "temp_c_por_decada_observada",
                                         "lluvia_pct_por_decada_observada")}
    resumen.update(periodo_reciente=[reciente[0], reciente[-1]], horizonte=HORIZONTE_PROYECCION,
                   temp_c_por_decada_usada=round(tendencia["temp_c_por_anio"] * 10, 2),
                   escenario="observado" if calentamiento_c_por_decada is None else "supuesto")
    return {"anios": list(reciente), "especies": indice, "escenarios": escenarios, "resumen": resumen}


def _simulador_con_ciclo(preparada: dict, lat: float, sitio: dict, riego: bool, ciclos: dict):
    """Como _simulador(), y deja en `ciclos` {ano: dias} el ciclo de cada ano en que la especie lo cerro."""
    def simular(df: pd.DataFrame):
        r = _simulacion_anual(preparada, lat, sitio, riego, df)
        if r is None:
            return None
        if r.get("ciclo_dias") is not None:
            ciclos[int(df.index[0].year)] = float(r["ciclo_dias"])
        return round(1 - r.get("perdida_simulada", 1.0), 3)
    return simular
