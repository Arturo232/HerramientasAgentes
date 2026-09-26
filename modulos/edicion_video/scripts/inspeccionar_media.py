"""Inspecciona un archivo de video/audio y devuelve sus metadatos en JSON."""

import argparse
import json
import os
import sys

import comun


def main(argv):
    ap = argparse.ArgumentParser(
        description="Inspecciona un medio y devuelve sus metadatos (duración, "
        "resolución, fps, codecs)."
    )
    ap.add_argument("--input", "-i", required=True, help="Ruta del video/audio")
    ap.add_argument("--salida", "-o", help="Archivo JSON de salida (opcional)")
    args = ap.parse_args(argv)

    ruta = os.path.abspath(args.input)
    if not os.path.exists(ruta):
        print("ERROR: no existe el archivo %s" % ruta, file=sys.stderr)
        return 1

    info = comun.inspeccionar_media(ruta)
    texto = json.dumps(info, ensure_ascii=False, indent=2)
    if args.salida:
        with open(args.salida, "w", encoding="utf-8") as f:
            f.write(texto)
    print(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
