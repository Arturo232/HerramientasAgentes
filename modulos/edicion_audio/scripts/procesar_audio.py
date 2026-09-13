"""Departamento de Audio: mejora de voz y mezcla con música.

Reutiliza la detección de binarios del Departamento de Edición de Video
(Shotcut/MLT/ffmpeg) y aplica cadenas de filtros de ffmpeg para limpiar la voz
(denoise, EQ, compresión, de-esser, normalización EBU R128) y mezclarla con
música usando ducking (sidechain compression).
"""

import argparse
import json
import os
import sys

_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _cand in ("editor-video", "edicion_video"):
    _p = os.path.join(_BASE, _cand, "scripts")
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

import comun

PRESETS = {
    "natural": {"highpass": 85, "denoise": None, "eq": False,
                "compresor": False, "deesser": False, "loudnorm": True},
    "voz_limpia": {"highpass": 85, "denoise": "medio", "eq": True,
                   "compresor": True, "deesser": True, "loudnorm": True},
    "fuerte": {"highpass": 90, "denoise": "fuerte", "eq": True,
               "compresor": True, "deesser": True, "loudnorm": True},
}

DENOISE = {
    "suave": "afftdn=nr=6:nf=-30",
    "medio": "afftdn=nr=12:nf=-25",
    "fuerte": "afftdn=nr=18:nf=-20",
}


def _cadena_voz(preset, opciones):
    p = dict(PRESETS.get(preset, PRESETS["voz_limpia"]))
    for k, v in (opciones or {}).items():
        if v is not None:
            p[k] = v
    f = []
    if p.get("highpass"):
        f.append("highpass=f=%s" % p["highpass"])
    dn = p.get("denoise")
    if dn and dn != "no":
        f.append(DENOISE.get(dn, DENOISE["medio"]))
    if p.get("eq"):
        f += [
            "equalizer=f=200:t=q:w=1:g=-2",
            "equalizer=f=350:t=q:w=1:g=-1.5",
            "equalizer=f=3000:t=q:w=1:g=2.5",
            "highshelf=f=8000:g=1.5",
        ]
    if p.get("compresor"):
        f.append("acompressor=threshold=-20dB:ratio=3:attack=8:release=180:makeup=2")
    if p.get("deesser"):
        f.append("deesser=i=0.5")
    if p.get("loudnorm"):
        lufs = p.get("lufs", -16)
        f.append("loudnorm=I=%s:TP=-1.5:LRA=11" % lufs)
    return ",".join(f) if f else "anull"


def _tiene_video(ruta):
    try:
        return comun.inspeccionar_media(ruta).get("tiene_video", False)
    except Exception:
        return False


def mejorar(entrada, salida=None, preset="voz_limpia", opciones=None):
    ff = comun.ruta_bin("ffmpeg")
    cadena = _cadena_voz(preset, opciones)
    if salida is None:
        base, _ = os.path.splitext(entrada)
        salida = base + "_voz.mp4" if _tiene_video(entrada) else base + "_voz.wav"
    cmd = [ff, "-y", "-i", entrada, "-af", cadena]
    if _tiene_video(entrada):
        cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-c:a", "pcm_s16le"]
    cmd.append(salida)
    p = comun.ejecutar(cmd)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg (mejorar voz) falló:\n" + (p.stderr or p.stdout)[-2000:])
    return os.path.abspath(salida)


def mezclar(entrada, musica, salida=None, preset="voz_limpia", opciones=None,
            volumen_musica=0.12, ducking=True, fundido=True, procesar_voz=True):
    ff = comun.ruta_bin("ffmpeg")
    cadena = _cadena_voz(preset, opciones) if procesar_voz else "anull"
    if salida is None:
        base, _ = os.path.splitext(entrada)
        salida = base + "_final.mp4"
    dur = comun.inspeccionar_media(entrada).get("duracion", 0) or 0
    out_st = max(dur - 2.5, 0.5)

    mus = "[1:a]volume=%s" % volumen_musica
    if fundido:
        mus += ",afade=t=in:st=0:d=1.5,afade=t=out:st=%.2f:d=2.5" % out_st
    mus += "[mus]"

    fc = ["[0:a]%s[voz]" % cadena, mus]
    if ducking:
        fc.append("[voz]asplit=2[v1][v2]")
        fc.append("[mus][v1]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=350[musd]")
        fc.append("[v2][musd]amix=inputs=2:duration=first:normalize=0[aout]")
    else:
        fc.append("[voz][mus]amix=inputs=2:duration=first:normalize=0[aout]")

    cmd = [ff, "-y", "-i", entrada, "-stream_loop", "-1", "-i", musica,
           "-filter_complex", ";".join(fc), "-map", "0:v?", "-map", "[aout]",
           "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", salida]
    p = comun.ejecutar(cmd)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg (mezcla) falló:\n" + (p.stderr or p.stdout)[-2000:])
    return os.path.abspath(salida)


def mezclar_con_sfx(entrada, musica, sfx, salida=None, volumen_musica=0.13,
                    ducking=True, procesar_voz=False, preset="voz_limpia",
                    opciones=None):
    ff = comun.ruta_bin("ffmpeg")
    if salida is None:
        base, _ = os.path.splitext(entrada)
        salida = base + "_produccion.mp4"
    dur = comun.inspeccionar_media(entrada).get("duracion", 0) or 0
    cadena = _cadena_voz(preset, opciones) if procesar_voz else "anull"

    cmd = [ff, "-y", "-i", entrada, "-stream_loop", "-1", "-i", musica]
    for e in sfx:
        cmd += ["-i", e["recurso"]]

    fc = ["[0:a]%s[voz]" % cadena]
    fc.append("[1:a]volume=%s,afade=t=in:st=0:d=1.5,afade=t=out:st=%.2f:d=2.5[mus]"
              % (volumen_musica, max(dur - 2.5, 0.5)))
    if ducking:
        fc.append("[voz]asplit=2[v1][v2]")
        fc.append("[mus][v1]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=350[musd]")
        mezcla = "[v2][musd]"
    else:
        mezcla = "[voz][mus]"
    n = 2
    for i, e in enumerate(sfx):
        delay = int(float(e.get("inicio", 0)) * 1000)
        vol = e.get("volumen", 0.5)
        fc.append("[%d:a]adelay=%d|%d,volume=%s[sx%d]" % (2 + i, delay, delay, vol, i))
        mezcla += "[sx%d]" % i
        n += 1
    fc.append("%samix=inputs=%d:duration=first:normalize=0,alimiter=limit=0.89[aout]"
              % (mezcla, n))

    cmd += ["-filter_complex", ";".join(fc), "-map", "0:v?", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", salida]
    p = comun.ejecutar(cmd)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg (producción) falló:\n" + (p.stderr or p.stdout)[-2000:])
    return os.path.abspath(salida)


def normalizar(entrada, salida=None, lufs=-16):
    ff = comun.ruta_bin("ffmpeg")
    if salida is None:
        base, ext = os.path.splitext(entrada)
        salida = base + "_norm" + (ext or ".mp4")
    cmd = [ff, "-y", "-i", entrada, "-af", "loudnorm=I=%s:TP=-1.5:LRA=11" % lufs,
           "-c:v", "copy" if _tiene_video(entrada) else "none",
           "-c:a", "aac" if _tiene_video(entrada) else "pcm_s16le", salida]
    p = comun.ejecutar(cmd)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg (normalizar) falló:\n" + (p.stderr or p.stdout)[-2000:])
    return os.path.abspath(salida)


def _opciones(args):
    o = {"denoise": None if args.sin_denoise else args.denoise,
         "eq": None, "compresor": None, "deesser": None}
    if args.sin_eq:
        o["eq"] = False
    if args.sin_compresor:
        o["compresor"] = False
    if args.sin_deesser:
        o["deesser"] = False
    return o


def main(argv):
    ap = argparse.ArgumentParser(
        prog="procesar_audio",
        description="Departamento de Audio: mejora de voz y mezcla con música.")
    sub = ap.add_subparsers(dest="comando")

    for nombre in ("mejorar", "mezclar", "masterizar"):
        p = sub.add_parser(nombre)
        p.add_argument("--input", "-i", required=True)
        p.add_argument("--salida", "-o")
        p.add_argument("--preset", choices=sorted(PRESETS.keys()), default="voz_limpia")
        p.add_argument("--denoise", choices=sorted(DENOISE.keys()), default="medio")
        p.add_argument("--sin-denoise", action="store_true")
        p.add_argument("--sin-eq", action="store_true")
        p.add_argument("--sin-compresor", action="store_true")
        p.add_argument("--sin-deesser", action="store_true")
        if nombre in ("mezclar", "masterizar"):
            p.add_argument("--musica", "-m", required=(nombre == "mezclar"))
            p.add_argument("--volumen", type=float, default=0.12)
            p.add_argument("--sin-ducking", action="store_true")
            p.add_argument("--sin-procesar-voz", action="store_true",
                           help="No re-procesar la voz (si ya está mejorada)")

    p = sub.add_parser("produccion", help="Mezcla voz + música + SFX (whoosh/hits)")
    p.add_argument("--input", "-i", required=True)
    p.add_argument("--musica", "-m", required=True)
    p.add_argument("--sfx", required=True, help="JSON [{recurso, inicio, volumen}, ...]")
    p.add_argument("--salida", "-o")
    p.add_argument("--volumen", type=float, default=0.13)
    p.add_argument("--sin-ducking", action="store_true")

    args = ap.parse_args(argv)
    try:
        if args.comando == "mejorar":
            print("Audio mejorado en %s" % mejorar(args.input, args.salida, args.preset, _opciones(args)))
        elif args.comando == "mezclar":
            print("Audio mezclado en %s" % mezclar(
                args.input, args.musica, args.salida, args.preset, _opciones(args),
                args.volumen, not args.sin_ducking,
                procesar_voz=not args.sin_procesar_voz))
        elif args.comando == "masterizar":
            if getattr(args, "musica", None):
                print("Máster final en %s" % mezclar(
                    args.input, args.musica, args.salida, args.preset, _opciones(args),
                    args.volumen, not args.sin_ducking,
                    procesar_voz=not args.sin_procesar_voz))
            else:
                print("Voz mejorada en %s" % mejorar(args.input, args.salida, args.preset, _opciones(args)))
        elif args.comando == "produccion":
            with open(args.sfx, "r", encoding="utf-8") as f:
                sfx = json.load(f)
            print("Producción final en %s" % mezclar_con_sfx(
                args.input, args.musica, sfx, args.salida, args.volumen,
                not args.sin_ducking))
        else:
            ap.print_help()
        return 0
    except Exception as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
