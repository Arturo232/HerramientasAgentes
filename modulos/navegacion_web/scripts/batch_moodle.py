#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ejecuta h5p_solver sobre un inventario y registra resultados.

Uso:
    python batch_moodle.py --inventario inventario.json
    python batch_moodle.py --inventario inventario.json --secciones 3 4
"""
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _AQUI)
_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(_AQUI)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
import h5p_solver  # noqa: E402
from playwright.sync_api import sync_playwright
from nucleo import cli  # noqa: E402
from nucleo.contrato import exito  # noqa: E402
from nucleo.registro import artefacto  # noqa: E402


def _construir(ap):
    ap.add_argument("--inventario", default="inventario.json")
    ap.add_argument("--salida", default="resultados.json")
    ap.add_argument("--secciones", type=int, nargs="*")


def _accion(ns):
    items = json.load(open(ns.inventario, encoding="utf-8"))
    if ns.secciones:
        items = [it for it in items if it.get("sec") in ns.secciones]

    p = sync_playwright().start()
    b = p.chromium.connect_over_cdp(h5p_solver.CDP)
    ctx = b.contexts[0]
    pg = [x for x in ctx.pages if "unicartagena" in x.url or "moodle" in x.url][0]

    results = []
    for n, it in enumerate(items, 1):
        url = it["href"]
        h5p_solver.SOLVED.clear()
        score, err = "", ""
        for intento in range(2):
            try:
                pg.goto(url, wait_until="domcontentloaded", timeout=45000)
                pg.wait_for_timeout(2800)
                if "/mod/hvp/" in url:
                    fr = h5p_solver.h5p_frame(pg)
                    if fr:
                        h5p_solver.resolver(fr, pg)
                        pg.wait_for_timeout(1200)
                        score = fr.evaluate(
                            r"(document.body.innerText.match(/You got [^\n]*points[^\n]*/)||[''])[0]")
                        if not score:
                            score = fr.evaluate(
                                r"(document.body.innerText.match(/[0-9]+\s*\/\s*[0-9]+/)||[''])[0]")
                    else:
                        err = "sin iframe"
                else:
                    score = "(vista)"
                err = ""
                break
            except Exception as e:
                err = str(e)[:100]
                pg.wait_for_timeout(2000)
        print("[%d/%d] %-28s %-44s %s %s" % (
            n, len(items), it.get("tipo", "")[:28], it["name"][:44], score, err),
            file=sys.stderr, flush=True)
        results.append({"name": it["name"], "tipo": it.get("tipo", ""), "sec": it.get("sec"),
                        "score": score, "err": err, "href": url})
        json.dump(results, open(ns.salida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    p.stop()
    return exito(datos={"resultados": results, "total": len(results)},
                 artefactos=[artefacto("json", ns.salida)])


if __name__ == "__main__":
    sys.exit(cli.correr("navegacion_web", _construir, _accion, sys.argv[1:],
                        prog="batch_moodle",
                        descripcion="Ejecutor por lotes del solver H5P."))
