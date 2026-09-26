# -*- coding: utf-8 -*-
"""Fachada de servicios del módulo de artes y diseño.

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

MODULO = "artes_diseno"


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
                 proc.stderr.strip() or "fallo el script de diseño",
                 "exit=%s" % proc.returncode)


def renderizar_html(html, salida, formato="A4"):
    return _run("renderizador_playwright.py",
                ["--input", html, "--salida", salida, "--formato", formato])


def inyectar_pptx(plantilla, datos, salida, no_pdf=False):
    args = ["--plantilla", plantilla, "--input", datos, "--salida", salida]
    if no_pdf:
        args.append("--no-pdf")
    return _run("motor_pptx_visual.py", args)
