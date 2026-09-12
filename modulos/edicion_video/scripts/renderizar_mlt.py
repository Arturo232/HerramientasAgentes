"""Renderiza un proyecto .mlt (MLT/Shotcut) a un archivo de video con melt."""

import argparse
import os
import sys

import comun

PRESETS = {
    "h264": {"vcodec": "libx264", "acodec": "aac", "an": "1"},
    "hevc": {"vcodec": "libx265", "acodec": "aac", "an": "1"},
    "webm": {"vcodec": "libvpx", "acodec": "libvorbis", "an": "1"},
    "gif": {"vcodec": "gif", "an": "0"},
}


def _sugerir_preset(salida):
    ext = os.path.splitext(salida)[1].lower()
    if ext == ".webm":
        return "webm"
    if ext == ".gif":
        return "gif"
    if ext in (".mkv", ".mov", ".mp4", ".m4v"):
        return "h264"
    return "h264"


def renderizar(mlt, salida, preset=None, crf=None, escala=None, threads=0):
    melt = comun.ruta_bin("melt")
    if not os.path.exists(mlt):
        raise FileNotFoundError("No existe el proyecto %s" % mlt)
    preset = preset or _sugerir_preset(salida)
    conf = dict(PRESETS.get(preset, PRESETS["h264"]))

    cmd = [melt, mlt, "-consumer", "avformat:%s" % os.path.abspath(salida)]
    for k, v in conf.items():
        cmd.append("%s=%s" % (k, v))
    if crf is not None and conf.get("vcodec") in ("libx264", "libx265"):
        cmd.append("crf=%s" % crf)
    if threads:
        cmd.append("threads=%d" % threads)

    p = comun.ejecutar(cmd)
    if p.returncode != 0:
        raise RuntimeError("melt falló:\n" + (p.stderr or p.stdout)[-2000:])

    if escala:
        ff = comun.ruta_bin("ffmpeg")
        tmp = os.path.abspath(salida) + ".pre_escala.mp4"
        os.rename(salida, tmp)
        cmd2 = [ff, "-y", "-i", tmp, "-vf", "scale=%s" % escala,
                "-c:v", "libx264", "-c:a", "copy", os.path.abspath(salida)]
        p2 = comun.ejecutar(cmd2)
        os.remove(tmp)
        if p2.returncode != 0:
            raise RuntimeError("ffmpeg (escala) falló:\n" + (p2.stderr or p2.stdout)[-2000:])
    return os.path.abspath(salida)


def main(argv):
    ap = argparse.ArgumentParser(description="Renderiza un .mlt a video con melt.")
    ap.add_argument("--input", "-i", required=True, help="Proyecto .mlt")
    ap.add_argument("--salida", "-o", required=True, help="Archivo de salida")
    ap.add_argument("--preset", choices=sorted(PRESETS.keys()), help="Preset de exportación")
    ap.add_argument("--crf", type=str, help="Calidad (CRF) para h264/hevc, p.ej. 23")
    ap.add_argument("--escala", help="Escala final, p.ej. 1920x1080 o -2:720")
    ap.add_argument("--threads", type=int, default=0, help="Hilos de codificación")
    args = ap.parse_args(argv)

    try:
        ruta = renderizar(args.input, args.salida, args.preset, args.crf,
                          args.escala, args.threads)
        print("Renderizado en %s" % ruta)
        return 0
    except Exception as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
