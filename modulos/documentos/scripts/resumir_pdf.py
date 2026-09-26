"""Resumen extractivo local de un PDF (sin usar el modelo de IA).

Genera un indice (encabezados) y un resumen extractivo por frecuencia de
terminos, para que el modelo reciba una version corta y de alta senal.
"""

import json
import os
import re
import sys
from collections import Counter

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _AQUI)
_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(_AQUI)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
import buscar_pdf  # noqa: E402
import leer_pdf  # noqa: E402
from nucleo import cli  # noqa: E402
from nucleo.contrato import exito  # noqa: E402
from nucleo.registro import artefacto  # noqa: E402

STOPWORDS = set("""a al algo algunas algunos ante antes como con contra cual cuando de del desde donde
dos el ella ellas ellos en entre era erais eran eras eres es esa esas ese eso esos esta estaba estado
estan estar estas este esto estos fue fueron ha han hasta hay la las le les lo los mas me mi mis mucho
muy no nos o os otra otras otro otros para pero poco por porque que quien quienes se sea segun ser si sin
sobre son su sus te tiene tienen todo todos tu tus un una uno unos y ya the of and to in a is are was
were for on with that this these those as by at from it its be been being or an not but if then than
""".split())


def _tokenizar(texto):
    return [w for w in re.findall(r"[a-z0-9áéíóúñü]+", texto.lower()) if w not in STOPWORDS]


def _oraciones(texto):
    texto = re.sub(r"\s+", " ", texto)
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", texto) if len(s.strip()) > 25]


def resumir(pdf, max_oraciones=12, salida_dir=None):
    info = buscar_pdf._asegurar_json(pdf, salida_dir)
    texto = "\n".join(p.get("texto", "") for p in info.get("paginas", []))

    freq = Counter(_tokenizar(texto))
    if freq:
        maxf = max(freq.values())
        for w in freq:
            freq[w] /= maxf

    oraciones = []
    for pag in info.get("paginas", []):
        for s in _oraciones(pag.get("texto", "")):
            tokens = _tokenizar(s)
            if not tokens:
                continue
            score = sum(freq.get(w, 0) for w in tokens) / (len(tokens) ** 0.5)
            oraciones.append((score, pag["pagina"], s))

    mejores = sorted(oraciones, key=lambda x: -x[0])[:max_oraciones]
    mejores.sort(key=lambda x: (x[1], x[2]))

    lineas_md = ["# Resumen de %s" % os.path.basename(pdf), ""]
    lineas_md.append("## Ideas principales")
    for _, pag, s in mejores:
        lineas_md.append("- (%s) %s" % (pag, s))
    return {
        "markdown": "\n".join(lineas_md),
        "resumen": [{"pagina": pag, "texto": s} for _, pag, s in mejores],
    }


def _construir(ap):
    ap.add_argument("--input", "-i", required=True)
    ap.add_argument("--max", type=int, default=12, help="Maximo de ideas")
    ap.add_argument("--salida", "-o", help="Archivo .md de salida")


def _accion(ns):
    res = resumir(ns.input, ns.max)
    arts = []
    if ns.salida:
        with open(ns.salida, "w", encoding="utf-8") as f:
            f.write(res["markdown"])
        arts.append(artefacto("markdown", ns.salida))
    return exito(datos=res, artefactos=arts)


if __name__ == "__main__":
    sys.exit(cli.correr("documentos", _construir, _accion, sys.argv[1:],
                        prog="resumir_pdf",
                        descripcion="Resumen extractivo local de un PDF."))
