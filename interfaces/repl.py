# -*- coding: utf-8 -*-
"""Consola interactiva del sistema (el prompt ``agente>``).

Reutiliza el mismo enrutado del CLI: cada línea se resuelve contra
``capacidades.json``. No calcula nada; solo despacha.

    agente> lista
    agente> ayuda pdf
    agente> pdf tarea.pdf
    agente> navegar --input https://example.com
    agente> salir
"""
from __future__ import annotations

import os
import shlex
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

import agente  # noqa: E402

AYUDA = """Consola de HerramientasAgentes.

  <comando> [opciones]   ejecuta un módulo (ver 'lista')
  lista                  catálogo de comandos
  ayuda <comando>        ayuda de un comando
  salir | exit | q       termina

Ejemplo:  pdf --input tarea.pdf --salida tmp
"""


def main(argv=None):
    print("agente> consola interactiva. Escribe 'lista', 'ayuda <cmd>' o 'salir'.\n")
    while True:
        try:
            linea = input("agente> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not linea:
            continue
        if linea in ("salir", "exit", "quit", "q"):
            break
        if linea in ("ayuda", "help", "?"):
            print(AYUDA)
            continue
        try:
            partes = shlex.split(linea)
        except ValueError as e:
            print("error: %s" % e, file=sys.stderr)
            continue
        try:
            agente.main(partes)
        except SystemExit:
            pass
        except Exception as e:  # noqa: BLE001
            print("error: %s" % e, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
