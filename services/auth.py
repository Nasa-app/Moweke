"""
Autenticacion — Fase 2 del plan de MVP.

Agricultor: identificado por telefono (mas confiable que email en el contexto
rural chilote). Admin: identificado por email. Password nunca en texto plano,
nunca en logs. JWT para la API; expiracion corta por defecto, sin refresh token
todavia (fuera de alcance del MVP -- el agricultor vuelve a iniciar sesion).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from passlib.context import CryptContext

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
ALGORITHM = "HS256"
EXPIRACION_MINUTOS = 60 * 24  # 24h -- razonable para un agricultor que abre la app una vez al dia
# Una cuenta anonima no tiene telefono ni contrasena: no hay forma de volver a entrar a ella salvo
# con este mismo token. Por eso dura un ano (mas que una temporada de cultivo) y no un dia.
EXPIRACION_ANONIMO_MINUTOS = 60 * 24 * 365


class ConfiguracionAuthFaltante(RuntimeError):
    """JWT_SECRET_KEY no esta en el entorno. Nunca usar un secreto por defecto
    hardcodeado -- eso equivaldria a no tener autenticacion en absoluto."""


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verificar_password(password: str, password_hash: str) -> bool:
    return _pwd.verify(password, password_hash)


def crear_token(id_usuario: int, rol: str, minutos: int = EXPIRACION_MINUTOS) -> str:
    if not SECRET_KEY:
        raise ConfiguracionAuthFaltante("JWT_SECRET_KEY no esta definida en el entorno.")
    expira = datetime.now(timezone.utc) + timedelta(minutes=minutos)
    payload = {"sub": str(id_usuario), "rol": rol, "exp": expira}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decodificar_token(token: str) -> dict:
    """Levanta jose.JWTError si el token es invalido o expiro -- quien llama
    (el middleware de FastAPI) lo traduce a 401, nunca deja pasar un token malo
    en silencio."""
    if not SECRET_KEY:
        raise ConfiguracionAuthFaltante("JWT_SECRET_KEY no esta definida en el entorno.")
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
