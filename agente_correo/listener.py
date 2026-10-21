"""Listener de correo: polling, lista blanca, deduplicación y respuesta.

Uso:
    python -m agente_correo.listener --once
    python -m agente_correo.listener --once --dry-run --fixture agente_correo/tests/fixtures
    python -m agente_correo.listener            # bucle 24/7
"""

from __future__ import annotations

# Permite ejecutar el archivo directamente además de `python -m agente_correo.listener`.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path

    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
    from agente_correo.listener import main as _main

    raise SystemExit(_main())

import argparse
import json
import logging
import re
import signal
import sys
import time
from pathlib import Path
from typing import Any

from . import dispatcher, gmail_client
from .config import Config, ErrorConfig
from .db import BaseDatos
from .orquestador import ErrorEnrutamiento, PuenteSelector, ResultadoTarea, redactar
from .parser import (
    Mensaje,
    detectar_control,
    es_auto_respuesta,
    es_mensaje_del_agente,
    parsear_mensaje,
    remitente_autorizado,
)

log = logging.getLogger("agente_correo.listener")


class Etiquetas:
    def __init__(self, cfg: Config, servicio):
        self.cfg = cfg
        self.servicio = servicio
        self.cache: dict[str, str] = {}

    def id(self, sufijo: str) -> str:
        return gmail_client.etiqueta_id(
            self.servicio, self.cfg.ruta_etiqueta(sufijo), self.cache
        )

    def preparar(self) -> None:
        for sufijo in ("Procesado", "Denegado", "Error"):
            try:
                self.id(sufijo)
            except Exception as exc:
                log.warning("No se pudo preparar la etiqueta %s: %s", sufijo, exc)


def _motivo_denegacion(mensaje: Mensaje, cfg: Config) -> str:
    if not mensaje.from_valido or not mensaje.from_email:
        return "cabecera From ausente, inválida o múltiple"
    if es_mensaje_del_agente(mensaje.from_email, cfg.gmail_user):
        return "mensaje del propio agente"
    automatico, motivo = es_auto_respuesta(mensaje.headers)
    if automatico:
        return f"auto-respuesta ({motivo})"
    if not remitente_autorizado(mensaje.from_email, cfg.autorizado_from):
        return "remitente no autorizado"
    return ""


def _reservar(db: BaseDatos, mensaje: Mensaje) -> bool:
    try:
        return db.reservar(
            mensaje.clave_idempotencia,
            mensaje.gmail_id,
            mensaje.thread_id,
            mensaje.from_email or mensaje.from_raw,
            mensaje.subject,
        )
    except Exception:
        log.exception("No se pudo reservar el mensaje en SQLite")
        return False


def _marcar(
    etiquetas: Etiquetas | None,
    mensaje: Mensaje,
    sufijo: str,
    *,
    archivar: bool = False,
) -> None:
    if etiquetas is None or not mensaje.gmail_id:
        return
    try:
        etiqueta = etiquetas.id(sufijo)
        quitar = ["UNREAD"]
        if archivar:
            quitar.append("INBOX")
        gmail_client.modificar_mensaje(
            etiquetas.servicio,
            mensaje.gmail_id,
            agregar=[etiqueta],
            quitar=quitar,
        )
    except Exception:
        log.exception("No se pudo etiquetar/marcar el mensaje %s", mensaje.gmail_id)


def _intencion(mensaje: Mensaje, cfg: Config) -> str:
    texto = mensaje.body.replace("\x00", "").strip()
    texto = re.sub(r"^\s*AGENTE\s*:\s*", "", texto, flags=re.IGNORECASE)
    if not texto:
        texto = mensaje.subject.replace("\x00", "").strip()
    return texto[: cfg.max_cuerpo_chars].strip()


def _cuerpo_control(
    comando: str, pausado_antes: bool, motivo: str, dry_run: bool
) -> str:
    prefijo = "[DRY-RUN] " if dry_run else ""
    if comando in {"PAUSA", "STOP"}:
        if pausado_antes:
            return (
                f"{prefijo}El agente ya estaba pausado ({motivo or 'sin motivo'}). "
                "Enviá REANUDAR para volver a procesar."
            )
        return (
            f"{prefijo}Comando {comando} recibido. El agente dejó de procesar "
            "correos hasta que envíes REANUDAR."
        )
    if not pausado_antes:
        return f"{prefijo}Comando REANUDAR recibido, pero el agente ya estaba activo."
    return (
        f"{prefijo}Comando REANUDAR recibido. El agente vuelve a procesar correos."
    )


def _cuerpo_ayuda() -> str:
    return (
        "No entendí el comando. Este buzón no es un chat libre: responde con "
        "una de estas órdenes, sola en el cuerpo:\n\n"
        "- estado del sistema\n"
        "- diagnóstico de red\n"
        "- genera un excel de prueba\n"
        "- PAUSA\n"
        "- REANUDAR\n\n"
        "Ejemplo: escribe solamente: estado del sistema"
    )


def _cuerpo_limite(cfg: Config) -> str:
    return (
        "No se ejecutó la tarea: se alcanzó el límite configurado de "
        f"{cfg.max_tareas_hora} tareas por hora. El mensaje quedó registrado; "
        "intenta de nuevo más tarde."
    )


def procesar_payload(
    payload: dict[str, Any],
    cfg: Config,
    db: BaseDatos,
    puente: PuenteSelector,
    *,
    dry_run: bool,
    servicio=None,
    etiquetas: Etiquetas | None = None,
) -> str:
    """Procesa un mensaje de Gmail (o un fixture) y devuelve el desenlace."""
    try:
        mensaje = parsear_mensaje(payload, cfg.max_cuerpo_chars)
    except Exception:
        log.exception("Payload de Gmail inválido; se ignora")
        return "invalido"

    log.info(
        "Mensaje %s de %s | asunto=%r | hilo=%s",
        mensaje.gmail_id or mensaje.message_id,
        mensaje.from_email or mensaje.from_raw or "(sin From)",
        mensaje.asunto_corto,
        mensaje.thread_id,
    )

    motivo = _motivo_denegacion(mensaje, cfg)
    if not motivo:
        pausado_antes, motivo_pausa = db.esta_pausado()
        control = detectar_control(mensaje.body)
        if not control and not mensaje.body.strip():
            control = detectar_control(mensaje.subject)
        if control:
            if not _reservar(db, mensaje):
                return "duplicado"
            if not dry_run:
                if control in {"PAUSA", "STOP"}:
                    db.pausar(motivo=f"correo {control} de {mensaje.from_email}")
                else:
                    db.reanudar()
            cuerpo = _cuerpo_control(control, pausado_antes, motivo_pausa, dry_run)
            try:
                envio = dispatcher.responder_texto(
                    cfg, mensaje, cuerpo, servicio=servicio, dry_run=dry_run
                )
            except Exception as exc:
                log.exception("Falló la respuesta al comando %s", control)
                db.finalizar(
                    mensaje.clave_idempotencia,
                    "error",
                    detalle=redactar(str(exc)),
                )
                if not dry_run:
                    _marcar(etiquetas, mensaje, "Error")
                return "error"
            db.finalizar(
                mensaje.clave_idempotencia,
                "control",
                detalle=f"{control} {envio.get('modo', '')}".strip(),
            )
            if not dry_run:
                _marcar(etiquetas, mensaje, "Procesado")
            return "control"

        if pausado_antes:
            log.info(
                "PAUSADO (%s): se omite %s sin marcarlo para poder procesarlo "
                "después de REANUDAR",
                motivo_pausa or "sin motivo",
                mensaje.gmail_id,
            )
            return "pausado"
    else:
        if not _reservar(db, mensaje):
            log.info("Mensaje ya registrado; no se reprocesa")
            return "duplicado"
        db.finalizar(
            mensaje.clave_idempotencia, "denegado", detalle=motivo
        )
        log.warning(
            "DENEGADO (%s) de %s; se archiva sin ejecutar",
            motivo,
            mensaje.from_email or mensaje.from_raw or "(sin From)",
        )
        if not dry_run:
            _marcar(etiquetas, mensaje, "Denegado", archivar=True)
        return "denegado"

    if db.contar_ejecutadas_ultima_hora() >= cfg.max_tareas_hora:
        if not _reservar(db, mensaje):
            return "duplicado"
        try:
            dispatcher.responder_texto(
                cfg,
                mensaje,
                _cuerpo_limite(cfg),
                servicio=servicio,
                dry_run=dry_run,
            )
        except Exception:
            log.exception("No se pudo avisar del límite de tareas")
        db.finalizar(mensaje.clave_idempotencia, "limite")
        if not dry_run:
            _marcar(etiquetas, mensaje, "Procesado")
        log.warning("Límite de %s tareas/hora alcanzado", cfg.max_tareas_hora)
        return "limite"

    if not _reservar(db, mensaje):
        log.info("Mensaje ya registrado; no se reprocesa")
        return "duplicado"

    intencion = _intencion(mensaje, cfg)
    if not intencion:
        resultado = ResultadoTarea(
            ok=False,
            herramienta="(sin intención)",
            comando=(),
            codigo=-1,
            stdout="",
            stderr="",
            datos=None,
            artefactos=(),
            duracion=0.0,
            error="El cuerpo y el asunto están vacíos.",
        )
    elif dry_run:
        try:
            enrutamiento = puente.enrutar(intencion)
            resultado = ResultadoTarea(
                ok=True,
                herramienta=enrutamiento.herramienta,
                comando=(
                    str(cfg.python_bin),
                    str(cfg.repo_dir / enrutamiento.script_relativo),
                    *enrutamiento.argumentos,
                ),
                codigo=0,
                stdout="",
                stderr="",
                datos={
                    "mensaje": "DRY-RUN: se ejecutaría esta herramienta.",
                    "argumentos": list(enrutamiento.argumentos),
                },
                artefactos=(),
                duracion=0.0,
                nota=enrutamiento.nota,
            )
        except Exception as exc:
            resultado = ResultadoTarea(
                ok=False,
                herramienta="(sin enrutar)",
                comando=(),
                codigo=-1,
                stdout="",
                stderr="",
                datos=None,
                artefactos=(),
                duracion=0.0,
                error=redactar(str(exc)),
            )
    else:
        try:
            resultado = puente.ejecutar(intencion)
        except ErrorEnrutamiento as exc:
            if str(exc).startswith("No entendí el comando"):
                resultado = None
            else:
                resultado = ResultadoTarea(
                    ok=False,
                    herramienta="(sin ejecutar)",
                    comando=(),
                    codigo=-1,
                    stdout="",
                    stderr="",
                    datos=None,
                    artefactos=(),
                    duracion=0.0,
                    error=redactar(str(exc)),
                )
        except Exception as exc:
            resultado = ResultadoTarea(
                ok=False,
                herramienta="(sin ejecutar)",
                comando=(),
                codigo=-1,
                stdout="",
                stderr="",
                datos=None,
                artefactos=(),
                duracion=0.0,
                error=redactar(str(exc)),
            )

    if resultado is None:
        try:
            envio = dispatcher.responder_texto(
                cfg,
                mensaje,
                _cuerpo_ayuda(),
                servicio=servicio,
                dry_run=dry_run,
            )
        except Exception as exc:
            log.exception("Falló el envío de la ayuda")
            db.finalizar(
                mensaje.clave_idempotencia,
                "error_envio",
                detalle=redactar(str(exc)),
            )
            if not dry_run:
                _marcar(etiquetas, mensaje, "Error")
            return "error_envio"
        db.finalizar(
            mensaje.clave_idempotencia,
            "ayuda",
            detalle="comando no reconocido",
        )
        log.info(
            "Ayuda %s",
            "guardada en " + str(envio.get("ruta"))
            if not envio.get("enviado")
            else "enviada",
        )
        if not dry_run:
            _marcar(etiquetas, mensaje, "Procesado")
        return "ayuda"

    estado = "ok" if resultado.ok else "error"
    ejecutada = not dry_run and resultado.herramienta in {
        "sistema", "redes", "datos", "libro", "auditoria_wifi"
    }
    db.finalizar(
        mensaje.clave_idempotencia,
        "dry-run" if dry_run else estado,
        herramienta=resultado.herramienta,
        codigo_salida=resultado.codigo,
        ejecutado=ejecutada,
        detalle=resultado.error or "",
    )
    log.info(
        "%s: herramienta=%s código=%s duración=%.1fs",
        "DRY-RUN" if dry_run else estado.upper(),
        resultado.herramienta,
        resultado.codigo,
        resultado.duracion,
    )

    try:
        envio = dispatcher.responder(
            cfg,
            mensaje,
            resultado,
            servicio=servicio,
            dry_run=dry_run,
        )
    except Exception as exc:
        log.exception("Falló el envío de la respuesta")
        db.finalizar(
            mensaje.clave_idempotencia,
            "error_envio",
            herramienta=resultado.herramienta,
            codigo_salida=resultado.codigo,
            ejecutado=ejecutada,
            detalle=redactar(str(exc)),
        )
        if not dry_run:
            _marcar(etiquetas, mensaje, "Error")
        return "error_envio"

    log.info(
        "Respuesta %s%s",
        "guardada en " + str(envio.get("ruta"))
        if not envio.get("enviado")
        else "enviada",
        "" if envio.get("enviado") else " (dry-run)",
    )
    if not dry_run:
        _marcar(
            etiquetas, mensaje, "Procesado" if resultado.ok else "Error"
        )
    return "dry-run" if dry_run else estado


def cargar_fixtures(ruta: str | Path) -> list[dict[str, Any]]:
    ruta = Path(ruta)
    if ruta.is_dir():
        archivos = sorted(ruta.glob("*.json"))
    elif ruta.is_file():
        archivos = [ruta]
    else:
        raise FileNotFoundError(f"No existe el fixture: {ruta}")
    mensajes: list[dict[str, Any]] = []
    for archivo in archivos:
        datos = json.loads(archivo.read_text(encoding="utf-8"))
        if isinstance(datos, list):
            mensajes.extend(d for d in datos if isinstance(d, dict))
        elif isinstance(datos, dict) and isinstance(datos.get("mensajes"), list):
            mensajes.extend(d for d in datos["mensajes"] if isinstance(d, dict))
        elif isinstance(datos, dict):
            mensajes.append(datos)
    return mensajes


def _pasada(
    servicio,
    cfg: Config,
    db: BaseDatos,
    puente: PuenteSelector,
    etiquetas: Etiquetas | None,
    limite: int,
    dry_run: bool,
) -> int:
    ids = gmail_client.listar_no_leidos(servicio, limite=limite)
    log.info("Mensajes no leídos en INBOX: %d", len(ids))
    procesados = 0
    for message_id in ids[:limite]:
        try:
            payload = gmail_client.obtener_mensaje(servicio, message_id)
        except Exception:
            log.exception("No se pudo leer el mensaje %s", message_id)
            continue
        procesar_payload(
            payload,
            cfg,
            db,
            puente,
            dry_run=dry_run,
            servicio=servicio,
            etiquetas=etiquetas,
        )
        procesados += 1
        time.sleep(0.2)
    return procesados


def _configurar_logging(cfg: Config, verbose: bool) -> None:
    nivel = logging.DEBUG if verbose else getattr(logging, cfg.log_level, logging.INFO)
    logging.basicConfig(
        level=nivel,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
        force=True,
    )


def _esperar(segundos: int, stop: dict[str, bool]) -> None:
    for _ in range(max(1, segundos)):
        if stop["valor"]:
            return
        time.sleep(1)


def _bucle(
    servicio,
    cfg: Config,
    db: BaseDatos,
    puente: PuenteSelector,
    etiquetas: Etiquetas | None,
    limite: int,
    dry_run: bool,
) -> int:
    stop = {"valor": False}

    def _parar(*_args):
        stop["valor"] = True

    signal.signal(signal.SIGTERM, _parar)
    signal.signal(signal.SIGINT, _parar)
    log.info(
        "Escuchando %s con polling cada %ss (límite %s/hora)",
        cfg.gmail_user,
        cfg.poll_segundos,
        cfg.max_tareas_hora,
    )
    errores = 0
    while not stop["valor"]:
        try:
            _pasada(servicio, cfg, db, puente, etiquetas, limite, dry_run)
            errores = 0
        except gmail_client.ErrorAuth as exc:
            errores += 1
            log.error("Autorización: %s", exc)
        except Exception:
            errores += 1
            log.exception("Error en la pasada de correo")
        espera = (
            cfg.poll_segundos
            if errores == 0
            else min(cfg.poll_segundos * (2 ** min(errores, 4)), 300)
        )
        _esperar(espera, stop)
    log.info("Listener detenido")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Agente de correo 24/7 sobre Gmail API y el selector local"
    )
    parser.add_argument(
        "--once", action="store_true", help="procesa los no leídos actuales y sale"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="no ejecuta herramientas ni envía; escribe .eml de muestra",
    )
    parser.add_argument(
        "--fixture",
        help="archivo o carpeta JSON con payloads de Gmail (implica --dry-run)",
    )
    parser.add_argument("--db", help="ruta alternativa de la base SQLite")
    parser.add_argument(
        "--limit", type=int, default=20, help="máximo de mensajes por pasada"
    )
    parser.add_argument("--verbose", action="store_true", help="log DEBUG")
    args = parser.parse_args(argv)

    if args.fixture and not args.dry_run:
        parser.error("--fixture solo se puede usar junto con --dry-run")
    limite = max(1, min(args.limit, 200))

    try:
        cfg = Config.cargar()
        cfg.preparar_directorios()
    except (ErrorConfig, OSError) as exc:
        print(f"ERROR de configuración: {exc}", file=sys.stderr)
        return 2
    _configurar_logging(cfg, args.verbose)

    if args.db:
        db_path: str | Path = Path(args.db).expanduser()
    elif args.dry_run:
        # Cada dry-run arranca limpio para poder repetir la demostración.
        db_path = ":memory:"
    else:
        db_path = cfg.dir_datos / "agente_correo.db"
    try:
        db = BaseDatos(db_path)
    except Exception as exc:
        log.error("No se pudo abrir la base SQLite %s: %s", db_path, exc)
        return 2
    puente = PuenteSelector(cfg)
    try:
        puente.validar_config()
    except Exception as exc:
        log.error("Configuración de herramientas inválida: %s", exc)
        db.cerrar()
        return 2

    for fila in db.reservas_colgadas(30):
        log.warning(
            "Reserva colgada (posible corte): %s estado=%s; no se reprocesa",
            fila["message_id"],
            fila["estado"],
        )

    pausado, motivo = db.esta_pausado()
    if pausado:
        log.warning("El agente está PAUSADO (%s). Enviá REANUDAR.", motivo or "sin motivo")

    if args.fixture:
        try:
            payloads = cargar_fixtures(args.fixture)
        except (OSError, json.JSONDecodeError) as exc:
            log.error("No se pudieron leer los fixtures: %s", exc)
            db.cerrar()
            return 2
        resultados: dict[str, int] = {}
        for payload in payloads:
            desenlace = procesar_payload(
                payload,
                cfg,
                db,
                puente,
                dry_run=True,
                servicio=None,
                etiquetas=None,
            )
            resultados[desenlace] = resultados.get(desenlace, 0) + 1
        log.info("DRY-RUN fixtures: %s", resultados)
        db.cerrar()
        return 0

    try:
        servicio = gmail_client.construir_servicio(cfg)
    except gmail_client.ErrorAuth as exc:
        log.error("%s", exc)
        if args.dry_run:
            log.error(
                "Sin credenciales reales no se puede leer Gmail. Usa: "
                "--once --dry-run --fixture agente_correo/tests/fixtures"
            )
        db.cerrar()
        return 2
    except gmail_client.ErrorGmail as exc:
        log.error("No se pudo crear el cliente de Gmail: %s", exc)
        db.cerrar()
        return 2
    except Exception as exc:
        log.error(
            "No se pudo crear el cliente de Gmail: %s",
            redactar(str(exc) or exc.__class__.__name__),
        )
        db.cerrar()
        return 2

    etiquetas = None if args.dry_run else Etiquetas(cfg, servicio)
    if etiquetas is not None:
        etiquetas.preparar()

    try:
        if args.once:
            _pasada(
                servicio,
                cfg,
                db,
                puente,
                etiquetas,
                limite,
                args.dry_run,
            )
            return 0
        return _bucle(
            servicio,
            cfg,
            db,
            puente,
            etiquetas,
            limite,
            args.dry_run,
        )
    except gmail_client.ErrorAuth as exc:
        log.error("Autorización: %s", exc)
        return 1
    except KeyboardInterrupt:
        return 0
    except Exception:
        log.exception("Error inesperado en el listener")
        return 1
    finally:
        db.cerrar()


if __name__ == "__main__":
    raise SystemExit(main())
