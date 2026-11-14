"""
Cliente AppEEARS v0.1 — HLS, SMAP, MOD13Q1, ECOSTRESS, SRTM.

NO VERIFICADO POR EJECUCION: AppEEARS exige login de Earthdata (usuario/clave -> token),
y este entorno no tiene credenciales ni acceso a internet mas alla de lo que ya se probo
con curl. A diferencia de services/cliente_power.py (probado en vivo), esto esta escrito
contra la documentacion real de la API (appeears.earthdatacloud.nasa.gov/api/) pero no
corrio ni una vez. Probar contra una cuenta real antes de confiar en el.

Patron, muy distinto al de POWER: no es una consulta sincrona que devuelve el dato al
tiro. Es un trabajo asincrono -- se pide, se espera (minutos a horas, no segundos), se
descarga cuando esta listo. Por eso Flujo 1/2 (docs/arquitectura-flujos-mogewe.md) tienen
una tabla `job_extraccion` en vez de llamar esto directo desde un endpoint que el usuario
espera en pantalla.

A diferencia de POWER (que entrega directo las columnas tmin/tmax/lluvia/rh del `clima`
que el motor consume), lo que devuelve AppEEARS NO entra al mismo DataFrame -- entra a
`cache_consulta_grilla`/`cache_consulta_regional` como un valor mas (EVI de hoy, humedad
de SMAP, elevacion de SRTM), consumido por funciones distintas del motor
(detect_curve_anomaly, el dispatcher de bioma, calcular_idoneidad), nunca por
pheno_engine.simular() directamente.
"""
from __future__ import annotations

import time

import requests

URL_BASE = "https://appeears.earthdatacloud.nasa.gov/api"


def iniciar_sesion(usuario: str, clave: str, timeout: int = 20) -> str:
    """Devuelve el token bearer. Expira a las 48h -- quien use este cliente en el job
    nocturno (Flujo 2) tiene que volver a loguearse si el token vencio, no asumir que
    un token guardado sigue valido indefinidamente."""
    r = requests.post(f"{URL_BASE}/login", auth=(usuario, clave), timeout=timeout)
    r.raise_for_status()
    return r.json()["token"]


def solicitar_extraccion_puntual(token: str, nombre_tarea: str, producto: str, capa: str,
                                  puntos: list[dict], fecha_inicio: str, fecha_fin: str,
                                  timeout: int = 20) -> str:
    """puntos: [{"latitude": lat, "longitude": lon, "id": "parcela_123", "category": "..."}].
    fechas: 'MM-DD-YYYY' (formato que pide la API, distinto al de POWER -- confirmar
    contra la documentacion vigente antes de usar, no asumir que no cambio).
    Devuelve task_id. No bloquea -- el trabajo queda corriendo del lado de AppEEARS."""
    return solicitar_extraccion_multicapa(token, nombre_tarea, [(producto, capa)],
                                           puntos, fecha_inicio, fecha_fin, timeout)


def solicitar_extraccion_multicapa(token: str, nombre_tarea: str, capas: list[tuple[str, str]],
                                    puntos: list[dict], fecha_inicio: str, fecha_fin: str,
                                    timeout: int = 20) -> str:
    """capas: [(producto, capa), ...] -- varias bandas/productos en UNA sola tarea (ej.
    B04+B05+B06 de HLSL30.020 para poder armar NDVI/NDMI del mismo pase, sin tres tareas
    separadas con posible desfase de fecha entre ellas). Mismo endpoint que
    solicitar_extraccion_puntual(), que ahora es el caso de una sola capa de este."""
    tarea = {
        "task_type": "point",
        "task_name": nombre_tarea,
        "params": {
            "dates": [{"startDate": fecha_inicio, "endDate": fecha_fin}],
            "layers": [{"product": p, "layer": c} for p, c in capas],
            "coordinates": puntos,
        },
    }
    r = requests.post(f"{URL_BASE}/task", json=tarea,
                       headers={"Authorization": f"Bearer {token}"}, timeout=timeout)
    r.raise_for_status()
    return r.json()["task_id"]


def estado_tarea(token: str, task_id: str, timeout: int = 20) -> str:
    """'pending' | 'processing' | 'done' | 'error' -- revisar el vocabulario exacto de la
    API, esto es lo que documentan pero no se confirmo contra una respuesta real."""
    r = requests.get(f"{URL_BASE}/task/{task_id}",
                      headers={"Authorization": f"Bearer {token}"}, timeout=timeout)
    r.raise_for_status()
    return r.json()["status"]


def esperar_y_descargar(token: str, task_id: str, destino: str,
                         intervalo_s: int = 300, max_intentos: int = 50) -> str | None:
    """Uso solo fuera del flujo de request HTTP del usuario -- esto es para el worker del
    Flujo 2 (job nocturno), nunca para un endpoint que alguien espera en pantalla. Con
    intervalo_s=300 y max_intentos=50 cubre hasta ~4 horas, consistente con lo que ya
    documentamos (AppEEARS puede tardar de minutos a horas)."""
    for _ in range(max_intentos):
        estado = estado_tarea(token, task_id)
        if estado == "done":
            return _descargar_bundle(token, task_id, destino)
        if estado == "error":
            return None
        time.sleep(intervalo_s)
    return None  # se agoto el tiempo de espera -- job_extraccion.estado queda 'en_proceso'


def _descargar_bundle(token: str, task_id: str, destino: str, timeout: int = 60) -> str:
    """VERIFICADO (Fase 4) con una extraccion real (MOD13Q1.061, Castro) -- un bundle 'point'
    trae 5 archivos: el CSV de resultados, metadata.xml, README.md, request.json y
    granule-list.txt. El viejo codigo tomaba `files[0]` a ciegas; hoy coincidia con el CSV
    por orden de suerte, no por seleccion real -- se busca explicito `file_type == 'csv'`."""
    r = requests.get(f"{URL_BASE}/bundle/{task_id}",
                      headers={"Authorization": f"Bearer {token}"}, timeout=timeout)
    r.raise_for_status()
    archivos = r.json()["files"]
    csv = next((f for f in archivos if f["file_type"] == "csv"), None)
    if csv is None:
        raise ValueError(f"bundle de la tarea {task_id} sin archivo csv: {[f['file_name'] for f in archivos]}")
    contenido = requests.get(f"{URL_BASE}/bundle/{task_id}/{csv['file_id']}",
                              headers={"Authorization": f"Bearer {token}"}, timeout=timeout)
    contenido.raise_for_status()
    with open(destino, "wb") as f:
        f.write(contenido.content)
    return destino


def nombre_columna_valor(producto: str, capa: str) -> str:
    """VERIFICADO (Fase 4): el CSV de resultados no usa el nombre de la capa tal cual --
    antepone el producto con puntos reemplazados por guion bajo, ej. producto='MOD13Q1.061'
    + capa='_250m_16_days_EVI' -> columna 'MOD13Q1_061__250m_16_days_EVI' (doble guion bajo
    porque la capa ya empieza con uno). Quien parsee el CSV (services/repositorio_clima.py,
    Fase 5) tiene que construir el nombre de columna asi, no asumir que es `capa`."""
    return f"{producto.replace('.', '_')}_{capa}"


VALOR_SIN_DATOS = -3000.0  # relleno real observado (pixel nublado/sin cobertura) -- filtrar
# antes de usar, no es un EVI valido (EVI real esta acotado aprox. [-1, 1]). Fechas del CSV
# de resultados vienen 'YYYY-MM-DD' (columna 'Date') -- distinto al formato de ENVIO de la
# tarea ('MM-DD-YYYY', ver solicitar_extraccion_puntual), no asumir que son el mismo formato.
# NO aplica a HLS -- HLSL30/HLSS30 no rellenan con -3000, las filas sin dato por nube
# quedan marcadas en el Fmask (bit 'Cloud'), ver filtrar_nubes_hls() mas abajo.


def consultar_punto_sincrono(token: str, nombre_tarea: str, capas: list[tuple[str, str]],
                              lat: float, lon: float, fecha_inicio: str, fecha_fin: str,
                              destino_csv: str, intervalo_s: int = 15, max_intentos: int = 40):
    """Version sincrona para una tarea 'point' -- estas tardan minutos, no horas (a
    diferencia de una tarea 'area'), asi que esperar en el mismo request es razonable
    para un endpoint de administracion/diagnostico. VERIFICADO (extension post-MVP):
    Landsat (HLSL30.020) corrio completo en menos de 5 minutos para un punto real.
    No usar este patron para una tarea 'area' ni dentro de un endpoint que un agricultor
    espere en pantalla -- para eso sigue siendo valido esperar_y_descargar() + job_extraccion."""
    import pandas as pd

    punto = [{"latitude": lat, "longitude": lon, "id": "consulta", "category": "parcela"}]
    task_id = solicitar_extraccion_multicapa(token, nombre_tarea, capas, punto, fecha_inicio, fecha_fin)
    for _ in range(max_intentos):
        estado = estado_tarea(token, task_id)
        if estado == "done":
            _descargar_bundle(token, task_id, destino_csv)
            return pd.read_csv(destino_csv)
        if estado == "error":
            raise RuntimeError(f"tarea {task_id} ({nombre_tarea}) termino en error")
        time.sleep(intervalo_s)
    raise TimeoutError(f"tarea {task_id} ({nombre_tarea}) no termino tras {max_intentos * intervalo_s}s")


def filtrar_nubes_hls(df, columna_fmask: str):
    """VERIFICADO contra una extraccion real de HLSL30.020: el bit 'Cloud' del Fmask
    marca la fila como nublada -- un valor de reflectancia bajo nube no es un dato real,
    aunque el CSV no lo rellene con un centinela como MOD13Q1. df debe tener la columna
    '{col_fmask}_Cloud'. BUG REAL encontrado al probar: esa columna NO es 0/1 entero --
    es el string "0b0"/"0b1" (igual que los demas campos de bitmask de AppEEARS, ej.
    VI_Quality de MOD13Q1). Comparar contra el entero 0 nunca matchea -- filtraba las 6
    de 6 filas de una extraccion real, descartando tambien el unico dia realmente
    despejado (2026-09-07, 'No' en la Description)."""
    columna_nube = f"{columna_fmask}_Cloud"
    if columna_nube not in df.columns:
        return df
    return df[df[columna_nube] == "0b0"].copy()


def calcular_ndvi_ndmi(df_b04, df_b05, df_b06, producto: str = "HLSL30.020"):
    """Combina tres extracciones de banda (roja/B04, NIR/B05, SWIR1/B06) por fecha real
    -- NDVI = (NIR-roja)/(NIR+roja) (vegetacion/reflectancia), NDMI = (NIR-SWIR1)/(NIR+SWIR1)
    (humedad de dosel/sequedad). Las tres vienen de tareas separadas (mismo producto,
    punto y rango de fechas) -- se cruzan por 'Date', no se asume que vengan en el mismo
    orden de filas (AppEEARS puede devolver pases distintos si una banda tuvo mas o menos
    cobertura util)."""
    import pandas as pd

    b04 = nombre_columna_valor(producto, "B04")
    b05 = nombre_columna_valor(producto, "B05")
    b06 = nombre_columna_valor(producto, "B06")
    m = df_b04[["Date", b04]].merge(df_b05[["Date", b05]], on="Date").merge(df_b06[["Date", b06]], on="Date")
    m["ndvi"] = (m[b05] - m[b04]) / (m[b05] + m[b04])
    m["ndmi"] = (m[b05] - m[b06]) / (m[b05] + m[b06])
    return m[["Date", "ndvi", "ndmi"]]
