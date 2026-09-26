#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Automatiza Canva por CDP (Chrome con sesion iniciada).

Canva renderiza los textos del diseno como `span.a_GcMg`; al hacer doble clic
se abre un editor Quill (`div.ql-editor` contenteditable) que permite reemplazar
el texto. Los disenos se exportan por Compartir -> Descargar.

Requisitos:
    python scripts/sesion_cdp.py abrir "https://www.canva.com/" --perfil <perfil>

Uso:
    python canva.py estado
    python canva.py plantillas --buscar "mapa conceptual"        # URLs de plantillas
    python canva.py usar --plantilla URL                         # crea un diseno desde la plantilla
    python canva.py textos                                       # lista los textos del diseno
    python canva.py reemplazar --mapa '{"Concept Map":"NUEVO"}'
    python canva.py exportar --formato png --salida C:\\ruta\\out.png
"""
import json
import os
import re
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
from nucleo import cli  # noqa: E402
from nucleo.contrato import exito  # noqa: E402
from nucleo.errores import AgenteError  # noqa: E402
from nucleo.registro import artefacto  # noqa: E402

CDP = "http://127.0.0.1:9333"
TEXT_SPAN = "span.a_GcMg"


def conectar(cdp=CDP):
    from playwright.sync_api import sync_playwright
    p = sync_playwright().start()
    b = p.chromium.connect_over_cdp(cdp)
    return p, b


def pagina_diseno(b):
    for c in b.contexts:
        for pg in c.pages:
            if "/design/" in pg.url:
                return pg
    return None


def traer_al_frente(pg):
    try:
        pg.bring_to_front()
    except Exception:
        pass
    pg.wait_for_timeout(800)


def _esc(pg, veces=2):
    for _ in range(veces):
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(300)


# ---------- operaciones ----------
def estado(pg):
    return {"url": pg.url, "titulo": pg.evaluate("document.title")}


def listar_textos(pg):
    traer_al_frente(pg)
    return pg.evaluate("""() => Array.from(document.querySelectorAll('span.a_GcMg')).map(s => {
        const r = s.getBoundingClientRect();
        return {txt: s.textContent, x: Math.round(r.x), y: Math.round(r.y),
                w: Math.round(r.width), h: Math.round(r.height)};
    })""")


def reemplazar(pg, mapa):
    """mapa: {texto_actual: texto_nuevo}. Reemplaza cada coincidencia."""
    traer_al_frente(pg)
    _esc(pg, 2)
    hechos, faltan = [], []
    for viejo, nuevo in mapa.items():
        spans = pg.query_selector_all(TEXT_SPAN)
        objetivo = None
        for s in spans:
            if (s.text_content() or "").strip() == viejo.strip():
                objetivo = s
                break
        if objetivo is None:
            faltan.append(viejo)
            continue
        r = objetivo.bounding_box()
        pg.mouse.dblclick(r["x"] + r["width"] / 2, r["y"] + r["height"] / 2)
        pg.wait_for_timeout(900)
        pg.keyboard.press("Control+A")
        pg.wait_for_timeout(150)
        pg.keyboard.type(nuevo)
        pg.wait_for_timeout(300)
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(600)
        hechos.append(viejo)
    return {"reemplazados": hechos, "no_encontrados": faltan}


def exportar(pg, formato="png", salida=None):
    """Exporta el diseno: Compartir -> Descargar -> (formato) -> Descargar."""
    traer_al_frente(pg)
    _esc(pg, 2)
    pg.locator("button:has-text('Compartir')").first.click(timeout=20000)
    pg.wait_for_timeout(2000)
    pg.locator("button:has-text('Descargar'), [role=menuitem]:has-text('Descargar')").first.click(timeout=20000)
    pg.wait_for_timeout(2500)
    etq = {"png": "PNG", "pdf": "PDF", "jpg": "JPG"}.get(formato.lower(), formato.upper())
    # Si el formato no es PNG (predeterminado), abrir el selector y elegirlo
    if formato.lower() != "png":
        try:
            pg.locator("button:has-text('PNG')").first.click(timeout=5000)
            pg.wait_for_timeout(800)
            pg.locator(f"[role='option']:has-text('{etq}'), li:has-text('{etq}')").first.click(timeout=5000)
            pg.wait_for_timeout(800)
        except Exception:
            pass
    boton = pg.locator("button[type='submit']:has-text('Descargar')").last
    with pg.expect_download(timeout=120000) as dl:
        boton.click(timeout=20000)
    descarga = dl.value
    destino = salida or descarga.suggested_filename
    descarga.save_as(destino)
    return destino


def plantillas(b, buscar, limite=20):
    pg = None
    for c in b.contexts:
        for q in c.pages:
            if q.url == "about:blank" or "canva.com" in q.url:
                pg = pg or q
    pg = pg or b.contexts[0].new_page()
    pg.goto("https://www.canva.com/templates/?query=" + buscar.replace(" ", "%20"),
            wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(3000)
    enlaces = pg.evaluate("""() => Array.from(document.querySelectorAll('a[href*="/templates/"]'))
        .map(a => ({t: a.innerText.trim(), h: a.href}))
        .filter(x => x.h && !x.h.includes('?query='))""")
    vistos, salida = set(), []
    for e in enlaces:
        if e["h"] in vistos:
            continue
        vistos.add(e["h"])
        salida.append(e)
        if len(salida) >= limite:
            break
    return salida


def usar(pg, plantilla_url):
    pg.goto(plantilla_url, wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(3500)
    try:
        pg.locator("text=Personalizar la plantilla").first.click(timeout=15000)
    except Exception:
        pg.locator("button:has-text('Personalizar')").first.click(timeout=15000)
    pg.wait_for_timeout(6000)
    return pg.url


def _construir(ap):
    ap.add_argument("cmd", choices=["estado", "plantillas", "usar", "textos", "reemplazar", "exportar"])
    ap.add_argument("--buscar")
    ap.add_argument("--plantilla")
    ap.add_argument("--mapa")
    ap.add_argument("--formato", default="png")
    ap.add_argument("--salida")
    ap.add_argument("--cdp", default=CDP)


def _accion(ns):
    p, b = conectar(ns.cdp)
    try:
        if ns.cmd == "plantillas":
            return exito(datos={"plantillas": plantillas(b, ns.buscar)})
        pg = pagina_diseno(b)
        if ns.cmd == "usar":
            if pg is None:
                pg = b.contexts[0].pages[0]
            return exito(datos={"diseno": usar(pg, ns.plantilla)})
        if pg is None:
            raise AgenteError("navegacion_web", "sinDiseno",
                              "No hay diseno abierto. Usa: canva.py usar --plantilla URL")
        if ns.cmd == "estado":
            return exito(datos=estado(pg))
        if ns.cmd == "textos":
            return exito(datos={"textos": listar_textos(pg)})
        if ns.cmd == "reemplazar":
            return exito(datos=reemplazar(pg, json.loads(ns.mapa)))
        destino = exportar(pg, ns.formato, ns.salida)
        return exito(datos={"archivo": destino},
                     artefactos=[artefacto(ns.formato, destino)])
    finally:
        p.stop()


if __name__ == "__main__":
    sys.exit(cli.correr("navegacion_web", _construir, _accion, sys.argv[1:],
                        prog="canva", descripcion="Canva por CDP."))
