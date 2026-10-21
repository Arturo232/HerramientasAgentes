from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from agente_correo.parser import (
    decodificar_cabecera,
    detectar_control,
    es_auto_respuesta,
    limpiar_cuerpo,
    parsear_mensaje,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _b64(texto: str) -> str:
    return base64.urlsafe_b64encode(texto.encode()).decode().rstrip("=")


def _payload(cuerpo: str, *, html: bool = False, from_: str = "arturo@example.com"):
    parte = {
        "partId": "1",
        "mimeType": "text/html" if html else "text/plain",
        "filename": "",
        "headers": [
            {
                "name": "Content-Type",
                "value": ("text/html" if html else "text/plain") + "; charset=UTF-8",
            }
        ],
        "body": {"size": len(cuerpo), "data": _b64(cuerpo)},
    }
    return {
        "id": "msg-1",
        "threadId": "hilo-1",
        "labelIds": ["UNREAD", "INBOX"],
        "payload": {
            "mimeType": "text/html" if html else "text/plain",
            "headers": [
                {"name": "From", "value": from_},
                {"name": "Subject", "value": "Prueba"},
                {"name": "Message-ID", "value": "<msg-1@example.com>"},
                {"name": "References", "value": "<previo@example.com>"},
            ],
            "body": {"size": 0},
            "parts": [parte],
        },
    }


def test_parsea_fixture_realista():
    datos = json.loads((FIXTURES / "correo_autorizado.json").read_text(encoding="utf-8"))
    mensaje = parsear_mensaje(datos)
    assert mensaje.from_email == "arturo@example.com"
    assert mensaje.from_nombre == "Arturo"
    assert mensaje.subject == "Estado del sistema"
    assert mensaje.body == "estado del sistema"
    assert mensaje.message_id == "<autorizado-001@example.com>"
    assert mensaje.thread_id == "hilo-autorizado-001"
    assert mensaje.references == ("<hilo-previo@example.com>",)


def test_parsea_html_si_no_hay_texto_plano():
    mensaje = parsear_mensaje(
        _payload("<p>Hola</p><p>estado del sistema</p>", html=True)
    )
    assert "Hola" in mensaje.body
    assert "estado del sistema" in mensaje.body


def test_quita_cita_y_firma():
    cuerpo = (
        "estado del sistema\n\n"
        "El lun, 20 oct 2026, alguien escribió:\n"
        "> texto viejo\n"
        "-- \n"
        "Firma"
    )
    mensaje = parsear_mensaje(_payload(cuerpo))
    assert mensaje.body == "estado del sistema"


def test_decodifica_asunto_rfc2047():
    assert decodificar_cabecera("=?UTF-8?B?RXN0YWRv?=") == "Estado"


@pytest.mark.parametrize(
    "cuerpo,esperado",
    [
        ("PAUSA", "PAUSA"),
        ("pausa.", "PAUSA"),
        ("STOP!\n", "STOP"),
        ("REANUDAR", "REANUDAR"),
        ("no pares el servidor", None),
        ("PAUSA y sigue", None),
        ("", None),
    ],
)
def test_detectar_control(cuerpo, esperado):
    assert detectar_control(cuerpo) == esperado


@pytest.mark.parametrize(
    "headers,esperado",
    [
        ({"auto-submitted": ("auto-replied",)}, True),
        ({"auto-submitted": ("no",)}, False),
        ({"x-autoreply": ("si",)}, True),
        ({"precedence": ("bulk",)}, True),
        ({}, False),
    ],
)
def test_auto_respuesta(headers, esperado):
    detectado, _motivo = es_auto_respuesta(headers)
    assert detectado is esperado


def test_from_multiple_es_invalido():
    datos = _payload("hola")
    datos["payload"]["headers"].append(
        {"name": "From", "value": "otro@example.com"}
    )
    mensaje = parsear_mensaje(datos)
    assert mensaje.from_valido is False
    assert mensaje.from_email == ""


def test_limpiar_cuerpo_colapsa_lineas():
    assert limpiar_cuerpo("a\n\n\n\nb") == "a\n\nb"
