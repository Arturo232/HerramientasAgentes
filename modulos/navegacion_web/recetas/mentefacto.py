# -*- coding: utf-8 -*-
"""Genera un mentefacto/mapa conceptual como HTML y lo exporta a PDF/PNG.

No depende de Canva: crea el diseno (concepto central + ramas) y lo renderiza
con Playwright (Chrome del sistema). Util para la "Actividad" de las unidades.

Uso:
    python mentefacto.py --contenido m.json --salida mentefacto.pdf
    python mentefacto.py --contenido m.json --salida mentefacto.png

Formato del JSON:
{
  "titulo": "NEGOCIOS INTERNACIONALES",
  "subtitulo": "MENTEFACTO · FUNDAMENTOS UNIDAD 1",
  "ramas": [
    {"titulo": "Globalización", "items": ["Integración de economías", "Cadenas globales de valor"]},
    {"titulo": "Comercio internacional", "items": ["Bienes y servicios", "OMC"]},
    {"titulo": "Inversión extranjera", "items": ["Filiales", "Alianzas"]},
    {"titulo": "Cultura", "items": ["Valores", "Negociación"]}
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
  @page {{ size: A4 landscape; margin: 0; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family: 'Segoe UI', Arial, sans-serif; background:#f4f7f6; }}
  .lienzo {{ width:1122px; height:793px; padding:34px 40px; display:flex; flex-direction:column; }}
  .cab {{ text-align:center; margin-bottom:14px; }}
  .cab h1 {{ margin:0; font-size:40px; letter-spacing:2px; color:#0f5c4d; }}
  .cab h2 {{ margin:6px 0 0; font-size:18px; font-weight:600; letter-spacing:3px; color:#2e8b74; }}
  .centro {{ align-self:center; background:#0f5c4d; color:#fff; padding:14px 34px; border-radius:40px;
            font-size:26px; font-weight:700; box-shadow:0 6px 14px rgba(0,0,0,.15); }}
  .linea {{ height:3px; background:#bfe0d6; margin:16px 6px 22px; }}
  .ramas {{ display:grid; grid-template-columns:repeat({n},1fr); gap:20px; flex:1; }}
  .rama {{ background:#fff; border-radius:16px; padding:16px 16px 18px; border-top:8px solid #2e8b74;
          box-shadow:0 4px 12px rgba(0,0,0,.08); display:flex; flex-direction:column; }}
  .rama h3 {{ margin:0 0 10px; font-size:19px; color:#0f5c4d; text-align:center; }}
  .rama ul {{ margin:0; padding-left:18px; }}
  .rama li {{ font-size:15px; color:#333; margin:6px 0; line-height:1.35; }}
  .pie {{ text-align:center; margin-top:12px; font-size:12px; color:#6b7d78; }}
</style></head><body>
  <div class="lienzo">
    <div class="cab"><h1>{titulo}</h1><h2>{subtitulo}</h2></div>
    <div class="centro">{titulo}</div>
    <div class="linea"></div>
    <div class="ramas">{ramas}</div>
    <div class="pie">Universidad de Cartagena · CTEV — elaborado por Arturo Andrés Baena Arias</div>
  </div>
</body></html>"""


def generar_html(contenido):
    ramas = contenido.get("ramas", [])
    n = max(1, min(len(ramas), 4))
    bloques = []
    for r in ramas:
        items = "".join("<li>%s</li>" % html.escape(str(i)) for i in r.get("items", []))
        bloques.append('<div class="rama"><h3>%s</h3><ul>%s</ul></div>'
                       % (html.escape(r.get("titulo", "")), items))
    return PLANTILLA.format(
        n=n,
        titulo=html.escape(contenido.get("titulo", "")),
        subtitulo=html.escape(contenido.get("subtitulo", "")),
        ramas="".join(bloques))


def render(html_str, salida, navegador=None):
    from playwright.sync_api import sync_playwright
    navegador = navegador or _navegador()
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=navegador, headless=True) if navegador else p.chromium.launch(headless=True)
        pg = b.new_page(viewport={"width": 1122, "height": 793})
        pg.set_content(html_str, wait_until="load")
        pg.wait_for_timeout(600)
        if salida.lower().endswith(".png"):
            pg.screenshot(path=salida, full_page=True)
        else:
            pg.pdf(path=salida, width="1122px", height="793px", print_background=True, landscape=True)
        b.close()
    return salida


def _construir(ap):
    ap.add_argument("--contenido", required=True, help="JSON del mentefacto")
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
                        prog="mentefacto",
                        descripcion="Genera un mentefacto (HTML -> PDF/PNG)."))
