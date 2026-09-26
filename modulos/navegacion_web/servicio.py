# -*- coding: utf-8 -*-
"""Fachada de servicios del módulo de navegación web.

Devuelve siempre el contrato común (``nucleo.contrato.Resultado``) y nunca
lanza al usuario: captura las excepciones y las convierte en error tipado.

Los scripts siguen funcionando por separado; esta fachada es para **componer**
(llamar desde el orquestador, pipelines o el REPL) sin depender de subprocesos.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.join(_HERE, "scripts")
_RECETAS = os.path.join(_HERE, "recetas")
_RAIZ = os.path.dirname(os.path.dirname(_HERE))
for _p in (_RAIZ, _SCRIPTS, _RECETAS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from nucleo.contrato import exito, fallo  # noqa: E402
from nucleo.errores import AgenteError  # noqa: E402

MODULO = "navegacion_web"


def _capturar(fn, *args, **kwargs):
    try:
        return exito(datos=fn(*args, **kwargs))
    except AgenteError as e:
        return e.a_resultado()
    except Exception as e:  # noqa: BLE001
        return fallo((MODULO, "interno"), str(e), repr(e))


# --- Configuración y memoria -------------------------------------------------
def configuracion():
    import config

    return _capturar(config.cargar)


def cursos():
    import config

    return _capturar(config.cursos)


def curso(nombre):
    import config

    return _capturar(config.curso, nombre)


def plataformas():
    import registro

    return _capturar(registro._leer_json, registro.PLATAFORMAS, {})


def recetas():
    import registro

    return _capturar(registro.listar_recetas)


# --- Moodle / SIMA (API REST) ------------------------------------------------
def token_sima(usuario=None, base=None):
    import sima_token

    kw = {}
    if usuario:
        kw["usuario"] = usuario
    if base:
        kw["base"] = base
    return _capturar(sima_token.obtener, **kw)


def estructura_moodle(curso, base=None, token=None, cache=True):
    import moodle_api

    return _capturar(
        moodle_api.estructura, curso, base=base or moodle_api.DEFAULT_BASE,
        token=token, cache=cache,
    )


# --- Subprocesos (actividades que requieren navegador/CDP) -------------------
def _subproceso(script, args):
    ruta = os.path.join(_SCRIPTS if os.path.sep not in script else _HERE, script)
    proc = subprocess.run(
        [sys.executable, ruta] + list(args),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        return fallo((MODULO, "subproceso"),
                     (proc.stderr or "fallo el subproceso").strip(),
                     "exit=%s" % proc.returncode)
    try:
        return exito(datos=json.loads(proc.stdout))
    except Exception:
        return exito(datos={"salida": proc.stdout.strip()})


def resolver_h5p(url):
    return _subproceso("h5p_solver.py", ["--url", url])


def canva(cmd, **opciones):
    args = [cmd]
    for k, v in opciones.items():
        if v is not None:
            args += ["--%s" % k.replace("_", "-"), str(v)]
    return _subproceso("canva.py", args)


def drive(cmd, **opciones):
    args = [cmd]
    for k, v in opciones.items():
        if v is not None:
            args += ["--%s" % k.replace("_", "-"), str(v)]
    return _subproceso("drive_google.py", args)
