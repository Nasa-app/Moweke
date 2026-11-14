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
    tarea = {
        "task_type": "point",
        "task_name": nombre_tarea,
        "params": {
            "dates": [{"startDate": fecha_inicio, "endDate": fecha_fin}],
            "layers": [{"product": producto, "layer": capa}],
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
    r = requests.get(f"{URL_BASE}/bundle/{task_id}",
                      headers={"Authorization": f"Bearer {token}"}, timeout=timeout)
    r.raise_for_status()
    # Descarga del primer archivo del bundle -- un gran salto de proveedor real a "un
    # archivo", sin verificar: en la practica un bundle de AppEEARS trae varios archivos
    # (uno por capa/fecha). Esto queda simplificado a proposito porque no se pudo probar
    # contra una respuesta real para saber la forma exacta.
    archivo_id = r.json()["files"][0]["file_id"]
    contenido = requests.get(f"{URL_BASE}/bundle/{task_id}/{archivo_id}",
                              headers={"Authorization": f"Bearer {token}"}, timeout=timeout)
    contenido.raise_for_status()
    with open(destino, "wb") as f:
        f.write(contenido.content)
    return destino
