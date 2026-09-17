# -*- coding: utf-8 -*-
"""Registro de artefactos y utilidades de integridad."""
from __future__ import annotations

import hashlib
import json
import os

from .contrato import Artefacto


def hash_archivo(ruta, bloque=1 << 20):
    """Devuelve el SHA-256 (prefijo) de un archivo, o ``None`` si no existe."""
    if not ruta or not os.path.exists(ruta):
        return None
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for chunk in iter(lambda: f.read(bloque), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def artefacto(tipo, ruta):
    """Crea un ``Artefacto`` con hash calculado."""
    return Artefacto(tipo=tipo, ruta=ruta, hash=hash_archivo(ruta))


def escribir_manifiesto(workspace, datos):
    """Escribe/actualiza ``manifest.json`` en un workspace de trabajo."""
    os.makedirs(workspace, exist_ok=True)
    ruta = os.path.join(workspace, "manifest.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2, default=str)
    return ruta
