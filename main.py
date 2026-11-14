"""
Mogewe — API. Fase 2 del plan de MVP: solo autenticacion por ahora. Las fases
siguientes agregan routers (parcelas, fenologia, rotacion, alertas) sin tocar este
bloque de auth.
"""
from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from services.auth import crear_token, decodificar_token, hash_password, verificar_password
from services.db import obtener_sesion

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
