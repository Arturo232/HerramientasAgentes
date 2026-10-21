from __future__ import annotations

import base64

from agente_correo import gmail_client


class _Req:
    def __init__(self, datos):
        self.datos = datos

    def execute(self):
        return self.datos


class _Mensajes:
    def __init__(self):
        self.modificados = []
        self.enviados = []

    def list(self, **kwargs):
        return _Req({"messages": [{"id": "m1"}, {"id": "m2"}]})

    def get(self, **kwargs):
        return _Req({"id": kwargs["id"], "threadId": "hilo"})

    def modify(self, **kwargs):
        self.modificados.append(kwargs)
        return _Req({})

    def send(self, **kwargs):
        self.enviados.append(kwargs)
        return _Req({"id": "salida", "threadId": kwargs.get("body", {}).get("threadId")})


class _Etiquetas:
    def list(self, **kwargs):
        return _Req({"labels": [{"id": "L1", "name": "AgenteCorreo/Procesado"}]})

    def create(self, **kwargs):
        return _Req({"id": "L2", "name": kwargs["body"]["name"]})


class _Usuarios:
    def __init__(self):
        self._mensajes = _Mensajes()
        self._etiquetas = _Etiquetas()

    def messages(self):
        return self._mensajes

    def labels(self):
        return self._etiquetas


class _Servicio:
    def __init__(self):
        self._usuarios = _Usuarios()

    def users(self):
        return self._usuarios


def test_listar_y_modificar_sin_red():
    servicio = _Servicio()
    assert gmail_client.listar_no_leidos(servicio, limite=10) == ["m1", "m2"]
    gmail_client.modificar_mensaje(servicio, "m1", quitar=["UNREAD"])
    assert servicio._usuarios._mensajes.modificados[0]["body"] == {
        "removeLabelIds": ["UNREAD"]
    }


def test_etiqueta_existente_y_creada():
    servicio = _Servicio()
    cache = {}
    assert gmail_client.etiqueta_id(servicio, "AgenteCorreo/Procesado", cache) == "L1"
    assert gmail_client.etiqueta_id(servicio, "AgenteCorreo/Error", cache) == "L2"
    assert cache["AgenteCorreo/Error"] == "L2"


def test_enviar_mime_codifica_raw_y_conserva_hilo():
    servicio = _Servicio()
    crudo = b"From: a@b.c\nTo: d@e.f\n\nhola"
    resultado = gmail_client.enviar_mime(servicio, crudo, "hilo-1")
    enviado = servicio._usuarios._mensajes.enviados[0]
    assert base64.urlsafe_b64decode(enviado["body"]["raw"]) == crudo
    assert enviado["body"]["threadId"] == "hilo-1"
    assert resultado["id"] == "salida"
