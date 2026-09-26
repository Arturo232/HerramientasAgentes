#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Carga la configuracion central del modulo (config.json).

Expone helpers para que los scripts no tengan rutas/IDs hardcodeados.

Uso:
    import config
    config.base_sima()            # https://sima.unicartagena.edu.co
    config.curso("Negocios Internacionales")   # 869
    config.cursos()               # {nombre: id}
    config.drive_materia("NEGOCIOS INTERNACIONALES")
    config.ruta("actividades")
"""
import json
import os

_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(_DIR, "config.json")


def cargar():
    try:
        return json.load(open(CONFIG, encoding="utf-8"))
    except Exception:
        return {}


def get(*ruta, defecto=None):
    d = cargar()
    for k in ruta:
        if not isinstance(d, dict) or k not in d:
            return defecto
        d = d[k]
    return d


def base_sima():
    return get("sima", "base", defecto="https://sima.unicartagena.edu.co")


def cursos():
    return get("sima", "cursos", defecto={})


def curso(nombre):
    for n, i in cursos().items():
        if nombre.lower() in n.lower():
            return i
    return None


def drive_materia(nombre):
    return get("drive", "materias_quinto", defecto={}).get(nombre.upper())


def ruta(nombre):
    r = get("rutas", nombre, defecto="")
    return os.path.expanduser(r)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("base_sima:", base_sima())
    print("cursos:")
    for n, i in cursos().items():
        print("  %-32s %s" % (n, i))
    print("actividades:", ruta("actividades"))
