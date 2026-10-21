"""Parseo de mensajes de Gmail y reglas de remitente/control.

Todo es puro: recibe el JSON de ``users.messages.get`` y devuelve un
``Mensaje``. No toca red, disco ni base de datos, lo que permite probarlo con
payloads fijos.
"""

from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass
from email.header import decode_header
from email.utils import getaddresses
from html.parser import HTMLParser
from typing import Any, Iterable, Mapping

_RE_ESCRIBIO = re.compile(
    r"^\s*(?:On\s.+wrote:|El\s.+escribi[oó]:|Em\s.+escreveu:|Le\s.+a\s+[eé]crit:)\s*$",
    re.IGNORECASE,
)
_RE_FIRMA = re.compile(r"^--\s*$")


@dataclass(frozen=True, slots=True)
class Adjunto:
    filename: str
    mime_type: str
    size: int
    attachment_id: str | None = None


@dataclass(frozen=True, slots=True)
class Mensaje:
    gmail_id: str
    thread_id: str
    message_id: str
    clave_idempotencia: str
    from_raw: str
    from_email: str
    from_nombre: str
    subject: str
    body: str
    references: tuple[str, ...]
    headers: Mapping[str, tuple[str, ...]]
    adjuntos: tuple[Adjunto, ...]
    label_ids: tuple[str, ...]
    from_valido: bool = True

    @property
    def asunto_corto(self) -> str:
        return (self.subject or "(sin asunto)")[:100]


def decodificar_cabecera(valor: str) -> str:
    """Decodifica RFC 2047 conservando el texto si algo falla."""
    try:
        partes = []
        for texto, charset in decode_header(valor):
            if isinstance(texto, bytes):
                partes.append(texto.decode(charset or "utf-8", errors="replace"))
            else:
                partes.append(texto)
        return "".join(partes)
    except (LookupError, UnicodeDecodeError, ValueError):
        return valor


def _cabeceras(payload: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    acumuladas: dict[str, list[str]] = {}
    for cabecera in payload.get("headers", []) or []:
        if not isinstance(cabecera, Mapping):
            continue
        nombre = str(cabecera.get("name", "")).strip().lower()
        if not nombre:
            continue
        valor = decodificar_cabecera(str(cabecera.get("value", "")))
        acumuladas.setdefault(nombre, []).append(valor)
    return {nombre: tuple(valores) for nombre, valores in acumuladas.items()}


def _primera(headers: Mapping[str, tuple[str, ...]], nombre: str) -> str:
    valores = headers.get(nombre, ())
    return valores[0] if valores else ""


def _direccion_unica(headers: Mapping[str, tuple[str, ...]]) -> tuple[bool, str, str]:
    valores = headers.get("from", ())
    if len(valores) != 1:
        return False, "", ""
    pares = getaddresses([valores[0]])
    if len(pares) != 1:
        return False, "", ""
    nombre, direccion = pares[0]
    direccion = direccion.strip()
    if not direccion or "@" not in direccion:
        return False, "", ""
    if any(c in direccion for c in " \t\r\n,;"):
        return False, "", ""
    return True, direccion.casefold(), nombre.strip()


def _cabecera_parte(part: Mapping[str, Any], nombre: str) -> str:
    objetivo = nombre.lower()
    for cabecera in part.get("headers", []) or []:
        if str(cabecera.get("name", "")).strip().lower() == objetivo:
            return str(cabecera.get("value", ""))
    return ""


def _charset(part: Mapping[str, Any]) -> str:
    tipo = _cabecera_parte(part, "Content-Type")
    coincidencia = re.search(r"charset\s*=\s*\"?([\w.-]+)\"?", tipo, re.IGNORECASE)
    return coincidencia.group(1) if coincidencia else "utf-8"


def _decodificar_base64url(datos: str) -> bytes:
    relleno = "=" * (-len(datos) % 4)
    try:
        return base64.urlsafe_b64decode(datos + relleno)
    except (ValueError, binascii.Error):
        return b""


def _texto_parte(part: Mapping[str, Any]) -> str:
    datos = str(part.get("body", {}).get("data", "") or "")
    if not datos:
        return ""
    crudo = _decodificar_base64url(datos)
    if not crudo:
        return ""
    return crudo.decode(_charset(part), errors="replace")


def _es_adjunto(part: Mapping[str, Any]) -> bool:
    if part.get("filename"):
        return True
    disposicion = _cabecera_parte(part, "Content-Disposition").lower()
    return "attachment" in disposicion


def _hojas(part: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    partes = part.get("parts") or []
    if partes:
        for subparte in partes:
            if isinstance(subparte, Mapping):
                yield from _hojas(subparte)
    else:
        yield part


class _HtmlATexto(HTMLParser):
    _BLOQUE = {
        "p", "div", "br", "li", "tr", "table", "h1", "h2", "h3", "h4",
        "h5", "h6", "blockquote", "section", "article", "header", "footer",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._partes: list[str] = []
        self._ignorar = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style"}:
            self._ignorar += 1
        elif tag in self._BLOQUE:
            self._partes.append("\n")
        elif tag == "li":
            self._partes.append("- ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._ignorar:
            self._ignorar -= 1
        elif tag in self._BLOQUE:
            self._partes.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignorar:
            self._partes.append(data)

    def texto(self) -> str:
        return "".join(self._partes)


def html_a_texto(html: str) -> str:
    if len(html) > 1_000_000:
        html = html[:1_000_000]
    extractor = _HtmlATexto()
    try:
        extractor.feed(html)
        extractor.close()
    except Exception:  # HTML malformado: se conserva lo extraído
        pass
    return extractor.texto()


def _cuerpo(payload: Mapping[str, Any]) -> str:
    texto_plano = ""
    texto_html = ""
    for parte in _hojas(payload):
        if _es_adjunto(parte):
            continue
        tipo = str(parte.get("mimeType", "")).lower()
        if tipo == "text/plain" and not texto_plano:
            texto_plano = _texto_parte(parte)
        elif tipo == "text/html" and not texto_html:
            texto_html = _texto_parte(parte)
    if texto_plano.strip():
        return texto_plano
    if texto_html.strip():
        return html_a_texto(texto_html)
    return ""


def limpiar_cuerpo(cuerpo: str) -> str:
    """Quita citas, firma y ruido de un correo de respuesta."""
    lineas = cuerpo.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    limpias: list[str] = []
    for linea in lineas:
        if _RE_ESCRIBIO.match(linea):
            break
        if linea.lstrip().startswith(">"):
            continue
        if _RE_FIRMA.match(linea):
            break
        limpias.append(linea)
    texto = "\n".join(limpias)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def detectar_control(cuerpo: str) -> str | None:
    """Devuelve ``PAUSA``, ``STOP``, ``REANUDAR`` o ``None``.

    Solo acepta una palabra sola en una de las primeras líneas útiles. Así
    "no pares el servidor" no activa nada.
    """
    utiles = [linea.strip() for linea in cuerpo.splitlines() if linea.strip()]
    for linea in utiles[:5]:
        normal = linea.strip(" .,;:!¡?¿()[]").upper()
        if normal in {"PAUSA", "STOP"}:
            return normal
        if normal == "REANUDAR":
            return normal
    return None


def es_auto_respuesta(headers: Mapping[str, tuple[str, ...]]) -> tuple[bool, str]:
    auto = _primera(headers, "auto-submitted").strip().lower()
    if auto and auto != "no":
        return True, f"Auto-Submitted: {auto}"
    for nombre in ("x-autoreply", "x-autorespond", "x-autoresponder"):
        if _primera(headers, nombre).strip():
            return True, f"{nombre} presente"
    precedencia = _primera(headers, "precedence").strip().lower()
    if precedencia in {"bulk", "junk", "list", "auto_reply"}:
        return True, f"Precedence: {precedencia}"
    return False, ""


def remitente_autorizado(from_email: str, autorizado_from: str) -> bool:
    """Comparación exacta, sin dominios ni subdirecciones, case-insensitive."""
    if not from_email or not autorizado_from:
        return False
    return from_email.strip().casefold() == autorizado_from.strip().casefold()


def parsear_mensaje(
    payload: Mapping[str, Any], max_cuerpo_chars: int = 4000
) -> Mensaje:
    gmail_id = str(payload.get("id", "") or "")
    thread_id = str(payload.get("threadId", "") or "")
    cuerpo_json = payload.get("payload", {}) or {}
    headers = _cabeceras(cuerpo_json)

    from_valido, from_email, from_nombre = _direccion_unica(headers)
    from_raw = _primera(headers, "from")

    message_id = _primera(headers, "message-id").strip()
    if not message_id:
        message_id = f"<gmail-{gmail_id or 'sin-id'}@agente.local>"
    clave = message_id if gmail_id else f"gmail:{gmail_id}"

    references = tuple(
        referencia
        for referencia in re.findall(r"<[^<>\s]+>", _primera(headers, "references"))
    )
    if not references:
        references = tuple(
            referencia
            for referencia in re.findall(
                r"<[^<>\s]+>", _primera(headers, "in-reply-to")
            )
        )

    adjuntos: list[Adjunto] = []
    for parte in _hojas(cuerpo_json):
        if not _es_adjunto(parte):
            continue
        filename = str(parte.get("filename", "") or "adjunto")
        cuerpo_parte = parte.get("body", {}) or {}
        adjuntos.append(
            Adjunto(
                filename=filename,
                mime_type=str(parte.get("mimeType", "application/octet-stream")),
                size=int(cuerpo_parte.get("size", 0) or 0),
                attachment_id=cuerpo_parte.get("attachmentId"),
            )
        )

    cuerpo = limpiar_cuerpo(_cuerpo(cuerpo_json))[:max_cuerpo_chars]

    return Mensaje(
        gmail_id=gmail_id,
        thread_id=thread_id,
        message_id=message_id,
        clave_idempotencia=clave,
        from_raw=from_raw,
        from_email=from_email if from_valido else "",
        from_nombre=from_nombre,
        subject=_primera(headers, "subject").strip(),
        body=cuerpo,
        references=references,
        headers=headers,
        adjuntos=tuple(adjuntos),
        label_ids=tuple(str(x) for x in payload.get("labelIds", []) or []),
        from_valido=from_valido,
    )


def es_mensaje_del_agente(from_email: str, gmail_user: str) -> bool:
    return bool(from_email) and from_email.casefold() == gmail_user.casefold()
