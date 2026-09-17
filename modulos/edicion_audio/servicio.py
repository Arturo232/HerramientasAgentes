# -*- coding: utf-8 -*-
"""Fachada de servicios del módulo de edición de audio.

Devuelve el contrato común (``nucleo.contrato.Resultado``) invocando el script
y parseando su salida ``--json``.
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

MODULO = "edicion_audio"
_SCRIPT = os.path.join(_SCRIPTS, "procesar_audio.py")


def _run(args):
    proc = subprocess.run(
        [sys.executable, _SCRIPT] + list(args) + ["--json"],
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
                 proc.stderr.strip() or "fallo el procesador de audio",
                 "exit=%s" % proc.returncode)


def mejorar(entrada, salida=None, preset="voz_limpia"):
    args = ["mejorar", "--input", entrada, "--preset", preset]
    if salida:
        args += ["--salida", salida]
    return _run(args)


def mezclar(entrada, musica, salida=None, preset="voz_limpia", volumen=0.12):
    args = ["mezclar", "--input", entrada, "--musica", musica,
            "--preset", preset, "--volumen", str(volumen)]
    if salida:
        args += ["--salida", salida]
    return _run(args)
