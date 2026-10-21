"""Tests del puente CLI de envío, sin red ni credenciales reales."""

from __future__ import annotations

import base64
import dataclasses
import email
import json
from email import policy
from pathlib import Path

import pytest

from agente_correo import gmail_client
from agente_correo.enviar import (
    CARPETA_DRY_RUN,
    ErrorEnvio,
    enviar_correo,
    main,
)


class _Req:
    def __init__(self, datos):
        self.datos = datos

    def execute(self):
        return self.datos


class _Mensajes:
    def __init__(self, payload):
        self.payload = payload
        self.enviados = []

    def get(self, **kwargs):
        return _Req(self.payload)

    def send(self, **kwargs):
        raise AssertionError("los tests deben simular enviar_mime")


class _Usuarios:
    def __init__(self, payload):
        self._mensajes = _Mensajes(payload)

    def messages(self):
        return self._mensajes


class _Servicio:
    """Servicio Gmail falso: solo implementa messages().get()."""

    def __init__(self, payload):
        self._usuarios = _Usuarios(payload)

    def users(self):
        return self._usuarios


class _Captura:
    """Sustituto de gmail_client.enviar_mime."""

    def __init__(self):
        self.llamadas: list[tuple[bytes, str | None]] = []

    def __call__(self, servicio, raw, thread_id=None):
        self.llamadas.append((raw, thread_id))
        return {
            "id": f"nuevo-{len(self.llamadas)}",
            "threadId": thread_id or "hilo-nuevo",
        }


def _payload_original(
    *,
    subject: str = "Estado",
    message_id: str | None = "<msg-1@example.com>",
    references: str = "<previo@example.com>",
) -> dict:
    cabeceras = [
        {"name": "From", "value": "Arturo <arturo@example.com>"},
        {"name": "To", "value": "agente@example.com"},
        {"name": "Subject", "value": subject},
        {"name": "References", "value": references},
    ]
    if message_id is not None:
        cabeceras.append({"name": "Message-ID", "value": message_id})
    cuerpo = base64.urlsafe_b64encode(b"cuerpo original").decode("ascii")
    return {
        "id": "g-1",
        "threadId": "hilo-1",
        "labelIds": ["INBOX"],
        "payload": {
            "mimeType": "text/plain",
            "headers": cabeceras,
            "body": {"data": cuerpo},
        },
    }


def _capturar(monkeypatch) -> _Captura:
    captura = _Captura()
    monkeypatch.setattr(gmail_client, "enviar_mime", captura)
    return captura


def _correo(raw: bytes):
    return email.message_from_bytes(raw, policy=policy.default)


def test_envio_permitido_con_adjunto(cfg, monkeypatch):
    adjunto = cfg.dir_salida / "reporte.txt"
    adjunto.write_text("datos", encoding="utf-8")
    captura = _capturar(monkeypatch)

    resultado = enviar_correo(
        cfg,
        para="Arturo <arturo@example.com>",
        asunto="Hola",
        cuerpo="Mensaje de prueba",
        adjuntos=(adjunto,),
    )

    assert resultado["ok"] is True
    assert resultado["mensaje_id"] == "nuevo-1"
    assert resultado["dry_run"] is False
    assert resultado["destinatarios"] == ["arturo@example.com"]
    assert resultado["adjuntos"] == ["reporte.txt"]
    assert len(captura.llamadas) == 1

    raw, hilo = captura.llamadas[0]
    assert hilo is None
    correo = _correo(raw)
    assert correo["To"] == "arturo@example.com"
    assert correo["Subject"] == "Hola"
    assert correo["In-Reply-To"] is None
    assert correo["Auto-Submitted"] is None
    assert correo["X-Agente-Correo"] == "v1"
    adjuntos = list(correo.iter_attachments())
    assert len(adjuntos) == 1
    assert adjuntos[0].get_filename() == "reporte.txt"


def test_destinatario_no_permitido_falla_sin_confirmar(cfg, monkeypatch):
    captura = _capturar(monkeypatch)

    with pytest.raises(ErrorEnvio, match="DESTINATARIOS_PERMITIDOS"):
        enviar_correo(
            cfg,
            para="otro@example.com",
            asunto="Hola",
            cuerpo="Mensaje",
        )

    assert captura.llamadas == []


def test_confirmar_permite_destinatario_externo(cfg, monkeypatch):
    captura = _capturar(monkeypatch)

    resultado = enviar_correo(
        cfg,
        para="otro@example.com",
        asunto="Hola",
        cuerpo="Mensaje",
        confirmar=True,
    )

    assert resultado["ok"] is True
    assert resultado["destinatarios"] == ["otro@example.com"]
    assert len(captura.llamadas) == 1


def test_lista_permitida_se_lee_del_entorno(cfg, monkeypatch):
    monkeypatch.setenv(
        "DESTINATARIOS_PERMITIDOS",
        "otro@example.com; tercero@example.com",
    )
    captura = _capturar(monkeypatch)

    resultado = enviar_correo(
        cfg,
        para="Otro <OTRO@example.com>",
        asunto="Hola",
        cuerpo="Mensaje",
    )
    assert resultado["ok"] is True
    assert resultado["destinatarios"] == ["otro@example.com"]

    with pytest.raises(ErrorEnvio, match="DESTINATARIOS_PERMITIDOS"):
        enviar_correo(
            cfg,
            para="arturo@example.com",
            asunto="Hola",
            cuerpo="Mensaje",
        )


def test_dry_run_escribe_eml_sin_enviar(cfg, monkeypatch):
    def _prohibido(*args, **kwargs):
        raise AssertionError("--dry-run no debe llamar a enviar_mime")

    monkeypatch.setattr(gmail_client, "enviar_mime", _prohibido)

    resultado = enviar_correo(
        cfg,
        para="arturo@example.com",
        asunto="Hola",
        cuerpo="Mensaje",
        dry_run=True,
    )

    assert resultado["ok"] is True
    assert resultado["dry_run"] is True
    assert resultado["mensaje_id"] is None
    ruta = Path(resultado["ruta_eml"])
    assert ruta.is_file()
    assert ruta.parent == cfg.dir_salida / CARPETA_DRY_RUN
    correo = _correo(ruta.read_bytes())
    assert correo["To"] == "arturo@example.com"
    assert correo["Subject"] == "Hola"


def test_respuesta_conserva_hilo(cfg, monkeypatch):
    servicio = _Servicio(_payload_original())
    captura = _capturar(monkeypatch)

    resultado = enviar_correo(
        cfg,
        para="arturo@example.com",
        responder_a="g-1",
        cuerpo="Recibido",
        servicio=servicio,
    )

    assert resultado["ok"] is True
    assert resultado["hilo"] == "hilo-1"
    raw, hilo = captura.llamadas[0]
    assert hilo == "hilo-1"
    correo = _correo(raw)
    assert correo["In-Reply-To"] == "<msg-1@example.com>"
    assert "<previo@example.com>" in correo["References"]
    assert "<msg-1@example.com>" in correo["References"]
    assert correo["Subject"] == "Re: Estado"


def test_respuesta_prefija_re_sin_duplicarlo(cfg, monkeypatch):
    servicio = _Servicio(_payload_original(subject="Re: Estado"))
    captura = _capturar(monkeypatch)

    enviar_correo(
        cfg,
        para="arturo@example.com",
        asunto="Estado",
        responder_a="g-1",
        cuerpo="Recibido",
        servicio=servicio,
    )

    correo = _correo(captura.llamadas[0][0])
    assert correo["Subject"] == "Re: Estado"


def test_respuesta_sin_message_id_usa_solo_thread_id(cfg, monkeypatch):
    servicio = _Servicio(_payload_original(message_id=None, references=""))
    captura = _capturar(monkeypatch)

    resultado = enviar_correo(
        cfg,
        para="arturo@example.com",
        responder_a="g-1",
        cuerpo="Recibido",
        servicio=servicio,
    )

    assert resultado["hilo"] == "hilo-1"
    raw, hilo = captura.llamadas[0]
    assert hilo == "hilo-1"
    correo = _correo(raw)
    assert correo["In-Reply-To"] is None
    assert correo["References"] is None


def test_adjunto_demasiado_grande_falla(cfg):
    archivo = cfg.dir_salida / "grande.bin"
    archivo.write_bytes(b"x" * 11)

    con_limite_total = dataclasses.replace(cfg, max_adjuntos_bytes=10)
    with pytest.raises(ErrorEnvio, match="MAX_ADJUNTOS_MB"):
        enviar_correo(
            con_limite_total,
            para="arturo@example.com",
            asunto="Hola",
            cuerpo="Mensaje",
            adjuntos=(archivo,),
        )

    con_limite_individual = dataclasses.replace(cfg, max_artefacto_bytes=10)
    with pytest.raises(ErrorEnvio, match="MAX_ARTEFACTO_MB"):
        enviar_correo(
            con_limite_individual,
            para="arturo@example.com",
            asunto="Hola",
            cuerpo="Mensaje",
            adjuntos=(archivo,),
        )


def test_adjunto_inexistente_o_fuera_de_rutas_falla(cfg, tmp_path, monkeypatch):
    with pytest.raises(ErrorEnvio, match="no existe"):
        enviar_correo(
            cfg,
            para="arturo@example.com",
            asunto="Hola",
            cuerpo="Mensaje",
            adjuntos=(cfg.dir_salida / "no-existe.txt",),
        )

    externo = tmp_path / "externo.txt"
    externo.write_text("dato", encoding="utf-8")
    with pytest.raises(ErrorEnvio, match="fuera de entrada"):
        enviar_correo(
            cfg,
            para="arturo@example.com",
            asunto="Hola",
            cuerpo="Mensaje",
            adjuntos=(externo,),
        )

    captura = _capturar(monkeypatch)
    resultado = enviar_correo(
        cfg,
        para="arturo@example.com",
        asunto="Hola",
        cuerpo="Mensaje",
        adjuntos=(externo,),
        permitir_rutas_externas=True,
    )
    assert resultado["ok"] is True
    assert len(captura.llamadas) == 1


def test_cli_dry_run_emite_json(cfg, capsys):
    codigo = main(
        [
            "--para",
            "arturo@example.com",
            "--asunto",
            "Hola",
            "--cuerpo-archivo",
            str(_cuerpo_en_entrada(cfg)),
            "--dry-run",
        ]
    )

    assert codigo == 0
    salida = json.loads(capsys.readouterr().out)
    assert salida["ok"] is True
    assert salida["dry_run"] is True
    assert Path(salida["ruta_eml"]).is_file()


def test_cli_falla_con_json_y_codigo_uno(cfg, capsys):
    codigo = main(
        [
            "--para",
            "otro@example.com",
            "--asunto",
            "Hola",
            "--cuerpo",
            "Mensaje",
            "--dry-run",
        ]
    )

    assert codigo == 1
    salida = json.loads(capsys.readouterr().out)
    assert salida["ok"] is False
    assert salida["dry_run"] is True
    assert "DESTINATARIOS_PERMITIDOS" in salida["error"]


def _cuerpo_en_entrada(cfg) -> Path:
    ruta = cfg.dir_entrada / "cuerpo.txt"
    ruta.write_text("Cuerpo desde archivo", encoding="utf-8")
    return ruta
