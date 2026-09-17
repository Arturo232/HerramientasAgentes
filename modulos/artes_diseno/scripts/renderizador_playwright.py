#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Renderiza un HTML local a PDF vectorial A4 con Playwright, esperando la carga de CDNs.

Uso:
    renderizador_playwright.py --input infografia.html --salida infografia.pdf
"""

import os
import shutil
import sys

from playwright.sync_api import sync_playwright

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
from nucleo import cli  # noqa: E402
from nucleo.contrato import exito  # noqa: E402
from nucleo.errores import AgenteError  # noqa: E402
from nucleo.registro import artefacto  # noqa: E402

CHROMIUM_RUTAS = [
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/google-chrome",
    "/usr/bin/brave-browser",
]


def buscar_chromium():
    for ruta in CHROMIUM_RUTAS:
        if os.path.isfile(ruta) or shutil.which(ruta):
            return ruta
    return None


def _construir(ap):
    ap.add_argument("--input", required=True, help="Ruta al archivo HTML local")
    ap.add_argument("--salida", required=True, help="Ruta del PDF de salida")
    ap.add_argument("--formato", default="A4", help="Formato del PDF (default: A4)")


def _accion(ns):
    path_html_absoluto = os.path.abspath(ns.input)
    if not os.path.isfile(path_html_absoluto):
        raise AgenteError("artes_diseno", "noExiste",
                          "No existe el archivo HTML: %s" % path_html_absoluto)
    os.makedirs(os.path.dirname(os.path.abspath(ns.salida)), exist_ok=True)

    with sync_playwright() as p:
        chromium = buscar_chromium()
        browser = p.chromium.launch(executable_path=chromium) if chromium else p.chromium.launch()
        page = browser.new_page()
        page.goto(f"file://{path_html_absoluto}", wait_until="networkidle")
        page.wait_for_timeout(1500)
        page.pdf(path=ns.salida, format=ns.formato, print_background=True)
        browser.close()

    return exito(datos={"pdf": ns.salida}, meta={"formato": ns.formato},
                 artefactos=[artefacto("pdf", ns.salida)])


if __name__ == "__main__":
    sys.exit(cli.correr("artes_diseno", _construir, _accion, sys.argv[1:],
                        prog="renderizador_playwright",
                        descripcion="Renderiza un HTML a PDF vectorial A4 con Playwright."))