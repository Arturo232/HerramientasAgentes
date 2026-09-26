"""Busca dentro de un PDF y devuelve SOLO los fragmentos relevantes (BM25).

Pensado para no volcar el documento completo al modelo: recibe una consulta y
entrega los trozos mas relevantes con su numero de pagina.
"""

import json
import math
import os
import re
import sys
from collections import Counter

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _AQUI)
_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(_AQUI)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
import leer_pdf  # noqa: E402
from nucleo import cli  # noqa: E402
from nucleo.contrato import exito  # noqa: E402


def _tokenizar(texto):
    return re.findall(r"[a-z0-9áéíóúñü]+", texto.lower())


def _asegurar_json(pdf, salida_dir=None):
    salida_dir = salida_dir or os.path.dirname(os.path.abspath(pdf))
    base = os.path.splitext(os.path.basename(pdf))[0]
    ruta = os.path.join(salida_dir, base + ".json")
    if not os.path.exists(ruta):
        leer_pdf.leer(pdf, salida_dir)
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def _fragmentos(info, tamano=700):
    frags = []
    for pag in info.get("paginas", []):
        texto = pag.get("texto", "")
        parrafos = [p.strip() for p in re.split(r"\n\s*\n", texto) if p.strip()]
        if not parrafos:
            parrafos = [texto]
        buffer = ""
        for p in parrafos:
            if len(buffer) + len(p) <= tamano:
                buffer = (buffer + "\n" + p).strip()
            else:
                if buffer:
                    frags.append({"pagina": pag["pagina"], "texto": buffer})
                buffer = p
        if buffer:
            frags.append({"pagina": pag["pagina"], "texto": buffer})
    return frags


def bm25(frags, consulta, k=5):
    docs = [{"tokens": _tokenizar(f["texto"]), "frag": f} for f in frags]
    N = len(docs)
    if N == 0:
        return []
    df = Counter()
    for d in docs:
        for w in set(d["tokens"]):
            df[w] += 1
    avg = sum(len(d["tokens"]) for d in docs) / N
    k1, b = 1.5, 0.75
    q = _tokenizar(consulta)
    resultados = []
    for d in docs:
        tf = Counter(d["tokens"])
        L = len(d["tokens"])
        score = 0.0
        for w in q:
            if w not in tf:
                continue
            idf = math.log(1 + (N - df[w] + 0.5) / (df[w] + 0.5))
            score += idf * (tf[w] * (k1 + 1)) / (tf[w] + k1 * (1 - b + b * L / avg))
        if score > 0:
            resultados.append((score, d["frag"]))
    resultados.sort(key=lambda x: -x[0])
    return resultados[:k]


def buscar(pdf, consulta, k=5, salida_dir=None):
    info = _asegurar_json(pdf, salida_dir)
    frags = _fragmentos(info)
    return [{"pagina": f["pagina"], "texto": f["texto"], "score": round(s, 3)}
            for s, f in bm25(frags, consulta, k)]


def _construir(ap):
    ap.add_argument("--input", "-i", required=True, help="PDF")
    ap.add_argument("--consulta", "-q", required=True)
    ap.add_argument("--k", "-k", type=int, default=5, help="Numero de fragmentos")


def _accion(ns):
    resultados = buscar(ns.input, ns.consulta, ns.k)
    return exito(datos={"resultados": resultados, "total": len(resultados)},
                 meta={"consulta": ns.consulta, "k": ns.k})


if __name__ == "__main__":
    sys.exit(cli.correr("documentos", _construir, _accion, sys.argv[1:],
                        prog="buscar_pdf",
                        descripcion="Busca fragmentos relevantes en un PDF."))
