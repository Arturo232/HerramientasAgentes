"""Re-mapea los tiempos (inicio/fin) de un JSON según un mapeo de recortes.

Se usa para ajustar subtítulos y títulos al timeline de un video recortado.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import recortar_silencios as rs


def main(argv):
    ap = argparse.ArgumentParser(description="Re-mapea tiempos de un JSON.")
    ap.add_argument("--mapeo", required=True, help="JSON con 'recortes'")
    ap.add_argument("--input", "-i", required=True, help="JSON lista de {inicio, fin, ...}")
    ap.add_argument("--salida", "-o", required=True)
    args = ap.parse_args(argv)

    with open(args.mapeo, "r", encoding="utf-8") as f:
        m = json.load(f)
    recortes = [tuple(x) for x in m.get("recortes", [])]
    with open(args.input, "r", encoding="utf-8") as f:
        items = json.load(f)

    for it in items:
        for k in ("inicio", "fin"):
            if k in it and isinstance(it[k], (int, float)):
                it[k] = round(rs.mapear(float(it[k]), recortes), 3)

    with open(args.salida, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=1)
    print("Mapeado: %s" % os.path.abspath(args.salida))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
