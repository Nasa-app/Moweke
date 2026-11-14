"""
Mogewe — API. Fase 2 del plan de MVP: solo autenticacion por ahora. Las fases
siguientes agregan routers (parcelas, fenologia, rotacion, alertas) sin tocar este
bloque de auth.
"""
from __future__ import annotations

import os
from datetime import date, timedelta

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

import services.cliente_clsoilmaps as cliente_clsoilmaps
import services.cliente_copernicus as cliente_copernicus
import services.cliente_cr2met as cliente_cr2met
import services.cliente_solar as cliente_solar
from services.auth import crear_token, decodificar_token, hash_password, verificar_password
from services.db import obtener_sesion
from services.repositorio_clima import guardar_consulta_grilla

_CACHE_CR2MET = os.environ.get("CR2MET_CACHE_DIR", "/tmp/cr2met_cache")
_CACHE_CLSOILMAPS = os.environ.get("CLSOILMAPS_CACHE_DIR", "/tmp/clsoilmaps_cache")
_CLSOILMAPS_ARCHIVO_INTERNO = "ROSETTA_MEAN/Total_AWC_0_200cm.tif"

app = FastAPI(title="Mogewe")

_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# ---------------------------------------------------------------- esquemas
class RegistroAgricultor(BaseModel):
    nombre: str
    telefono: str
    password: str
    pais: str = "Chile"
    lat: float
    lon: float


class LoginAgricultor(BaseModel):
    telefono: str
    password: str


class LoginAdmin(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------- dependencias de autorizacion
async def usuario_actual(token: str | None = Depends(_oauth2), session: AsyncSession = Depends(obtener_sesion)) -> dict:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta token")
    try:
        payload = decodificar_token(token)
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalido o expirado")
    fila = (await session.execute(
        text("SELECT id, nombre, rol FROM usuarios WHERE id = :id"), {"id": int(payload["sub"])}
    )).mappings().first()
    if not fila:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario no existe")
    return dict(fila)


async def requerir_admin(usuario: dict = Depends(usuario_actual)) -> dict:
    if usuario["rol"] != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Requiere rol admin")
    return usuario


# ---------------------------------------------------------------- endpoints
@app.post("/api/auth/registro", response_model=TokenOut)
async def registro_agricultor(datos: RegistroAgricultor, session: AsyncSession = Depends(obtener_sesion)):
    existe = (await session.execute(
        text("SELECT id FROM usuarios WHERE telefono = :t"), {"t": datos.telefono}
    )).first()
    if existe:
        raise HTTPException(status.HTTP_409_CONFLICT, "Telefono ya registrado")
    fila = (await session.execute(
        text("""INSERT INTO usuarios (nombre, pais, telefono, password_hash, rol, geometria)
                 VALUES (:nombre, :pais, :telefono, :ph, 'agricultor', ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
                 RETURNING id"""),
        {"nombre": datos.nombre, "pais": datos.pais, "telefono": datos.telefono,
         "ph": hash_password(datos.password), "lon": datos.lon, "lat": datos.lat},
    )).first()
    await session.commit()
    return TokenOut(access_token=crear_token(fila.id, "agricultor"))


@app.post("/api/auth/login", response_model=TokenOut)
async def login_agricultor(datos: LoginAgricultor, session: AsyncSession = Depends(obtener_sesion)):
    fila = (await session.execute(
        text("SELECT id, password_hash, rol FROM usuarios WHERE telefono = :t"), {"t": datos.telefono}
    )).mappings().first()
    if not fila or not fila["password_hash"] or not verificar_password(datos.password, fila["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Telefono o contraseña incorrectos")
    return TokenOut(access_token=crear_token(fila["id"], fila["rol"]))


@app.post("/api/auth/login-admin", response_model=TokenOut)
async def login_admin(datos: LoginAdmin, session: AsyncSession = Depends(obtener_sesion)):
    fila = (await session.execute(
        text("SELECT id, password_hash, rol FROM usuarios WHERE email = :e AND rol = 'admin'"), {"e": datos.email}
    )).mappings().first()
    if not fila or not fila["password_hash"] or not verificar_password(datos.password, fila["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email o contraseña incorrectos")
    return TokenOut(access_token=crear_token(fila["id"], fila["rol"]))


@app.get("/api/auth/yo")
async def yo(usuario: dict = Depends(usuario_actual)):
    return usuario


# ---------------------------------------------------------------- fuentes nuevas (extension
# post-MVP: Copernicus + Explorador Solar, ver plan) -- solo admin, es ingesta/diagnostico,
# no algo que un agricultor consulte directo. No reemplazan la Fase 5 completa (POWER +
# AppEEARS orquestados) -- son las dos fuentes nuevas evaluadas, cada una verificada por
# separado contra services/cliente_solar.py y services/cliente_copernicus.py.

@app.post("/api/admin/parcelas/{id_parcela}/ingesta/solar")
async def ingesta_solar(id_parcela: int, session: AsyncSession = Depends(obtener_sesion),
                         _admin: dict = Depends(requerir_admin)):
    centroide = (await session.execute(
        text("SELECT ST_Y(ST_Centroid(geometria)) AS lat, ST_X(ST_Centroid(geometria)) AS lon "
             "FROM parcela WHERE id = :id"), {"id": id_parcela},
    )).mappings().first()
    if not centroide:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Parcela no existe")
    lat, lon = centroide["lat"], centroide["lon"]

    if not cliente_solar.disponibilidad(lat, lon):
        for capa in ("explorador_solar_ghi", "explorador_solar_dni", "explorador_solar_difh"):
            await guardar_consulta_grilla(session, id_parcela, capa, date(2004, 1, 1), date(2016, 12, 31),
                                           None, "1km", "explorador_solar_v1", "sin_dato")
        return {"disponible": False, "parcela": id_parcela, "lat": lat, "lon": lon}

    datos = cliente_solar.consultar_vista_rapida(lat, lon)
    periodo_inicio, periodo_fin = date(2004, 1, 1), date(2016, 12, 31)  # periodo real de la climatologia
    guardado = {}
    for capa, valor in (("explorador_solar_ghi", datos["ghi_kwh_m2_dia"]),
                         ("explorador_solar_dni", datos["dni_kwh_m2_dia"]),
                         ("explorador_solar_difh", datos["difh_kwh_m2_dia"])):
        await guardar_consulta_grilla(session, id_parcela, capa, periodo_inicio, periodo_fin,
                                       valor, "1km", "explorador_solar_v1", "completa")
        guardado[capa] = valor
    return {"disponible": True, "parcela": id_parcela, "lat": lat, "lon": lon,
            "guardado_en_cache_consulta_grilla": guardado, "datos_completos": datos}


@app.post("/api/admin/parcelas/{id_parcela}/ingesta/suelo")
async def ingesta_suelo(id_parcela: int, session: AsyncSession = Depends(obtener_sesion),
                         _admin: dict = Depends(requerir_admin)):
    """CLSoilMaps -- agua disponible total (0-200cm). La primera llamada en un
    despliegue nuevo tarda ~20 min (extrae 328MB comprimidos del zip remoto de Zenodo,
    ver cliente_clsoilmaps.py); las siguientes son instantaneas (archivo ya en cache)."""
    centroide = (await session.execute(
        text("SELECT ST_Y(ST_Centroid(geometria)) AS lat, ST_X(ST_Centroid(geometria)) AS lon "
             "FROM parcela WHERE id = :id"), {"id": id_parcela},
    )).mappings().first()
    if not centroide:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Parcela no existe")
    lat, lon = centroide["lat"], centroide["lon"]

    os.makedirs(_CACHE_CLSOILMAPS, exist_ok=True)
    destino = os.path.join(_CACHE_CLSOILMAPS, "Total_AWC_0_200cm.tif")
    archivo = cliente_clsoilmaps.extraer_archivo(_CLSOILMAPS_ARCHIVO_INTERNO, destino)
    valor = cliente_clsoilmaps.leer_valor_punto(archivo, lat, lon)

    # Sin dimension temporal real (mapa estatico) -- se usa el periodo de publicacion
    # (Zenodo, dic-2022) como marca, igual que el 2004-2016 del Explorador Solar.
    await guardar_consulta_grilla(session, id_parcela, "clsoilmaps_awc_total_mm",
                                   date(2022, 1, 1), date(2022, 12, 31), valor,
                                   "100m", "CLSoilMaps_v1", "sin_dato" if valor is None else "completa")
    return {"parcela": id_parcela, "lat": lat, "lon": lon, "agua_disponible_total_mm": valor}


@app.get("/api/admin/copernicus/sentinel2/disponibilidad")
async def disponibilidad_sentinel2(lat: float, lon: float, dias: int = 30, nube_max: float = 30.0,
                                    _admin: dict = Depends(requerir_admin)):
    hoy = date.today()
    desde = date.fromordinal(hoy.toordinal() - dias)
    escenas = cliente_copernicus.buscar_sentinel2(lat, lon, desde.isoformat(), hoy.isoformat(), nube_max=nube_max)
    return {"lat": lat, "lon": lon, "desde": desde.isoformat(), "hasta": hoy.isoformat(),
            "nube_max_pct": nube_max, "escenas_encontradas": len(escenas), "escenas": escenas}


@app.get("/api/admin/copernicus/sentinel1/disponibilidad")
async def disponibilidad_sentinel1(lat: float, lon: float, dias: int = 14,
                                    _admin: dict = Depends(requerir_admin)):
    hoy = date.today()
    desde = date.fromordinal(hoy.toordinal() - dias)
    escenas = cliente_copernicus.buscar_sentinel1(lat, lon, desde.isoformat(), hoy.isoformat())
    return {"lat": lat, "lon": lon, "desde": desde.isoformat(), "hasta": hoy.isoformat(),
            "escenas_encontradas": len(escenas), "escenas": escenas}


@app.post("/api/admin/parcelas/{id_parcela}/ingesta/cr2met")
async def ingesta_cr2met(id_parcela: int, dias: int = 90, session: AsyncSession = Depends(obtener_sesion),
                          _admin: dict = Depends(requerir_admin)):
    """Un dia de clima = una fila (mismo patron que POWER/AppEEARS, ver comentario en
    database/schema.sql sobre cache_consulta_grilla) -- no un solo valor agregado."""
    centroide = (await session.execute(
        text("SELECT ST_Y(ST_Centroid(geometria)) AS lat, ST_X(ST_Centroid(geometria)) AS lon "
             "FROM parcela WHERE id = :id"), {"id": id_parcela},
    )).mappings().first()
    if not centroide:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Parcela no existe")
    lat, lon = centroide["lat"], centroide["lon"]

    hoy = date.today()
    desde = hoy - timedelta(days=dias)
    clima = cliente_cr2met.consultar_cr2met(lat, lon, desde.isoformat(), hoy.isoformat(), _CACHE_CR2MET)

    filas_escritas = 0
    for fecha, fila in clima.iterrows():
        dia = fecha.date()
        for capa, valor in (("cr2met_tmin", fila["tmin"]), ("cr2met_tmax", fila["tmax"]),
                             ("cr2met_lluvia", fila["lluvia"])):
            if valor != valor:  # NaN real (dia todavia sin dato por la latencia del NRT)
                continue
            await guardar_consulta_grilla(session, id_parcela, capa, dia, dia,
                                           float(valor), "0.05deg_~5km", "cr2met_v2.5_nrt", "completa")
            filas_escritas += 1
    return {"parcela": id_parcela, "lat": lat, "lon": lon, "dias_con_dato": len(clima),
            "filas_escritas_en_cache": filas_escritas, "ultimo_dia_real": str(clima.index.max().date())}


@app.post("/api/admin/parcelas/{id_parcela}/ingesta/copernicus")
async def ingesta_copernicus(id_parcela: int, dias: int = 30, intervalo_dias: int = 10,
                              session: AsyncSession = Depends(obtener_sesion),
                              _admin: dict = Depends(requerir_admin)):
    """NDVI (Sentinel-2, enmascarado por nubes) + backscatter VV (Sentinel-1, sin nubes)
    via Statistical API -- necesita COPERNICUS_CLIENT_ID/COPERNICUS_CLIENT_SECRET en el
    entorno (OAuth client de dataspace.copernicus.eu, no el usuario/clave de la cuenta)."""
    client_id, client_secret = os.environ.get("COPERNICUS_CLIENT_ID"), os.environ.get("COPERNICUS_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                             "Faltan COPERNICUS_CLIENT_ID/COPERNICUS_CLIENT_SECRET en el entorno")

    fila_parcela = (await session.execute(
        text("SELECT ST_XMin(geometria) AS xmin, ST_YMin(geometria) AS ymin, "
             "ST_XMax(geometria) AS xmax, ST_YMax(geometria) AS ymax FROM parcela WHERE id = :id"),
        {"id": id_parcela},
    )).mappings().first()
    if not fila_parcela:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Parcela no existe")
    bbox = [fila_parcela["xmin"], fila_parcela["ymin"], fila_parcela["xmax"], fila_parcela["ymax"]]

    hoy = date.today()
    desde = hoy - timedelta(days=dias)
    token = cliente_copernicus.obtener_token_oauth(client_id, client_secret)
    ndvi = cliente_copernicus.ndvi_estadistico(token, bbox, desde.isoformat(), hoy.isoformat(), intervalo_dias)
    vv = cliente_copernicus.backscatter_estadistico(token, bbox, desde.isoformat(), hoy.isoformat(), "VV", intervalo_dias)

    filas_escritas = 0
    for capa, serie in (("sentinel2_ndvi", ndvi), ("sentinel1_vv", vv)):
        for intervalo in serie:
            sin_dato = intervalo["noDataCount"] == intervalo["sampleCount"]
            await guardar_consulta_grilla(
                session, id_parcela, capa, date.fromisoformat(intervalo["desde"][:10]),
                date.fromisoformat(intervalo["hasta"][:10]),
                None if sin_dato else float(intervalo["mean"]), "10m",
                "sentinel-2-l2a" if capa == "sentinel2_ndvi" else "sentinel-1-grd",
                "sin_dato" if sin_dato else "completa",
            )
            filas_escritas += 1
    return {"parcela": id_parcela, "bbox": bbox, "filas_escritas_en_cache": filas_escritas,
            "ndvi": ndvi, "backscatter_vv": vv}
