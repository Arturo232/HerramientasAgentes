"""Cliente mínimo de Gmail API.

Las importaciones de Google son perezosas: el módulo se puede importar y
probar sin tener instaladas las dependencias ni credenciales.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from .config import SCOPES, Config

log = logging.getLogger(__name__)

CONSULTA_NO_LEIDOS = "is:unread in:inbox"


class ErrorGmail(RuntimeError):
    """Error de Gmail con mensaje apto para el usuario."""


class ErrorAuth(ErrorGmail):
    """Falta autorización o el token ya no es válido."""


def _dependencias():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise ErrorGmail(
            "Faltan librerías de Google. Ejecuta: "
            "python -m pip install -r agente_correo/requirements.txt"
        ) from exc
    return Request, Credentials, build


def guardar_token(credenciales, ruta: Path, obligatorio: bool = False) -> None:
    """Escribe el token de forma atómica y con permisos 600.

    En el servicio systemd ``secrets/`` puede ser de solo lectura; en ese caso
    el refresh se mantiene en memoria y solo se avisa por log.
    """
    ruta = Path(ruta)
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(ruta.parent, 0o700)
        descriptor, temporal = tempfile.mkstemp(
            prefix=".token-", dir=str(ruta.parent), text=True
        )
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as archivo:
                json.dump(json.loads(credenciales.to_json()), archivo)
                archivo.flush()
                os.fsync(archivo.fileno())
            os.replace(temporal, ruta)
            os.chmod(ruta, 0o600)
        except Exception:
            try:
                os.unlink(temporal)
            except OSError:
                pass
            raise
    except OSError as exc:
        if obligatorio:
            raise ErrorAuth(f"No se pudo guardar el token en {ruta}: {exc}") from exc
        log.warning("No se pudo guardar el token refrescado (%s); se usa en memoria", exc)


def cargar_credenciales(cfg: Config, permitir_refresco: bool = True):
    """Carga ``token.json``, refresca si caducó y valida los scopes."""
    Request, Credentials, _build = _dependencias()
    ruta = Path(cfg.token)
    if not ruta.is_file():
        raise ErrorAuth(
            "No hay token OAuth. Ejecuta: python -m agente_correo.oauth_login"
        )
    try:
        info_token = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ErrorAuth(
            "El token OAuth no se pudo leer. Vuelve a autorizar con oauth_login.py"
        ) from exc
    guardados = info_token.get("scopes")
    if isinstance(guardados, str):
        guardados = guardados.split()
    if guardados:
        faltantes = set(SCOPES) - set(guardados)
        if faltantes:
            raise ErrorAuth(
                "El token no tiene todos los permisos necesarios. Vuelve a "
                "autorizar con oauth_login.py (faltan: %s)"
                % ", ".join(sorted(faltantes))
            )

    try:
        credenciales = Credentials.from_authorized_user_file(str(ruta), list(SCOPES))
    except (ValueError, OSError) as exc:
        raise ErrorAuth(
            "El token OAuth no se pudo leer. Vuelve a autorizar con oauth_login.py"
        ) from exc

    if credenciales.expired:
        if not permitir_refresco or not credenciales.refresh_token:
            raise ErrorAuth(
                "El token OAuth caducó y no tiene refresh_token. "
                "Vuelve a ejecutar oauth_login.py."
            )
        try:
            credenciales.refresh(Request())
        except Exception as exc:  # google.auth lanza excepciones variadas
            raise ErrorAuth(
                "No se pudo refrescar el token OAuth. Revisa la conexión y "
                "vuelve a ejecutar oauth_login.py si persiste."
            ) from exc
        guardar_token(credenciales, ruta, obligatorio=False)

    if not credenciales.valid:
        raise ErrorAuth(
            "El token OAuth no es válido. Ejecuta oauth_login.py de nuevo."
        )

    return credenciales


def construir_servicio(cfg: Config, api: str = "gmail", version: str = "v1"):
    _Request, _Credentials, build = _dependencias()
    return build(
        api,
        version,
        credentials=cargar_credenciales(cfg),
        cache_discovery=False,
    )


def perfil(servicio) -> dict[str, Any]:
    return servicio.users().getProfile(userId="me").execute()


def listar_no_leidos(servicio, limite: int = 20) -> list[str]:
    respuesta = (
        servicio.users()
        .messages()
        .list(userId="me", q=CONSULTA_NO_LEIDOS, maxResults=max(1, limite))
        .execute()
    )
    return [str(m["id"]) for m in respuesta.get("messages", []) if m.get("id")]


def obtener_mensaje(servicio, message_id: str) -> dict[str, Any]:
    return (
        servicio.users()
        .messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )


def modificar_mensaje(
    servicio,
    message_id: str,
    *,
    agregar: list[str] | None = None,
    quitar: list[str] | None = None,
) -> None:
    cuerpo: dict[str, list[str]] = {}
    if agregar:
        cuerpo["addLabelIds"] = agregar
    if quitar:
        cuerpo["removeLabelIds"] = quitar
    if not cuerpo:
        return
    servicio.users().messages().modify(
        userId="me", id=message_id, body=cuerpo
    ).execute()


def etiqueta_id(servicio, nombre: str, cache: dict[str, str] | None = None) -> str:
    cache = cache if cache is not None else {}
    if nombre in cache:
        return cache[nombre]
    etiquetas = (
        servicio.users().labels().list(userId="me").execute().get("labels", [])
    )
    for etiqueta in etiquetas:
        if etiqueta.get("name") == nombre:
            cache[nombre] = str(etiqueta["id"])
            return cache[nombre]
    creada = (
        servicio.users()
        .labels()
        .create(
            userId="me",
            body={
                "name": nombre,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            },
        )
        .execute()
    )
    cache[nombre] = str(creada["id"])
    return cache[nombre]


def marcar_leido(servicio, message_id: str) -> None:
    modificar_mensaje(servicio, message_id, quitar=["UNREAD"])


def archivar(servicio, message_id: str) -> None:
    modificar_mensaje(servicio, message_id, quitar=["INBOX"])


def enviar_mime(
    servicio, raw: bytes, thread_id: str | None = None
) -> dict[str, Any]:
    cuerpo: dict[str, Any] = {
        "raw": base64.urlsafe_b64encode(raw).decode("ascii"),
    }
    if thread_id:
        cuerpo["threadId"] = thread_id
    return servicio.users().messages().send(userId="me", body=cuerpo).execute()


def descargar_adjunto(servicio, message_id: str, attachment_id: str) -> bytes:
    respuesta = (
        servicio.users()
        .messages()
        .attachments()
        .get(userId="me", messageId=message_id, id=attachment_id)
        .execute()
    )
    datos = str(respuesta.get("data", ""))
    return base64.urlsafe_b64decode(datos + "=" * (-len(datos) % 4))
