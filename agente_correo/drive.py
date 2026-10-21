"""Subida de artefactos a Google Drive y compartición con el autorizado."""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Any

from .config import Config
from . import gmail_client

log = logging.getLogger(__name__)

NOMBRE_CARPETA = "AgenteCorreo"


class ErrorDrive(RuntimeError):
    pass


def _servicio(cfg: Config):
    return gmail_client.construir_servicio(cfg, api="drive", version="v3")


def _crear_carpeta(servicio) -> str:
    metadatos = {
        "name": NOMBRE_CARPETA,
        "mimeType": "application/vnd.google-apps.folder",
    }
    carpeta = (
        servicio.files()
        .create(body=metadatos, fields="id,name", supportsAllDrives=True)
        .execute()
    )
    return str(carpeta["id"])


def _buscar_carpeta(servicio) -> str | None:
    consulta = (
        f"name = '{NOMBRE_CARPETA}' and "
        "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    respuesta = (
        servicio.files()
        .list(
            q=consulta,
            spaces="drive",
            fields="files(id,name)",
            pageSize=1,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )
    archivos = respuesta.get("files", [])
    return str(archivos[0]["id"]) if archivos else None


def carpeta_destino(servicio, cfg: Config) -> str:
    """Devuelve la carpeta configurada o una creada por la propia app.

    Con el scope ``drive.file`` la app solo ve archivos que ella creó. Si el
    ``DRIVE_FOLDER_ID`` apunta a una carpeta creada a mano, Drive responde 404.
    En ese caso se usa/crea ``AgenteCorreo`` en la raíz de My Drive.
    """
    if cfg.drive_folder_id:
        try:
            carpeta = (
                servicio.files()
                .get(
                    fileId=cfg.drive_folder_id,
                    fields="id,name,mimeType,trashed",
                    supportsAllDrives=True,
                )
                .execute()
            )
            if carpeta.get("mimeType") == "application/vnd.google-apps.folder" and not carpeta.get(
                "trashed"
            ):
                return str(carpeta["id"])
            log.warning(
                "DRIVE_FOLDER_ID no es una carpeta válida; se usará %s", NOMBRE_CARPETA
            )
        except Exception as exc:
            log.warning(
                "No se pudo abrir DRIVE_FOLDER_ID (%s); se usará una carpeta "
                "creada por la app. Con drive.file una carpeta creada a mano "
                "no es visible.",
                exc.__class__.__name__,
            )
    try:
        existente = _buscar_carpeta(servicio)
    except Exception as exc:
        log.warning(
            "No se pudo buscar la carpeta %s (%s); se intentará crear",
            NOMBRE_CARPETA,
            exc.__class__.__name__,
        )
        existente = None
    return existente or _crear_carpeta(servicio)


def subir_y_compartir(cfg: Config, ruta: Path, destinatario: str) -> dict[str, Any]:
    """Sube un archivo, lo comparte como lector y devuelve sus metadatos."""
    ruta = Path(ruta)
    if not ruta.is_file():
        raise ErrorDrive(f"No existe el archivo a subir: {ruta.name}")
    if ruta.stat().st_size > cfg.max_artefacto_bytes:
        raise ErrorDrive(f"El archivo supera el máximo permitido: {ruta.name}")

    try:
        from googleapiclient.http import MediaFileUpload
    except ImportError as exc:  # pragma: no cover
        raise ErrorDrive("Faltan librerías de Google para subir a Drive") from exc

    servicio = _servicio(cfg)
    carpeta = carpeta_destino(servicio, cfg)
    tipo = mimetypes.guess_type(str(ruta))[0] or "application/octet-stream"
    metadatos = {"name": ruta.name, "parents": [carpeta]}
    medio = MediaFileUpload(str(ruta), mimetype=tipo, resumable=True)

    try:
        archivo = (
            servicio.files()
            .create(
                body=metadatos,
                media_body=medio,
                fields="id,name,size,webViewLink",
                supportsAllDrives=True,
            )
            .execute()
        )
        servicio.permissions().create(
            fileId=archivo["id"],
            body={
                "type": "user",
                "role": "reader",
                "emailAddress": destinatario,
            },
            sendNotificationEmail=False,
            supportsAllDrives=True,
            fields="id",
        ).execute()
    except Exception as exc:
        raise ErrorDrive(
            f"No se pudo subir/compartir {ruta.name} en Drive ({exc.__class__.__name__})"
        ) from exc

    enlace = archivo.get("webViewLink") or (
        f"https://drive.google.com/file/d/{archivo['id']}/view"
    )
    return {
        "id": str(archivo["id"]),
        "nombre": str(archivo.get("name", ruta.name)),
        "enlace": enlace,
        "bytes": int(archivo.get("size", ruta.stat().st_size) or 0),
    }
