#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Abre una página web con Playwright y extrae su contenido.

Uso:
    abrir_pagina.py --input https://ejemplo.com --modo texto
    abrir_pagina.py --input https://ejemplo.com --modo html --salida out
    abrir_pagina.py --input https://ejemplo.com --modo captura
    abrir_pagina.py --input https://flipux.cloud/login --modo texto --esperar-login

Modos:
    texto    -> guarda el texto visible de la página en un .txt
    html     -> guarda el HTML completo renderizado en un .html
    captura  -> guarda una captura de la página completa en un .png

Con --esperar-login el navegador abre visible y espera a que el usuario
inicie sesión manualmente y presione Enter en la terminal; luego extrae.
"""

import argparse
import os
import re
import shutil
import sys

from playwright.sync_api import sync_playwright

NAVEGADORES = [
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/google-chrome",
    "/usr/bin/brave-browser",
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
]


def buscar_navegador():
    for ruta in NAVEGADORES:
        if shutil.which(ruta) or os.path.isfile(ruta):
            return ruta
    return None


def nombre_base(url):
    limpio = re.sub(r"^https?://", "", url).strip("/")
    limpio = re.sub(r"[^A-Za-z0-9._-]+", "_", limpio)
    return limpio[:60]


def main():
    ap = argparse.ArgumentParser(description="Abre una página web y extrae su contenido.")
    ap.add_argument("--input", required=True, help="URL de la página")
    ap.add_argument("--modo", choices=["texto", "html", "captura"], default="texto")
    ap.add_argument("--salida", default=".", help="Carpeta de salida (default: .)")
    ap.add_argument("--esperar-login", action="store_true",
                    help="Abrir el navegador visible y esperar a que el usuario inicie sesión")
    ap.add_argument("--tiempo-espera", type=int, default=2000,
                    help="ms adicionales de espera tras cargar (default: 2000)")
    args = ap.parse_args()

    os.makedirs(args.salida, exist_ok=True)
    base = nombre_base(args.input)
    extension = {"texto": "txt", "html": "html", "captura": "png"}[args.modo]
    salida = os.path.join(args.salida, f"{base}.{extension}")

    with sync_playwright() as p:
        navegador = buscar_navegador()
        if navegador:
            browser = p.chromium.launch(executable_path=navegador, headless=not args.esperar_login)
        else:
            print("Chromium del sistema no encontrado; usando el navegador de Playwright.")
            browser = p.chromium.launch(headless=not args.esperar_login)

        page = browser.new_page()
        page.goto(args.input, wait_until="domcontentloaded")

        if args.esperar_login:
            print(f"Navegador abierto en {args.input}. Inicia sesión si hace falta y presiona Enter aquí...")
            input("> Enter para continuar: ")

        page.wait_for_timeout(args.tiempo_espera)

        if args.modo == "texto":
            contenido = page.evaluate("document.body.innerText")
            with open(salida, "w", encoding="utf-8") as f:
                f.write(contenido)
        elif args.modo == "html":
            contenido = page.evaluate("document.documentElement.outerHTML")
            with open(salida, "w", encoding="utf-8") as f:
                f.write(contenido)
        else:
            page.screenshot(path=salida, full_page=True)

        browser.close()

    print(f"Guardado: {salida}")


if __name__ == "__main__":
    main()