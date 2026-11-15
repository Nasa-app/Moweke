"""Rutas para importar el motor igual que main.py: `services` como paquete y, ademas, la
carpeta services en el path, porque catalogo_especies importa `pheno_engine` y `motor_estres`
con imports planos."""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for ruta in (RAIZ, os.path.join(RAIZ, "services")):
    if ruta not in sys.path:
        sys.path.insert(0, ruta)
