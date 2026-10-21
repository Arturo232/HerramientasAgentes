from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from agente_correo import listener
from agente_correo.db import BaseDatos
from agente_correo.orquestador import (
    Enrutamiento,
    ErrorEnrutamiento,
    ResultadoTarea,
    PuenteSelector,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _payload(nombre: str) -> dict:
    return json.loads((FIXTURES / nombre).read_text(encoding="utf-8"))


def _resultado() -> ResultadoTarea:
    return ResultadoTarea(
        ok=True,
        herramienta="sistema",
        comando=("python", "script.py", "--info"),
        codigo=0,
        stdout='{"mensaje": "ok"}',
        stderr="",
        datos={"mensaje": "ok"},
        artefactos=(),
        duracion=0.1,
    )


def test_denegado_no_ejecuta_ni_responde(cfg, tmp_path, monkeypatch):
    db = BaseDatos(tmp_path / "test.db")
    puente = PuenteSelector(cfg)
    llamadas = []
    monkeypatch.setattr(
        listener.dispatcher, "responder", lambda *a, **k: llamadas.append(a)
    )
    desenlace = listener.procesar_payload(
        _payload("correo_denegado.json"),
        cfg,
        db,
        puente,
        dry_run=False,
        servicio=None,
        etiquetas=None,
    )
    assert desenlace == "denegado"
    assert llamadas == []
    fila = db.obtener("<denegado-001@example.com>")
    assert fila["estado"] == "denegado"
    assert "no autorizado" in fila["detalle"]
    db.cerrar()


def test_dedupe_no_reprocesa(cfg, tmp_path, monkeypatch):
    db = BaseDatos(tmp_path / "test.db")
    puente = PuenteSelector(cfg)
    monkeypatch.setattr(
        puente,
        "ejecutar",
        lambda intencion: _resultado(),
    )
    llamadas = []
    monkeypatch.setattr(
        listener.dispatcher,
        "responder",
        lambda *a, **k: llamadas.append(a) or {"enviado": False, "ruta": "/tmp/x.eml"},
    )
    payload = _payload("correo_autorizado.json")
    primero = listener.procesar_payload(
        payload, cfg, db, puente, dry_run=False, servicio=None, etiquetas=None
    )
    segundo = listener.procesar_payload(
        payload, cfg, db, puente, dry_run=False, servicio=None, etiquetas=None
    )
    assert primero == "ok"
    assert segundo == "duplicado"
    assert len(llamadas) == 1
    fila = db.obtener("<autorizado-001@example.com>")
    assert fila["ejecutado"] == 1
    assert db.contar_ejecutadas_ultima_hora() == 1
    db.cerrar()


def test_dry_run_enruta_sin_ejecutar(cfg, tmp_path, monkeypatch):
    db = BaseDatos(tmp_path / "test.db")
    puente = PuenteSelector(cfg)
    monkeypatch.setattr(
        puente,
        "enrutar",
        lambda intencion: Enrutamiento(
            "sistema", "scripts/sistema/mantenimiento_pc.py", ("--info",)
        ),
    )
    envios = []
    monkeypatch.setattr(
        listener.dispatcher,
        "responder",
        lambda *a, **k: envios.append(a) or {"enviado": False, "ruta": "/tmp/x.eml"},
    )
    desenlace = listener.procesar_payload(
        _payload("correo_autorizado.json"),
        cfg,
        db,
        puente,
        dry_run=True,
        servicio=None,
        etiquetas=None,
    )
    assert desenlace == "dry-run"
    assert len(envios) == 1
    fila = db.obtener("<autorizado-001@example.com>")
    assert fila["estado"] == "dry-run"
    assert fila["ejecutado"] == 0
    db.cerrar()


def test_pausa_y_reanudar(cfg, tmp_path, monkeypatch):
    db = BaseDatos(tmp_path / "test.db")
    puente = PuenteSelector(cfg)
    monkeypatch.setattr(
        listener.dispatcher,
        "responder_texto",
        lambda *a, **k: {"enviado": False, "ruta": "/tmp/x.eml"},
    )
    listener.procesar_payload(
        _payload("correo_control.json"),
        cfg,
        db,
        puente,
        dry_run=False,
        servicio=None,
        etiquetas=None,
    )
    assert db.esta_pausado()[0] is True
    db.reanudar()
    assert db.esta_pausado()[0] is False
    db.cerrar()


def test_limite_hora_no_ejecuta(cfg, tmp_path, monkeypatch):
    db = BaseDatos(tmp_path / "test.db")
    db.reservar("<viejo@example.com>", "viejo")
    db.finalizar("<viejo@example.com>", "ok", ejecutado=True)
    puente = PuenteSelector(cfg)
    ejecutado = []
    monkeypatch.setattr(
        puente, "ejecutar", lambda intencion: ejecutado.append(intencion)
    )
    monkeypatch.setattr(
        listener.dispatcher,
        "responder_texto",
        lambda *a, **k: {"enviado": False, "ruta": "/tmp/x.eml"},
    )
    cfg_limite = dataclasses.replace(cfg, max_tareas_hora=1)
    desenlace = listener.procesar_payload(
        _payload("correo_autorizado.json"),
        cfg_limite,
        db,
        puente,
        dry_run=False,
        servicio=None,
        etiquetas=None,
    )
    assert desenlace == "limite"
    assert ejecutado == []
    db.cerrar()


def test_comando_no_entendido_responde_ayuda(cfg, tmp_path, monkeypatch):
    db = BaseDatos(tmp_path / "test.db")
    puente = PuenteSelector(cfg)
    monkeypatch.setattr(
        puente,
        "ejecutar",
        lambda _intencion: (_ for _ in ()).throw(
            ErrorEnrutamiento(
                "No entendí el comando. Envía una orden válida."
            )
        ),
    )
    capturado = {}

    def _responder_texto(cfg_, mensaje, cuerpo, **kwargs):
        capturado["cuerpo"] = cuerpo
        return {"enviado": False, "ruta": "/tmp/ayuda.eml"}

    monkeypatch.setattr(listener.dispatcher, "responder_texto", _responder_texto)
    desenlace = listener.procesar_payload(
        _payload("correo_autorizado.json"),
        cfg,
        db,
        puente,
        dry_run=False,
        servicio=None,
        etiquetas=None,
    )
    assert desenlace == "ayuda"
    assert "No entendí el comando" in capturado["cuerpo"]
    assert "estado del sistema" in capturado["cuerpo"]
    assert "REANUDAR" in capturado["cuerpo"]
    fila = db.obtener("<autorizado-001@example.com>")
    assert fila["estado"] == "ayuda"
    db.cerrar()
