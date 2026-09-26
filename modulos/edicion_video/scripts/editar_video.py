"""Punto de entrada del Departamento de Edición de Video.

Subcomandos:
  editar          plan.json -> .mlt -> video final
  extraer-audio   extrae la pista de audio de un video
  convertir       convierte/comprime/cambia resolución con ffmpeg
"""

import json
import os
import subprocess
import sys

_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(_SCRIPTS)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
import comun  # noqa: E402
from nucleo import cli  # noqa: E402
from nucleo.contrato import exito  # noqa: E402
from nucleo.errores import AgenteError  # noqa: E402
from nucleo.registro import artefacto  # noqa: E402

SCRIPTS = _SCRIPTS


def _run(py_file, args):
    cmd = [sys.executable, os.path.join(SCRIPTS, py_file)] + args
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if p.stdout:
        print(p.stdout, end="", file=sys.stderr)
    if p.returncode != 0:
        print((p.stderr or p.stdout)[-2000:], file=sys.stderr)
    return p.returncode


def cmd_editar(ns):
    plan = os.path.abspath(ns.plan)
    with open(plan, "r", encoding="utf-8") as f:
        datos = json.load(f)
    exportar = datos.get("exportar", {})
    salida = ns.salida or exportar.get("salida") or "salida.mp4"
    mlt = os.path.splitext(os.path.abspath(salida))[0] + ".mlt"

    rc = _run("generar_proyecto_mlt.py", ["--plan", plan, "--salida", mlt])
    if rc != 0:
        raise AgenteError("edicion_video", "generarMlt",
                          "fallo generar_proyecto_mlt (rc=%s)" % rc)
    args_render = ["--input", mlt, "--salida", salida]
    if exportar.get("preset"):
        args_render += ["--preset", exportar["preset"]]
    if exportar.get("crf"):
        args_render += ["--crf", str(exportar["crf"])]
    if exportar.get("escala"):
        args_render += ["--escala", exportar["escala"]]
    rc = _run("renderizar_mlt.py", args_render)
    if rc != 0:
        raise AgenteError("edicion_video", "renderMlt",
                          "fallo renderizar_mlt (rc=%s)" % rc)
    return salida


def cmd_extraer_audio(ns):
    ff = comun.ruta_bin("ffmpeg")
    salida = ns.salida or os.path.splitext(ns.input)[0] + ".mp3"
    if salida.lower().endswith(".wav"):
        codec = ["-c:a", "pcm_s16le"]
    else:
        codec = ["-c:a", "libmp3lame", "-q:a", "2"]
    p = comun.ejecutar([ff, "-y", "-i", ns.input, "-vn"] + codec + [salida])
    if p.returncode != 0:
        raise AgenteError("edicion_video", "ffmpeg",
                          (p.stderr or p.stdout)[-2000:])
    return salida


def cmd_convertir(ns):
    ff = comun.ruta_bin("ffmpeg")
    cmd = [ff, "-y", "-i", ns.input]
    if ns.escala:
        cmd += ["-vf", "scale=%s" % ns.escala]
    cmd += ["-c:v", "libx264", "-crf", str(ns.crf or 23), "-preset", "medium"]
    cmd += ["-c:a", "aac"]
    cmd += [ns.salida]
    p = comun.ejecutar(cmd)
    if p.returncode != 0:
        raise AgenteError("edicion_video", "ffmpeg", (p.stderr or p.stdout)[-2000:])
    return ns.salida


def _construir(ap):
    sub = ap.add_subparsers(dest="comando")

    p = sub.add_parser("editar", help="Procesa un plan JSON de edición")
    p.add_argument("--plan", "-p", required=True)
    p.add_argument("--salida", "-o")
    cli.agregar_flags_comunes(p)

    p = sub.add_parser("extraer-audio", help="Extrae el audio de un video")
    p.add_argument("--input", "-i", required=True)
    p.add_argument("--salida", "-o")
    cli.agregar_flags_comunes(p)

    p = sub.add_parser("convertir", help="Convierte/comprime un video")
    p.add_argument("--input", "-i", required=True)
    p.add_argument("--salida", "-o", required=True)
    p.add_argument("--crf", type=int)
    p.add_argument("--escala")
    cli.agregar_flags_comunes(p)


def _accion(ns):
    if ns.comando == "editar":
        out = cmd_editar(ns)
        return exito(datos={"video": out}, artefactos=[artefacto("video", out)])
    if ns.comando == "extraer-audio":
        out = cmd_extraer_audio(ns)
        return exito(datos={"audio": out}, artefactos=[artefacto("audio", out)])
    if ns.comando == "convertir":
        out = cmd_convertir(ns)
        return exito(datos={"video": out}, artefactos=[artefacto("video", out)])
    return exito(datos={"uso": "subcomandos: editar | extraer-audio | convertir"})


if __name__ == "__main__":
    sys.exit(cli.correr(
        "edicion_video", _construir, _accion, sys.argv[1:],
        prog="editar_video",
        descripcion="Departamento de Edición de Video (Shotcut/MLT)"))
