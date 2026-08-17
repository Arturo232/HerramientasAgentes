#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Renderiza un HTML local a PDF vectorial A4 con Playwright, esperando la carga de CDNs.

Uso:
    renderizador_playwright.py --input infografia.html --salida infografia.pdf
"""

import argparse
import os
import shutil
import sys

from playwright.sync_api import sync_playwright

CHROMIUM_RUTAS = [
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/google-chrome",
    "/usr/bin/brave-browser",
]


def buscar_chromium():
    for ruta in CHROMIUM_RUTAS:
        if shutil.which(ruta):
            return ruta
    return None


def main():
    ap = argparse.ArgumentParser(description="Renderiza un HTML a PDF vectorial A4 con Playwright.")
    ap.add_argument("--input", required=True, help="Ruta al archivo HTML local")
    ap.add_argument("--salida", required=True, help="Ruta del PDF de salida")
    ap.add_argument("--formato", default="A4", help="Formato del PDF (default: A4)")
    args = ap.parse_args()

    path_html_absoluto = os.path.abspath(args.input)
    if not os.path.isfile(path_html_absoluto):
        sys.exit(f"No existe el archivo HTML: {path_html_absoluto}")
    os.makedirs(os.path.dirname(os.path.abspath(args.salida)), exist_ok=True)

    with sync_playwright() as p:
        chromium = buscar_chromium()
        if chromium:
            browser = p.chromium.launch(executable_path=chromium)
        else:
            print("Chromium del sistema no encontrado; usando el navegador de Playwright.")
            browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(f"file://{path_html_absoluto}", wait_until="networkidle")
        page.wait_for_timeout(1500)
        page.pdf(
            path=args.salida,
            format=args.formato,
            print_background=True,
        )
        browser.close()

    print(f"PDF generado: {args.salida}")


if __name__ == "__main__":
    main()