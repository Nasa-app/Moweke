"""
Mogewe — API. Fase 2 del plan de MVP: solo autenticacion por ahora. Las fases
siguientes agregan routers (parcelas, fenologia, rotacion, alertas) sin tocar este
bloque de auth.
"""
from __future__ import annotations

from datetime import date

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

import services.cliente_copernicus as cliente_copernicus
import services.cliente_solar as cliente_solar
from services.auth import crear_token, decodificar_token, hash_password, verificar_password
from services.db import obtener_sesion
from services.repositorio_clima import guardar_consulta_grilla

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
