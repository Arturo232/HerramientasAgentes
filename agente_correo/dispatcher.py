"""Construcción y envío de respuestas: mismo hilo, adjuntos o Drive."""

from __future__ import annotations

import logging
import re
import shlex
import time
from email.message import EmailMessage
from email.utils import formatdate
from pathlib import Path
from typing import Any

from . import drive, gmail_client
from .config import LIMITE_MENSAJE_GMAIL, Config
from .orquestador import ResultadoTarea, redactar, resumir_resultado
from .parser import Mensaje

log = logging.getLogger(__name__)


class ErrorEnvio(RuntimeError):
    pass


def construir_asunto(original: str) -> str:
    asunto = _limpiar_cabecera(original or "(sin asunto)", 200)
    if asunto.casefold().startswith("re:"):
        return asunto
    return f"Re: {asunto}"


def _limpiar_cabecera(valor: str, maximo: int = 300) -> str:
    limpio = re.sub(r"[\r\n\t]+", " ", str(valor)).strip()
    return limpio[:maximo]


def _referencias(mensaje: Mensaje) -> str:
    tokens = [
        token
        for token in (*mensaje.references, mensaje.message_id)
        if re.fullmatch(r"<[^<>\s]+>", token or "")
    ]
    vistos: list[str] = []
    for token in tokens:
        if token not in vistos:
            vistos.append(token)
    return " ".join(vistos[-10:])


def planificar_adjuntos(
    artefactos: tuple[Path, ...], cfg: Config
) -> tuple[str, tuple[Path, ...]]:
    archivos = tuple(p for p in artefactos if p.is_file())
    if not archivos:
        return "sin_adjuntos", ()
    total = sum(p.stat().st_size for p in archivos)
    if total <= cfg.max_adjuntos_bytes:
        return "adjuntar", archivos
    return "drive", archivos


def _tamano(bytes_: int) -> str:
    if bytes_ >= 1024 * 1024:
        return f"{bytes_ / (1024 * 1024):.1f} MB"
    if bytes_ >= 1024:
        return f"{bytes_ / 1024:.0f} KB"
    return f"{bytes_} B"


def construir_cuerpo(
    resultado: ResultadoTarea,
    cfg: Config,
    modo: str,
    archivos: tuple[Path, ...],
    enlaces: list[dict[str, Any]],
    avisos: list[str],
    dry_run: bool = False,
) -> str:
    lineas: list[str] = []
    if dry_run:
        lineas.append("[DRY-RUN] Este correo NO se envió y la herramienta NO se ejecutó.")
        lineas.append("")
    lineas.append(f"Resultado: {'OK' if resultado.ok else 'FALLÓ'}")
    lineas.append(f"Herramienta: {resultado.herramienta}")
    lineas.append(
        "Comando: " + shlex.join(resultado.comando)[:500]
    )
    lineas.append(f"Código de salida: {resultado.codigo}")
    lineas.append(f"Duración: {resultado.duracion:.1f} s")
    if resultado.nota:
        lineas.append(f"Nota: {resultado.nota}")
    if resultado.error:
        lineas.append(f"Error: {redactar(resultado.error)}")
    lineas.append("")
    lineas.append("Resumen")
    lineas.append("-------")
    lineas.append(
        resumir_resultado(resultado.datos, resultado.stdout, cfg.max_resumen_chars)
        or "(sin salida)"
    )

    if archivos:
        lineas.append("")
        if modo == "adjuntar":
            lineas.append(f"Adjuntos ({len(archivos)}):")
        else:
            lineas.append(f"Archivos grandes ({len(archivos)}):")
        for archivo in archivos:
            lineas.append(f"- {archivo.name} ({_tamano(archivo.stat().st_size)})")

    if enlaces:
        lineas.append("")
        lineas.append("Enlaces de Google Drive (compartidos como lector):")
        for enlace in enlaces:
            lineas.append(
                f"- {enlace['nombre']} ({_tamano(enlace.get('bytes', 0))}): "
                f"{enlace['enlace']}"
            )

    if avisos:
        lineas.append("")
        lineas.append("Avisos:")
        for aviso in avisos:
            lineas.append(f"- {redactar(aviso, 800)}")

    lineas.extend(
        [
            "",
            "--",
            "Agente automático de correo. Este mensaje se generó sin intervención humana.",
        ]
    )
    return "\n".join(lineas)


def construir_mime(
    cfg: Config,
    mensaje: Mensaje,
    asunto: str,
    cuerpo: str,
    adjuntos: tuple[Path, ...] = (),
    *,
    para: str | None = None,
    en_hilo: bool = True,
    auto_respuesta: bool = True,
) -> bytes:
    """Construye el mensaje RFC 5322 listo para ``gmail_client.enviar_mime``.

    ``para`` sustituye el destinatario tomado del ``Mensaje``; es lo que usa
    el puente CLI cuando el usuario elige otro destinatario. ``en_hilo``
    añade ``In-Reply-To`` y ``References`` (solo tiene sentido al responder) y
    ``auto_respuesta`` marca el correo como generado automáticamente. Los
    valores por defecto conservan el comportamiento de las respuestas del
    listener.
    """
    correo = EmailMessage()
    correo["From"] = cfg.gmail_user
    correo["To"] = _limpiar_cabecera(
        para or mensaje.from_email or cfg.autorizado_from, 1000
    )
    correo["Subject"] = _limpiar_cabecera(asunto, 200)
    correo["Date"] = formatdate(localtime=True)
    if en_hilo:
        correo["In-Reply-To"] = _limpiar_cabecera(mensaje.message_id, 300)
        referencias = _referencias(mensaje)
        if referencias:
            correo["References"] = _limpiar_cabecera(referencias, 2000)
    if auto_respuesta:
        correo["Auto-Submitted"] = "auto-replied"
        correo["X-Auto-Response-Suppress"] = "All"
    correo["X-Agente-Correo"] = "v1"
    correo.set_content(cuerpo, subtype="plain", charset="utf-8")

    for ruta in adjuntos:
        tipo = _mimetype(ruta)
        maintype, _, subtype = tipo.partition("/")
        correo.add_attachment(
            ruta.read_bytes(),
            maintype=maintype or "application",
            subtype=subtype or "octet-stream",
            filename=ruta.name,
        )
    return correo.as_bytes()


def _mimetype(ruta: Path) -> str:
    import mimetypes

    return mimetypes.guess_type(str(ruta))[0] or "application/octet-stream"


def guardar_eml(
    cfg: Config, raw: bytes, nombre: str, carpeta: str = "dry-run"
) -> Path:
    """Guarda un mensaje crudo en ``out/<carpeta>/`` con permisos 600."""
    destino = cfg.dir_salida / carpeta
    destino.mkdir(parents=True, exist_ok=True)
    seguro = re.sub(r"[^A-Za-z0-9_.-]", "_", str(nombre or "mensaje"))[:60]
    ruta = destino / (
        f"{time.strftime('%Y%m%d-%H%M%S')}-{time.time_ns() % 1_000_000:06d}-"
        f"{seguro}.eml"
    )
    ruta.write_bytes(raw)
    try:
        ruta.chmod(0o600)
    except OSError:
        pass
    return ruta


def _enviar_o_guardar(
    cfg: Config,
    mensaje: Mensaje,
    raw: bytes,
    *,
    servicio=None,
    dry_run: bool = False,
) -> dict[str, Any]:
    if dry_run:
        ruta = guardar_eml(cfg, raw, mensaje.gmail_id, "dry-run")
        log.info("DRY-RUN: respuesta guardada en %s", ruta)
        return {"enviado": False, "modo": "dry-run", "ruta": str(ruta)}
    try:
        servicio = servicio or gmail_client.construir_servicio(cfg)
        respuesta = gmail_client.enviar_mime(
            servicio, raw, mensaje.thread_id or None
        )
    except Exception as exc:
        ruta = guardar_eml(cfg, raw, mensaje.gmail_id, "fallidos")
        raise ErrorEnvio(
            f"No se pudo enviar la respuesta; se guardó en {ruta}"
        ) from exc
    return {
        "enviado": True,
        "id": respuesta.get("id"),
        "threadId": respuesta.get("threadId"),
    }


def responder(
    cfg: Config,
    mensaje: Mensaje,
    resultado: ResultadoTarea,
    *,
    servicio=None,
    dry_run: bool = False,
) -> dict[str, Any]:
    modo, archivos = planificar_adjuntos(resultado.artefactos, cfg)
    enlaces: list[dict[str, Any]] = []
    avisos: list[str] = []

    if modo == "drive":
        if dry_run:
            avisos.append(
                "DRY-RUN: estos archivos se subirían a Drive y se compartirían "
                "con el remitente autorizado."
            )
        else:
            for archivo in archivos:
                try:
                    enlaces.append(
                        drive.subir_y_compartir(cfg, archivo, cfg.autorizado_from)
                    )
                except Exception as exc:
                    avisos.append(
                        f"No se pudo subir {archivo.name} a Drive: {exc}"
                    )
        cuerpo = construir_cuerpo(
            resultado, cfg, modo, archivos, enlaces, avisos, dry_run=dry_run
        )
        raw = construir_mime(
            cfg, mensaje, construir_asunto(mensaje.subject), cuerpo, ()
        )
        return _enviar_o_guardar(
            cfg, mensaje, raw, servicio=servicio, dry_run=dry_run
        )

    cuerpo = construir_cuerpo(
        resultado, cfg, modo, archivos, enlaces, avisos, dry_run=dry_run
    )
    raw = construir_mime(
        cfg, mensaje, construir_asunto(mensaje.subject), cuerpo, archivos
    )

    # Gmail limita el mensaje completo a 25 MB; base64 infla el contenido.
    if archivos and len(raw) > LIMITE_MENSAJE_GMAIL:
        if dry_run:
            avisos.append(
                "DRY-RUN: el mensaje supera el límite de Gmail; se subiría a Drive."
            )
        else:
            for archivo in archivos:
                try:
                    enlaces.append(
                        drive.subir_y_compartir(cfg, archivo, cfg.autorizado_from)
                    )
                except Exception as exc:
                    avisos.append(
                        f"No se pudo subir {archivo.name} a Drive: {exc}"
                    )
        cuerpo = construir_cuerpo(
            resultado, cfg, "drive", archivos, enlaces, avisos, dry_run=dry_run
        )
        raw = construir_mime(
            cfg, mensaje, construir_asunto(mensaje.subject), cuerpo, ()
        )

    return _enviar_o_guardar(cfg, mensaje, raw, servicio=servicio, dry_run=dry_run)


def responder_texto(
    cfg: Config,
    mensaje: Mensaje,
    cuerpo: str,
    *,
    servicio=None,
    dry_run: bool = False,
) -> dict[str, Any]:
    raw = construir_mime(
        cfg, mensaje, construir_asunto(mensaje.subject), cuerpo, ()
    )
    return _enviar_o_guardar(
        cfg, mensaje, raw, servicio=servicio, dry_run=dry_run
    )
