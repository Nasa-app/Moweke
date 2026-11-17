"""
mogen — API. Autenticacion (Fase 2), el flujo del agricultor punto -> predio ->
especies candidatas (/api/parcelas) y las ingestas de verificacion solo para admin
(/api/admin). Las fases siguientes agregan fenologia, rotacion y alertas sin tocar el
bloque de auth.
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import sys
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

# catalogo_especies.py (y lo que importa: pheno_engine/motor_estres) usa imports planos
# (`from pheno_engine import ...`), no `services.pheno_engine` -- mismo patron que todas
# las verificaciones de este proyecto (`sys.path.insert(0, 'services')` + import plano).
# Sin esto, `import services.catalogo_especies` revienta con ModuleNotFoundError al
# intentar resolver su `from pheno_engine import Cultivo` interno.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "services"))

import services.catalogo_especies as catalogo_especies
import services.alertas_clima as alertas_clima
import services.cliente_appeears as cliente_appeears
import services.cliente_clsoilmaps as cliente_clsoilmaps
import services.cliente_copernicus as cliente_copernicus
import services.cliente_cr2met as cliente_cr2met
import services.cliente_firms as cliente_firms
import services.cliente_soilgrids as cliente_soilgrids
import services.cliente_solar as cliente_solar
import services.indicadores_locales as indicadores_locales
import services.zonas as zonas
from services.riego import lluvia_reciente
import services.ingesta_predio as ingesta_predio
import services.multianual as multianual
import services.plan_rotacion as plan_rotacion
from services.auth import (EXPIRACION_ANONIMO_MINUTOS, crear_token, decodificar_token, hash_password,
                          verificar_password)
from services import db as base_de_datos
from services.calculos_compartidos import CalculosCompartidos
from services.db import obtener_sesion
from services.limite_intentos import LimiteIntentos
from services.repositorio_clima import (CAPAS_MAPA, guardar_consulta_grilla, lado_celda_para, leer_clima_diario,
                                        leer_cercania_cauce, leer_disponibilidad_optica, leer_factores_et0,
                                        leer_historia, leer_humedad_suelo_nasa, leer_incendios, leer_mapa, leer_ndvi, leer_sitio)
from services.repositorio_postgres import RepositorioPostgres
from motor_estres import PROFUNDIDAD_SUELO_M

_CACHE_CR2MET = ingesta_predio.CACHE_CR2MET
_CACHE_APPEEARS = os.environ.get("APPEEARS_CACHE_DIR", "/tmp/appeears_cache")
_CACHE_CLSOILMAPS = ingesta_predio.CACHE_CLSOILMAPS
_CLSOILMAPS_ARCHIVO_INTERNO = ingesta_predio.CLSOILMAPS_ARCHIVO_INTERNO

# Limites del flujo de predio. El tope de hectareas acota el poligono que se genera a
# partir del punto; el de parcelas por usuario acota cuantas ingestas externas puede
# disparar una sola cuenta.
HECTAREAS_MAX = 1000.0
HECTAREAS_MIN_DIBUJADO = 0.05     # 500 m2: menos que eso es un clic de mas, no un predio
VERTICES_MAX_PERIMETRO = 500
PARCELAS_MAX_POR_USUARIO = 20
CULTIVOS_MAX_POR_PARCELA = 50
# Riegos que el agricultor declara: hasta cuantos dias atras se acepta uno (el balance de agua
# del predio mira un mes atras de la siembra) y cuantos puede tener un cultivo.
RIEGO_DIAS_ATRAS_MAX = 30
RIEGOS_MAX_POR_CULTIVO = 400
# Ventana aceptada para una fecha de siembra: hacia atras hasta donde llega el clima
# guardado del predio (un ano), hacia adelante una siembra planeada a pocos meses.
SIEMBRA_DIAS_ATRAS_MAX = 365
SIEMBRA_DIAS_ADELANTE_MAX = 180
# Dias de clima previos a la siembra que se leen para que el balance de agua del suelo
# no parta de un balde lleno justo el dia de la siembra.
DIAS_PREVIOS_BALANCE = 30
# Hasta cuantos dias hacia atras entrega el clima diario de un predio.
DIAS_CLIMA_ATRAS_MAX = 120
# Caja aproximada de Chile continental: CR2MET, CLSoilMaps y el Explorador Solar no
# cubren nada fuera. Un punto dentro de la caja pero fuera de Chile (Argentina, mar)
# pasa esta validacion y queda con sus fuentes en 'sin_cobertura'.

# La documentacion interactiva lista todos los endpoints, incluidos los de admin: solo se
# publica si API_DOCS=1 (desarrollo). En produccion queda apagada.
_DOCS = os.environ.get("API_DOCS") == "1"


async def _precargar_catalogo() -> None:
    """Lee el catalogo de especies a la memoria al arrancar: la primera lista de "Que sembrar" despues de cada
    despliegue tardaba el doble porque lo cargaba entonces. Si la base no responde no pasa nada: se carga al
    primer pedido, como antes."""
    if base_de_datos.SessionLocal is None:
        return
    try:
        async with base_de_datos.SessionLocal() as sesion:
            repo = multianual.RepositorioCacheado(RepositorioPostgres(sesion), _ALMACEN_CATALOGO)
            await repo.catalogo_vectorial()
            await repo.identidades()
            await repo.especies_con_fenologia()
    except Exception:
        pass


@asynccontextmanager
async def _ciclo_de_vida(_app: FastAPI):
    tarea = asyncio.create_task(_precargar_catalogo())
    yield
    tarea.cancel()


app = FastAPI(title="mogen", docs_url="/docs" if _DOCS else None, redoc_url=None,
              openapi_url="/openapi.json" if _DOCS else None, lifespan=_ciclo_de_vida)

# El frontend (Vite, otro origen) llama a esta API desde el navegador con el token en la
# cabecera Authorization: sin CORS el navegador bloquea cada llamada. Los origenes
# permitidos vienen de CORS_ORIGENES (separados por coma); por defecto, solo el servidor
# de desarrollo local. No se usan cookies, asi que no se permiten credenciales.
_ORIGENES = [o.strip() for o in os.environ.get(
    "CORS_ORIGENES", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=_ORIGENES, allow_credentials=False,
                   allow_methods=["GET", "POST", "PUT"], allow_headers=["Authorization", "Content-Type"])

_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

# Registro y login se pueden llamar sin token: se acotan por IP y, el login, tambien por
# cuenta (para que repartir los intentos entre muchas IP no sirva contra una sola cuenta).
# Los topes por IP son holgados a proposito: en zonas rurales varios agricultores salen
# por la misma IP del operador movil.
_REGISTROS_POR_IP = LimiteIntentos(10, 60 * 60)
_LOGINS_POR_IP = LimiteIntentos(30, 5 * 60)
_LOGINS_POR_CUENTA = LimiteIntentos(10, 15 * 60)
# Sesion anonima (la app la pide sola al abrirse, sin registro): una cuenta por dispositivo. El tope
# por IP es holgado porque en zonas rurales varios agricultores salen por la misma IP del operador
# movil; el global acota cuantas cuentas puede crear cualquiera que reparta sus pedidos entre muchas IP.
_ANONIMOS_POR_IP = LimiteIntentos(30, 60 * 60)
_ANONIMOS_GLOBAL = LimiteIntentos(300, 24 * 60 * 60)
# Cada predio nuevo dispara descargas a servicios externos. Con cuentas anonimas baratas de crear, el tope
# por usuario (PARCELAS_MAX_POR_USUARIO) ya no basta: se acota tambien por IP. Holgado por la misma razon
# que el de arriba (varios agricultores comparten la IP del operador movil).
_PARCELAS_POR_IP = LimiteIntentos(30, 60 * 60)
# Una cuenta anonima necesita un punto (usuarios.geometria es obligatoria): el de la comuna piloto,
# igual que el registro con telefono. El predio real se marca despues.
_PUNTO_ANONIMO = {"lon": -73.6508595, "lat": -42.1581806}
# Reportes de indicadores locales: por usuario, para que una cuenta no llene la base ni
# fabrique ella sola una senal "confirmada" (eso ademas exige agricultores distintos).
_OBSERVACIONES_POR_USUARIO = LimiteIntentos(60, 60 * 60)
_RIEGOS_POR_USUARIO = LimiteIntentos(60, 60 * 60)
_RENOVACIONES_POR_USUARIO = LimiteIntentos(10, 60 * 60)
_REPORTES_POR_USUARIO = LimiteIntentos(60, 60 * 60)
# El tiempo de una comuna se ve sin cuenta: se acota por IP aunque el resultado se guarda en memoria.
_ZONAS_POR_IP = LimiteIntentos(120, 60 * 60)
ESCENARIOS_CALENTAMIENTO = {"observado": None, "moderado": 0.3, "fuerte": 0.6}   # °C por decada hasta 2040
# El ranking de una parcela tarda segundos y varias pantallas lo piden con los mismos datos: se calcula una vez y se
# comparte unos minutos. La clave lleva todo lo que lo cambia (suelo declarado, clima, filtros), asi que un cambio
# del agricultor o una ingesta nueva lo recalcula solo.
_RANKINGS = CalculosCompartidos(vigencia_s=15 * 60, maximo=64)
_ALMACEN_CATALOGO: dict = {}   # catalogo de especies en memoria del proceso (ver multianual.RepositorioCacheado)
# Detras de un proxy la conexion llega desde el proxy, no desde el cliente. Si
# CABECERA_IP_CLIENTE nombra la cabecera donde el proxy pone la IP real (en Railway,
# x-real-ip), se usa esa. Solo hay que definirla cuando el unico camino hasta la API es
# ese proxy: de lo contrario cualquiera podria escribir la cabecera y saltarse el limite.
_CABECERA_IP = os.environ.get("CABECERA_IP_CLIENTE", "").strip().lower()


def _ip_cliente(request: Request) -> str:
    if _CABECERA_IP:
        valor = request.headers.get(_CABECERA_IP, "").strip()
        if valor:
            return valor[:64]
    return request.client.host if request.client else "desconocida"


def _frenar(limite: LimiteIntentos, clave: str) -> None:
    espera = limite.registrar(clave)
    if espera is not None:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                             "Demasiados intentos. Espera unos minutos e intenta otra vez.",
                             headers={"Retry-After": str(math.ceil(espera))})


# ---------------------------------------------------------------- esquemas
# Largos acotados en el borde: nada de lo que llega a estos endpoints sin autenticar
# entra a la base ni al hash de la contrasena con tamano libre.
class RegistroAgricultor(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    telefono: str = Field(min_length=6, max_length=32)
    password: str = Field(min_length=6, max_length=128)
    pais: str = Field("Chile", min_length=1, max_length=60)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class LoginAgricultor(BaseModel):
    telefono: str = Field(max_length=32)
    password: str = Field(max_length=128)


class LoginAdmin(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ParcelaNueva(BaseModel):
    """Dos formas de registrar un predio: `perimetro` (el poligono que el agricultor dibujo
    sobre el mapa, GeoJSON en WGS84) o un punto con sus hectareas (se genera un cuadrado
    aproximado). Una u otra, no las dos."""
    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-180, le=180)
    hectareas: float | None = Field(None, gt=0, le=HECTAREAS_MAX)
    perimetro: dict | None = None

    @model_validator(mode="after")
    def _una_forma(self):
        punto = (self.lat, self.lon, self.hectareas)
        if self.perimetro is not None:
            if any(v is not None for v in punto):
                raise ValueError("Envia `perimetro` o `lat`/`lon`/`hectareas`, no ambos")
        elif any(v is None for v in punto):
            raise ValueError("Faltan `lat`, `lon` y `hectareas`, o bien `perimetro`")
        return self


class SueloDeclarado(BaseModel):
    """Lo que el agricultor responde sobre su suelo. Cada campo es opcional; null borra la respuesta."""
    drenaje: Literal["poorly", "well", "excessive"] | None = None
    salinidad: Literal["low", "medium", "high"] | None = None
    profundidad: Literal["very_shallow", "shallow", "medium", "deep"] | None = None
    fertilidad: Literal["low", "moderate", "high"] | None = None


class CultivoNuevo(BaseModel):
    especie: str = Field(min_length=1, max_length=120)
    variedad_local: str | None = Field(None, min_length=1, max_length=120)
    fecha_siembra: date


class RiegoDeclarado(BaseModel):
    fecha: date


# Las labores que el agricultor anota en un cultivo (manejo_predio.tipo_labor). Fungicida y pesticida atenuan el
# dano que calcula el motor donde hay una regla de mitigacion (hoy, el tizon de la papa); fertilizacion y riego
# se anotan y el riego ademas alimenta el balance de agua.
LABORES_ANOTABLES = ("riego", "fertilizacion", "pesticida", "fungicida")
LABORES_MAX_POR_CULTIVO = 600


# El reporte de campo: lo que el agricultor ve en su cultivo (en que etapa esta). Se guarda en fenologia_observada.
FASES_REPORTE = ("brote", "hojas", "flor", "fruto", "amarilla", "cosecha")
REPORTES_MAX_POR_CULTIVO = 500


class ReporteDeCampo(BaseModel):
    fase: Literal["brote", "hojas", "flor", "fruto", "amarilla", "cosecha"]
    fecha: date
    capturado: datetime | None = None   # la hora del telefono al reportar: puede ser anterior a cuando llega


class LaborDeclarada(BaseModel):
    tipo: Literal["riego", "fertilizacion", "pesticida", "fungicida"]
    fecha: date


class ZonaNueva(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    perimetro: dict

    @field_validator("nombre")
    @classmethod
    def _nombre_limpio(cls, valor: str) -> str:
        return indicadores_locales.limpiar_texto(valor)


class IndicadorNuevo(BaseModel):
    """Lo que la comunidad define: que se observa y que anuncia. El texto libre se limpia
    en el borde porque otros usuarios lo ven."""
    id_zona: int
    categoria: indicadores_locales.Categoria
    nombre: str = Field(min_length=1, max_length=120)
    evento: str = Field(min_length=1, max_length=200)
    significado: indicadores_locales.Significado
    nota: str | None = Field(None, min_length=1, max_length=300)
    mes_desde: int = Field(ge=1, le=12)
    mes_hasta: int = Field(ge=1, le=12)
    umbral_reportes: int = Field(3, ge=1, le=50)
    vigencia_dias: int = Field(90, ge=7, le=365)

    @field_validator("nombre", "evento", "nota")
    @classmethod
    def _texto_limpio(cls, valor: str | None) -> str | None:
        return None if valor is None else indicadores_locales.limpiar_texto(valor)


class EstadoIndicador(BaseModel):
    activo: bool


class ObservacionNueva(BaseModel):
    fecha_observada: date


# ---------------------------------------------------------------- dependencias de autorizacion
async def usuario_actual(token: str | None = Depends(_oauth2), session: AsyncSession = Depends(obtener_sesion)) -> dict:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta token")
    try:
        payload = decodificar_token(token)
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido o expirado")
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
@app.get("/api/salud")
async def salud(session: AsyncSession = Depends(obtener_sesion)):
    """Para el chequeo de salud de la plataforma: responde 200 solo si la base contesta."""
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Base de datos no disponible")
    return {"estado": "ok"}


@app.get("/api/zonas")
async def listar_zonas():
    """Las comunas que se pueden mirar sin tener predio, con el punto donde abre el mapa (el pueblo cabecera)."""
    return [{"nombre": n, "lat": lat, "lon": lon} for n, (lat, lon) in zonas.COMUNAS.items()]


@app.get("/api/zonas/{nombre}/clima")
async def clima_zona(nombre: str, request: Request):
    """El tiempo de ahora en una comuna y la primera helada pronosticada (minima de 0 °C o menos en 7 dias), sin
    cuenta. Es pronostico de modelo (Open-Meteo), no medicion. Solo acepta comunas de la lista: no se consultan
    puntos que mande el cliente."""
    if nombre not in zonas.COMUNAS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comuna no existe")
    _frenar(_ZONAS_POR_IP, _ip_cliente(request))
    try:
        return await asyncio.to_thread(zonas.clima_de_zona, nombre)
    except Exception:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "El pronóstico no está disponible por ahora")


@app.post("/api/auth/registro", response_model=TokenOut)
async def registro_agricultor(datos: RegistroAgricultor, request: Request,
                               session: AsyncSession = Depends(obtener_sesion)):
    _frenar(_REGISTROS_POR_IP, _ip_cliente(request))
    existe = (await session.execute(
        text("SELECT id FROM usuarios WHERE telefono = :t"), {"t": datos.telefono}
    )).first()
    if existe:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ese teléfono ya está registrado")
    fila = (await session.execute(
        text("""INSERT INTO usuarios (nombre, pais, telefono, password_hash, rol, geometria)
                 VALUES (:nombre, :pais, :telefono, :ph, 'agricultor', ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
                 RETURNING id"""),
        {"nombre": datos.nombre, "pais": datos.pais, "telefono": datos.telefono,
         "ph": hash_password(datos.password), "lon": datos.lon, "lat": datos.lat},
    )).first()
    await session.commit()
    return TokenOut(access_token=crear_token(fila.id, "agricultor"))


@app.post("/api/auth/anonimo", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def sesion_anonima(request: Request, session: AsyncSession = Depends(obtener_sesion)):
    """Cuenta sin telefono ni contrasena para usar la app sin registro. El token que devuelve ES la
    cuenta: quien lo tiene ve y modifica los predios de esa cuenta, y nadie mas; no se puede volver a
    entrar a ella de otra forma (no tiene datos con que iniciar sesion). Rol siempre 'agricultor'."""
    _frenar(_ANONIMOS_POR_IP, _ip_cliente(request))
    _frenar(_ANONIMOS_GLOBAL, "global")
    fila = (await session.execute(
        text("""INSERT INTO usuarios (nombre, pais, rol, geometria)
                 VALUES ('Anónimo', 'Chile', 'agricultor', ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
                 RETURNING id"""), _PUNTO_ANONIMO)).first()
    await session.commit()
    return TokenOut(access_token=crear_token(fila.id, "agricultor", EXPIRACION_ANONIMO_MINUTOS))


@app.post("/api/auth/login", response_model=TokenOut)
async def login_agricultor(datos: LoginAgricultor, request: Request,
                           session: AsyncSession = Depends(obtener_sesion)):
    _frenar(_LOGINS_POR_IP, _ip_cliente(request))
    _frenar(_LOGINS_POR_CUENTA, "agricultor:" + datos.telefono.strip())
    fila = (await session.execute(
        text("SELECT id, password_hash, rol FROM usuarios WHERE telefono = :t"), {"t": datos.telefono}
    )).mappings().first()
    if not fila or not fila["password_hash"] or not verificar_password(datos.password, fila["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Teléfono o contraseña incorrectos")
    return TokenOut(access_token=crear_token(fila["id"], fila["rol"]))


@app.post("/api/auth/login-admin", response_model=TokenOut)
async def login_admin(datos: LoginAdmin, request: Request, session: AsyncSession = Depends(obtener_sesion)):
    _frenar(_LOGINS_POR_IP, _ip_cliente(request))
    _frenar(_LOGINS_POR_CUENTA, "admin:" + datos.email.strip().lower())
    fila = (await session.execute(
        text("SELECT id, password_hash, rol FROM usuarios WHERE email = :e AND rol = 'admin'"), {"e": datos.email}
    )).mappings().first()
    if not fila or not fila["password_hash"] or not verificar_password(datos.password, fila["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email o contraseña incorrectos")
    return TokenOut(access_token=crear_token(fila["id"], fila["rol"]))


@app.post("/api/auth/renovar", response_model=TokenOut)
async def renovar_sesion(session: AsyncSession = Depends(obtener_sesion), usuario: dict = Depends(usuario_actual)):
    """Un token nuevo de un ano para una cuenta anonima, a cambio de uno que todavia vale. Como el token ES la
    cuenta, sin esto la cuenta moriria al cumplirse el ano aunque la persona la use todos los dias. Solo las
    cuentas anonimas (sin telefono ni email): las demas conservan su vigencia corta y no se prolongan."""
    _frenar(_RENOVACIONES_POR_USUARIO, str(usuario["id"]))
    fila = (await session.execute(text("SELECT telefono, email FROM usuarios WHERE id = :id"),
                                  {"id": usuario["id"]})).mappings().first()
    if usuario["rol"] != "agricultor" or fila is None or fila["telefono"] or fila["email"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo las cuentas anónimas se renuevan")
    return TokenOut(access_token=crear_token(usuario["id"], "agricultor", EXPIRACION_ANONIMO_MINUTOS))


@app.get("/api/auth/yo")
async def yo(usuario: dict = Depends(usuario_actual)):
    return usuario


# ---------------------------------------------------------------- flujo de predio (agricultor)
# Punto + hectareas -> poligono -> ingesta de las fuentes de sitio -> especies candidatas.

async def _parcela_autorizada(id_parcela: int, usuario: dict, session: AsyncSession) -> dict:
    """La parcela, solo si es del usuario (o el usuario es admin). Una parcela ajena
    responde 404 igual que una inexistente: no se confirma que el id existe."""
    fila = (await session.execute(text("""
        SELECT p.id, p.id_usuario, p.altitud_msnm,
               p.suelo_drenaje, p.suelo_salinidad, p.suelo_profundidad, p.suelo_fertilidad,
               ST_Y(ST_Centroid(p.geometria)) AS lat, ST_X(ST_Centroid(p.geometria)) AS lon,
               ST_Area(p.geometria::geography) / 10000 AS hectareas,
               ST_AsGeoJSON(p.geometria, 6) AS perimetro, p.origen_perimetro, p.lado_celda_m,
               e.eco_name AS ecorregion, e.bioma_wwf AS bioma
        FROM parcela p LEFT JOIN ecoregion_wwf e ON e.id = p.id_ecoregion
        WHERE p.id = :id
    """), {"id": id_parcela})).mappings().first()
    if not fila or (fila["id_usuario"] != usuario["id"] and usuario["rol"] != "admin"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Parcela no existe")
    parcela = dict(fila)
    del parcela["id_usuario"]
    parcela["suelo"] = {campo: parcela.pop(f"suelo_{campo}") for campo in catalogo_especies.CAMPOS_SUELO}
    parcela["hectareas"] = round(parcela["hectareas"], 2)
    parcela["perimetro"] = json.loads(parcela["perimetro"])
    # Fuente: Biomes and Ecoregions 2017 (RESOLVE), CC-BY 4.0 -- citar donde se muestre.
    nombre, bioma = parcela.pop("ecorregion"), parcela.pop("bioma")
    parcela["ecorregion"] = {"nombre": nombre, "bioma": bioma} if nombre else None
    return parcela


def _validar_perimetro(perimetro: dict) -> str:
    """Primera validacion del poligono dibujado, sin tocar la base: forma del GeoJSON,
    tope de vertices y coordenadas dentro de rango. Devuelve el GeoJSON normalizado (un
    solo anillo, cerrado, solo lon/lat) listo para ST_GeomFromGeoJSON. Levanta 422."""
    def rechazar(motivo: str):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Perímetro inválido: {motivo}")

    if perimetro.get("type") != "Polygon" or not isinstance(perimetro.get("coordinates"), list):
        rechazar("debe ser un GeoJSON de tipo Polygon")
    anillos = perimetro["coordinates"]
    if len(anillos) != 1 or not isinstance(anillos[0], list):
        rechazar("debe tener un solo contorno, sin huecos")
    if not 3 <= len(anillos[0]) <= VERTICES_MAX_PERIMETRO:
        rechazar(f"debe tener entre 3 y {VERTICES_MAX_PERIMETRO} vértices")
    anillo = []
    for punto in anillos[0]:
        if (not isinstance(punto, (list, tuple)) or len(punto) < 2
                or not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                           for v in punto[:2])):
            rechazar("cada vértice debe ser [longitud, latitud]")
        lon, lat = float(punto[0]), float(punto[1])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            rechazar("las coordenadas quedan fuera de rango")
        anillo.append([lon, lat])
    if anillo[0] != anillo[-1]:
        anillo.append(anillo[0])     # un dibujo sin cerrar se cierra aca
    if len(anillo) < 4:
        rechazar("necesita al menos tres vértices distintos")
    return json.dumps({"type": "Polygon", "coordinates": [anillo]})


@app.post("/api/parcelas", status_code=status.HTTP_201_CREATED)
async def crear_parcela(datos: ParcelaNueva, tareas: BackgroundTasks, request: Request,
                         session: AsyncSession = Depends(obtener_sesion),
                         usuario: dict = Depends(usuario_actual)):
    """Flujo 1, paso 7. Con `perimetro`, el predio es el poligono que el agricultor dibujo.
    Sin el, da un punto y las hectareas y el perimetro es un cuadrado de esa area centrado
    en el punto (aproximacion declarada, no un deslinde), armado en metros en la zona UTM
    del punto. En los dos casos deja encolada la ingesta y responde sin esperarla."""
    _frenar(_PARCELAS_POR_IP, _ip_cliente(request))
    dibujado = _validar_perimetro(datos.perimetro) if datos.perimetro is not None else None
    if dibujado is None and not (abs(datos.lat) <= 80 and abs(datos.lon) <= 179):
        # El cuadrado del punto se arma en UTM (80 S a 84 N) y no puede cruzar el antimeridiano.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "El punto queda fuera de la zona donde se pueden crear terrenos")
    if usuario["rol"] != "admin":
        cantidad = (await session.execute(
            text("SELECT count(*) FROM parcela WHERE id_usuario = :u"), {"u": usuario["id"]})).scalar_one()
        if cantidad >= PARCELAS_MAX_POR_USUARIO:
            raise HTTPException(status.HTTP_409_CONFLICT,
                                 f"Ya tienes {PARCELAS_MAX_POR_USUARIO} parcelas, el máximo permitido")

    if dibujado is not None:
        # Segunda validacion, geometrica, en PostGIS: que el poligono no se cruce a si
        # mismo y que su superficie tenga sentido. Recien entonces se inserta.
        forma = (await session.execute(text("""
            SELECT ST_IsValid(g) AND ST_IsSimple(g) AS valido, ST_Area(g::geography) / 10000 AS hectareas
            FROM (SELECT ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326) AS g) x
        """), {"gj": dibujado})).mappings().first()
        if not forma["valido"]:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                                 "El perímetro se cruza a sí mismo; dibújalo de nuevo sin cruzar líneas")
        if not HECTAREAS_MIN_DIBUJADO <= forma["hectareas"] <= HECTAREAS_MAX:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                                 f"El perímetro mide {forma['hectareas']:.2f} hectáreas; debe medir entre "
                                 f"{HECTAREAS_MIN_DIBUJADO} y {HECTAREAS_MAX:.0f}")
        id_parcela = (await session.execute(text("""
            INSERT INTO parcela (id_usuario, geometria, origen_perimetro)
            VALUES (:usuario, ST_ForcePolygonCCW(ST_Force2D(ST_SetSRID(ST_GeomFromGeoJSON(:gj), 4326))), 'dibujado')
            RETURNING id
        """), {"usuario": usuario["id"], "gj": dibujado})).scalar_one()
    else:
        srid_utm = (32700 if datos.lat < 0 else 32600) + int((datos.lon + 180) // 6) + 1
        medio_lado_m = (datos.hectareas * 10_000) ** 0.5 / 2
        id_parcela = (await session.execute(text("""
            INSERT INTO parcela (id_usuario, geometria)
            VALUES (:usuario, ST_Transform(ST_Expand(ST_Transform(
                        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), CAST(:srid AS integer)),
                        CAST(:medio_lado AS double precision)), 4326))
            RETURNING id
        """), {"usuario": usuario["id"], "lon": datos.lon, "lat": datos.lat,
               "srid": srid_utm, "medio_lado": medio_lado_m})).scalar_one()
    # Grilla del predio: zona UTM de su centro y lado de celda segun su superficie.
    centro = (await session.execute(text("""
        SELECT ST_Y(ST_Centroid(geometria)) AS lat, ST_X(ST_Centroid(geometria)) AS lon,
               ST_Area(geometria::geography) AS m2 FROM parcela WHERE id = :id
    """), {"id": id_parcela})).mappings().first()
    await session.execute(
        text("UPDATE parcela SET srid_utm = :srid, lado_celda_m = :lado WHERE id = :id"),
        {"id": id_parcela, "lado": lado_celda_para(centro["m2"]),
         "srid": (32700 if centro["lat"] < 0 else 32600) + int((centro["lon"] + 180) // 6) + 1})
    # Ecorregion: la que contiene el centroide o, si cae en un borde simplificado (costa),
    # la mas cercana a menos de 5 km. Sin ninguna, queda en NULL.
    await session.execute(text("""
        UPDATE parcela p SET id_ecoregion = (
            SELECT e.id FROM ecoregion_wwf e
            WHERE ST_DWithin(e.geometria::geography, ST_Centroid(p.geometria)::geography, 5000)
            ORDER BY ST_Distance(e.geometria::geography, ST_Centroid(p.geometria)::geography) LIMIT 1)
        WHERE p.id = :id
    """), {"id": id_parcela})
    await session.commit()

    jobs = await ingesta_predio.encolar(session, id_parcela)
    tareas.add_task(ingesta_predio.ingerir_predio, id_parcela, jobs)
    parcela = await _parcela_autorizada(id_parcela, usuario, session)
    return {**parcela, "estado_ingesta": await ingesta_predio.estado_ingesta(session, id_parcela)}


@app.get("/api/parcelas")
async def listar_parcelas(session: AsyncSession = Depends(obtener_sesion),
                           usuario: dict = Depends(usuario_actual)):
    filas = (await session.execute(text("""
        SELECT id, altitud_msnm, ST_Y(ST_Centroid(geometria)) AS lat, ST_X(ST_Centroid(geometria)) AS lon,
               round((ST_Area(geometria::geography) / 10000)::numeric, 2)::float AS hectareas,
               ST_AsGeoJSON(geometria, 6) AS perimetro
        FROM parcela WHERE id_usuario = :u ORDER BY id
    """), {"u": usuario["id"]})).mappings().all()
    return {"parcelas": [{**f, "perimetro": json.loads(f["perimetro"])} for f in filas]}


@app.get("/api/parcelas/{id_parcela}")
async def ver_parcela(id_parcela: int, tareas: BackgroundTasks, session: AsyncSession = Depends(obtener_sesion),
                       usuario: dict = Depends(usuario_actual)):
    parcela = await _parcela_autorizada(id_parcela, usuario, session)
    # Los focos de calor se leen aca (Tu terreno, Hoy): si la revision esta vencida, o nunca corrio para esta
    # parcela, se deja refrescandose. Antes solo se refrescaba al pedir el seguimiento de un cultivo, asi que
    # una parcela sin cultivos se quedaba con los focos del dia en que se marco, o sin revisar para siempre.
    jobs = await ingesta_predio.encolar(session, id_parcela, ("firms", "inundacion"))
    if jobs:
        tareas.add_task(ingesta_predio.ingerir_predio, id_parcela, jobs)
    return {**parcela, "incendios_cercanos": await leer_incendios(session, id_parcela),
            "cercania_cauce": await leer_cercania_cauce(session, id_parcela),
            "curva_satelital": await leer_disponibilidad_optica(session, id_parcela),
            "estado_ingesta": await ingesta_predio.estado_ingesta(session, id_parcela)}


@app.put("/api/parcelas/{id_parcela}/suelo")
async def guardar_suelo(id_parcela: int, datos: SueloDeclarado, session: AsyncSession = Depends(obtener_sesion),
                         usuario: dict = Depends(usuario_actual)):
    """Guarda lo que el agricultor responde sobre su suelo: drenaje, sal, profundidad y
    fertilidad. Cambia solo los campos que vienen en el cuerpo; null borra la respuesta. Estos
    datos no se pueden medir desde el satelite: entran a la lista de especies tal como el
    agricultor los declara."""
    await _parcela_autorizada(id_parcela, usuario, session)
    cambios = {campo: getattr(datos, campo) for campo in datos.model_fields_set if campo in catalogo_especies.CAMPOS_SUELO}
    if cambios:
        # Los nombres de columna salen de CAMPOS_SUELO, nunca del cuerpo de la peticion.
        asignaciones = ", ".join(f"suelo_{campo} = :{campo}" for campo in cambios)
        await session.execute(text(f"UPDATE parcela SET {asignaciones} WHERE id = :id"), {**cambios, "id": id_parcela})
        await session.commit()
    return {"suelo": (await _parcela_autorizada(id_parcela, usuario, session))["suelo"]}


@app.get("/api/parcelas/{id_parcela}/mapa")
async def mapa_parcela(id_parcela: int, tareas: BackgroundTasks,
                        capa: str = Query("ndvi", pattern="^(" + "|".join(CAPAS_MAPA) + ")$"),
                        session: AsyncSession = Depends(obtener_sesion),
                        usuario: dict = Depends(usuario_actual)):
    """El predio como mapa: un GeoJSON con una entidad por celda de su grilla, recortada
    a la forma del perimetro, y en cada una el valor de la capa pedida -- ver
    repositorio_clima.leer_mapa() y CAPAS_MAPA. Capas: 'ndvi' (vigor de la vegetacion,
    Sentinel-2, el ultimo dato util), 'altitud' y 'pendiente' (relieve, dato fijo) y 'hand'
    (altura sobre el cauce mas cercano, dato fijo). Si
    los datos de la capa faltan o estan vencidos los deja cargandose y responde con lo
    que hay."""
    parcela = await _parcela_autorizada(id_parcela, usuario, session)
    fuente = CAPAS_MAPA[capa]["fuente_ingesta"]
    jobs = await ingesta_predio.encolar(session, id_parcela, (fuente,))
    if jobs:
        tareas.add_task(ingesta_predio.ingerir_predio, id_parcela, jobs)
    mapa = await leer_mapa(session, id_parcela, capa)
    estado = await ingesta_predio.estado_ingesta(session, id_parcela)
    return {**mapa, "id_parcela": id_parcela, "origen_perimetro": parcela["origen_perimetro"],
            "lado_celda_m": parcela["lado_celda_m"], "hectareas": parcela["hectareas"],
            "estado_ingesta": estado[fuente]}


@app.post("/api/parcelas/{id_parcela}/ingesta", status_code=status.HTTP_202_ACCEPTED)
async def reintentar_ingesta(id_parcela: int, tareas: BackgroundTasks,
                              session: AsyncSession = Depends(obtener_sesion),
                              usuario: dict = Depends(usuario_actual)):
    """Vuelve a encolar solo las fuentes que fallaron, se interrumpieron o nunca
    corrieron -- las completas y las que estan en curso no se repiten."""
    await _parcela_autorizada(id_parcela, usuario, session)
    jobs = await ingesta_predio.encolar(session, id_parcela)
    if jobs:
        tareas.add_task(ingesta_predio.ingerir_predio, id_parcela, jobs)
    return {"fuentes_encoladas": list(jobs),
            "estado_ingesta": await ingesta_predio.estado_ingesta(session, id_parcela)}


def _armar_datos_sitio(parcela: dict, sitio: dict):
    """Lo que el ranking y el motor de rotacion esperan de un predio: el clima de CR2MET (una celda de 5 km) llevado a
    la altura de la parcela, sus normales y el suelo declarado. Devuelve (datos_sitio, clima, correccion, altitud,
    textura)."""
    altitud = sitio["altitud_dem_m"] if sitio["altitud_dem_m"] is not None else parcela["altitud_msnm"]
    correccion = catalogo_especies.delta_temperatura_por_altitud(altitud, sitio["altitud_celda_m"])
    clima = catalogo_especies.corregir_temperatura(sitio["clima"], correccion)
    normales = catalogo_especies.normales_mensuales(clima)
    textura = catalogo_especies.clase_textura(sitio["arcilla_pct"], sitio["arena_pct"])
    datos_sitio = {"normales": normales, "ph": sitio["ph"], "ghi_mensual": sitio["ghi_mensual"], "awc_mm": sitio["awc_mm"],
                   "altitud_m": altitud, "textura": textura, "suelo": parcela["suelo"],
                   "textura_posibles": catalogo_especies.clases_textura_posibles(sitio["arcilla_pct"], sitio["arena_pct"])}
    datos_sitio["et0_factor_mensual"] = sitio.get("et0_factor_mensual")
    return datos_sitio, clima, correccion, altitud, textura


def _resumen_sitio(parcela: dict, sitio: dict, normales: dict, altitud, correccion: float, textura) -> dict:
    """Lo medido del sitio tal como lo ve el agricultor (Tu terreno): normales de clima, radiacion, suelo y altitud."""
    inicio, fin = sitio["periodo_clima"]
    redondear = lambda serie: None if serie is None else [round(v, 2) for v in serie]
    return {
        "periodo_clima": [inicio.isoformat(), fin.isoformat()],
        "temperatura_media_mensual": redondear(normales["tmedia"]),
        "temperatura_minima_mas_baja_mensual": redondear(normales["tmin_extrema"]),
        "lluvia_mensual_mm": redondear(normales["lluvia"]),
        "lluvia_anual_mm": None if normales["lluvia"] is None else round(sum(normales["lluvia"]), 1),
        "ghi_mensual_kwh_m2_dia": redondear(sitio["ghi_mensual"]),
        "fuente_radiacion": sitio["fuente_radiacion"], "fuente_clima": sitio.get("fuente_clima"),
        "ph": sitio["ph"], "agua_disponible_suelo_mm": sitio["awc_mm"], "fuente_agua_suelo": sitio.get("fuente_agua_suelo"),
        "altitud_m": None if altitud is None else round(altitud),
        "altitud_celda_m": None if sitio["altitud_celda_m"] is None else round(sitio["altitud_celda_m"]),
        "correccion_temperatura_c": round(correccion, 2),
        "textura": textura, "suelo": parcela["suelo"],
    }


@app.get("/api/parcelas/{id_parcela}/sitio")
async def sitio_parcela(id_parcela: int, tareas: BackgroundTasks, session: AsyncSession = Depends(obtener_sesion),
                         usuario: dict = Depends(usuario_actual)):
    """Lo medido del sitio de la parcela (clima normal, radiacion, pH, agua del suelo, altitud), sin calcular el
    ranking de especies: es lo que Tu terreno necesita y cambia muy de vez en cuando, asi que el cliente lo guarda.
    Mismo contenido que `datos_sitio` de candidatas_siembra. Responde 409 mientras no haya clima del predio."""
    parcela = await _parcela_autorizada(id_parcela, usuario, session)
    jobs = await ingesta_predio.encolar(session, id_parcela, ingesta_predio.FUENTES_DE_SITIO)
    if jobs:
        tareas.add_task(ingesta_predio.ingerir_predio, id_parcela, jobs)
    sitio = await leer_sitio(session, id_parcela)
    datos_sitio, _clima, correccion, altitud, textura = _armar_datos_sitio(parcela, sitio)
    normales = datos_sitio["normales"]
    if normales["tmedia"] is None:
        raise HTTPException(status.HTTP_409_CONFLICT, {
            "mensaje": "Todavía no hay un año de clima para este predio",
            "estado_ingesta": await ingesta_predio.estado_ingesta(session, id_parcela)})
    return {"parcela": id_parcela, "datos_sitio": _resumen_sitio(parcela, sitio, normales, altitud, correccion, textura),
            "datos_faltantes": catalogo_especies.datos_faltantes(datos_sitio)}


@app.get("/api/parcelas/{id_parcela}/candidatas_siembra")
async def candidatas_siembra(id_parcela: int, tareas: BackgroundTasks,
                              limite: int = Query(20, ge=1, le=200),
                              categorias: str | None = Query(None, max_length=300),
                              incluir_no_aptas: bool = False,
                              especie: str | None = Query(None, max_length=300),
                              riego: bool = False,
                              clima_futuro: Literal["tradicional", "emergente", "en_riesgo"] | None = None,
                              escenario: Literal["observado", "moderado", "fuerte"] = "observado",
                              session: AsyncSession = Depends(obtener_sesion),
                              usuario: dict = Depends(usuario_actual)):
    """Flujo 1b: especies candidatas para el predio, de mas a menos idoneas, segun
    tolerancia climatica (temperatura y helada letal), humedad (lluvia), pH y radiacion
    -- ver catalogo_especies.ranking_idoneidad(). `categorias`: lista separada por coma
    de categorias de EcoCrop (ej. 'vegetables,roots/tubers'); sin ella se dejan fuera
    forestales, ornamentales y malezas. `limite` se aplica despues de filtrar por
    categorias, y `especies_aptas` / `especies_evaluadas` cuentan solo esas categorias.
    `especie`: lista separada por coma de claves; devuelve solo esas, aptas o no, sin
    aplicar `limite` ni `incluir_no_aptas`. `riego`: el calculo parte de que el agricultor
    repone la falta de lluvia (por defecto, solo lluvia). `datos_faltantes` lista lo que no
    se pudo medir del sitio. Responde 409 mientras no haya clima del predio.

    Con la serie historica de la parcela (35 anos, ver multianual.py) cada especie se evalua en cada ano:
    `apta` es que su ano dificil reciente (el peor decil de los ultimos 15) llegue al minimo, `puntaje` es la
    compatibilidad tipica (la mediana) y `puntaje_ano_dificil` la del peor decil. `clima` trae los tres periodos
    (historico, reciente, proyectado a 2040 con la tendencia de la propia serie) y la categoria: tradicional,
    emergente o en_riesgo; `clima_futuro` filtra por ella e incluye las que aun no son aptas. `escenario`: como
    sube la temperatura hasta 2040: la tendencia observada en la parcela (por defecto) o un supuesto de +0,3 o +0,6 °C
    por decada. Sin historia todavia se usa el ano de clima de antes."""
    parcela = await _parcela_autorizada(id_parcela, usuario, session)
    # Solo las fuentes de sitio: CR2MET vence cada mes y, si la tarea programada no
    # corrio, esta consulta lo deja refrescandose.
    jobs = await ingesta_predio.encolar(session, id_parcela, ingesta_predio.FUENTES_DE_SITIO)
    if jobs:
        tareas.add_task(ingesta_predio.ingerir_predio, id_parcela, jobs)
    estado = await ingesta_predio.estado_ingesta(session, id_parcela)
    sitio = await leer_sitio(session, id_parcela)
    datos_sitio, clima, correccion, altitud, textura = _armar_datos_sitio(parcela, sitio)
    normales = datos_sitio["normales"]
    if normales["tmedia"] is None:
        raise HTTPException(status.HTTP_409_CONFLICT, {
            "mensaje": "Todavía no hay un año de clima para este predio", "estado_ingesta": estado})

    filtro = {c.strip() for c in categorias.split(",") if c.strip()} if categorias else None
    pedidas = {e.strip() for e in especie.split(",") if e.strip()} if especie else None
    historia = await leer_historia(session, id_parcela)
    clave = (id_parcela, riego, escenario, frozenset(filtro) if filtro else None,
             frozenset(pedidas) if pedidas else None, tuple(sorted((parcela["suelo"] or {}).items())),
             sitio["periodo_clima"], len(historia or {}), sitio["ph"], sitio["awc_mm"], altitud)

    async def calcular():
        # Con su propia sesion: el calculo lo comparten otras solicitudes y no debe caer con la de quien lo lanzo.
        async with base_de_datos.SessionLocal() as sesion_propia:
            return await multianual.ranking_multianual(
                datos_sitio, multianual.RepositorioCacheado(RepositorioPostgres(sesion_propia), _ALMACEN_CATALOGO),
                historia, clima, parcela["lat"], categorias=filtro, riego=riego,
                delta_temp=correccion, calentamiento_c_por_decada=ESCENARIOS_CALENTAMIENTO[escenario],
                incluir_silvestres=bool(especie),   # pedir una especie puntual la devuelve aunque sea maleza
                unir_variedades=not especie,        # y se puede pedir una variedad puntual, no solo la que gana
                solo=pedidas)                       # sin simular las demas especies del catalogo

    ranking, serie = await _RANKINGS.obtener(clave, calcular)
    evaluadas = len(ranking)
    aptas = sum(1 for r in ranking if r["apta"])
    por_categoria = {c: sum(1 for r in ranking if (r.get("clima") or {}).get("categoria") == c)
                     for c in ("tradicional", "emergente", "en_riesgo")}
    if clima_futuro:
        # una especie 'emergente' puede no ser apta todavia: la categoria ya dice que importa, aptas o no
        ranking = [r for r in ranking if (r.get("clima") or {}).get("categoria") == clima_futuro]
        incluir_no_aptas = True
    lista = catalogo_especies.seleccionar_candidatas(ranking, limite, incluir_no_aptas, especie)

    return {
        "parcela": id_parcela, "hectareas": parcela["hectareas"], "estado_ingesta": estado,
        "datos_sitio": _resumen_sitio(parcela, sitio, normales, altitud, correccion, textura),
        "especies_evaluadas": evaluadas, "especies_aptas": aptas,
        "criterio": "multianual" if serie else "un_ano", "serie_climatica": serie, "escenario": escenario,
        "especies_por_categoria_clima": por_categoria if serie else None,
        "riego": riego, "datos_faltantes": catalogo_especies.datos_faltantes(datos_sitio),
        "suelo_sin_declarar": catalogo_especies.suelo_sin_declarar(datos_sitio),
        "candidatas": lista,
    }


_ROTACION_POR_USUARIO = LimiteIntentos(20, 60 * 60)   # cada consulta son unos segundos de calculo


@app.get("/api/parcelas/{id_parcela}/rotacion/comparar")
async def comparar_rotaciones(id_parcela: int,
                              riego: bool = False,
                              escenario: Literal["observado", "moderado", "fuerte"] = "observado",
                              largo_max: int = Query(5, ge=3, le=5),
                              limite: int = Query(5, ge=1, le=8),
                              session: AsyncSession = Depends(obtener_sesion),
                              usuario: dict = Depends(usuario_actual)):
    """Compara estrategias de rotacion para la parcela desde la proxima temporada: repetir el cultivo actual contra las
    mejores rotaciones de 3 a `largo_max` temporadas, con el mismo modelo de agua y de riesgo del ranking de especies
    (ver services/plan_rotacion.py). Las solanaceas nunca van una tras otra, tambien contra lo ya sembrado. `escenario`
    y `riego` como en candidatas_siembra. Salen al menos 3 estrategias si hay especies viables, aunque `limite` sea
    menor. El puntaje ordena opciones; no predice rendimiento. 409 si no hay clima o historia suficiente."""
    _frenar(_ROTACION_POR_USUARIO, f"usuario:{usuario['id']}")
    parcela = await _parcela_autorizada(id_parcela, usuario, session)
    sitio = await leer_sitio(session, id_parcela)
    datos_sitio, _, correccion, _, _ = _armar_datos_sitio(parcela, sitio)
    if datos_sitio["normales"]["tmedia"] is None:
        raise HTTPException(status.HTTP_409_CONFLICT, {
            "mensaje": "Todavía no hay un año de clima para este predio",
            "estado_ingesta": await ingesta_predio.estado_ingesta(session, id_parcela)})
    filas = (await session.execute(text("""
        SELECT especie FROM predio_cultivos WHERE id_parcela = :p
        ORDER BY fecha_siembra DESC NULLS LAST, id DESC LIMIT :n
    """), {"p": id_parcela, "n": plan_rotacion.MAX_PREVIOS})).mappings().all()
    previos = [f["especie"] for f in reversed(filas)]          # del mas antiguo al mas reciente
    repo = multianual.RepositorioCacheado(RepositorioPostgres(session), _ALMACEN_CATALOGO)
    plan = await plan_rotacion.plan_rotacion(
        datos_sitio, repo, await leer_historia(session, id_parcela), parcela["lat"], previos, riego=riego,
        delta_temp=correccion, calentamiento_c_por_decada=ESCENARIOS_CALENTAMIENTO[escenario],
        largo_max=largo_max, limite=limite)
    if plan["estado"] != "ok":
        raise HTTPException(status.HTTP_409_CONFLICT, {"mensaje": "Todavía no hay historia de clima suficiente "
                            "para evaluar rotaciones", "estado": plan["estado"], "vacios": plan["vacios"]})
    return {"parcela": id_parcela, "escenario": escenario, "riego": riego, "cultivos_previos": previos, **plan}


# ---------------------------------------------------------------- cultivo sembrado: fases y condiciones
_NIVELES_CON_FENOLOGIA = ("perfil_fenologico_regional", "perfil_calibrado")


@app.post("/api/parcelas/{id_parcela}/cultivos", status_code=status.HTTP_201_CREATED)
async def declarar_cultivo(id_parcela: int, datos: CultivoNuevo, tareas: BackgroundTasks,
                            session: AsyncSession = Depends(obtener_sesion),
                            usuario: dict = Depends(usuario_actual)):
    """El agricultor declara que siembra (o planea sembrar) una especie del catalogo en
    su predio. Cualquier especie del catalogo se puede declarar; el seguimiento por fase
    solo existe para las que tienen perfil fenologico (`fenologia_disponible`)."""
    await _parcela_autorizada(id_parcela, usuario, session)
    hoy = date.today()
    if not (hoy - timedelta(days=SIEMBRA_DIAS_ATRAS_MAX) <= datos.fecha_siembra
            <= hoy + timedelta(days=SIEMBRA_DIAS_ADELANTE_MAX)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                             f"La fecha de siembra debe estar entre {SIEMBRA_DIAS_ATRAS_MAX} días atrás "
                             f"y {SIEMBRA_DIAS_ADELANTE_MAX} días adelante")
    repo = RepositorioPostgres(session)
    if await repo.requisitos(datos.especie, datos.variedad_local) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "La especie no está en el catálogo")
    cantidad = (await session.execute(
        text("SELECT count(*) FROM predio_cultivos WHERE id_parcela = :p"), {"p": id_parcela})).scalar_one()
    if cantidad >= CULTIVOS_MAX_POR_PARCELA:
        raise HTTPException(status.HTTP_409_CONFLICT,
                             f"La parcela ya tiene {CULTIVOS_MAX_POR_PARCELA} cultivos, el máximo permitido")

    id_cultivo = (await session.execute(text("""
        INSERT INTO predio_cultivos (id_parcela, especie, variedad_local, fecha_siembra)
        VALUES (:parcela, :especie, :variedad, :siembra) RETURNING id
    """), {"parcela": id_parcela, "especie": datos.especie, "variedad": datos.variedad_local,
           "siembra": datos.fecha_siembra})).scalar_one()
    await session.commit()

    nivel = await catalogo_especies.nivel_madurez(datos.especie, datos.variedad_local, repo)
    etapas = catalogo_especies.elegir_etapas(
        await repo.umbrales_fenologicos(datos.especie, datos.variedad_local), datos.variedad_local)
    jobs = await ingesta_predio.encolar(session, id_parcela)  # refresca el clima diario si esta vencido
    if jobs:
        tareas.add_task(ingesta_predio.ingerir_predio, id_parcela, jobs)
    return {"id": id_cultivo, "id_parcela": id_parcela, "especie": datos.especie,
            "variedad_local": datos.variedad_local, "fecha_siembra": datos.fecha_siembra.isoformat(),
            "nivel_madurez": nivel, "fenologia_disponible": nivel in _NIVELES_CON_FENOLOGIA,
            "calendario_aproximado": await catalogo_especies.calendario_aproximado(
                datos.especie, datos.variedad_local, repo),
            "etapas": [u["etapa"] for u in etapas]}


@app.get("/api/parcelas/{id_parcela}/cultivos")
async def listar_cultivos(id_parcela: int, session: AsyncSession = Depends(obtener_sesion),
                           usuario: dict = Depends(usuario_actual)):
    await _parcela_autorizada(id_parcela, usuario, session)
    filas = (await session.execute(text("""
        SELECT id, especie, variedad_local, fecha_siembra FROM predio_cultivos
        WHERE id_parcela = :p ORDER BY fecha_siembra DESC NULLS LAST, id DESC
    """), {"p": id_parcela})).mappings().all()
    return {"cultivos": [dict(f) for f in filas]}


@app.get("/api/cultivos/{id_cultivo}/fenologia")
async def fenologia_cultivo(id_cultivo: int, tareas: BackgroundTasks,
                             session: AsyncSession = Depends(obtener_sesion),
                             usuario: dict = Depends(usuario_actual)):
    """Flujo 4 (parte): fechas de cada etapa, fase actual y condiciones y eventos de dano
    por fase, con cada cosa marcada como observada, de pronostico o estimada -- ver
    catalogo_especies.seguimiento_cultivo() y repositorio_clima.leer_clima_diario().
    Si el clima diario del predio esta vencido lo deja refrescandose en segundo plano y
    responde con lo que hay; `estado_ingesta` dice si conviene volver a consultar."""
    cultivo = (await session.execute(text(
        "SELECT id, id_parcela, especie, variedad_local, fecha_siembra FROM predio_cultivos WHERE id = :id"
    ), {"id": id_cultivo})).mappings().first()
    try:
        if cultivo is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND)
        parcela = await _parcela_autorizada(cultivo["id_parcela"], usuario, session)
    except HTTPException:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cultivo no existe")
    if cultivo["fecha_siembra"] is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "El cultivo no tiene fecha de siembra")
    id_parcela = cultivo["id_parcela"]

    jobs = await ingesta_predio.encolar(session, id_parcela)
    if jobs:
        tareas.add_task(ingesta_predio.ingerir_predio, id_parcela, jobs)
    estado = await ingesta_predio.estado_ingesta(session, id_parcela)

    clima = await leer_clima_diario(session, id_parcela,
                                     cultivo["fecha_siembra"] - timedelta(days=DIAS_PREVIOS_BALANCE))
    awc = (await session.execute(text(
        "SELECT valor FROM cache_consulta_grilla WHERE id_parcela = :id AND capa = 'clsoilmaps_awc_total_mm'"
    ), {"id": id_parcela})).scalar_one_or_none()
    manejo = (await session.execute(text(
        "SELECT tipo_labor, fecha FROM manejo_predio WHERE id_cultivo = :id"), {"id": id_cultivo})).mappings().all()
    # Lo que el agricultor reporto haber visto (brote, flor): reancla el calendario a la fecha real.
    reportes = (await session.execute(text(
        "SELECT fase_fenologica AS fase, fecha_observada AS fecha FROM fenologia_observada "
        "WHERE id_cultivo = :id AND fase_fenologica = ANY(:fases)"),
        {"id": id_cultivo, "fases": list(catalogo_especies.ETAPA_DE_REPORTE)})).mappings().all()

    sin_clima = {"mensaje": "Todavía no hay clima diario del predio desde la fecha de siembra",
                 "estado_ingesta": estado}
    if clima is None:
        raise HTTPException(status.HTTP_409_CONFLICT, sin_clima)
    try:
        resultado = await catalogo_especies.seguimiento_cultivo(
            cultivo["especie"], cultivo["variedad_local"], RepositorioPostgres(session), clima,
            cultivo["fecha_siembra"], parcela["lat"], awc, date.today(), manejo=tuple(dict(m) for m in manejo),
            reportes=tuple(dict(r) for r in reportes),
            et0_factores=await leer_factores_et0(session, id_parcela),
            prof_suelo_m=PROFUNDIDAD_SUELO_M.get(parcela["suelo"]["profundidad"]))
    except (catalogo_especies.EspecieSinPerfil, catalogo_especies.EspecieSinPerfilFenologico):
        raise HTTPException(status.HTTP_409_CONFLICT,
                             "Esta especie todavía no tiene seguimiento por etapa: solo se evalúa si el sitio le sirve")
    except ValueError:
        raise HTTPException(status.HTTP_409_CONFLICT, sin_clima)
    # Humedad del suelo de NASA (POWER), como contexto junto a la recomendacion de riego: es de una celda de ~50 km y
    # no entra al balance de agua del predio, asi que viaja aparte de los calculos.
    humedad_nasa = await leer_humedad_suelo_nasa(session, id_parcela)
    if humedad_nasa and "agua_pct" in resultado["riego"]:
        resultado["riego"]["humedad_suelo_nasa"] = humedad_nasa
    # Lo que llovio estos dias en el predio: es parte del mismo balance, dicho en dias y milimetros.
    if "agua_pct" in resultado["riego"]:
        resultado["riego"]["lluvia_reciente"] = lluvia_reciente(clima["lluvia"], date.today())
    # Eventos que no salen del clima: focos de calor cerca del predio desde la siembra,
    # cada uno con la fase en que estaba el cultivo. Son alerta, no perdida calculada:
    # no hay una regla de dano por incendio con respaldo.
    incendios = await leer_incendios(session, id_parcela, cultivo["fecha_siembra"])
    externos = [{"tipo": "incendio_cercano", **dia,
                 "fase": next((f["fase"] for f in resultado["fases"]
                               if f["inicio"] <= dia["fecha"] <= (f["fin"] or "9999")), None)}
                for dia in incendios["dias_con_focos"]]
    # Contraste con el satelite, solo donde el cielo deja ver el predio con frecuencia.
    optica = await leer_disponibilidad_optica(session, id_parcela)
    if not optica["viable"]:
        curva = {"disponible": False, "ventanas_con_pasada_pct": optica.get("ventanas_con_pasada_pct"),
                 "motivo": "sin_medir" if optica["viable"] is None else "zona_con_pocas_pasadas_despejadas"}
    elif estado["sentinel2_ndvi"]["estado"] == "sin_configurar" and estado["hls_ndvi"]["estado"] == "sin_configurar":
        curva = {"disponible": False, "motivo": "faltan_credenciales_del_satelite"}
    else:
        siembra = cultivo["fecha_siembra"]
        observaciones = await leer_ndvi(session, id_parcela, siembra - timedelta(days=40))
        primera = resultado["etapas"][0]
        curva = {"disponible": True, "primera_etapa": primera["etapa"], "fecha_simulada": primera["fecha"],
                 **catalogo_especies.curva_optica(
                     observaciones, siembra, date.fromisoformat(primera["fecha"]) if primera["fecha"] else None),
                 "ultimas_observaciones": [{"fecha": o["fecha"].isoformat(), "ndvi": round(o["ndvi"], 3),
                                            "visible": round(o["visible"], 2), "fuente": o["fuente"]}
                                           for o in observaciones[-8:]]}
    return {"id_cultivo": id_cultivo, "id_parcela": id_parcela, "especie": cultivo["especie"],
            "variedad_local": cultivo["variedad_local"], **resultado, "curva_satelital": curva,
            "eventos_externos": externos, "incendios_revisados": incendios["revisado"],
            "correccion_sesgo": clima.attrs.get("correccion_sesgo"), "estado_ingesta": estado}


async def _cultivo_autorizado(id_cultivo: int, usuario: dict, session: AsyncSession) -> dict:
    """El cultivo, solo si su parcela es del usuario (o el usuario es admin). Uno ajeno responde 404
    igual que uno inexistente."""
    cultivo = (await session.execute(text(
        "SELECT id, id_parcela, fecha_siembra FROM predio_cultivos WHERE id = :id"), {"id": id_cultivo})).mappings().first()
    try:
        if cultivo is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND)
        await _parcela_autorizada(cultivo["id_parcela"], usuario, session)
    except HTTPException:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cultivo no existe")
    return dict(cultivo)


@app.post("/api/cultivos/{id_cultivo}/riegos", status_code=status.HTTP_201_CREATED)
async def declarar_riego(id_cultivo: int, datos: RiegoDeclarado, respuesta: Response,
                          session: AsyncSession = Depends(obtener_sesion),
                          usuario: dict = Depends(usuario_actual)):
    """El agricultor avisa que rego un dia. Se toma como un riego completo (deja la zona de raices
    llena): no se le pregunta la lamina. Desde ese dia el balance de agua de /fenologia parte de
    ahi. Declarar de nuevo el mismo dia responde 200 y no duplica."""
    _frenar(_RIEGOS_POR_USUARIO, f"usuario:{usuario['id']}")
    cultivo = await _cultivo_autorizado(id_cultivo, usuario, session)
    if cultivo["fecha_siembra"] is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "El cultivo no tiene fecha de siembra")
    hoy = date.today()
    desde = max(cultivo["fecha_siembra"], hoy - timedelta(days=RIEGO_DIAS_ATRAS_MAX))
    if not desde <= datos.fecha <= hoy:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                             f"La fecha del riego debe estar entre el {desde.isoformat()} y hoy")
    parametros = {"c": id_cultivo, "f": datos.fecha}
    if (await session.execute(text(
            "SELECT 1 FROM manejo_predio WHERE id_cultivo = :c AND tipo_labor = 'riego' AND fecha = :f"), parametros)).first():
        respuesta.status_code = status.HTTP_200_OK
        return {"registrado": False}
    cantidad = (await session.execute(text(
        "SELECT count(*) FROM manejo_predio WHERE id_cultivo = :c AND tipo_labor = 'riego'"), {"c": id_cultivo})).scalar_one()
    if cantidad >= RIEGOS_MAX_POR_CULTIVO:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Este cultivo ya tiene {RIEGOS_MAX_POR_CULTIVO} riegos registrados")
    await session.execute(text(
        "INSERT INTO manejo_predio (id_cultivo, tipo_labor, fecha) VALUES (:c, 'riego', :f)"), parametros)
    await session.commit()
    return {"registrado": True}


@app.post("/api/cultivos/{id_cultivo}/riegos/anular")
async def anular_riego(id_cultivo: int, datos: RiegoDeclarado, session: AsyncSession = Depends(obtener_sesion),
                        usuario: dict = Depends(usuario_actual)):
    """Borra el riego declarado ese dia (por si se marco sin querer). No falla si no habia ninguno."""
    _frenar(_RIEGOS_POR_USUARIO, f"usuario:{usuario['id']}")
    await _cultivo_autorizado(id_cultivo, usuario, session)
    borrados = (await session.execute(text(
        "DELETE FROM manejo_predio WHERE id_cultivo = :c AND tipo_labor = 'riego' AND fecha = :f RETURNING id"),
        {"c": id_cultivo, "f": datos.fecha})).all()
    await session.commit()
    return {"anulado": bool(borrados)}


@app.get("/api/cultivos/{id_cultivo}/labores")
async def listar_labores(id_cultivo: int, session: AsyncSession = Depends(obtener_sesion),
                          usuario: dict = Depends(usuario_actual)):
    """El registro del cultivo: lo que se declaro (especie, variedad, siembra) y las labores anotadas, de la mas
    reciente a la mas antigua. Incluye los riegos de la tarjeta de riego: es la misma tabla."""
    await _cultivo_autorizado(id_cultivo, usuario, session)
    cultivo = (await session.execute(text(
        "SELECT id, id_parcela, especie, variedad_local, fecha_siembra FROM predio_cultivos WHERE id = :id"),
        {"id": id_cultivo})).mappings().first()
    filas = (await session.execute(text(
        "SELECT tipo_labor AS tipo, fecha FROM manejo_predio WHERE id_cultivo = :id AND tipo_labor = ANY(:tipos) "
        "ORDER BY fecha DESC, id DESC"), {"id": id_cultivo, "tipos": list(LABORES_ANOTABLES)})).mappings().all()
    return {"cultivo": {**dict(cultivo), "fecha_siembra": cultivo["fecha_siembra"].isoformat() if cultivo["fecha_siembra"] else None},
            "labores": [{"tipo": f["tipo"], "fecha": f["fecha"].isoformat()} for f in filas]}


@app.post("/api/cultivos/{id_cultivo}/labores", status_code=status.HTTP_201_CREATED)
async def declarar_labor(id_cultivo: int, datos: LaborDeclarada, respuesta: Response,
                          session: AsyncSession = Depends(obtener_sesion),
                          usuario: dict = Depends(usuario_actual)):
    """Anota una labor (riego, fertilizacion, pesticida o fungicida) hecha un dia: entre la siembra (o los ultimos
    RIEGO_DIAS_ATRAS_MAX dias) y hoy. Anotar la misma labor el mismo dia responde 200 y no duplica."""
    _frenar(_RIEGOS_POR_USUARIO, f"usuario:{usuario['id']}")
    cultivo = await _cultivo_autorizado(id_cultivo, usuario, session)
    if cultivo["fecha_siembra"] is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "El cultivo no tiene fecha de siembra")
    hoy = date.today()
    desde = max(cultivo["fecha_siembra"], hoy - timedelta(days=RIEGO_DIAS_ATRAS_MAX))
    if not desde <= datos.fecha <= hoy:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                             f"La fecha de la labor debe estar entre el {desde.isoformat()} y hoy")
    parametros = {"c": id_cultivo, "t": datos.tipo, "f": datos.fecha}
    if (await session.execute(text(
            "SELECT 1 FROM manejo_predio WHERE id_cultivo = :c AND tipo_labor = :t AND fecha = :f"), parametros)).first():
        respuesta.status_code = status.HTTP_200_OK
        return {"registrado": False}
    cantidad = (await session.execute(text(
        "SELECT count(*) FROM manejo_predio WHERE id_cultivo = :c"), {"c": id_cultivo})).scalar_one()
    if cantidad >= LABORES_MAX_POR_CULTIVO:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Este cultivo ya tiene {LABORES_MAX_POR_CULTIVO} labores anotadas")
    await session.execute(text(
        "INSERT INTO manejo_predio (id_cultivo, tipo_labor, fecha) VALUES (:c, :t, :f)"), parametros)
    await session.commit()
    return {"registrado": True}


@app.post("/api/cultivos/{id_cultivo}/labores/anular")
async def anular_labor(id_cultivo: int, datos: LaborDeclarada, session: AsyncSession = Depends(obtener_sesion),
                        usuario: dict = Depends(usuario_actual)):
    """Borra la labor anotada ese dia (por si se marco sin querer). No falla si no habia ninguna."""
    _frenar(_RIEGOS_POR_USUARIO, f"usuario:{usuario['id']}")
    await _cultivo_autorizado(id_cultivo, usuario, session)
    borrados = (await session.execute(text(
        "DELETE FROM manejo_predio WHERE id_cultivo = :c AND tipo_labor = :t AND fecha = :f RETURNING id"),
        {"c": id_cultivo, "t": datos.tipo, "f": datos.fecha})).all()
    await session.commit()
    return {"anulado": bool(borrados)}


@app.get("/api/cultivos/{id_cultivo}/reportes")
async def listar_reportes(id_cultivo: int, session: AsyncSession = Depends(obtener_sesion),
                           usuario: dict = Depends(usuario_actual)):
    """Los reportes de campo del cultivo, del mas reciente al mas antiguo (hasta 50)."""
    await _cultivo_autorizado(id_cultivo, usuario, session)
    filas = (await session.execute(text(
        "SELECT fase_fenologica AS fase, fecha_observada AS fecha FROM fenologia_observada "
        "WHERE id_cultivo = :id AND fase_fenologica = ANY(:fases) ORDER BY fecha_observada DESC, id DESC LIMIT 50"),
        {"id": id_cultivo, "fases": list(FASES_REPORTE)})).mappings().all()
    return {"reportes": [{"fase": f["fase"], "fecha": f["fecha"].isoformat()} for f in filas]}


@app.post("/api/cultivos/{id_cultivo}/reportes", status_code=status.HTTP_201_CREATED)
async def declarar_reporte(id_cultivo: int, datos: ReporteDeCampo, respuesta: Response,
                            session: AsyncSession = Depends(obtener_sesion),
                            usuario: dict = Depends(usuario_actual)):
    """Guarda un reporte de campo (la etapa en que el agricultor ve su cultivo) con la fecha en que lo vio: de la
    siembra a hoy. El mismo reporte (misma etapa, mismo dia) responde 200 y no se duplica: el telefono puede
    reenviar lo que dejo en cola sin saber si ya llego."""
    _frenar(_REPORTES_POR_USUARIO, f"usuario:{usuario['id']}")
    cultivo = await _cultivo_autorizado(id_cultivo, usuario, session)
    hoy = date.today()
    # Un dia de margen: el telefono puede estar en otra zona horaria que el servidor.
    if cultivo["fecha_siembra"] is None or not cultivo["fecha_siembra"] <= datos.fecha <= hoy + timedelta(days=1):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "La fecha del reporte debe estar entre la siembra y hoy")
    parametros = {"c": id_cultivo, "f": datos.fase, "d": datos.fecha}
    if (await session.execute(text(
            "SELECT 1 FROM fenologia_observada WHERE id_cultivo = :c AND fase_fenologica = :f AND fecha_observada = :d"),
            parametros)).first():
        respuesta.status_code = status.HTTP_200_OK
        return {"registrado": False}
    cantidad = (await session.execute(text(
        "SELECT count(*) FROM fenologia_observada WHERE id_cultivo = :c"), {"c": id_cultivo})).scalar_one()
    if cantidad >= REPORTES_MAX_POR_CULTIVO:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Este cultivo ya tiene {REPORTES_MAX_POR_CULTIVO} reportes")
    capturado = datos.capturado.replace(tzinfo=None) if datos.capturado else None
    await session.execute(text(
        "INSERT INTO fenologia_observada (id_cultivo, fase_fenologica, fecha_observada, fecha_reporte_cliente) "
        "VALUES (:c, :f, :d, :t)"), {**parametros, "t": capturado})
    await session.commit()
    return {"registrado": True}


@app.get("/api/especies/nombres")
async def nombres_especies(response: Response, session: AsyncSession = Depends(obtener_sesion)):
    """Nombre en espanol e ingles de cada especie y de las variedades conocidas. Es el
    catalogo publico, sin datos de nadie: no pide sesion para que la interfaz lo cargue al abrir."""
    response.headers["Cache-Control"] = "public, max-age=3600"
    return await RepositorioPostgres(session).nombres_especies()


@app.get("/api/especies/buscar")
async def buscar_especies(q: str = Query(..., min_length=2, max_length=60), limite: int = Query(12, ge=1, le=30),
                           session: AsyncSession = Depends(obtener_sesion), usuario: dict = Depends(usuario_actual)):
    """Busca una especie por su nombre (espanol, ingles, comun o cientifico) para agregarla como cultivo. Devuelve solo
    lo que se puede sembrar y marca cuales tienen calendario por etapa (`seguimiento`): las demas se registran
    pero no se les calcula calendario. Cualquiera de las devueltas se puede declarar con POST /parcelas/{id}/cultivos."""
    repo = multianual.RepositorioCacheado(RepositorioPostgres(session), _ALMACEN_CATALOGO)
    fuentes = {r["especie"]: r.get("fuente") for r in await repo.requisitos_genericos()}
    return {"especies": catalogo_especies.buscar_especies(
        await repo.identidades(), fuentes, set(await repo.especies_con_fenologia()), q, limite)}


@app.get("/api/especies/con_seguimiento")
async def especies_con_seguimiento(session: AsyncSession = Depends(obtener_sesion),
                                    usuario: dict = Depends(usuario_actual)):
    """Las especies del catalogo que tienen seguimiento por fase, con sus etapas y la
    fecha de siembra de referencia: lo que una pantalla necesita para ofrecer 'que
    sembraste' sin llevar la lista escrita en el codigo."""
    repo = RepositorioPostgres(session)
    especies = []
    for especie in sorted(await repo.especies_con_fenologia()):
        etapas = catalogo_especies.elegir_etapas(await repo.umbrales_fenologicos(especie, None), None)
        rasgos = await repo.rasgos_rotacion(especie) or {}
        especies.append({"especie": especie, "etapas": [u["etapa"] for u in etapas],
                         "nivel_madurez": await catalogo_especies.nivel_madurez(especie, None, repo),
                         "calendario_aproximado": await catalogo_especies.calendario_aproximado(especie, None, repo),
                         "siembra_mes": rasgos.get("siembra_mes"), "siembra_dia": rasgos.get("siembra_dia")})
    return {"especies": especies}


# ---------------------------------------------------------------- indicadores locales
# Conocimiento de la comunidad (aves, floracion de especies) y lo que anuncia, por zona.
# Informativo y sin validar: no toca la proyeccion del cultivo. Ver services/indicadores_locales.py.

@app.get("/api/parcelas/{id_parcela}/indicadores")
async def indicadores_parcela(id_parcela: int, session: AsyncSession = Depends(obtener_sesion),
                               usuario: dict = Depends(usuario_actual)):
    """Los indicadores activos de la zona del predio y su condicion: cuantos agricultores
    distintos los reportaron dentro de su vigencia y si ya salen 'confirmados'. `resumen`
    junta lo que anuncian hoy las senales confirmadas."""
    await _parcela_autorizada(id_parcela, usuario, session)
    indicadores = await indicadores_locales.senales_del_predio(session, id_parcela, usuario["id"], date.today())
    return {"indicadores": indicadores, "resumen": indicadores_locales.resumen_por_significado(indicadores),
            "validado": False}


@app.post("/api/indicadores/{id_indicador}/observaciones", status_code=status.HTTP_201_CREATED)
async def reportar_indicador(id_indicador: int, datos: ObservacionNueva, respuesta: Response,
                              session: AsyncSession = Depends(obtener_sesion),
                              usuario: dict = Depends(usuario_actual)):
    """El agricultor reporta que vio el evento de un indicador de su zona. Solo puede
    hacerlo si tiene un predio dentro de ella. Repetir el mismo reporte (mismo dia) responde
    200 y no cuenta otra vez: el telefono sin senal puede reintentar."""
    _frenar(_OBSERVACIONES_POR_USUARIO, f"usuario:{usuario['id']}")
    hoy = date.today()
    if not hoy - timedelta(days=indicadores_locales.OBSERVACION_DIAS_ATRAS_MAX) <= datos.fecha_observada <= hoy:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                             f"La fecha debe estar entre {indicadores_locales.OBSERVACION_DIAS_ATRAS_MAX} días atrás y hoy")
    indicador = await indicadores_locales.indicador_para_reportar(session, id_indicador, usuario["id"])
    if indicador is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Indicador no existe")
    if not indicadores_locales.mes_en_ventana(datos.fecha_observada, indicador["mes_desde"], indicador["mes_hasta"]):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                             f"Ese día queda fuera de los meses en que cuenta este indicador "
                             f"({indicador['mes_desde']} a {indicador['mes_hasta']})")
    nueva = await indicadores_locales.registrar_observacion(session, id_indicador, usuario["id"], datos.fecha_observada)
    if not nueva:
        respuesta.status_code = status.HTTP_200_OK
    return {"registrada": nueva}


@app.post("/api/admin/zonas-indicadores", status_code=status.HTTP_201_CREATED)
async def admin_crear_zona(datos: ZonaNueva, session: AsyncSession = Depends(obtener_sesion),
                            _admin: dict = Depends(requerir_admin)):
    """Una zona es un poligono (GeoJSON, WGS84): por ejemplo una comuna o un sector. Los
    indicadores se definen para una zona y los ven los predios cuyo centro cae dentro."""
    geojson = _validar_perimetro(datos.perimetro)
    try:
        id_zona = await indicadores_locales.crear_zona(session, datos.nombre, geojson)
    except indicadores_locales.ZonaInvalida as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error))
    if id_zona is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya hay una zona con ese nombre")
    return {"id": id_zona, "nombre": datos.nombre}


@app.get("/api/admin/zonas-indicadores")
async def admin_listar_zonas(session: AsyncSession = Depends(obtener_sesion),
                              _admin: dict = Depends(requerir_admin)):
    return {"zonas": await indicadores_locales.listar_zonas(session)}


@app.post("/api/admin/indicadores-locales", status_code=status.HTTP_201_CREATED)
async def admin_crear_indicador(datos: IndicadorNuevo, session: AsyncSession = Depends(obtener_sesion),
                                 _admin: dict = Depends(requerir_admin)):
    if not await indicadores_locales.zona_existe(session, datos.id_zona):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Zona no existe")
    return {"id": await indicadores_locales.crear_indicador(session, datos.model_dump())}


@app.get("/api/admin/indicadores-locales")
async def admin_listar_indicadores(id_zona: int | None = Query(None), session: AsyncSession = Depends(obtener_sesion),
                                    _admin: dict = Depends(requerir_admin)):
    return {"indicadores": await indicadores_locales.listar_indicadores(session, date.today(), id_zona)}


@app.post("/api/admin/indicadores-locales/{id_indicador}/estado")
async def admin_estado_indicador(id_indicador: int, datos: EstadoIndicador,
                                  session: AsyncSession = Depends(obtener_sesion),
                                  _admin: dict = Depends(requerir_admin)):
    if not await indicadores_locales.cambiar_estado(session, id_indicador, datos.activo):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Indicador no existe")
    return {"id": id_indicador, "activo": datos.activo}


_FUENTES_CLIMA_DIARIO = ("power", "open_meteo")


@app.get("/api/parcelas/{id_parcela}/clima")
async def clima_parcela(id_parcela: int, tareas: BackgroundTasks,
                         dias_atras: int = Query(30, ge=1, le=DIAS_CLIMA_ATRAS_MAX),
                         session: AsyncSession = Depends(obtener_sesion),
                         usuario: dict = Depends(usuario_actual)):
    """El clima diario del predio alrededor de hoy: los ultimos `dias_atras` dias y el
    pronostico, cada dia con su fuente y su horizonte ('observado' o 'pronostico') -- ver
    repositorio_clima.leer_clima_diario(). Lo estimado con el ano anterior no se entrega:
    aca se muestra tiempo, no una referencia para completar un ciclo. Si las fuentes
    diarias estan vencidas las deja refrescandose y responde con lo que hay."""
    await _parcela_autorizada(id_parcela, usuario, session)
    jobs = await ingesta_predio.encolar(session, id_parcela, _FUENTES_CLIMA_DIARIO)
    if jobs:
        tareas.add_task(ingesta_predio.ingerir_predio, id_parcela, jobs)
    completo = await ingesta_predio.estado_ingesta(session, id_parcela)
    estado = {f: completo[f] for f in ("cr2met", *_FUENTES_CLIMA_DIARIO)}
    hoy = date.today()
    serie = await leer_clima_diario(session, id_parcela, hoy - timedelta(days=dias_atras), hoy)
    if serie is not None:
        serie = serie[serie["horizonte"] != "estimado"]
    if serie is None or serie.empty:
        raise HTTPException(status.HTTP_409_CONFLICT, {
            "mensaje": "Todavía no hay clima diario para este predio", "estado_ingesta": estado})
    numero = lambda v: None if v is None or v != v else round(float(v), 1)
    # Como estuvo o va a estar el cielo: el codigo de tiempo (WMO) que trae el modelo de Open-Meteo para el dia.
    codigos = {f["fecha"]: int(f["valor"]) for f in (await session.execute(text(
        "SELECT periodo_inicio AS fecha, valor FROM cache_consulta_grilla WHERE id_parcela = :id "
        "AND capa = 'openmeteo_codigo_tiempo' AND valor IS NOT NULL AND periodo_inicio >= :desde"),
        {"id": id_parcela, "desde": hoy - timedelta(days=dias_atras)})).mappings().all()}
    return {"id_parcela": id_parcela, "hoy": hoy.isoformat(),
            "dias": [{"fecha": fecha.date().isoformat(), "tmin": numero(d["tmin"]), "tmax": numero(d["tmax"]),
                      "lluvia_mm": numero(d["lluvia"]), "humedad_relativa": numero(d["rh"]),
                      "codigo_tiempo": codigos.get(fecha.date()),
                      "fuente": d["fuente"], "horizonte": d["horizonte"]}
                     for fecha, d in serie.iterrows()],
            "correccion_sesgo": serie.attrs.get("correccion_sesgo"), "estado_ingesta": estado}


@app.get("/api/parcelas/{id_parcela}/alertas_clima")
async def alertas_clima_parcela(id_parcela: int, session: AsyncSession = Depends(obtener_sesion),
                                 usuario: dict = Depends(usuario_actual)):
    """Los cambios fuertes de clima que vienen para el predio (helada, calor, lluvia fuerte, saltos bruscos de la
    maxima), de hoy al final del pronostico. No depende del cultivo y no dispara descargas: lee lo que ya hay. Sin
    clima diario responde `alertas: []` con `hay_datos: false`, para no decir "sin alertas" cuando no se miro."""
    await _parcela_autorizada(id_parcela, usuario, session)
    hoy = date.today()
    serie = await leer_clima_diario(session, id_parcela, hoy - timedelta(days=1))
    if serie is not None:
        serie = serie[serie["horizonte"] != "estimado"]
    if serie is None or serie.empty:
        return {"id_parcela": id_parcela, "hoy": hoy.isoformat(), "hay_datos": False, "alertas": []}
    return {"id_parcela": id_parcela, "hoy": hoy.isoformat(), "hay_datos": True,
            "hasta": serie.index.max().date().isoformat(),
            "alertas": alertas_clima.cambios_fuertes(serie, hoy.isoformat())}


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


@app.post("/api/admin/parcelas/{id_parcela}/ingesta/suelo_quimico")
async def ingesta_suelo_quimico(id_parcela: int, session: AsyncSession = Depends(obtener_sesion),
                                 _admin: dict = Depends(requerir_admin)):
    """SoilGrids (ISRIC) -- pH, textura, carbono organico. Complementa a CLSoilMaps
    (/ingesta/suelo), que no tiene pH -- ver cliente_soilgrids.py. Sin dimension temporal
    (mapa estatico, igual tratamiento que CLSoilMaps/Explorador Solar)."""
    centroide = (await session.execute(
        text("SELECT ST_Y(ST_Centroid(geometria)) AS lat, ST_X(ST_Centroid(geometria)) AS lon "
             "FROM parcela WHERE id = :id"), {"id": id_parcela},
    )).mappings().first()
    if not centroide:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Parcela no existe")
    lat, lon = centroide["lat"], centroide["lon"]

    datos = cliente_soilgrids.consultar_suelo(lat, lon)
    periodo_inicio, periodo_fin = date(2020, 1, 1), date(2020, 12, 31)  # version de SoilGrids v2.0 (2020)
    guardado = {}
    for capa, valor in (("soilgrids_ph", datos["ph"]), ("soilgrids_arcilla_pct", datos["arcilla_pct"]),
                         ("soilgrids_arena_pct", datos["arena_pct"]), ("soilgrids_limo_pct", datos["limo_pct"]),
                         ("soilgrids_carbono_organico_g_kg", datos["carbono_organico_g_kg"])):
        await guardar_consulta_grilla(session, id_parcela, capa, periodo_inicio, periodo_fin, valor,
                                       "250m", "SoilGrids_v2.0", "sin_dato" if valor is None else "completa")
        guardado[capa] = valor
    return {"parcela": id_parcela, "lat": lat, "lon": lon, "guardado_en_cache_consulta_grilla": guardado}


@app.post("/api/admin/parcelas/{id_parcela}/ingesta/incendios")
async def ingesta_incendios(id_parcela: int, dias: int = 5, radio_grados: float = 0.1,
                             session: AsyncSession = Depends(obtener_sesion),
                             _admin: dict = Depends(requerir_admin)):
    """NASA FIRMS -- focos de calor reales (VIIRS). Necesita FIRMS_MAP_KEY en el entorno
    (clave gratuita por email, ver cliente_firms.py). dias: 1-5 (limite real de la API
    para productos _NRT). radio_grados: medio lado del cuadrado alrededor de la parcela
    -- un foco de incendio es un evento regional, no tiene sentido pedir solo el centroide
    como las demas fuentes puntuales."""
    map_key = os.environ.get("FIRMS_MAP_KEY")
    if not map_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Falta FIRMS_MAP_KEY en el entorno")

    centroide = (await session.execute(
        text("SELECT ST_Y(ST_Centroid(geometria)) AS lat, ST_X(ST_Centroid(geometria)) AS lon "
             "FROM parcela WHERE id = :id"), {"id": id_parcela},
    )).mappings().first()
    if not centroide:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Parcela no existe")
    lat, lon = centroide["lat"], centroide["lon"]
    bbox = (lon - radio_grados, lat - radio_grados, lon + radio_grados, lat + radio_grados)

    try:
        focos = cliente_firms.consultar_focos(map_key, bbox, dias=dias)
    except cliente_firms.ErrorFirms as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error))
    hoy = date.today()
    desde = hoy - timedelta(days=dias - 1)
    frp_max = float(focos["frp"].max()) if len(focos) else None
    await guardar_consulta_grilla(session, id_parcela, "firms_focos_detectados", desde, hoy,
                                   float(len(focos)), "375m_VIIRS", "VIIRS_NOAA20_NRT", "completa")
    await guardar_consulta_grilla(session, id_parcela, "firms_frp_max", desde, hoy,
                                   frp_max, "375m_VIIRS", "VIIRS_NOAA20_NRT",
                                   "sin_dato" if frp_max is None else "completa")
    return {"parcela": id_parcela, "bbox": bbox, "dias": dias, "focos_detectados": len(focos),
            "frp_maximo": frp_max, "detalle": focos.to_dict("records")}


@app.get("/api/admin/parcelas/{id_parcela}/idoneidad")
async def idoneidad_parcela(id_parcela: int, especies: str | None = None, limite: int = 50,
                             session: AsyncSession = Depends(obtener_sesion),
                             _admin: dict = Depends(requerir_admin)):
    """catalogo_especies.calcular_idoneidad() real -- pH real (SoilGrids), agua
    disponible real (CLSoilMaps), y la serie DIARIA real de clima (hoy CR2MET) para
    correr la simulacion real por fase en las especies que ya tienen perfil fenologico
    (ver _idoneidad_simulada en catalogo_especies.py) -- no solo el promedio ciego de
    tmin/tmax, que es lo unico que se podia hacer antes de esto. `especies`: lista
    separada por coma, cada entrada 'especie' o 'especie:variedad_local' (ej.
    'papa,solanum_tuberosum:yagana') -- BUG REAL corregido: antes esto siempre consultaba
    la fila generica (variedad_local NULL), sin forma de pedir una variedad especifica
    aunque requisitos_especie/regla_dano_especie si tienen esa columna.

    Sin `especies`: BUG REAL corregido, otro -- antes el default (3 nombres a mano) era
    lo UNICO que se podia evaluar sin que alguien ya supiera de antemano el nombre
    cientifico exacto a escribir; las 2068 especies de EcoCrop quedaban invisibles para
    cualquier consulta real. Ahora recorre el catalogo real via
    `repo.listar_especies()` -- `limite` (default 50) por el costo real de evaluar cada
    una (una consulta a Postgres por especie, no instantaneo sobre 2071 filas); pasar
    `limite=0` corre el catalogo completo, mas lento pero sin tope."""
    centroide = (await session.execute(
        text("SELECT ST_Y(ST_Centroid(geometria)) AS lat FROM parcela WHERE id = :id"), {"id": id_parcela},
    )).mappings().first()
    if not centroide:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Parcela no existe")
    lat = centroide["lat"]

    # Lista explicita de capas por variable -- BUG REAL corregido: antes era
    # `capa LIKE '%tmin%'`/`'%tmax%'`, que promediaria en silencio cualquier capa futura
    # que tuviera esa substring en el nombre, sin que quien llama se entere. Agregar una
    # fuente nueva de temperatura significa agregarla aca explicito, a proposito.
    CAPAS_TMIN = ("cr2met_tmin",)
    CAPAS_TMAX = ("cr2met_tmax",)
    fila = (await session.execute(text("""
        SELECT
          avg(valor) FILTER (WHERE capa = 'soilgrids_ph') AS ph,
          avg(valor) FILTER (WHERE capa = 'clsoilmaps_awc_total_mm') AS awc_mm,
          avg(valor) FILTER (WHERE capa = ANY(:capas_tmin)) AS tmin,
          avg(valor) FILTER (WHERE capa = ANY(:capas_tmax)) AS tmax
        FROM cache_consulta_grilla WHERE id_parcela = :id
    """), {"id": id_parcela, "capas_tmin": list(CAPAS_TMIN), "capas_tmax": list(CAPAS_TMAX)})).mappings().first()
    if fila is None or all(v is None for v in fila.values()):
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                             "Parcela sin datos en cache_consulta_grilla todavia -- correr las ingestas primero")
    sitio = dict(fila)

    filas_clima = (await session.execute(text("""
        SELECT periodo_inicio AS fecha, capa, valor FROM cache_consulta_grilla
        WHERE id_parcela = :id AND capa IN ('cr2met_tmin', 'cr2met_tmax', 'cr2met_lluvia')
        ORDER BY periodo_inicio
    """), {"id": id_parcela})).mappings().all()
    clima = None
    if filas_clima:
        import pandas as pd
        df = pd.DataFrame(filas_clima)
        clima = df.pivot(index="fecha", columns="capa", values="valor")
        clima.index = pd.to_datetime(clima.index)
        clima = clima.rename(columns={"cr2met_tmin": "tmin", "cr2met_tmax": "tmax", "cr2met_lluvia": "lluvia"})

    repo = RepositorioPostgres(session)
    if especies is None:
        lista_especies = await repo.listar_especies()
        if limite > 0:
            lista_especies = lista_especies[:limite]
    else:
        lista_especies = []
        for entrada in especies.split(","):
            if ":" in entrada:
                especie, variedad = entrada.split(":", 1)
            else:
                especie, variedad = entrada, None
            lista_especies.append((especie.strip(), variedad.strip() if variedad else None))

    resultado = await catalogo_especies.calcular_idoneidad(sitio, lista_especies, repo, clima=clima, lat=lat)
    return {"parcela": id_parcela, "sitio": sitio, "especies_evaluadas": len(lista_especies),
            "clima_dias_reales_usados": len(clima) if clima is not None else 0, "idoneidad": resultado}


@app.post("/api/admin/parcelas/{id_parcela}/ingesta/appeears")
async def ingesta_appeears(id_parcela: int, dias: int = 60, session: AsyncSession = Depends(obtener_sesion),
                            _admin: dict = Depends(requerir_admin)):
    """Landsat (HLS, reflectancia + NDVI/NDMI, filtrado por nube real), SMAP (humedad de
    suelo superficial) y ECOSTRESS (temperatura de superficie, estres termico) -- las tres
    tareas 'point' se piden primero y se esperan despues, no una por una, para no sumar
    los minutos de las tres en serie. Necesita EARTHDATA_USUARIO/EARTHDATA_CLAVE en el
    entorno (cuenta real de Earthdata Login -- ver Fase 4: el login debe ser por
    usuario/clave reales, no por email ni por el token de usuario de EDL, que no
    funciona federado contra esta API)."""
    usuario, clave = os.environ.get("EARTHDATA_USUARIO"), os.environ.get("EARTHDATA_CLAVE")
    if not usuario or not clave:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Faltan EARTHDATA_USUARIO/EARTHDATA_CLAVE en el entorno")

    centroide = (await session.execute(
        text("SELECT ST_Y(ST_Centroid(geometria)) AS lat, ST_X(ST_Centroid(geometria)) AS lon "
             "FROM parcela WHERE id = :id"), {"id": id_parcela},
    )).mappings().first()
    if not centroide:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Parcela no existe")
    lat, lon = centroide["lat"], centroide["lon"]

    token = cliente_appeears.iniciar_sesion(usuario, clave)
    os.makedirs(_CACHE_APPEEARS, exist_ok=True)
    punto = [{"latitude": lat, "longitude": lon, "id": f"parcela_{id_parcela}", "category": "parcela"}]
    hoy, desde = date.today(), date.today() - timedelta(days=dias)
    rango = (desde.strftime("%m-%d-%Y"), hoy.strftime("%m-%d-%Y"))

    # Las cuatro se piden de entrada -- corren en paralelo del lado de AppEEARS, esperar
    # una antes de pedir la siguiente desperdiciaria los minutos de cola de cada una.
    # Landsat pide B02/B07 ademas de B04/B05/B06 -- las necesitan EVI/SAVI/NBR/BSI y los
    # indices minerales (arcillas/oxidos de hierro), ver calcular_indices_opticos().
    tareas = {
        "landsat": cliente_appeears.solicitar_extraccion_multicapa(
            token, f"mogewe_p{id_parcela}_landsat",
            [("HLSL30.020", "B02"), ("HLSL30.020", "B04"), ("HLSL30.020", "B05"),
             ("HLSL30.020", "B06"), ("HLSL30.020", "B07"), ("HLSL30.020", "Fmask")],
            punto, *rango),
        "smap": cliente_appeears.solicitar_extraccion_puntual(
            token, f"mogewe_p{id_parcela}_smap", "SPL4SMGP.008", "Geophysical_Data_sm_surface", punto, *rango),
        "ecostress": cliente_appeears.solicitar_extraccion_puntual(
            token, f"mogewe_p{id_parcela}_ecostress", "ECO_L2_LSTE.002", "LST", punto, *rango),
        # LST propio de Landsat (TIRS), distinto del de ECOSTRESS -- misma variable fisica,
        # dos sensores/resoluciones distintas (30m vs 70m), ver clasificacion NASA/USGS
        # que trajo el usuario. ST_B10 viene en Kelvin ya escalado por AppEEARS (verificar
        # igual contra el valor real antes de usarlo para decidir algo).
        "landsat_lst": cliente_appeears.solicitar_extraccion_puntual(
            token, f"mogewe_p{id_parcela}_landsat_lst", "L08_ST.002", "ST_B10", punto, *rango),
    }

    resultados, filas_escritas = {}, 0
    for nombre, task_id in tareas.items():
        destino = os.path.join(_CACHE_APPEEARS, f"p{id_parcela}_{nombre}.csv")
        archivo = cliente_appeears.esperar_y_descargar(token, task_id, destino, intervalo_s=15, max_intentos=40)
        if archivo is None:
            resultados[nombre] = {"estado": "no_disponible"}
            continue
        import pandas as pd
        df = pd.read_csv(archivo)

        if nombre == "landsat":
            df = cliente_appeears.filtrar_nubes_hls(df, "HLSL30_020_Fmask")
            if df.empty:
                resultados[nombre] = {"dias_sin_nube": 0}
                continue
            indices = cliente_appeears.calcular_indices_opticos(df, "HLSL30.020")
            capas_indices = ("ndvi", "ndmi", "evi", "savi", "nbr", "bsi", "arcilla_ratio", "oxido_hierro_ratio")
            for _, fila in indices.iterrows():
                dia = date.fromisoformat(fila["Date"])
                for capa in capas_indices:
                    await guardar_consulta_grilla(session, id_parcela, f"landsat_{capa}", dia, dia,
                                                   float(fila[capa]), "30m", "HLSL30.020", "completa")
                    filas_escritas += 1
            resultados[nombre] = {"dias_sin_nube": len(df),
                                   **{f"{c}_ultimo": float(indices.iloc[-1][c]) for c in capas_indices}}

        elif nombre == "landsat_lst":
            col = cliente_appeears.nombre_columna_valor("L08_ST.002", "ST_B10")
            for _, fila in df.iterrows():
                dia = date.fromisoformat(str(fila["Date"])[:10])
                await guardar_consulta_grilla(session, id_parcela, "landsat_lst_kelvin", dia, dia,
                                               float(fila[col]), "30m", "L08_ST.002", "completa")
                filas_escritas += 1
            resultados[nombre] = {"pases": len(df)}

        elif nombre == "smap":
            col = cliente_appeears.nombre_columna_valor("SPL4SMGP.008", "Geophysical_Data_sm_surface")
            df["dia"] = df["Date"].str[:10]
            diario = df.groupby("dia")[col].mean()
            for dia_str, valor in diario.items():
                dia = date.fromisoformat(dia_str)
                await guardar_consulta_grilla(session, id_parcela, "smap_humedad_superficial", dia, dia,
                                               float(valor), "9km", "SPL4SMGP.008", "completa")
                filas_escritas += 1
            resultados[nombre] = {"dias": len(diario), "humedad_promedio": float(diario.mean())}

        elif nombre == "ecostress":
            col = cliente_appeears.nombre_columna_valor("ECO_L2_LSTE.002", "LST")
            for _, fila in df.iterrows():
                dia = date.fromisoformat(str(fila["Date"])[:10])
                await guardar_consulta_grilla(session, id_parcela, "ecostress_lst", dia, dia,
                                               float(fila[col]), "70m", "ECO_L2_LSTE.002", "completa")
                filas_escritas += 1
            resultados[nombre] = {"pases": len(df)}

    return {"parcela": id_parcela, "lat": lat, "lon": lon, "filas_escritas_en_cache": filas_escritas,
            "resultados": resultados}


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
