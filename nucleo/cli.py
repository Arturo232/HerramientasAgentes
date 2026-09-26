# -*- coding: utf-8 -*-
"""Banderas estándar y salida común para todos los scripts.

Contrato de CLI (ver ``docs/ARQUITECTURA_OBJETIVO.md``)::

    script [--json] [--quiet] [--yes] [--dry-run] [--help]

Reglas:
- Datos -> ``stdout``; logs/errores -> ``stderr``.
- Exit codes: ``0`` ok, ``1`` error de operación, ``2`` mal uso (argparse).
- Nunca pide input salvo bandera explícita.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from .contrato import Resultado, fallo
from .errores import AgenteError


def agregar_flags_comunes(ap):
    """Agrega las banderas comunes a un ``ArgumentParser`` existente."""
    ap.add_argument("--json", action="store_true", help="Salida máquina (contrato JSON)")
    ap.add_argument("--quiet", action="store_true", help="Silenciar logs")
    ap.add_argument("--yes", action="store_true", help="Auto-confirmar acciones destructivas")
    ap.add_argument("--dry-run", action="store_true", help="Previsualizar sin ejecutar")
    return ap


def asegurar_utf8():
    """Fuerza UTF-8 en stdout/stderr (evita UnicodeEncodeError en Windows)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def emitir(resultado, json_mode=False, quiet=False):
    """Imprime el resultado según el modo (máquina o humano)."""
    if json_mode:
        try:
            print(resultado.a_json())
        except UnicodeEncodeError:
            print(resultado.a_json_ascii())
        return
    if resultado.ok:
        _humano(resultado, quiet=quiet)
    else:
        err = resultado.error or {}
        print(
            "[%s] %s" % (err.get("codigo", "agente:error"), err.get("mensaje", "")),
            file=sys.stderr,
        )


def _humano(resultado, quiet=False):
    d = resultado.datos
    if d is not None:
        if isinstance(d, (dict, list)):
            print(json.dumps(d, ensure_ascii=False, indent=2, default=str))
        else:
            print(d)
    if not quiet:
        for a in resultado.artefactos:
            a = a.a_dict() if hasattr(a, "a_dict") else a
            print("-> %s: %s" % (a.get("tipo"), a.get("ruta")), file=sys.stderr)


def correr(modulo, construir, funcion, argv=None, prog=None, descripcion=None):
    """Ejecuta ``funcion(ns) -> Resultado`` con manejo estándar de errores/salida.

    ``construir`` recibe el ``ArgumentParser`` y agrega los argumentos propios.
    """
    ap = argparse.ArgumentParser(prog=prog or modulo, description=descripcion)
    construir(ap)
    agregar_flags_comunes(ap)
    asegurar_utf8()
    ns = ap.parse_args(argv)
    try:
        res = funcion(ns)
        if not isinstance(res, Resultado):
            res = Resultado(ok=True, datos=res)
    except AgenteError as e:
        res = e.a_resultado()
    except Exception as e:  # noqa: BLE001
        res = fallo((modulo, "interno"), str(e), repr(e))
    emitir(res, json_mode=getattr(ns, "json", False), quiet=getattr(ns, "quiet", False))
    return 0 if res.ok else 1


def requerir_archivo(ruta, modulo, codigo="noExiste"):
    """Lanza ``AgenteError`` si la ruta no existe."""
    if not ruta or not os.path.exists(ruta):
        raise AgenteError(modulo, codigo, "No existe el archivo: %s" % ruta)
    return ruta


def leer_stdin():
    """Lee todo ``stdin`` (para composición con ``|``)."""
    return sys.stdin.read()
