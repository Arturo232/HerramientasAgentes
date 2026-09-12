"""Recorta los silencios de un video y devuelve el mapeo de tiempos.

Detecta los silencios con ffmpeg, conserva los tramos con voz (con un pequeño
margen), concatena el video resultante y guarda un JSON con los tramos
eliminados para poder re-mapear subtítulos y títulos al nuevo timeline.
"""

import argparse
import json
import os
import re
import sys

import comun


def detectar_silencios(ruta, umbral_db=-35, min_dur=0.5):
    ff = comun.ruta_bin("ffmpeg")
    p = comun.ejecutar([
        ff, "-hide_banner", "-i", ruta, "-af",
        "silencedetect=noise=%ddB:d=%s" % (umbral_db, min_dur),
        "-f", "null", "-",
    ])
    txt = p.stderr or p.stdout
    silencios = []
    cur = None
    for m in re.finditer(r"silence_(start|end): ([\d.]+)", txt):
        tipo, val = m.group(1), float(m.group(2))
        if tipo == "start":
            cur = val
        elif cur is not None:
            silencios.append((cur, val))
            cur = None
    return silencios


def recortes_a_eliminar(silencios, duracion, margen=0.2, min_sil=0.5):
    recortes = []
    for s, e in silencios:
        if e - s >= min_sil:
            a = min(s + margen, e)
            b = max(e - margen, a)
            if b > a:
                recortes.append((a, b))
    return recortes


def conservados(recortes, duracion):
    tramos = []
    pos = 0.0
    for a, b in recortes:
        if a > pos + 0.01:
            tramos.append((pos, a))
        pos = max(pos, b)
    if pos < duracion - 0.01:
        tramos.append((pos, duracion))
    return tramos


def mapear(t, recortes):
    offset = 0.0
    for a, b in recortes:
        if t >= b:
            offset += (b - a)
        elif t > a:
            return a - offset
        else:
            break
    return t - offset


def recortar(entrada, salida, umbral_db=-35, min_sil=0.5, margen=0.2):
    ff = comun.ruta_bin("ffmpeg")
    info = comun.inspeccionar_media(entrada)
    duracion = info.get("duracion", 0) or 0
    silencios = detectar_silencios(entrada, umbral_db, min_sil)
    recortes = recortes_a_eliminar(silencios, duracion, margen, min_sil)
    tramos = conservados(recortes, duracion)
    if not tramos:
        raise RuntimeError("No se pudieron calcular tramos a conservar")

    partes = []
    refs = []
    for i, (a, b) in enumerate(tramos):
        partes.append("[0:v]trim=start=%.3f:end=%.3f,setpts=PTS-STARTPTS[v%d]" % (a, b, i))
        partes.append("[0:a]atrim=start=%.3f:end=%.3f,asetpts=PTS-STARTPTS[a%d]" % (a, b, i))
        refs.append((("[v%d]" % i), ("[a%d]" % i)))
    concat_in = "".join(v + a for v, a in refs)
    partes.append("%sconcat=n=%d:v=1:a=1[v][a]" % (concat_in, len(tramos)))
    grafo = ";".join(partes)

    cmd = [ff, "-y", "-i", entrada, "-filter_complex", grafo,
           "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "18",
           "-preset", "medium", "-c:a", "aac", "-b:a", "192k", salida]
    p = comun.ejecutar(cmd)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg (recorte) falló:\n" + (p.stderr or p.stdout)[-2500:])

    nueva = comun.inspeccionar_media(salida).get("duracion", 0)
    return {
        "salida": os.path.abspath(salida),
        "duracion_original": duracion,
        "duracion_final": nueva,
        "recortes": recortes,
        "tramos": tramos,
    }


def main(argv):
    ap = argparse.ArgumentParser(description="Recorta silencios de un video.")
    ap.add_argument("--input", "-i", required=True)
    ap.add_argument("--salida", "-o", required=True)
    ap.add_argument("--umbral", type=int, default=-35, help="Umbral de silencio en dB")
    ap.add_argument("--min-silencio", type=float, default=0.5)
    ap.add_argument("--margen", type=float, default=0.2)
    ap.add_argument("--mapeo", help="JSON donde guardar el mapeo de tiempos")
    args = ap.parse_args(argv)

    try:
        res = recortar(args.input, args.salida, args.umbral, args.min_silencio, args.margen)
        if args.mapeo:
            with open(args.mapeo, "w", encoding="utf-8") as f:
                json.dump(res, f, ensure_ascii=False, indent=1)
        print("Recortado: %s (%.1f s -> %.1f s)"
              % (res["salida"], res["duracion_original"], res["duracion_final"]))
        return 0
    except Exception as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
