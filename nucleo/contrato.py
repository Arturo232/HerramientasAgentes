# -*- coding: utf-8 -*-
"""Contrato único de resultado del sistema.

Todo módulo devuelve un ``Resultado`` con la misma forma, en éxito y en fallo::

    {"ok": true, "datos": {...}, "meta": {...},
     "artefactos": [...], "error": null}

    {"ok": false, "datos": null, "meta": {}, "artefactos": [],
     "error": {"codigo": "agente:pdf:noExiste", "mensaje": "...", "causa": null}}

Así cualquier pieza puede consumir a cualquier otra (composición tipo Unix).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Artefacto:
    """Un producto generado por un módulo (archivo, imagen, reporte...)."""

    tipo: str
    ruta: str
    hash: Optional[str] = None

    def a_dict(self):
        d = {"tipo": self.tipo, "ruta": self.ruta}
        if self.hash:
            d["hash"] = self.hash
        return d


@dataclass
class Resultado:
    """Resultado estándar de cualquier operación."""

    ok: bool = True
    datos: Any = None
    meta: dict = field(default_factory=dict)
    artefactos: list = field(default_factory=list)
    error: Optional[dict] = None

    def a_dict(self):
        return {
            "ok": self.ok,
            "datos": self.datos,
            "meta": self.meta,
            "artefactos": [
                a.a_dict() if isinstance(a, Artefacto) else a for a in self.artefactos
            ],
            "error": self.error,
        }

    def a_json(self, indent=None):
        return json.dumps(self.a_dict(), ensure_ascii=False, indent=indent, default=str)

    def a_json_ascii(self, indent=None):
        return json.dumps(self.a_dict(), ensure_ascii=True, indent=indent, default=str)


def exito(datos=None, meta=None, artefactos=None):
    """Construye un resultado correcto."""
    return Resultado(ok=True, datos=datos, meta=meta or {}, artefactos=artefactos or [])


def fallo(codigo, mensaje, causa=None):
    """Construye un resultado de error.

    ``codigo`` puede ser el identificador completo ``agente:<modulo>:<codigo>``
    o una tupla ``(modulo, codigo)``.
    """
    if isinstance(codigo, (tuple, list)) and len(codigo) == 2:
        codigo = "agente:%s:%s" % (codigo[0], codigo[1])
    return Resultado(
        ok=False, error={"codigo": codigo, "mensaje": mensaje, "causa": causa}
    )
