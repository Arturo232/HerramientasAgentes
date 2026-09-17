# -*- coding: utf-8 -*-
"""Automatiza Google Drive / Google Docs sobre una sesion Chrome por CDP.

- Sube archivos a una carpeta de Drive.
- Comparte un documento con enlace "cualquiera puede editar".
- Con "Convertir cargas a Documentos de Google" activado, un .docx subido
  se convierte en Google Doc automaticamente.

Requiere un Chrome abierto con depuracion remota (ver sesion_cdp.py):
    python scripts/sesion_cdp.py abrir "https://drive.google.com"

Uso:
    python drive_google.py subir --carpeta URL_CARPETA --archivos a.pdf b.docx
    python drive_google.py compartir --url https://docs.google.com/document/d/ID/edit
    python drive_google.py convertir --carpeta URL_CARPETA --docx archivo.docx
"""
import os
import re
import sys

from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
from nucleo import cli  # noqa: E402
from nucleo.contrato import exito  # noqa: E402

CDP = "http://127.0.0.1:9333"
IFRAME = 'iframe[title="Contenido"]'


def conectar(cdp=CDP):
    p = sync_playwright().start()
    b = p.chromium.connect_over_cdp(cdp)
    ctx = b.contexts[0] if b.contexts else b.new_context()
    pg = ctx.pages[0] if ctx.pages else ctx.new_page()
    return p, pg


def subir(pg, carpeta_url, archivos, timeout=90000):
    """Sube archivos a la carpeta de Drive indicada."""
    pg.goto(carpeta_url, wait_until="domcontentloaded", timeout=timeout)
    pg.wait_for_timeout(2500)
    with pg.expect_file_chooser(timeout=timeout) as fc:
        pg.get_by_role("button", name="Nuevo").click()
        pg.wait_for_timeout(700)
        pg.get_by_role("menuitem", name=re.compile("Subir archivo")).click()
    fc.value.set_files(archivos)
    pg.wait_for_timeout(4000)
    return True


def compartir(pg, doc_url, rol="Editor"):
    """Pone el documento en 'cualquier persona con el enlace' con el rol dado."""
    pg.goto(doc_url, wait_until="domcontentloaded", timeout=90000)
    pg.wait_for_timeout(2500)
    pg.get_by_role("button", name=re.compile(r"Compartir\.")).first.click()
    pg.wait_for_timeout(1500)
    frame = pg.frame_locator(IFRAME)
    frame.get_by_role("button", name=re.compile("Restringido cambiar el acceso|Cualquier persona")).click()
    pg.wait_for_timeout(900)
    frame.get_by_role("menuitemradio", name="Cualquier persona con el enlace").click()
    pg.wait_for_timeout(1500)
    frame.get_by_role("button", name=re.compile("Lector\\. Cambiar permiso|Editor\\. Cambiar permiso")).click()
    pg.wait_for_timeout(900)
    frame.get_by_role("menuitemradio", name=rol).click()
    pg.wait_for_timeout(1200)
    frame.get_by_role("button", name="Hecho").click()
    pg.wait_for_timeout(1000)
    return True


def _construir(ap):
    ap.add_argument("cmd", choices=["subir", "compartir", "convertir"])
    ap.add_argument("--carpeta")
    ap.add_argument("--archivos", nargs="*", default=[])
    ap.add_argument("--docx")
    ap.add_argument("--url")
    ap.add_argument("--cdp", default=CDP)


def _accion(ns):
    p, pg = conectar(ns.cdp)
    try:
        if ns.cmd == "subir":
            subir(pg, ns.carpeta, ns.archivos)
            return exito(datos={"subidos": ns.archivos, "carpeta": ns.carpeta})
        if ns.cmd == "compartir":
            compartir(pg, ns.url)
            return exito(datos={"compartido": ns.url})
        subir(pg, ns.carpeta, [ns.docx])
        pg.wait_for_timeout(3000)
        return exito(datos={"convertido": ns.docx, "carpeta": ns.carpeta})
    finally:
        p.stop()


if __name__ == "__main__":
    sys.exit(cli.correr("navegacion_web", _construir, _accion, sys.argv[1:],
                        prog="drive_google", descripcion="Drive/Google Docs por CDP."))
