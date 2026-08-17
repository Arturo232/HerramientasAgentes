#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera una infografía en PDF (vectorial) a partir de datos JSON y una plantilla HTML.

Uso:
    generar_infografia.py [--input datos_infografia.json] [--salida infografia.pdf]
"""

import argparse
import json
import os
import shutil
import tempfile

import jinja2
from playwright.sync_api import sync_playwright

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANTILLA = os.path.join(BASE, "plantillas", "infografia", "base_timeline.html")

CHROMIUM_RUTAS = [
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/google-chrome",
    "/usr/bin/brave-browser",
]


def validar_datos(datos):
    if not isinstance(datos, dict):
        raise ValueError("El JSON debe contener un objeto con titulo, subtitulo y pasos.")
    for campo in ("titulo", "subtitulo", "pasos"):
        if campo not in datos:
            raise ValueError(f"Falta el campo '{campo}' en datos_infografia.json.")
    if not isinstance(datos["pasos"], list) or not datos["pasos"]:
        raise ValueError("'pasos' debe ser una lista no vacía.")
    for paso in datos["pasos"]:
        for campo in ("numero", "titulo_paso", "descripcion"):
            if campo not in paso:
                raise ValueError(f"Cada paso debe incluir '{campo}'.")
    if not (4 <= len(datos["pasos"]) <= 8):
        print(f"Advertencia: {len(datos['pasos'])} pasos (se recomienda 4-8 para una A4 vertical).")
    return datos


def render_html(datos):
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(os.path.dirname(PLANTILLA)),
        autoescape=True,
    )
    template = env.get_template(os.path.basename(PLANTILLA))
    return template.render(titulo=datos["titulo"], subtitulo=datos["subtitulo"], pasos=datos["pasos"])


def buscar_chromium():
    for ruta in CHROMIUM_RUTAS:
        if shutil.which(ruta):
            return ruta
    return None


def generar_pdf(html, salida):
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_html = os.path.join(tmpdir, "temp.html")
        with open(temp_html, "w", encoding="utf-8") as f:
            f.write(html)
        with sync_playwright() as p:
            chromium = buscar_chromium()
            if chromium:
                browser = p.chromium.launch(executable_path=chromium)
            else:
                print("Chromium del sistema no encontrado; usando el navegador de Playwright.")
                browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(f"file://{temp_html}", wait_until="load")
            page.pdf(path=salida, format="A4", print_background=True, prefer_css_page_size=True)
            browser.close()


def main():
    ap = argparse.ArgumentParser(description="Genera una infografía PDF a partir de datos JSON.")
    ap.add_argument("--input", default="datos_infografia.json", help="Ruta al archivo de datos JSON")
    ap.add_argument("--salida", default="infografia.pdf", help="Ruta del PDF de salida")
    args = ap.parse_args()

    with open(args.input, encoding="utf-8") as f:
        datos = json.load(f)

    validar_datos(datos)
    html = render_html(datos)
    generar_pdf(html, args.salida)
    print(f"Infografía generada: {args.salida}")


if __name__ == "__main__":
    main()