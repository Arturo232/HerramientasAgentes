"""CLI unificado de HerramientasAgentes (el "eje" del sistema).

Un solo punto de entrada para todos los módulos. El enrutado se lee de
``capacidades.json`` (fuente de verdad única), no de una tabla hardcodeada.

    python agente.py                      # lista los comandos
    python agente.py lista [--json]       # catálogo (humano o máquina)
    python agente.py ayuda pdf [--json]   # ayuda / esquema del comando
    python agente.py pdf --input doc.pdf [--json]
    python agente.py navegar --input URL --json
    python agente.py sync

Cada comando delega en el script del módulo correspondiente pasándole las
banderas comunes (``--json``, ``--quiet``, ``--yes``, ``--dry-run``).
"""

import json
import os
import subprocess
import sys

RAIZ = os.path.dirname(os.path.abspath(__file__))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from nucleo import config  # noqa: E402


def _lista(argv):
    json_mode = "--json" in argv
    cmds = config.comandos()
    if json_mode:
        print(json.dumps({"comandos": cmds}, ensure_ascii=False, indent=2))
        return 0
    print("Comandos disponibles (agente <comando> [opciones]):\n")
    for c in sorted(cmds, key=lambda x: x["id"]):
        print("  %-18s %s" % (c["id"], c.get("descripcion", "")))
    print("\n  %-18s %s" % ("lista", "Lista este catálogo"))
    print("  %-18s %s" % ("ayuda <cmd>", "Muestra ayuda/esquema de un comando"))
    print("  %-18s %s" % ("run <flujo.json>", "Ejecuta un pipeline declarativo"))
    print("  %-18s %s" % ("repl", "Abre la consola interactiva (agente>)"))
    print("\nEjemplo: python agente.py pdf --input documento.pdf")
    return 0


def _ayuda(argv):
    if not argv:
        print("Uso: agente ayuda <comando> [--json]", file=sys.stderr)
        return 2
    cmd = argv[0]
    json_mode = "--json" in argv[1:]
    entrada = config.buscar(cmd)
    if not entrada:
        print("Comando desconocido: %s. Usa 'agente lista'." % cmd, file=sys.stderr)
        return 2
    if json_mode:
        print(json.dumps(entrada, ensure_ascii=False, indent=2))
        return 0
    script = os.path.join(RAIZ, entrada["script"])
    print("%s — %s\n" % (cmd, entrada.get("descripcion", "")))
    print("Módulo:   %s" % entrada.get("modulo", ""))
    print("Script:   %s" % entrada.get("script", ""))
    if entrada.get("produce"):
        print("Produce:  %s" % ", ".join(p.get("tipo", "") for p in entrada["produce"]))
    if entrada.get("delega_en"):
        print("Delega en: %s" % ", ".join(entrada["delega_en"]))
    print("\n-- Ayuda del script --")
    return subprocess.call([sys.executable, script, "--help"])


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        return _lista([])
    primero = argv[0]
    if primero in ("lista", "list", "--lista"):
        return _lista(argv[1:])
    if primero in ("ayuda", "help", "--help", "-h"):
        return _ayuda(argv[1:])
    if primero in ("repl", "consola", "shell"):
        from interfaces import repl
        return repl.main(argv[1:])
    if primero == "run":
        from interfaces import flujo
        return flujo.main(argv[1:])

    entrada = config.buscar(primero)
    if not entrada:
        print("Comando desconocido: %s. Usa 'agente lista'." % primero, file=sys.stderr)
        return 2
    script = os.path.join(RAIZ, entrada["script"])
    if not os.path.exists(script):
        print("ERROR: no existe %s" % script, file=sys.stderr)
        return 1
    return subprocess.call([sys.executable, script] + argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
