# -*- coding: utf-8 -*-
"""Configuración central y acceso al catálogo ``capacidades.json``."""
from __future__ import annotations

import json
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPACIDADES = os.path.join(RAIZ, "capacidades.json")


def cargar_capacidades():
    try:
        with open(CAPACIDADES, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"comandos": []}


def comandos():
    return cargar_capacidades().get("comandos", [])


def buscar(comando_id):
    for c in comandos():
        if c.get("id") == comando_id:
            return c
    return None


def ruta_script(comando_id):
    c = buscar(comando_id)
    if not c:
        return None
    return os.path.join(RAIZ, c["script"])
