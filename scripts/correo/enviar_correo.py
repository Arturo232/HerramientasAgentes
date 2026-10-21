#!/usr/bin/env python3
"""Puente CLI para ``agente.py`` y el servidor MCP.

Envía correos reutilizando ``agente_correo.enviar``. Acepta las mismas
banderas que el módulo y descarta las banderas comunes que añade el MCP
(``--json``, ``--quiet``, ``--yes``).
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from agente_correo.enviar import main as _enviar_main  # noqa: E402

_IGNORAR = {"--json", "--quiet", "--yes"}


def main(argv: list[str] | None = None) -> int:
    argumentos = list(sys.argv[1:] if argv is None else argv)
    argumentos = [arg for arg in argumentos if arg not in _IGNORAR]
    return _enviar_main(argumentos)


if __name__ == "__main__":
    raise SystemExit(main())
