"""Configuración del agente de correo.

Lee ``.env`` y variables de entorno del sistema. Las credenciales OAuth no se
guardan aquí: solo se referencian rutas a archivos con permisos 600.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from email.utils import getaddresses
from pathlib import Path

MODULO_DIR = Path(__file__).resolve().parent
REPO_DIR = MODULO_DIR.parent

SCOPES = (
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/drive.file",
)

HERRAMIENTAS_POR_DEFECTO = ("sistema", "redes", "datos")

# Gmail rechaza mensajes de más de 25 MB. Se deja margen para cabeceras y
# codificación base64 (que infla el contenido ~33 %).
LIMITE_MENSAJE_GMAIL = 24 * 1024 * 1024


class ErrorConfig(ValueError):
    """Configuración inválida o incompleta."""


def cargar_dotenv(ruta: Path) -> None:
    """Carga un ``.env`` sencillo sin dependencias externas.

    Las variables ya presentes en el entorno tienen prioridad (systemd
    ``EnvironmentFile`` manda). Admite comentarios de línea completa,
    ``export`` y valores entre comillas simples o dobles.
    """
    if not ruta.is_file():
        return
    for numero, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        if linea.startswith("export "):
            linea = linea[7:].lstrip()
        if "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        clave = clave.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", clave):
            raise ErrorConfig(f"Variable inválida en {ruta}:{numero}: {clave!r}")
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in {"'", '"'}:
            valor = valor[1:-1]
        else:
            valor = re.split(r"\s+#", valor, maxsplit=1)[0].strip()
        os.environ.setdefault(clave, valor)


def _texto(nombre: str, defecto: str | None = None, requerido: bool = False) -> str:
    valor = os.environ.get(nombre, defecto)
    if valor is None or not valor.strip():
        if requerido:
            raise ErrorConfig(f"Falta la variable obligatoria {nombre} en .env")
        return ""
    return valor.strip()


def _entero(nombre: str, defecto: int, minimo: int, maximo: int) -> int:
    crudo = os.environ.get(nombre)
    if crudo is None or not crudo.strip():
        return defecto
    try:
        valor = int(crudo)
    except ValueError as exc:
        raise ErrorConfig(f"{nombre} debe ser un entero, no {crudo!r}") from exc
    if not minimo <= valor <= maximo:
        raise ErrorConfig(f"{nombre} debe estar entre {minimo} y {maximo}")
    return valor


def _booleano(nombre: str, defecto: bool = False) -> bool:
    crudo = os.environ.get(nombre)
    if crudo is None or not crudo.strip():
        return defecto
    return crudo.strip().casefold() in {"1", "true", "si", "sí", "yes", "on"}


def _ruta(nombre: str, defecto: Path) -> Path:
    crudo = os.environ.get(nombre, "").strip()
    ruta = Path(os.path.expandvars(os.path.expanduser(crudo))) if crudo else defecto
    if not ruta.is_absolute():
        ruta = MODULO_DIR / ruta
    return ruta.resolve()


def _ruta_bin(nombre: str, defecto: Path) -> Path:
    """Como ``_ruta`` pero sin resolver symlinks del intérprete.

    ``.venv/bin/python`` suele ser un enlace a ``/usr/bin/pythonX.Y``. Si se
    resuelve, se pierde el venv y los scripts no ven sus dependencias.
    """
    crudo = os.environ.get(nombre, "").strip()
    ruta = Path(os.path.expandvars(os.path.expanduser(crudo))) if crudo else defecto
    if not ruta.is_absolute():
        ruta = MODULO_DIR / ruta
    return Path(os.path.abspath(str(ruta)))


def normalizar_direccion(valor: str) -> str:
    """Devuelve la dirección de un único remitente, en minúsculas.

    Acepta ``Nombre <correo@dominio>``. Rechaza listas, vacíos y valores con
    más de una dirección. La comparación de la lista blanca es exacta.
    """
    if not valor or not valor.strip():
        raise ErrorConfig("La dirección de correo está vacía")
    pares = getaddresses([valor])
    if len(pares) != 1:
        raise ErrorConfig(f"Se esperaba una sola dirección, no {valor!r}")
    _nombre, direccion = pares[0]
    direccion = direccion.strip()
    if not direccion or "@" not in direccion or any(c in direccion for c in " \t\r\n,;"):
        raise ErrorConfig(f"Dirección de correo inválida: {valor!r}")
    return direccion.casefold()


def _herramientas(valor: str) -> tuple[str, ...]:
    nombres = [n.strip() for n in re.split(r"[,\s]+", valor) if n.strip()]
    if not nombres:
        return ()
    for nombre in nombres:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", nombre):
            raise ErrorConfig(f"Nombre de herramienta inválido: {nombre!r}")
    return tuple(dict.fromkeys(nombres))


@dataclass(frozen=True, slots=True)
class Config:
    gmail_user: str
    autorizado_from: str
    client_secret: Path
    token: Path
    drive_folder_id: str
    repo_dir: Path
    python_bin: Path
    dir_datos: Path
    dir_salida: Path
    dir_entrada: Path
    poll_segundos: int
    max_tareas_hora: int
    max_adjuntos_bytes: int
    max_salida_bytes: int
    timeout_tarea: int
    timeout_selector: int
    max_cuerpo_chars: int
    max_resumen_chars: int
    max_artefactos: int
    max_artefacto_bytes: int
    herramientas_permitidas: tuple[str, ...]
    permitir_reconexion: bool
    etiqueta_base: str
    log_level: str
    oauth_port: int

    @classmethod
    def cargar(cls) -> "Config":
        cargar_dotenv(MODULO_DIR / ".env")

        gmail_user = normalizar_direccion(
            _texto("GMAIL_USER", requerido=True)
        )
        autorizado = normalizar_direccion(
            _texto("AUTORIZADO_FROM", requerido=True)
        )

        python_defecto = REPO_DIR / ".venv" / "bin" / "python"
        if not python_defecto.is_file():
            python_defecto = Path(sys.executable)

        etiqueta = _texto("GMAIL_ETIQUETA_BASE", "AgenteCorreo").strip("/")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", etiqueta):
            raise ErrorConfig("GMAIL_ETIQUETA_BASE solo admite letras, números, _ y -")

        return cls(
            gmail_user=gmail_user,
            autorizado_from=autorizado,
            client_secret=_ruta(
                "GOOGLE_CLIENT_SECRET", MODULO_DIR / "secrets" / "client_secret.json"
            ),
            token=_ruta("GOOGLE_TOKEN", MODULO_DIR / "secrets" / "token.json"),
            drive_folder_id=_texto("DRIVE_FOLDER_ID"),
            repo_dir=_ruta("REPO_DIR", REPO_DIR),
            python_bin=_ruta_bin("PYTHON_BIN", python_defecto),
            dir_datos=_ruta("DIR_DATOS", MODULO_DIR / "data"),
            dir_salida=_ruta("DIR_SALIDA", MODULO_DIR / "out"),
            dir_entrada=_ruta("DIR_ENTRADA", MODULO_DIR / "entrada"),
            poll_segundos=_entero("POLL_SEGUNDOS", 50, 15, 3600),
            max_tareas_hora=_entero("MAX_TAREAS_HORA", 6, 1, 1000),
            max_adjuntos_bytes=_entero("MAX_ADJUNTOS_MB", 20, 1, 24)
            * 1024
            * 1024,
            max_salida_bytes=_entero("MAX_SALIDA_BYTES", 65536, 1024, 4 * 1024 * 1024),
            timeout_tarea=_entero("TIMEOUT_TAREA", 120, 5, 3600),
            timeout_selector=_entero("TIMEOUT_SELECTOR", 15, 5, 120),
            max_cuerpo_chars=_entero("MAX_CUERPO_CHARS", 4000, 200, 50000),
            max_resumen_chars=_entero("MAX_RESUMEN_CHARS", 6000, 500, 50000),
            max_artefactos=_entero("MAX_ARTEFACTOS", 8, 1, 20),
            max_artefacto_bytes=_entero(
                "MAX_ARTEFACTO_MB", 200, 1, 1024
            )
            * 1024
            * 1024,
            herramientas_permitidas=_herramientas(
                _texto(
                    "HERRAMIENTAS_PERMITIDAS",
                    ",".join(HERRAMIENTAS_POR_DEFECTO),
                )
            ),
            permitir_reconexion=_booleano("PERMITIR_RECONEXION", False),
            etiqueta_base=etiqueta,
            log_level=_texto("LOG_LEVEL", "INFO").upper(),
            oauth_port=_entero("OAUTH_PORT", 8765, 1024, 65535),
        )

    def preparar_directorios(self) -> None:
        """Crea los directorios de trabajo con permisos restrictivos."""
        for ruta in (
            self.dir_datos,
            self.dir_salida,
            self.dir_entrada,
            self.token.parent,
        ):
            ruta.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(ruta, 0o700)
            except OSError:
                pass

    def ruta_etiqueta(self, sufijo: str) -> str:
        return f"{self.etiqueta_base}/{sufijo}"
