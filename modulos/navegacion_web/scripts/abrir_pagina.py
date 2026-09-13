#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Abre una pagina web con Playwright y extrae su contenido.

Uso:
    abrir_pagina.py --input https://ejemplo.com --modo texto
    abrir_pagina.py --input https://ejemplo.com --modo html --salida out
    abrir_pagina.py --input https://ejemplo.com --modo captura
    abrir_pagina.py --input https://moodle... --modo texto --perfil PERFIL --visible
    abrir_pagina.py --input https://sitio/login --modo texto --esperar-login

Modos:
    texto    -> guarda el texto visible de la pagina en un .txt
    html     -> guarda el HTML completo renderizado en un .html
    captura  -> guarda una captura de la pagina completa en un .png

Con --esperar-login (o --visible) el navegador abre visible y espera a que el
usuario inicie sesion manualmente y presione Enter en la terminal.
Con --perfil se reutiliza una sesion persistente (cookies/login).
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
    ap = argparse.ArgumentParser(description="Abre una pagina web y extrae su contenido.")
    ap.add_argument("--input", required=True, help="URL de la pagina")
    ap.add_argument("--modo", choices=["texto", "html", "captura"], default="texto")
    ap.add_argument("--salida", default=".", help="Carpeta de salida (default: .)")
    ap.add_argument("--perfil", help="Carpeta de perfil persistente (cookies/login)")
    ap.add_argument("--visible", action="store_true", help="Abrir el navegador visible")
    ap.add_argument("--esperar-login", action="store_true",
                    help="Abrir visible y esperar a que el usuario inicie sesion")
    ap.add_argument("--esperar-selector", help="Esperar a que aparezca un selector CSS")
    ap.add_argument("--tiempo-espera", type=int, default=2000,
                    help="ms adicionales de espera tras cargar (default: 2000)")
    args = ap.parse_args()

    os.makedirs(args.salida, exist_ok=True)
    base = nombre_base(args.input)
    extension = {"texto": "txt", "html": "html", "captura": "png"}[args.modo]
    salida = os.path.join(args.salida, f"{base}.{extension}")
    visible = args.visible or args.esperar_login

    with sync_playwright() as p:
        navegador = buscar_navegador()
        if args.perfil:
            ctx = p.chromium.launch_persistent_context(
                args.perfil, headless=not visible, executable_path=navegador)
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            cerrar = ctx.close
        elif navegador:
            browser = p.chromium.launch(executable_path=navegador, headless=not visible)
            page = browser.new_page()
            cerrar = browser.close
        else:
            print("Chromium del sistema no encontrado; usando el navegador de Playwright.")
            browser = p.chromium.launch(headless=not visible)
            page = browser.new_page()
            cerrar = browser.close

        page.goto(args.input, wait_until="domcontentloaded")
        if args.esperar_selector:
            try:
                page.wait_for_selector(args.esperar_selector, timeout=30000)
            except Exception:
                pass

        if args.esperar_login:
            print(f"Navegador abierto en {args.input}. Inicia sesion y presiona Enter aqui...")
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

        cerrar()

    print(f"Guardado: {salida}")


if __name__ == "__main__":
    main()
