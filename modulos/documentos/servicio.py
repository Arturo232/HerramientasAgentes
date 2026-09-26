# -*- coding: utf-8 -*-
"""Fachada de servicios del módulo de documentos (PDF).

Devuelve siempre el contrato común (``nucleo.contrato.Resultado``).
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.join(_HERE, "scripts")
_RAIZ = os.path.dirname(os.path.dirname(_HERE))
for _p in (_RAIZ, _SCRIPTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from nucleo.contrato import exito, fallo  # noqa: E402
from nucleo.errores import AgenteError  # noqa: E402

MODULO = "documentos"


def _capturar(fn, *args, **kwargs):
    try:
        return exito(datos=fn(*args, **kwargs))
    except AgenteError as e:
        return e.a_resultado()
    except Exception as e:  # noqa: BLE001
        return fallo((MODULO, "interno"), str(e), repr(e))


def leer(pdf, salida=None, **kw):
    import leer_pdf

    return _capturar(leer_pdf.leer, pdf, salida, **kw)


def buscar(pdf, consulta, k=5, salida_dir=None):
    import buscar_pdf

    return _capturar(buscar_pdf.buscar, pdf, consulta, k, salida_dir)


def resumir(pdf, max_oraciones=12, salida_dir=None):
    import resumir_pdf

    return _capturar(resumir_pdf.resumir, pdf, max_oraciones, salida_dir)
