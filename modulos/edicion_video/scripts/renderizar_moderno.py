"""Renderiza la versión moderna de un video (vertical 9:16 u horizontal 16:9).

Aplica: encuadre/relleno, color grading, sharpen, B-roll superpuesto con
fundido, zoom suave opcional, barra de progreso, títulos animados, lower-third,
marca de agua y subtítulos karaoke (ASS) quemados.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys

import comun


def _esc(texto):
    return (texto.replace("\\", "\\\\").replace(":", "\\:")
            .replace("'", "\\'").replace("%", "\\%"))


def _drawtext_titulo(t, fuente_base):
    ini = comun.parsear_tiempo(t.get("inicio", 0))
    fin = comun.parsear_tiempo(t.get("fin", ini + 3))
    texto = _esc(str(t.get("texto", "")))
    tamano = int(t.get("tamano", 64))
    color = t.get("color", "white")
    borde = t.get("borde", "black")
    y = t.get("y", "120")
    ff_opt = ("fontfile=%s" % fuente_base) if fuente_base else "font=Arial Black"
    return ("drawtext=%s:text='%s':fontcolor=%s:fontsize=%d:borderw=5:"
            "bordercolor=%s:x=(w-text_w)/2:y=%s:enable='between(t,%.2f,%.2f)'"
            % (ff_opt, texto, color, tamano, borde, y, ini, fin))


def _drawtext_lowerthird(lt, fuente_base):
    ini = float(lt.get("inicio", 0.5))
    fin = float(lt.get("fin", 7.0))
    texto = _esc(str(lt.get("texto", "")))
    tam = int(lt.get("tamano", 34))
    ff_opt = ("fontfile=%s" % fuente_base) if fuente_base else "font=Arial"
    alpha = ("if(lt(t\\,%.2f)\\,0\\,if(lt(t\\,%.2f)\\,(t-%.2f)/0.5\\,"
             "if(lt(t\\,%.2f)\\,1\\,(%.2f-t)/0.5)))" % (ini, ini + 0.5, ini, fin - 0.5, fin))
    return ("drawtext=%s:text='%s':fontcolor=white:fontsize=%d:box=1:"
            "boxcolor=black@0.55:boxborderw=14:x=60:y=h-160:alpha='%s'"
            % (ff_opt, texto, tam, alpha))


def renderizar(entrada, salida, ass=None, titulos=None, broll=None, lowerthird=None,
               marca=None, progreso=True, zoom=False, grade=True, sharpen=True,
               ancho=1920, alto=1080, crf=20, preset="medium", formato="horizontal",
               fuente_archivo=None):
    ff = comun.ruta_bin("ffmpeg")
    dur = comun.inspeccionar_media(entrada).get("duracion", 0) or 1

    wd = os.path.dirname(os.path.abspath(ass)) if ass else os.path.dirname(os.path.abspath(salida))
    os.makedirs(wd, exist_ok=True)
    fuente_base = None
    if fuente_archivo and os.path.exists(fuente_archivo):
        fuente_base = os.path.basename(fuente_archivo)
        shutil.copy(fuente_archivo, os.path.join(wd, fuente_base))

    cmd = [ff, "-y", "-i", entrada]
    for b in (broll or []):
        cmd += ["-loop", "1", "-framerate", "30", "-t", "%.3f" % dur, "-i", b["recurso"]]

    cadena = []
    if formato == "horizontal":
        cadena.append("[0:v]scale=%d:%d:force_original_aspect_ratio=increase,"
                      "crop=%d:%d[base0]" % (ancho, alto, ancho, alto))
    else:
        cadena.append("[0:v]split=2[bg][fg]")
        cadena.append("[bg]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,"
                      "boxblur=18:4,eq=brightness=-0.08[bg2]" % (ancho, alto, ancho, alto))
        cadena.append("[fg]scale=%d:-2[fg2]" % ancho)
        cadena.append("[bg2][fg2]overlay=(W-w)/2:(H-h)/2[base0]")

    actual = "base0"
    filtros = []
    if grade:
        filtros.append("eq=contrast=1.06:saturation=1.12:brightness=0.01")
    if sharpen:
        filtros.append("unsharp=5:5:0.8")
    if filtros:
        cadena.append("[%s]%s[graded]" % (actual, ",".join(filtros)))
        actual = "graded"

    for i, b in enumerate(broll or []):
        ini = float(b["inicio"])
        fin = float(b["fin"])
        fade = float(b.get("fundido", 0.6))
        cadena.append(
            "[%d:v]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,format=rgba,"
            "fade=t=in:st=%.3f:d=%.2f:alpha=1,fade=t=out:st=%.3f:d=%.2f:alpha=1[br%d]"
            % (1 + i, ancho, alto, ancho, alto, ini, fade, max(fin - fade, ini), fade, i))
        cadena.append("[%s][br%d]overlay=0:0:eof_action=pass:"
                      "enable='between(t,%.3f,%.3f)'[o%d]" % (actual, i, ini, fin, i))
        actual = "o%d" % i

    if zoom:
        cadena.append("[%s]zoompan=z='min(1+0.0006*on,1.12)':d=1:"
                      "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=%dx%d:fps=30[zm]"
                      % (actual, ancho, alto))
        actual = "zm"

    if progreso:
        cadena.append("[%s]drawbox=x=0:y=0:w='iw*t/%.3f':h=14:color=0xffd400@1:t=fill[bar]"
                      % (actual, dur))
        actual = "bar"

    for t in (titulos or []):
        cadena.append("[%s]%s[tx]" % (actual, _drawtext_titulo(t, fuente_base)))
        actual = "tx"

    for lt in (lowerthird or []):
        cadena.append("[%s]%s[lt]" % (actual, _drawtext_lowerthird(lt, fuente_base)))
        actual = "lt"

    if marca:
        ff_opt = ("fontfile=%s" % fuente_base) if fuente_base else "font=Arial"
        cadena.append("[%s]drawtext=%s:text='%s':fontcolor=white@0.55:fontsize=32:"
                      "borderw=2:bordercolor=black@0.4:x=w-text_w-40:y=h-70[mk]"
                      % (actual, ff_opt, _esc(marca)))
        actual = "mk"

    if ass:
        opt = "ass=%s" % os.path.basename(ass)
        if fuente_base:
            opt += ":fontsdir=."
        cadena.append("[%s]%s[v]" % (actual, opt))
        actual = "v"
    else:
        cadena.append("[%s]null[v]" % actual)

    cmd += ["-filter_complex", ";".join(cadena), "-map", "[v]", "-map", "0:a?",
            "-c:v", "libx264", "-crf", str(crf), "-preset", preset, "-pix_fmt", "yuv420p",
            "-c:a", "copy", "-movflags", "+faststart", os.path.abspath(salida)]
    p = subprocess.run(cmd, cwd=wd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise RuntimeError("ffmpeg (render moderno) falló:\n" + (p.stderr or p.stdout)[-3000:])
    return os.path.abspath(salida)


def _cargar(ruta):
    if not ruta:
        return None
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def main(argv):
    ap = argparse.ArgumentParser(description="Render moderno (vertical u horizontal).")
    ap.add_argument("--input", "-i", required=True)
    ap.add_argument("--salida", "-o", required=True)
    ap.add_argument("--ass")
    ap.add_argument("--titulos")
    ap.add_argument("--broll")
    ap.add_argument("--lowerthird")
    ap.add_argument("--marca")
    ap.add_argument("--fuente", help="Archivo .ttf para títulos/lower-third")
    ap.add_argument("--sin-progreso", action="store_true")
    ap.add_argument("--sin-grade", action="store_true")
    ap.add_argument("--sin-sharpen", action="store_true")
    ap.add_argument("--zoom", action="store_true")
    ap.add_argument("--formato", choices=["vertical", "horizontal"], default="vertical")
    ap.add_argument("--ancho", type=int, default=0)
    ap.add_argument("--alto", type=int, default=0)
    ap.add_argument("--crf", type=int, default=20)
    ap.add_argument("--preset", default="medium")
    args = ap.parse_args(argv)

    ancho, alto = args.ancho, args.alto
    if not ancho or not alto:
        ancho, alto = (1920, 1080) if args.formato == "horizontal" else (1080, 1920)
    try:
        ruta = renderizar(args.input, args.salida, args.ass, _cargar(args.titulos),
                          _cargar(args.broll), _cargar(args.lowerthird), args.marca,
                          not args.sin_progreso, args.zoom, not args.sin_grade,
                          not args.sin_sharpen, ancho, alto, args.crf, args.preset,
                          args.formato, args.fuente)
        print("Render moderno en %s" % ruta)
        return 0
    except Exception as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
