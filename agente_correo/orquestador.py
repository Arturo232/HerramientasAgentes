"""Puente entre el correo y el selector determinista del repositorio.

No ejecuta bash ni código del correo. Invoca exactamente:

    <venv>/bin/python scripts/orquestador/selector_herramientas.py \
        --intencion="<texto>"

Lee el JSON de salida, valida la herramienta contra una lista blanca y solo
entonces ejecuta el script registrado, con argumentos filtrados por política.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
import signal
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

from .config import Config, ErrorConfig

log = logging.getLogger(__name__)

SALIDA_TRUNCADA = "\n... [salida truncada]"
RUIDO_RESUMEN = {
    "script",
    "comando_ejecutado",
    "cold_start",
    "intencion",
    "script_absoluto",
    "argumentos",
}
EXTENSIONES_ARTEFACTO = {
    ".xlsx", ".xls", ".csv", ".docx", ".pdf", ".pptx", ".png", ".jpg",
    ".jpeg", ".webp", ".txt", ".md", ".json", ".zip", ".mp4", ".mp3",
    ".wav", ".srt", ".vtt",
}
# El selector usa nombres funcionales; el catálogo usa ids de comando.
ID_CAPACIDAD = {
    "sistema": "sistema",
    "redes": "red",
    "datos": "excel",
    "libro": "libro",
    "auditoria_wifi": "wifi",
}
IDIOMAS = {
    "espanol", "español", "ingles", "inglés", "frances", "francés",
    "portugues", "portugués", "aleman", "alemán", "italiano", "chino",
    "japones", "japonés", "ruso",
}


class ErrorEnrutamiento(RuntimeError):
    """El selector no supo enrutar o devolvió algo no confiable."""


class ErrorPolitica(RuntimeError):
    """La herramienta o sus argumentos no están permitidos por correo."""


@dataclass(frozen=True, slots=True)
class Enrutamiento:
    herramienta: str
    script_relativo: str
    argumentos: tuple[str, ...]
    salida_forzada: Path | None = None
    nota: str = ""


@dataclass(frozen=True, slots=True)
class ResultadoTarea:
    ok: bool
    herramienta: str
    comando: tuple[str, ...]
    codigo: int
    stdout: str
    stderr: str
    datos: dict[str, Any] | None
    artefactos: tuple[Path, ...]
    duracion: float
    error: str | None = None
    nota: str = ""


def _texto_salida(valor: Any) -> str:
    if valor is None:
        return ""
    if isinstance(valor, bytes):
        return valor.decode("utf-8", errors="replace")
    return str(valor)


def _recortar(texto: str, max_bytes: int) -> str:
    crudo = texto.encode("utf-8", errors="replace")
    if len(crudo) <= max_bytes:
        return texto
    return crudo[:max_bytes].decode("utf-8", errors="ignore") + SALIDA_TRUNCADA


def redactar(texto: str, max_chars: int = 2000) -> str:
    """Quita tokens y bloques PEM de cualquier texto que vaya al correo."""
    texto = texto or ""
    patrones = (
        (
            r"(?i)\b(access_token|refresh_token|client_secret|password|"
            r"contraseña)\b\s*[=:]\s*[^\s,;]+",
            r"\1=<redactado>",
        ),
        (r"ya29\.[A-Za-z0-9._-]+", "<token>"),
        (r"1//[A-Za-z0-9._-]+", "<token>"),
        (r"AIza[A-Za-z0-9._-]{20,}", "<api-key>"),
        (
            r"-----BEGIN [^-]+-----.*?-----END [^-]+-----",
            "<clave-privada>",
        ),
    )
    for patron, reemplazo in patrones:
        texto = re.sub(patron, reemplazo, texto, flags=re.DOTALL)
    if len(texto) > max_chars:
        texto = texto[:max_chars] + "... [recortado]"
    return texto.strip()


def resumir_resultado(
    datos: dict[str, Any] | None, stdout: str, max_chars: int = 6000
) -> str:
    """Resumen legible sin volcar JSON gigantes ni rutas internas de más."""
    if not isinstance(datos, dict):
        return redactar(stdout.strip(), max_chars)
    lineas: list[str] = []
    vistos: set[str] = set()
    preferidos = (
        "mensaje",
        "exito",
        "herramienta",
        "archivo_generado",
        "filas_procesadas",
        "columnas",
        "internet",
        "dns",
        "latencia_ms",
        "ram_porcentaje",
        "disco_libre_gb",
        "paquetes_huerfanos",
        "cache_pacman_mb",
    )
    for clave in preferidos:
        if clave in datos:
            lineas.append(f"{clave}: {_valor_legible(datos[clave])}")
            vistos.add(clave)
    for clave, valor in datos.items():
        if clave in vistos or clave in RUIDO_RESUMEN:
            continue
        if len(lineas) >= 25:
            break
        lineas.append(f"{clave}: {_valor_legible(valor)}")
    texto = "\n".join(lineas)
    if len(texto) > max_chars:
        texto = texto[:max_chars] + "\n... [resumen recortado]"
    return redactar(texto, max_chars + 50)


def _valor_legible(valor: Any) -> str:
    if isinstance(valor, bool):
        return "sí" if valor else "no"
    if valor is None:
        return "-"
    if isinstance(valor, (int, float)):
        return str(valor)
    if isinstance(valor, str):
        return valor[:300]
    try:
        texto = json.dumps(valor, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        texto = str(valor)
    return texto[:300]


class PuenteSelector:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._catalogo: dict[str, dict[str, Any]] | None = None
        self._capacidades: dict[str, str] | None = None

    # -- selector ---------------------------------------------------------
    def _ejecutar_selector(self, argumentos: list[str]) -> dict[str, Any]:
        selector = self.cfg.repo_dir / "scripts" / "orquestador" / "selector_herramientas.py"
        if not selector.is_file():
            raise ErrorConfig(f"No existe el selector: {selector}")
        comando = [str(self.cfg.python_bin), str(selector), *argumentos]
        try:
            proceso = subprocess.run(
                comando,
                cwd=str(self.cfg.repo_dir),
                env=self._env_hijo(),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.cfg.timeout_selector,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ErrorEnrutamiento(f"No se pudo ejecutar el selector: {exc}") from exc
        try:
            datos = json.loads(proceso.stdout)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ErrorEnrutamiento(
                "El selector no devolvió JSON válido"
            ) from exc
        if not isinstance(datos, dict):
            raise ErrorEnrutamiento("El selector devolvió un JSON inesperado")
        return datos

    def catalogo(self) -> dict[str, dict[str, Any]]:
        if self._catalogo is None:
            datos = self._ejecutar_selector(["--listar"])
            herramientas = datos.get("herramientas", [])
            if not isinstance(herramientas, list):
                raise ErrorEnrutamiento("Catálogo del selector inválido")
            self._catalogo = {
                str(h["nombre"]): h
                for h in herramientas
                if isinstance(h, dict) and h.get("nombre")
            }
        return self._catalogo

    def _cargar_capacidades(self) -> dict[str, str]:
        if self._capacidades is None:
            ruta = self.cfg.repo_dir / "capacidades.json"
            try:
                datos = json.loads(ruta.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ErrorConfig(f"No se pudo leer {ruta}") from exc
            self._capacidades = {
                str(c["id"]): str(c["script"]).replace("\\", "/")
                for c in datos.get("comandos", [])
                if isinstance(c, dict) and c.get("id") and c.get("script")
            }
        return self._capacidades

    def validar_config(self) -> None:
        if not self.cfg.herramientas_permitidas:
            raise ErrorConfig("HERRAMIENTAS_PERMITIDAS está vacía")
        catalogo = self.catalogo()
        capacidades = self._cargar_capacidades()
        for nombre in self.cfg.herramientas_permitidas:
            if nombre not in catalogo:
                raise ErrorConfig(
                    f"La herramienta {nombre!r} no la conoce el selector. "
                    "Revisa HERRAMIENTAS_PERMITIDAS."
                )
            if nombre not in _POLITICAS:
                raise ErrorConfig(
                    f"No hay política de argumentos para {nombre!r}; "
                    "se rechaza por seguridad."
                )
            script = str(catalogo[nombre].get("script", "")).replace("\\", "/")
            id_capacidad = ID_CAPACIDAD.get(nombre)
            if not id_capacidad or capacidades.get(id_capacidad) != script:
                raise ErrorConfig(
                    f"El script de {nombre!r} no coincide con capacidades.json"
                )

    # -- enrutamiento -----------------------------------------------------
    def enrutar(self, intencion: str) -> Enrutamiento:
        datos = self._ejecutar_selector([f"--intencion={intencion}"])
        if not datos.get("exito"):
            mensaje = str(datos.get("mensaje", "Intención no clasificable"))
            if "No se pudo clasificar" in mensaje:
                mensaje = (
                    "No entendí el comando. Envía en el cuerpo una de estas "
                    "órdenes: 'estado del sistema', 'diagnóstico de red', "
                    "'genera un excel de prueba', 'PAUSA' o 'REANUDAR'."
                )
            raise ErrorEnrutamiento(redactar(mensaje))
        return self.validar_enrutamiento(datos, self.catalogo())

    def validar_enrutamiento(
        self, datos: dict[str, Any], catalogo: dict[str, dict[str, Any]]
    ) -> Enrutamiento:
        nombre = str(datos.get("herramienta", "")).strip()
        if nombre not in self.cfg.herramientas_permitidas:
            raise ErrorPolitica(
                f"La herramienta {nombre!r} no está en la lista blanca "
                f"({', '.join(self.cfg.herramientas_permitidas)})"
            )
        if nombre not in _POLITICAS:
            raise ErrorPolitica(f"No hay política de argumentos para {nombre!r}")
        script = str(datos.get("script", "")).replace("\\", "/").strip()
        if not script:
            raise ErrorEnrutamiento("El selector no devolvió script")
        esperado = str(catalogo.get(nombre, {}).get("script", "")).replace("\\", "/")
        if script != esperado:
            raise ErrorEnrutamiento(
                f"El script devuelto no coincide con el catálogo para {nombre!r}"
            )
        ruta_relativa = PurePosixPath(script)
        if ruta_relativa.is_absolute() or ".." in ruta_relativa.parts:
            raise ErrorEnrutamiento("Ruta de script no permitida")
        id_capacidad = ID_CAPACIDAD.get(nombre)
        if not id_capacidad or self._cargar_capacidades().get(id_capacidad) != script:
            raise ErrorEnrutamiento(
                f"{nombre!r} no coincide con el script registrado en capacidades.json"
            )
        ruta = (self.cfg.repo_dir / ruta_relativa).resolve()
        try:
            ruta.relative_to(self.cfg.repo_dir.resolve())
        except ValueError as exc:
            raise ErrorEnrutamiento("El script sale del repositorio") from exc
        if not ruta.is_file():
            raise ErrorEnrutamiento(f"No existe el script: {script}")

        argumentos_crudos = datos.get("argumentos", [])
        if not isinstance(argumentos_crudos, list):
            raise ErrorEnrutamiento("Los argumentos del selector no son una lista")
        argumentos: list[str] = []
        for argumento in argumentos_crudos:
            if not isinstance(argumento, str):
                raise ErrorEnrutamiento("Argumento no textual del selector")
            if len(argumento) > 500 or any(c in argumento for c in "\x00\r\n"):
                raise ErrorEnrutamiento("Argumento con caracteres no permitidos")
            argumentos.append(argumento)
        if len(argumentos) > 20:
            raise ErrorEnrutamiento("Demasiados argumentos")

        politica = _POLITICAS[nombre]
        finales, salida_forzada, nota = politica(self.cfg, argumentos)
        return Enrutamiento(
            herramienta=nombre,
            script_relativo=script,
            argumentos=tuple(finales),
            salida_forzada=salida_forzada,
            nota=nota,
        )

    # -- ejecución --------------------------------------------------------
    def ejecutar(self, intencion: str) -> ResultadoTarea:
        enrutamiento = self.enrutar(intencion)
        inicio = time.monotonic()
        script = self.cfg.repo_dir / enrutamiento.script_relativo
        comando = tuple(
            [str(self.cfg.python_bin), str(script), *enrutamiento.argumentos]
        )
        log.info(
            "Ejecutando %s: %s", enrutamiento.herramienta, shlex.join(comando)
        )
        try:
            proceso = subprocess.Popen(
                list(comando),
                cwd=str(self.cfg.repo_dir),
                env=self._env_hijo(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                start_new_session=True,
            )
        except OSError as exc:
            duracion = time.monotonic() - inicio
            return ResultadoTarea(
                ok=False,
                herramienta=enrutamiento.herramienta,
                comando=comando,
                codigo=-1,
                stdout="",
                stderr="",
                datos=None,
                artefactos=(),
                duracion=duracion,
                error=redactar(f"No se pudo iniciar el script: {exc}"),
                nota=enrutamiento.nota,
            )

        agotado = False
        try:
            salida_cruda, error_crudo = proceso.communicate(
                timeout=self.cfg.timeout_tarea
            )
        except subprocess.TimeoutExpired:
            agotado = True
            try:
                os.killpg(os.getpgid(proceso.pid), signal.SIGKILL)
            except OSError:
                proceso.kill()
            try:
                salida_cruda, error_crudo = proceso.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                salida_cruda, error_crudo = "", ""

        duracion = time.monotonic() - inicio
        stdout = _recortar(salida_cruda or "", self.cfg.max_salida_bytes)
        stderr = _recortar(error_crudo or "", self.cfg.max_salida_bytes)
        if agotado:
            return ResultadoTarea(
                ok=False,
                herramienta=enrutamiento.herramienta,
                comando=comando,
                codigo=-1,
                stdout=stdout,
                stderr=stderr,
                datos=None,
                artefactos=(),
                duracion=duracion,
                error=redactar(
                    f"Tiempo máximo de {self.cfg.timeout_tarea} s excedido"
                ),
                nota=enrutamiento.nota,
            )

        datos = _json_de_salida(stdout)
        ok = proceso.returncode == 0 and not (
            isinstance(datos, dict) and datos.get("exito") is False
        )
        error = None
        if not ok:
            if isinstance(datos, dict):
                error = redactar(
                    str(datos.get("error") or datos.get("mensaje") or "")
                )
            if not error:
                error = redactar(stderr or stdout or "El script falló sin detalle")
        artefactos = self._artefactos(datos, enrutamiento.salida_forzada, inicio)

        return ResultadoTarea(
            ok=ok,
            herramienta=enrutamiento.herramienta,
            comando=comando,
            codigo=proceso.returncode,
            stdout=stdout,
            stderr=stderr,
            datos=datos,
            artefactos=artefactos,
            duracion=duracion,
            error=error,
            nota=enrutamiento.nota,
        )

    def _artefactos(
        self,
        datos: dict[str, Any] | None,
        salida_forzada: Path | None,
        inicio: float,
    ) -> tuple[Path, ...]:
        candidatos: list[Path] = []
        if salida_forzada is not None:
            candidatos.append(salida_forzada)
        for valor in _rutas_de_json(datos):
            ruta = Path(valor)
            if not ruta.is_absolute():
                ruta = self.cfg.repo_dir / ruta
            candidatos.append(ruta.resolve())

        salida = self.cfg.dir_salida.resolve()
        encontrados: list[Path] = []
        vistos: set[Path] = set()
        for ruta in candidatos:
            try:
                ruta = ruta.resolve()
                ruta.relative_to(salida)
            except (OSError, ValueError):
                continue
            if ruta in vistos or not ruta.is_file():
                continue
            if ruta.suffix.lower() not in EXTENSIONES_ARTEFACTO:
                continue
            try:
                if ruta.stat().st_size > self.cfg.max_artefacto_bytes:
                    log.warning("Artefacto demasiado grande, se omite: %s", ruta.name)
                    continue
                if ruta.stat().st_mtime < inicio - 5:
                    continue
            except OSError:
                continue
            vistos.add(ruta)
            encontrados.append(ruta)

        # Los archivos con nombre forzado pueden no aparecer en el JSON.
        if salida_forzada is not None and salida_forzada.exists():
            try:
                resuelta = salida_forzada.resolve()
                if (
                    resuelta.is_file()
                    and resuelta not in vistos
                    and resuelta.stat().st_size <= self.cfg.max_artefacto_bytes
                ):
                    encontrados.append(resuelta)
            except OSError:
                pass

        encontrados.sort(key=lambda p: p.name)
        return tuple(encontrados[: self.cfg.max_artefactos])

    def _env_hijo(self) -> dict[str, str]:
        """Entorno mínimo: sin tokens, sin credenciales, sin secretos."""
        permitidas = (
            "PATH", "HOME", "USER", "LOGNAME", "SHELL", "TZ",
            "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS",
        )
        entorno = {k: os.environ[k] for k in permitidas if k in os.environ}
        entorno.setdefault(
            "PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        )
        entorno.setdefault("HOME", str(Path.home()))
        entorno["LANG"] = "C.UTF-8"
        entorno["LC_ALL"] = "C.UTF-8"
        entorno["PYTHONIOENCODING"] = "utf-8"
        entorno["PYTHONUNBUFFERED"] = "1"
        entorno["PYTHONDONTWRITEBYTECODE"] = "1"
        return entorno


def _json_de_salida(stdout: str) -> dict[str, Any] | None:
    texto = stdout.strip()
    if not texto:
        return None
    try:
        cargado = json.loads(texto)
        if isinstance(cargado, dict):
            return cargado
    except (json.JSONDecodeError, ValueError):
        pass
    inicio = texto.find("{")
    fin = texto.rfind("}")
    if 0 <= inicio < fin:
        try:
            cargado = json.loads(texto[inicio : fin + 1])
            if isinstance(cargado, dict):
                return cargado
        except (json.JSONDecodeError, ValueError):
            return None
    return None


def _rutas_de_json(datos: Any, profundidad: int = 0) -> list[str]:
    if profundidad > 4:
        return []
    rutas: list[str] = []
    if isinstance(datos, dict):
        for clave, valor in datos.items():
            if clave in {"archivo_generado", "salida", "ruta", "ruta_salida", "archivo"}:
                if isinstance(valor, str) and valor.strip():
                    rutas.append(valor.strip())
                    continue
            rutas.extend(_rutas_de_json(valor, profundidad + 1))
    elif isinstance(datos, list):
        for valor in datos:
            rutas.extend(_rutas_de_json(valor, profundidad + 1))
    return rutas


# -- políticas de argumentos ------------------------------------------------
def _politica_sistema(cfg: Config, args: list[str]):
    if "--limpiar" in args:
        raise ErrorPolitica(
            "La limpieza del sistema no está permitida por correo. "
            "Ejecútala manualmente en la estación."
        )
    permitidos = {"--info", "--dry-run"}
    desconocidos = [a for a in args if a not in permitidos]
    if desconocidos:
        raise ErrorPolitica(f"Argumentos no permitidos: {desconocidos}")
    finales = list(dict.fromkeys(args))
    if "--info" not in finales:
        finales.insert(0, "--info")
    return finales, None, ""


def _politica_redes(cfg: Config, args: list[str]):
    permitidos = {"--sin-reconexion", "--dry-run", "--simular-offline"}
    desconocidos = [a for a in args if a not in permitidos]
    if desconocidos:
        raise ErrorPolitica(f"Argumentos no permitidos: {desconocidos}")
    if cfg.permitir_reconexion:
        return list(dict.fromkeys(args)), None, "Reconexión permitida por configuración."
    finales = [a for a in args if a in {"--dry-run", "--simular-offline"}]
    finales.append("--sin-reconexion")
    return finales, None, "Reconexión deshabilitada: solo diagnóstico."


def _politica_datos(cfg: Config, args: list[str]):
    if args and args != ["--test"]:
        raise ErrorPolitica(
            "El módulo de datos por correo solo admite el reporte de prueba "
            "(--test). No se aceptan rutas ni JSON del mensaje."
        )
    marca = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    salida = cfg.dir_salida / f"reporte-{marca}.xlsx"
    salida.parent.mkdir(parents=True, exist_ok=True)
    return ["--test", "--salida", str(salida)], salida, ""


def _politica_libro(cfg: Config, args: list[str]):
    banderas = {"--traducir", "--extraer", "--solo-compilar", "--sin-portada", "--sin-imagenes"}
    opciones = {"--pdf", "--idioma", "--capitulos", "--bloque-chars", "--pasadas"}
    finales: list[str] = []
    pdf: str | None = None
    i = 0
    while i < len(args):
        actual = args[i]
        if actual in banderas:
            finales.append(actual)
            i += 1
            continue
        if actual not in opciones:
            raise ErrorPolitica(f"Argumento no permitido en libro: {actual}")
        if i + 1 >= len(args):
            raise ErrorPolitica(f"Falta el valor de {actual}")
        valor = args[i + 1]
        if actual == "--pdf":
            pdf = valor
        elif actual == "--idioma":
            if valor.casefold() not in IDIOMAS:
                raise ErrorPolitica(f"Idioma no permitido: {valor}")
            finales.extend([actual, valor])
        elif actual == "--capitulos":
            if not re.fullmatch(r"[\d,\- ]{1,50}", valor):
                raise ErrorPolitica("Rango de capítulos inválido")
            finales.extend([actual, valor])
        elif actual == "--bloque-chars":
            try:
                numero = int(valor)
            except ValueError as exc:
                raise ErrorPolitica("--bloque-chars debe ser entero") from exc
            if not 1000 <= numero <= 200000:
                raise ErrorPolitica("--bloque-chars fuera de rango")
            finales.extend([actual, str(numero)])
        elif actual == "--pasadas":
            try:
                numero = int(valor)
            except ValueError as exc:
                raise ErrorPolitica("--pasadas debe ser entero") from exc
            if not 1 <= numero <= 10:
                raise ErrorPolitica("--pasadas fuera de rango")
            finales.extend([actual, str(numero)])
        i += 2

    if not pdf:
        raise ErrorPolitica("libro requiere --pdf con un archivo de entrada/")
    ruta = Path(pdf).expanduser()
    if not ruta.is_absolute():
        ruta = cfg.dir_entrada / ruta
    try:
        ruta = ruta.resolve()
        ruta.relative_to(cfg.dir_entrada.resolve())
    except (OSError, ValueError) as exc:
        raise ErrorPolitica(
            "El PDF debe estar dentro del directorio de entrada del agente"
        ) from exc
    if not ruta.is_file():
        raise ErrorPolitica("No existe el PDF indicado")
    marca = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    salida = cfg.dir_salida / f"libro-{marca}.pdf"
    salida.parent.mkdir(parents=True, exist_ok=True)
    finales.extend(["--pdf", str(ruta), "--salida", str(salida)])
    return finales, salida, ""


def _politica_wifi(cfg: Config, args: list[str]):
    if args not in (["status"], []):
        raise ErrorPolitica(
            "Por correo solo se permite 'wifi status'; escaneo, captura y "
            "crack quedan fuera por requerir sudo y autorización expresa."
        )
    return ["status"], None, "Auditoría WiFi en modo solo lectura."


_POLITICAS = {
    "sistema": _politica_sistema,
    "redes": _politica_redes,
    "datos": _politica_datos,
    "libro": _politica_libro,
    "auditoria_wifi": _politica_wifi,
}
