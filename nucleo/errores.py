# -*- coding: utf-8 -*-
"""Errores tipados del sistema.

Formato canónico: ``agente:<modulo>:<codigo>``.
"""
from __future__ import annotations


class AgenteError(Exception):
    """Error de dominio con identificador estable."""

    def __init__(self, modulo, codigo, mensaje, causa=None):
        super().__init__(mensaje)
        self.modulo = modulo
        self.codigo = codigo
        self.mensaje = mensaje
        self.causa = causa

    @property
    def id(self):
        return "agente:%s:%s" % (self.modulo, self.codigo)

    def a_dict(self):
        return {"codigo": self.id, "mensaje": self.mensaje, "causa": self.causa}

    def a_resultado(self):
        from .contrato import Resultado

        return Resultado(ok=False, error=self.a_dict())
