# -*- coding: utf-8 -*-
"""Genera un diagrama de flujo vertical (HTML -> PDF/PNG) sin dependencias externas.

Reutiliza el enfoque de mentefacto.py (Playwright + Chrome del sistema).

Uso:
    python diagrama_flujo.py --contenido d.json --salida diagrama.pdf
    python diagrama_flujo.py --contenido d.json --salida diagrama.png

Formato del JSON:
{
  "titulo": "PROCESO DE IMPORTACION",
  "subtitulo": "Diagrama de flujo - Negocios Internacionales - Unidad 2",
  "nodos": [
    {"tipo": "inicio",  "texto": "Necesidad de importar un bien"},
    {"tipo": "fase",    "texto": "FASE 1 - PLANEACION"},
    {"tipo": "proceso", "texto": "Investigar y seleccionar el proveedor en el extranjero"},
    {"tipo": "doc",     "texto": "Factura comercial, lista de empaque, certificado de origen"},
    {"tipo": "decision","texto": "La mercancia cumple los requisitos aduaneros?",
                        "no": "Retencion / aprehension: subsanar y volver a presentar"},
    {"tipo": "fin",     "texto": "Entrega y registro de la importacion"}
  ]
}
"""
import html
import json
import os
import shutil
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
from nucleo import cli  # noqa: E402
from nucleo.contrato import exito  # noqa: E402
from nucleo.registro import artefacto  # noqa: E402

CHROMES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/google-chrome", "/usr/bin/chromium",
]


def _navegador():
    for c in CHROMES:
        if os.path.isfile(c) or shutil.which(c):
            return c
    return None


PLANTILLA = """<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><style>
  @page {{ size: A4 portrait; margin: 0; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family:'Segoe UI',Arial,sans-serif; background:#f4f7f6; }}
  .lienzo {{ width:794px; min-height:1123px; padding:28px 46px; display:flex; flex-direction:column; align-items:center; }}
  .cab {{ text-align:center; margin-bottom:14px; }}
  .cab h1 {{ margin:0; font-size:25px; letter-spacing:1px; color:#0f5c4d; }}
  .cab h2 {{ margin:6px 0 0; font-size:12px; font-weight:600; letter-spacing:2px; color:#2e8b74; }}
  .flow {{ display:flex; flex-direction:column; align-items:center; width:100%; }}
  .flecha {{ width:3px; height:20px; background:#8fbcae; position:relative; }}
  .flecha::after {{ content:''; position:absolute; bottom:-1px; left:-4px;
    border-left:5px solid transparent; border-right:5px solid transparent; border-top:8px solid #8fbcae; }}
  .nodo {{ width:470px; text-align:center; padding:11px 16px; border-radius:12px;
    font-size:14px; font-weight:600; color:#12332c; background:#fff; border:2px solid #2e8b74;
    box-shadow:0 3px 8px rgba(0,0,0,.07); line-height:1.28; }}
  .nodo.inicio, .nodo.fin {{ background:#0f5c4d; color:#fff; border-radius:26px; border-color:#0f5c4d; }}
  .nodo.doc {{ border-color:#c98a2b; background:#fff8ec; color:#7a4d00; }}
  .nodo.fase {{ background:#0f5c4d; color:#fff; border-color:#0f5c4d; font-size:12px;
    letter-spacing:1.5px; padding:8px 16px; width:470px; border-radius:8px; }}
  .decision {{ display:flex; align-items:center; gap:22px; margin:4px 0; }}
  .rama {{ display:flex; flex-direction:column; align-items:center; gap:6px; }}
  .rombo {{ width:158px; height:158px; transform:rotate(45deg); background:#fff3e0;
    border:2px solid #e08a2b; display:flex; align-items:center; justify-content:center;
    box-shadow:0 3px 8px rgba(0,0,0,.07); }}
  .rombo span {{ transform:rotate(-45deg); font-size:12px; font-weight:700; color:#8a4b00;
    text-align:center; width:124px; line-height:1.2; }}
  .etq {{ font-size:12px; font-weight:700; color:#2e8b74; }}
  .etq.no {{ color:#c0392b; }}
  .lado {{ width:210px; padding:10px; border-radius:10px; background:#fdecea;
    border:2px solid #e0a9a2; font-size:12px; color:#7a1f16; text-align:center; line-height:1.25; }}
  .pie {{ margin-top:auto; font-size:10px; color:#6b7d78; padding-top:12px; }}
</style></head><body>
  <div class="lienzo">
    <div class="cab"><h1>{titulo}</h1><h2>{subtitulo}</h2></div>
    <div class="flow">{cuerpo}</div>
    <div class="pie">Universidad de Cartagena - CTEV | Elaborado por Arturo Andres Baena Arias</div>
  </div>
</body></html>"""


def _nodo(tipo, texto):
    return '<div class="nodo %s">%s</div>' % (tipo, html.escape(texto))


def generar_html(contenido):
    partes = []
    nodos = contenido.get("nodos", [])
    for i, n in enumerate(nodos):
        tipo = n.get("tipo", "proceso")
        if tipo == "decision":
            no = n.get("no", "")
            lado = ('<div class="rama"><div class="etq no">No</div>'
                    '<div class="lado">%s</div></div>' % html.escape(no)) if no else ""
            partes.append(
                '<div class="decision">'
                '<div class="rama"><div class="rombo"><span>%s</span></div>'
                '<div class="etq">Si</div></div>%s</div>'
                % (html.escape(n.get("texto", "")), lado))
        else:
            partes.append(_nodo(tipo, n.get("texto", "")))
        if i < len(nodos) - 1:
            partes.append('<div class="flecha"></div>')
    return PLANTILLA.format(
        titulo=html.escape(contenido.get("titulo", "")),
        subtitulo=html.escape(contenido.get("subtitulo", "")),
        cuerpo="".join(partes))


def render(html_str, salida, navegador=None):
    from playwright.sync_api import sync_playwright
    navegador = navegador or _navegador()
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=navegador, headless=True) if navegador else p.chromium.launch(headless=True)
        pg = b.new_page(viewport={"width": 794, "height": 1123})
        pg.set_content(html_str, wait_until="load")
        pg.wait_for_timeout(600)
        if salida.lower().endswith(".png"):
            pg.screenshot(path=salida, full_page=True)
        else:
            pg.pdf(path=salida, width="794px", height="1123px", print_background=True)
        b.close()
    return salida


def _construir(ap):
    ap.add_argument("--contenido", required=True, help="JSON del diagrama")
    ap.add_argument("--salida", required=True, help=".pdf o .png")
    ap.add_argument("--html", help="Guardar tambien el HTML")


def _accion(ns):
    contenido = json.load(open(ns.contenido, encoding="utf-8"))
    html_str = generar_html(contenido)
    if ns.html:
        open(ns.html, "w", encoding="utf-8").write(html_str)
    render(html_str, ns.salida)
    arts = [artefacto("imagen", ns.salida)]
    if ns.html:
        arts.append(artefacto("html", ns.html))
    return exito(datos={"salida": ns.salida}, artefactos=arts)


if __name__ == "__main__":
    sys.exit(cli.correr("navegacion_web", _construir, _accion, sys.argv[1:],
                        prog="diagrama_flujo",
                        descripcion="Genera un diagrama de flujo (HTML -> PDF/PNG)."))
