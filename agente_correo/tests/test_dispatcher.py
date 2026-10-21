from __future__ import annotations

import dataclasses
import email
from email import policy
from pathlib import Path

from agente_correo import dispatcher
from agente_correo.orquestador import ResultadoTarea
from agente_correo.parser import Mensaje


def _mensaje() -> Mensaje:
    return Mensaje(
        gmail_id="g-1",
        thread_id="hilo-1",
        message_id="<msg-1@example.com>",
        clave_idempotencia="<msg-1@example.com>",
        from_raw="Arturo <arturo@example.com>",
        from_email="arturo@example.com",
        from_nombre="Arturo",
        subject="Estado",
        body="estado del sistema",
        references=("<previo@example.com>",),
        headers={},
        adjuntos=(),
        label_ids=("UNREAD", "INBOX"),
    )


def _resultado(**cambios) -> ResultadoTarea:
    base = dict(
        ok=True,
        herramienta="sistema",
        comando=("python", "script.py", "--info"),
        codigo=0,
        stdout='{"mensaje": "ok"}',
        stderr="",
        datos={"mensaje": "ok", "ram_porcentaje": 42},
        artefactos=(),
        duracion=1.2,
    )
    base.update(cambios)
    return ResultadoTarea(**base)


def test_asunto_no_duplica_re():
    assert dispatcher.construir_asunto("Hola") == "Re: Hola"
    assert dispatcher.construir_asunto("Re: Hola") == "Re: Hola"


def test_mime_en_hilo_y_adjunto(cfg, tmp_path):
    adjunto = tmp_path / "reporte.xlsx"
    adjunto.write_bytes(b"datos")
    raw = dispatcher.construir_mime(
        cfg,
        _mensaje(),
        "Re: Estado",
        "cuerpo",
        (adjunto,),
    )
    correo = email.message_from_bytes(raw, policy=policy.default)
    assert correo["In-Reply-To"] == "<msg-1@example.com>"
    assert "<previo@example.com>" in correo["References"]
    assert correo["Auto-Submitted"] == "auto-replied"
    assert correo["X-Agente-Correo"] == "v1"
    adjuntos = list(correo.iter_attachments())
    assert len(adjuntos) == 1
    assert adjuntos[0].get_filename() == "reporte.xlsx"


def test_planificar_adjuntos_por_tamano(cfg, tmp_path):
    archivo = tmp_path / "grande.bin"
    archivo.write_bytes(b"x" * 11)
    pequeno = dataclasses.replace(cfg, max_adjuntos_bytes=10)
    modo, archivos = dispatcher.planificar_adjuntos((archivo,), pequeno)
    assert modo == "drive"
    assert archivos == (archivo,)
    modo, archivos = dispatcher.planificar_adjuntos((archivo,), cfg)
    assert modo == "adjuntar"


def test_dry_run_escribe_eml_sin_enviar(cfg):
    respuesta = dispatcher.responder(
        cfg, _mensaje(), _resultado(), dry_run=True
    )
    assert respuesta["enviado"] is False
    ruta = Path(respuesta["ruta"])
    assert ruta.is_file()
    correo = email.message_from_bytes(ruta.read_bytes(), policy=policy.default)
    cuerpo = correo.get_body(preferencelist=("plain",)).get_content()
    assert "Resultado: OK" in cuerpo
    assert "DRY-RUN" in cuerpo


def test_error_se_redacta_en_el_cuerpo(cfg):
    resultado = _resultado(
        ok=False,
        codigo=1,
        datos=None,
        error="access_token=SUPERSECRETO",
    )
    respuesta = dispatcher.responder(
        cfg, _mensaje(), resultado, dry_run=True
    )
    correo = email.message_from_bytes(
        Path(respuesta["ruta"]).read_bytes(), policy=policy.default
    )
    cuerpo = correo.get_body(preferencelist=("plain",)).get_content()
    assert "SUPERSECRETO" not in cuerpo
    assert "Error:" in cuerpo
