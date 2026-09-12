"""Punto de entrada del Departamento de Edición de Video.

Subcomandos:
  editar          plan.json -> .mlt -> video final
  extraer-audio   extrae la pista de audio de un video
  convertir       convierte/comprime/cambia resolución con ffmpeg
"""

import argparse
import json
import os
import subprocess
import sys

import comun

SCRIPTS = os.path.dirname(os.path.abspath(__file__))


def _run(py_file, args):
    cmd = [sys.executable, os.path.join(SCRIPTS, py_file)] + args
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if p.stdout:
        print(p.stdout, end="")
    if p.returncode != 0:
        print((p.stderr or p.stdout)[-2000:], file=sys.stderr)
    return p.returncode


def cmd_editar(args):
    plan = os.path.abspath(args.plan)
    with open(plan, "r", encoding="utf-8") as f:
        datos = json.load(f)
    exportar = datos.get("exportar", {})
    salida = args.salida or exportar.get("salida") or "salida.mp4"
    mlt = os.path.splitext(os.path.abspath(salida))[0] + ".mlt"

    rc = _run("generar_proyecto_mlt.py", ["--plan", plan, "--salida", mlt])
    if rc != 0:
        return rc
    args_render = ["--input", mlt, "--salida", salida]
    if exportar.get("preset"):
        args_render += ["--preset", exportar["preset"]]
    if exportar.get("crf"):
        args_render += ["--crf", str(exportar["crf"])]
    if exportar.get("escala"):
        args_render += ["--escala", exportar["escala"]]
    return _run("renderizar_mlt.py", args_render)


def cmd_extraer_audio(args):
    ff = comun.ruta_bin("ffmpeg")
    salida = args.salida or os.path.splitext(args.input)[0] + ".mp3"
    if salida.lower().endswith(".wav"):
        codec = ["-c:a", "pcm_s16le"]
    else:
        codec = ["-c:a", "libmp3lame", "-q:a", "2"]
    p = comun.ejecutar([ff, "-y", "-i", args.input, "-vn"] + codec + [salida])
    if p.returncode != 0:
        print("ERROR:\n" + (p.stderr or p.stdout)[-2000:], file=sys.stderr)
        return 1
    print("Audio extraído en %s" % os.path.abspath(salida))
    return 0


def cmd_convertir(args):
    ff = comun.ruta_bin("ffmpeg")
    cmd = [ff, "-y", "-i", args.input]
    if args.escala:
        cmd += ["-vf", "scale=%s" % args.escala]
    cmd += ["-c:v", "libx264", "-crf", str(args.crf or 23), "-preset", "medium"]
    cmd += ["-c:a", "aac"]
    cmd += [args.salida]
    p = comun.ejecutar(cmd)
    if p.returncode != 0:
        print("ERROR:\n" + (p.stderr or p.stdout)[-2000:], file=sys.stderr)
        return 1
    print("Convertido en %s" % os.path.abspath(args.salida))
    return 0


def main(argv):
    ap = argparse.ArgumentParser(prog="editar_video",
                                 description="Departamento de Edición de Video (Shotcut/MLT)")
    sub = ap.add_subparsers(dest="comando")

    p = sub.add_parser("editar", help="Procesa un plan JSON de edición")
    p.add_argument("--plan", "-p", required=True)
    p.add_argument("--salida", "-o")

    p = sub.add_parser("extraer-audio", help="Extrae el audio de un video")
    p.add_argument("--input", "-i", required=True)
    p.add_argument("--salida", "-o")

    p = sub.add_parser("convertir", help="Convierte/comprime un video")
    p.add_argument("--input", "-i", required=True)
    p.add_argument("--salida", "-o", required=True)
    p.add_argument("--crf", type=int)
    p.add_argument("--escala")

    args = ap.parse_args(argv)
    if args.comando == "editar":
        return cmd_editar(args)
    if args.comando == "extraer-audio":
        return cmd_extraer_audio(args)
    if args.comando == "convertir":
        return cmd_convertir(args)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
