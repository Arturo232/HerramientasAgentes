# -*- coding: utf-8 -*-
"""Fachada de servicios del módulo de edición de video.

Devuelve el contrato común (``nucleo.contrato.Resultado``) invocando los
scripts y parseando su salida ``--json``.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.join(_HERE, "scripts")
_RAIZ = os.path.dirname(os.path.dirname(_HERE))
for _p in (_RAIZ, _SCRIPTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from nucleo.contrato import Resultado, fallo  # noqa: E402

MODULO = "edicion_video"


def _run(script, args):
    proc = subprocess.run(
        [sys.executable, os.path.join(_SCRIPTS, script)] + list(args) + ["--json"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    for linea in reversed(proc.stdout.strip().splitlines()):
        try:
            d = json.loads(linea)
        except Exception:
            continue
        return Resultado(ok=d.get("ok", False), datos=d.get("datos"),
                         meta=d.get("meta", {}), artefactos=d.get("artefactos", []),
                         error=d.get("error"))
    return fallo((MODULO, "subproceso"),
                 proc.stderr.strip() or "fallo el script de video",
                 "exit=%s" % proc.returncode)


def editar(plan, salida=None):
    args = ["editar", "--plan", plan]
    if salida:
        args += ["--salida", salida]
    return _run("editar_video.py", args)


def extraer_audio(entrada, salida=None):
    args = ["extraer-audio", "--input", entrada]
    if salida:
        args += ["--salida", salida]
    return _run("editar_video.py", args)


def convertir(entrada, salida, crf=None, escala=None):
    args = ["convertir", "--input", entrada, "--salida", salida]
    if crf is not None:
        args += ["--crf", str(crf)]
    if escala:
        args += ["--escala", escala]
    return _run("editar_video.py", args)


def render_moderno(entrada, salida, **opciones):
    args = ["--input", entrada, "--salida", salida]
    for k, v in opciones.items():
        if v is True:
            args.append("--%s" % k.replace("_", "-"))
        elif v not in (None, False):
            args += ["--%s" % k.replace("_", "-"), str(v)]
    return _run("renderizar_moderno.py", args)


def subtitulos(entrada, **opciones):
    args = ["--input", entrada]
    for k, v in opciones.items():
        if v is True:
            args.append("--%s" % k.replace("_", "-"))
        elif v not in (None, False):
            args += ["--%s" % k.replace("_", "-"), str(v)]
    return _run("subtitulos.py", args)
