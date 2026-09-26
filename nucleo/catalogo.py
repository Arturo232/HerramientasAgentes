# -*- coding: utf-8 -*-
"""Alta, actualización y baja de comandos en ``capacidades.json``.

``capacidades.json`` es la fuente única: al registrar aquí un comando, aparece
automáticamente en el CLI (``agente``), la ayuda, el REPL y el servidor MCP.
"""
from __future__ import annotations

import json

from . import config


def _escribir(data):
    with open(config.CAPACIDADES, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def existe(comando_id):
    return config.buscar(comando_id) is not None


def agregar(entrada, reemplazar=False):
    """Agrega (o reemplaza) un comando. Devuelve ``True`` si se guardó."""
    data = config.cargar_capacidades()
    cmds = data.setdefault("comandos", [])
    for i, c in enumerate(cmds):
        if c.get("id") == entrada["id"]:
            if not reemplazar:
                return False
            cmds[i] = entrada
            _escribir(data)
            return True
    cmds.append(entrada)
    _escribir(data)
    return True


def quitar(comando_id):
    """Quita un comando del catálogo (no borra el archivo del script)."""
    data = config.cargar_capacidades()
    cmds = data.get("comandos", [])
    nuevos = [c for c in cmds if c.get("id") != comando_id]
    if len(nuevos) == len(cmds):
        return False
    data["comandos"] = nuevos
    _escribir(data)
    return True
