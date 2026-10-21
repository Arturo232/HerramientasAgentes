from __future__ import annotations

import pytest

from agente_correo.config import ErrorConfig, normalizar_direccion
from agente_correo.parser import (
    es_mensaje_del_agente,
    remitente_autorizado,
)


@pytest.mark.parametrize(
    "from_email,autorizado,esperado",
    [
        ("arturo@example.com", "Arturo@Example.com", True),
        ("ARTURO@EXAMPLE.COM", "arturo@example.com", True),
        ("arturo@example.com", "otro@example.com", False),
        ("arturo@example.com.evil", "arturo@example.com", False),
        ("sub.arturo@example.com", "arturo@example.com", False),
        ("arturo+tag@example.com", "arturo@example.com", False),
        ("", "arturo@example.com", False),
        ("arturo@example.com", "", False),
    ],
)
def test_whitelist_exacta_case_insensitive(from_email, autorizado, esperado):
    assert remitente_autorizado(from_email, autorizado) is esperado


def test_normaliza_display_name():
    assert normalizar_direccion('Arturo Pérez <Arturo@Example.com>') == "arturo@example.com"


@pytest.mark.parametrize(
    "valor",
    [
        "",
        "arturo@example.com, otro@example.com",
        "sin-arroba",
        "dos@example.com; tres@example.com",
    ],
)
def test_normalizar_rechaza_listas_y_vacios(valor):
    with pytest.raises(ErrorConfig):
        normalizar_direccion(valor)


def test_mensaje_del_propio_agente():
    assert es_mensaje_del_agente("agente@example.com", "Agente@Example.com")
    assert not es_mensaje_del_agente("arturo@example.com", "agente@example.com")
