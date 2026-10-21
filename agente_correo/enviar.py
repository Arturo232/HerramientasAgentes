"""Puente CLI para enviar correos y responder dentro de un hilo.

Ejemplos::

    # Correo nuevo (sin credenciales, solo escribe el .eml)
    python -m agente_correo.enviar --para arturo@example.com \
        --asunto "Hola" --cuerpo "Mensaje" --dry-run

    # Envío real con adjunto
    python -m agente_correo.enviar --para arturo@example.com \
        --asunto "Informe" --cuerpo-archivo out/cuerpo.txt \
        --adjunto out/informe.pdf

    # Respuesta en el mismo hilo
    python -m agente_correo.enviar --para arturo@example.com \
        --responder-a 18f0c2... --cuerpo "Recibido"

Decisiones de seguridad (deliberadas y comprobadas por los tests):

* Solo se escribe a ``DESTINATARIOS_PERMITIDOS`` (coma-separada). Si la
  variable no existe o está vacía se usa ``AUTORIZADO_FROM``. ``--confirmar``
  abre la lista únicamente para esa ejecución.
* Los adjuntos y el archivo de cuerpo deben vivir dentro de ``DIR_ENTRADA`` o
  ``DIR_SALIDA``. ``--permitir-rutas-externas`` autoriza explícitamente rutas
  concretas fuera de ellos (por ejemplo, un archivo que la persona acaba de
  indicar en el chat). Las rutas se resuelven con ``strict=True`` para que un
  symlink no escape de los directorios permitidos.
* Este puente no sube nada a Drive: si se supera ``MAX_ADJUNTOS_MB``,
  ``MAX_ARTEFACTO_MB`` o el límite de Gmail, el envío falla con un error
  claro. El listener conserva su política de Drive para las respuestas
  automáticas.
* ``--dry-run`` escribe el ``.eml`` en ``out/envios-dry-run/`` y no envía. No
  construye el servicio de Gmail salvo que ``--responder-a`` obligue a leer el
  mensaje original.
* La salida estándar es un único objeto JSON; los errores legibles van a
  ``stderr`` para no romper el contrato del chat/agente.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Mapping, Sequence
from email.utils import getaddresses
from pathlib import Path
from typing import Any

from . import dispatcher, gmail_client
from .config import (
    LIMITE_MENSAJE_GMAIL,
    Config,
    ErrorConfig,
    normalizar_direccion,
)
from .gmail_client import ErrorGmail
from .parser import Mensaje, parsear_mensaje

CARPETA_DRY_RUN = "envios-dry-run"
MAX_DESTINATARIOS = 50
_RE_ID_GMAIL = re.compile(r"[A-Za-z0-9_-]{1,200}")
_RE_MESSAGE_ID = re.compile(r"<[^<>\s]+>")


class ErrorEnvio(RuntimeError):
    """Error de validación o de envío con mensaje apto para el usuario."""


def destinatarios_permitidos(cfg: Config) -> tuple[str, ...]:
    """Lista blanca efectiva de destinatarios, en minúsculas.

    ``DESTINATARIOS_PERMITIDOS`` se lee del entorno (``Config.cargar`` ya
    volcó el ``.env`` allí). Si no está definida o queda vacía, se usa
    ``AUTORIZADO_FROM``.
    """
    crudo = os.environ.get("DESTINATARIOS_PERMITIDOS", "").strip()
    if not crudo:
        return (cfg.autorizado_from,)

    permitidos: list[str] = []
    for trozo in crudo.replace(";", ",").split(","):
        trozo = trozo.strip()
        if not trozo:
            continue
        try:
            permitidos.append(normalizar_direccion(trozo))
        except ErrorConfig as exc:
            raise ErrorEnvio(
                f"DESTINATARIOS_PERMITIDOS contiene una dirección inválida: {exc}"
            ) from exc

    if not permitidos:
        return (cfg.autorizado_from,)
    return tuple(dict.fromkeys(permitidos))


def normalizar_destinatarios(valor: str) -> tuple[str, ...]:
    """Valida ``--para`` y devuelve direcciones únicas en minúsculas.

    Admite una o varias direcciones separadas por comas y nombres visibles
    (``Nombre <correo@dominio>``). Rechaza cabeceras con saltos de línea.
    """
    if not valor or not valor.strip():
        raise ErrorEnvio("Falta --para: indica al menos un destinatario")
    if any(c in valor for c in "\r\n"):
        raise ErrorEnvio("--para no puede contener saltos de línea")

    direcciones: list[str] = []
    for _nombre, direccion in getaddresses([valor]):
        if not direccion.strip():
            continue
        try:
            direcciones.append(normalizar_direccion(direccion))
        except ErrorConfig as exc:
            raise ErrorEnvio(f"Destinatario inválido en --para: {exc}") from exc

    if not direcciones:
        raise ErrorEnvio(f"--para no contiene direcciones válidas: {valor!r}")
    if len(direcciones) > MAX_DESTINATARIOS:
        raise ErrorEnvio(
            f"--para admite como máximo {MAX_DESTINATARIOS} destinatarios"
        )
    return tuple(dict.fromkeys(direcciones))


def _formato_bytes(cantidad: int) -> str:
    if cantidad >= 1024 * 1024:
        return f"{cantidad / (1024 * 1024):.1f} MB"
    if cantidad >= 1024:
        return f"{cantidad / 1024:.0f} KB"
    return f"{cantidad} B"


def _resolver_lectura(
    valor: str | Path,
    cfg: Config,
    permitir_rutas_externas: bool,
    etiqueta: str,
) -> Path:
    """Resuelve y valida un archivo de entrada.

    Por defecto solo se aceptan archivos dentro de ``entrada/`` y ``out/``.
    La comprobación se hace sobre la ruta ya resuelta, así que un symlink que
    apunte fuera también se rechaza.
    """
    crudo = str(valor).strip()
    if not crudo:
        raise ErrorEnvio(f"{etiqueta} no tiene ruta")

    ruta = Path(os.path.expandvars(os.path.expanduser(crudo)))
    if not ruta.is_absolute():
        ruta = Path.cwd() / ruta

    try:
        resuelta = ruta.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ErrorEnvio(
            f"{etiqueta} no existe o no se puede leer: {crudo}"
        ) from exc

    if not resuelta.is_file():
        raise ErrorEnvio(f"{etiqueta} no es un archivo regular: {crudo}")
    if not os.access(resuelta, os.R_OK):
        raise ErrorEnvio(f"{etiqueta} no tiene permiso de lectura: {crudo}")

    if not permitir_rutas_externas:
        raices = (cfg.dir_entrada.resolve(), cfg.dir_salida.resolve())
        if not any(resuelta.is_relative_to(raiz) for raiz in raices):
            raise ErrorEnvio(
                f"{etiqueta} está fuera de entrada/ y out/: {crudo}. "
                "Si el usuario autorizó esa ruta, repite con "
                "--permitir-rutas-externas."
            )
    return resuelta


def preparar_adjuntos(
    adjuntos: Sequence[str | Path],
    cfg: Config,
    permitir_rutas_externas: bool = False,
) -> tuple[Path, ...]:
    """Valida rutas, deduplica y aplica los límites de tamaño."""
    rutas: list[Path] = []
    vistos: set[Path] = set()

    for valor in adjuntos:
        ruta = _resolver_lectura(
            valor, cfg, permitir_rutas_externas, "El adjunto"
        )
        if ruta in vistos:
            continue
        vistos.add(ruta)

        try:
            tamano = ruta.stat().st_size
        except OSError as exc:
            raise ErrorEnvio(
                f"No se pudo medir el adjunto {ruta.name}: {exc}"
            ) from exc

        if tamano > cfg.max_artefacto_bytes:
            raise ErrorEnvio(
                f"El adjunto {ruta.name} ocupa {_formato_bytes(tamano)} y "
                "supera MAX_ARTEFACTO_MB "
                f"({_formato_bytes(cfg.max_artefacto_bytes)})."
            )
        rutas.append(ruta)

    total = 0
    for ruta in rutas:
        try:
            total += ruta.stat().st_size
        except OSError as exc:
            raise ErrorEnvio(
                f"No se pudo medir el adjunto {ruta.name}: {exc}"
            ) from exc

    if total > cfg.max_adjuntos_bytes:
        raise ErrorEnvio(
            f"Los adjuntos suman {_formato_bytes(total)} y superan "
            f"MAX_ADJUNTOS_MB ({_formato_bytes(cfg.max_adjuntos_bytes)})."
        )
    return tuple(rutas)


def _leer_cuerpo(
    cuerpo: str | None,
    cuerpo_archivo: str | None,
    cfg: Config,
    permitir_rutas_externas: bool,
) -> str:
    """Devuelve el cuerpo desde ``--cuerpo`` o desde ``--cuerpo-archivo``."""
    if cuerpo is not None:
        return cuerpo
    if not cuerpo_archivo:
        raise ErrorEnvio("Indica --cuerpo o --cuerpo-archivo")
    ruta = _resolver_lectura(
        cuerpo_archivo, cfg, permitir_rutas_externas, "El archivo de cuerpo"
    )
    try:
        return ruta.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ErrorEnvio(
            f"El archivo de cuerpo no es texto UTF-8: {ruta}"
        ) from exc
    except OSError as exc:
        raise ErrorEnvio(
            f"No se pudo leer el archivo de cuerpo {ruta}: {exc}"
        ) from exc


def _validar_id_mensaje(valor: str) -> str:
    limpio = valor.strip()
    if not _RE_ID_GMAIL.fullmatch(limpio):
        raise ErrorEnvio(
            "--responder-a debe ser el id de Gmail del mensaje "
            "(letras, números, _ y -)"
        )
    return limpio


def _message_id_real(mensaje: Mensaje) -> str:
    """Devuelve el ``Message-ID`` original, o ``""`` si no es utilizable.

    ``parsear_mensaje`` inventa un identificador cuando el correo no trae
    ``Message-ID``. Ese valor sirve para deduplicar, pero no para encadenar
    cabeceras RFC 5322.
    """
    for valor in mensaje.headers.get("message-id", ()):
        limpio = valor.strip()
        if _RE_MESSAGE_ID.fullmatch(limpio):
            return limpio
    return ""


def _obtener_servicio(cfg: Config, servicio):
    """Devuelve el servicio inyectado o construye uno, con error legible."""
    if servicio is not None:
        return servicio
    try:
        return gmail_client.construir_servicio(cfg)
    except ErrorGmail:
        raise
    except Exception as exc:
        raise ErrorEnvio(f"No se pudo conectar con Gmail: {exc}") from exc


def _leer_original(servicio, message_id: str, cfg: Config) -> Mensaje:
    try:
        payload = gmail_client.obtener_mensaje(servicio, message_id)
    except ErrorGmail:
        raise
    except Exception as exc:
        raise ErrorEnvio(
            f"No se pudo leer el mensaje original {message_id}: {exc}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise ErrorEnvio(
            f"Gmail devolvió un mensaje con formato inesperado: {message_id}"
        )
    return parsear_mensaje(payload, cfg.max_cuerpo_chars)


def _asunto_final(asunto: str | None, original: Mensaje | None) -> str:
    """Usa ``--asunto`` o el del original; al responder garantiza ``Re:``."""
    if original is not None:
        base = asunto if asunto is not None and asunto.strip() else original.subject
        return dispatcher.construir_asunto(base)
    if asunto is not None and asunto.strip():
        return asunto
    raise ErrorEnvio("Falta --asunto para un correo nuevo")


def _mensaje_para_mime(
    destinatarios: tuple[str, ...],
    asunto: str,
    original: Mensaje | None,
    message_id: str,
) -> Mensaje:
    """Construye el ``Mensaje`` que consume ``dispatcher.construir_mime``.

    El parser y el dispatcher comparten esa estructura; para un envío nuevo
    se rellenan solo los campos que el generador de MIME necesita.
    """
    if original is not None:
        return Mensaje(
            gmail_id=original.gmail_id,
            thread_id=original.thread_id,
            message_id=message_id,
            clave_idempotencia=original.clave_idempotencia,
            from_raw=original.from_raw,
            from_email=", ".join(destinatarios),
            from_nombre=original.from_nombre,
            subject=asunto,
            body="",
            references=original.references,
            headers=original.headers,
            adjuntos=(),
            label_ids=(),
        )

    return Mensaje(
        gmail_id="",
        thread_id="",
        message_id="",
        clave_idempotencia="envio-manual",
        from_raw="",
        from_email=", ".join(destinatarios),
        from_nombre="",
        subject=asunto,
        body="",
        references=(),
        headers={},
        adjuntos=(),
        label_ids=(),
    )


def enviar_correo(
    cfg: Config,
    *,
    para: str,
    cuerpo: str,
    asunto: str | None = None,
    adjuntos: Sequence[str | Path] = (),
    responder_a: str | None = None,
    dry_run: bool = False,
    confirmar: bool = False,
    permitir_rutas_externas: bool = False,
    servicio=None,
) -> dict[str, Any]:
    """Valida, construye y envía (o guarda en dry-run) un correo.

    Devuelve el diccionario que el CLI serializa a JSON. Lanza ``ErrorEnvio``
    ante cualquier problema de validación o de envío. ``servicio`` permite
    inyectar un Gmail falso en los tests.
    """
    destinatarios = normalizar_destinatarios(para)
    permitidos = destinatarios_permitidos(cfg)
    fuera = [d for d in destinatarios if d not in permitidos]
    if fuera and not confirmar:
        raise ErrorEnvio(
            "Destinatario(s) fuera de DESTINATARIOS_PERMITIDOS: "
            + ", ".join(fuera)
            + ". Usa --confirmar para enviar de todos modos."
        )

    rutas = preparar_adjuntos(adjuntos, cfg, permitir_rutas_externas)

    original: Mensaje | None = None
    message_id = ""
    if responder_a:
        identificador = _validar_id_mensaje(responder_a)
        servicio = _obtener_servicio(cfg, servicio)
        original = _leer_original(servicio, identificador, cfg)
        message_id = _message_id_real(original)

    asunto_final = _asunto_final(asunto, original)
    plantilla = _mensaje_para_mime(
        destinatarios, asunto_final, original, message_id
    )

    raw = dispatcher.construir_mime(
        cfg,
        plantilla,
        asunto_final,
        cuerpo,
        rutas,
        para=", ".join(destinatarios),
        en_hilo=bool(original is not None and message_id),
        auto_respuesta=False,
    )

    if len(raw) > LIMITE_MENSAJE_GMAIL:
        raise ErrorEnvio(
            f"El mensaje codificado ocupa {_formato_bytes(len(raw))} y supera "
            f"el límite de Gmail ({_formato_bytes(LIMITE_MENSAJE_GMAIL)}). "
            "Reduce los adjuntos."
        )

    hilo = original.thread_id if original is not None else ""
    nombre_copia = original.gmail_id if original is not None else "envio"

    resultado: dict[str, Any] = {
        "ok": True,
        "mensaje_id": None,
        "hilo": hilo or None,
        "destinatarios": list(destinatarios),
        "adjuntos": [ruta.name for ruta in rutas],
        "dry_run": bool(dry_run),
    }

    if dry_run:
        ruta_eml = dispatcher.guardar_eml(
            cfg, raw, nombre_copia, CARPETA_DRY_RUN
        )
        resultado["ruta_eml"] = str(ruta_eml)
        return resultado

    servicio = _obtener_servicio(cfg, servicio)
    try:
        respuesta = gmail_client.enviar_mime(servicio, raw, hilo or None)
    except Exception as exc:
        ruta_fallida = dispatcher.guardar_eml(
            cfg, raw, nombre_copia, "fallidos"
        )
        raise ErrorEnvio(
            "No se pudo enviar el correo; se guardó una copia en "
            f"{ruta_fallida}: {exc}"
        ) from exc

    if not isinstance(respuesta, Mapping):
        raise ErrorEnvio(
            "Gmail devolvió una respuesta inesperada al enviar el correo"
        )

    resultado["mensaje_id"] = respuesta.get("id")
    resultado["hilo"] = respuesta.get("threadId") or hilo or None
    return resultado

def _crear_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m agente_correo.enviar",
        description=(
            "Envía correos o responde en un hilo reutilizando el cliente de "
            "Gmail y el generador MIME del agente."
        ),
    )
    parser.add_argument(
        "--para",
        required=True,
        help="destinatario(s), separados por comas",
    )
    parser.add_argument(
        "--asunto",
        help=(
            "asunto; al responder se usa el original y se garantiza el "
            "prefijo 'Re:'"
        ),
    )
    cuerpo = parser.add_mutually_exclusive_group(required=True)
    cuerpo.add_argument("--cuerpo", help="cuerpo del correo en texto plano")
    cuerpo.add_argument(
        "--cuerpo-archivo",
        metavar="RUTA",
        help="archivo UTF-8 con el cuerpo del correo",
    )
    parser.add_argument(
        "--adjunto",
        action="append",
        default=[],
        metavar="RUTA",
        help="adjunto; se puede repetir",
    )
    parser.add_argument(
        "--responder-a",
        metavar="MESSAGE_ID",
        help="id de Gmail del mensaje original para conservar el hilo",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="escribe el .eml en out/envios-dry-run/ y no envía",
    )
    parser.add_argument(
        "--confirmar",
        action="store_true",
        help="permite destinatarios fuera de DESTINATARIOS_PERMITIDOS",
    )
    parser.add_argument(
        "--permitir-rutas-externas",
        action="store_true",
        help=(
            "permite leer adjuntos o cuerpo fuera de entrada/ y out/ "
            "(solo si el usuario indicó esa ruta)"
        ),
    )
    return parser


def _salida_fallida(args: argparse.Namespace, error: str) -> dict[str, Any]:
    try:
        destinatarios = list(normalizar_destinatarios(args.para))
    except ErrorEnvio:
        destinatarios = []
    return {
        "ok": False,
        "mensaje_id": None,
        "hilo": None,
        "destinatarios": destinatarios,
        "adjuntos": [Path(ruta).name for ruta in args.adjunto],
        "dry_run": bool(args.dry_run),
        "error": error,
    }


def main(argv: list[str] | None = None) -> int:
    args = _crear_parser().parse_args(argv)

    try:
        cfg = Config.cargar()
        cfg.preparar_directorios()
    except (ErrorConfig, OSError) as exc:
        mensaje = f"ERROR de configuración: {exc}"
        print(
            json.dumps(_salida_fallida(args, mensaje), ensure_ascii=False),
            file=sys.stdout,
        )
        print(mensaje, file=sys.stderr)
        return 2

    try:
        cuerpo = _leer_cuerpo(
            args.cuerpo,
            args.cuerpo_archivo,
            cfg,
            args.permitir_rutas_externas,
        )
        resultado = enviar_correo(
            cfg,
            para=args.para,
            cuerpo=cuerpo,
            asunto=args.asunto,
            adjuntos=tuple(args.adjunto),
            responder_a=args.responder_a,
            dry_run=args.dry_run,
            confirmar=args.confirmar,
            permitir_rutas_externas=args.permitir_rutas_externas,
        )
    except (ErrorEnvio, ErrorGmail, OSError) as exc:
        print(
            json.dumps(_salida_fallida(args, str(exc)), ensure_ascii=False),
            file=sys.stdout,
        )
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(resultado, ensure_ascii=False), file=sys.stdout)
    return 0


if __name__ == "__main__":  # pragma: no cover - entrada del módulo
    raise SystemExit(main())
