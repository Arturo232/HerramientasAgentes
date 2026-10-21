from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from agente_correo.config import Config  # noqa: E402


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("GMAIL_USER", "agente@example.com")
    monkeypatch.setenv("AUTORIZADO_FROM", "arturo@example.com")
    monkeypatch.setenv("PYTHON_BIN", sys.executable)
    monkeypatch.setenv("REPO_DIR", str(RAIZ))
    monkeypatch.setenv("DIR_DATOS", str(tmp_path / "data"))
    monkeypatch.setenv("DIR_SALIDA", str(tmp_path / "out"))
    monkeypatch.setenv("DIR_ENTRADA", str(tmp_path / "entrada"))
    monkeypatch.setenv("HERRAMIENTAS_PERMITIDAS", "sistema,redes,datos")
    monkeypatch.setenv("MAX_TAREAS_HORA", "6")
    monkeypatch.setenv("MAX_ADJUNTOS_MB", "20")
    monkeypatch.setenv("TIMEOUT_TAREA", "30")
    monkeypatch.setenv("POLL_SEGUNDOS", "50")
    config = Config.cargar()
    # Aísla los tests de un .env local con listas de destinatarios propias.
    monkeypatch.delenv("DESTINATARIOS_PERMITIDOS", raising=False)
    config.preparar_directorios()
    return config
