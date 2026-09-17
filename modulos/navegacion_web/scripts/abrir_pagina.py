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

import os
import re
import shutil
import sys

from playwright.sync_api import sync_playwright

_AQUI = os.path.dirname(os.path.abspath(__file__))
_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(_AQUI)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
from nucleo import cli  # noqa: E402
from nucleo.contrato import exito  # noqa: E402
from nucleo.registro import artefacto  # noqa: E402

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


def _construir(ap):
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


def _accion(ns):
    os.makedirs(ns.salida, exist_ok=True)
    base = nombre_base(ns.input)
    extension = {"texto": "txt", "html": "html", "captura": "png"}[ns.modo]
    salida = os.path.join(ns.salida, f"{base}.{extension}")
    visible = ns.visible or ns.esperar_login

    with sync_playwright() as p:
        navegador = buscar_navegador()
        if ns.perfil:
            ctx = p.chromium.launch_persistent_context(
                ns.perfil, headless=not visible, executable_path=navegador)
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            cerrar = ctx.close
        elif navegador:
            browser = p.chromium.launch(executable_path=navegador, headless=not visible)
            page = browser.new_page()
            cerrar = browser.close
        else:
            browser = p.chromium.launch(headless=not visible)
            page = browser.new_page()
            cerrar = browser.close

        page.goto(ns.input, wait_until="domcontentloaded")
        if ns.esperar_selector:
            try:
                page.wait_for_selector(ns.esperar_selector, timeout=30000)
            except Exception:
                pass

        if ns.esperar_login:
            print(f"Navegador abierto en {ns.input}. Inicia sesion y presiona Enter aqui...")
            input("> Enter para continuar: ")

        page.wait_for_timeout(ns.tiempo_espera)

        if ns.modo == "texto":
            contenido = page.evaluate("document.body.innerText")
            with open(salida, "w", encoding="utf-8") as f:
                f.write(contenido)
        elif ns.modo == "html":
            contenido = page.evaluate("document.documentElement.outerHTML")
            with open(salida, "w", encoding="utf-8") as f:
                f.write(contenido)
        else:
            page.screenshot(path=salida, full_page=True)

        cerrar()

    return exito(
        datos={"archivo": salida, "modo": ns.modo, "url": ns.input},
        meta={"via": "playwright", "modulo": "navegacion_web"},
        artefactos=[artefacto(ns.modo, salida)],
    )


if __name__ == "__main__":
    sys.exit(cli.correr("navegacion_web", _construir, _accion, sys.argv[1:],
                        prog="abrir_pagina",
                        descripcion="Abre una pagina web y extrae su contenido."))
