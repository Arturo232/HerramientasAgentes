#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inventario de actividades de un curso Moodle (tipo H5P + requisito).

Recorre las secciones del curso, lista las actividades y, para las de tipo H5P,
detecta la libreria (via H5PIntegration con fetch, rapido) y el requisito de
finalizacion.

Uso:
    python inventario_moodle.py --curso 444
    python inventario_moodle.py --curso 444 --pendientes --salida inventario.json
"""
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from playwright.sync_api import sync_playwright

_AQUI = os.path.dirname(os.path.abspath(__file__))
_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(_AQUI)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
from nucleo import cli  # noqa: E402
from nucleo.contrato import exito  # noqa: E402
from nucleo.registro import artefacto  # noqa: E402

CDP = "http://127.0.0.1:9333"

JS_ACT = r"""
() => {
  const out = [];
  document.querySelectorAll('li.activity, li.modtype_page, li.modtype_assign, li.modtype_hvp, li.modtype_forum, li.modtype_quiz, li.modtype_resource, li.modtype_url, li.modtype_board, li.modtype_book').forEach(li => {
    const a = li.querySelector('a.aalink, a[href*="/mod/"]');
    const nameEl = li.querySelector('.instancename');
    const comp = li.querySelector('[data-region="completion"] button, .completion-dropdown button, .autocompletion');
    out.push({
      name: nameEl ? nameEl.innerText.replace(/\n/g, ' / ').trim() : (a ? a.innerText.trim() : ''),
      href: a ? a.href : '',
      completion: comp ? comp.innerText.trim() : ''
    });
  });
  return out;
}
"""

JS_LIB = r"""
async (url) => {
  try {
    const t = await fetch(url, {credentials: 'include'}).then(r => r.text());
    const m = t.match(/"library":"(H5P\.[^"]+)"/);
    return m ? m[1].split(' ')[0] : '';
  } catch (e) { return ''; }
}
"""


def _construir(ap):
    ap.add_argument("--curso", required=True, help="ID del curso")
    ap.add_argument("--base", default="https://ingles.unicartagena.edu.co")
    ap.add_argument("--secciones", type=int, default=6)
    ap.add_argument("--pendientes", action="store_true", help="Solo pendientes/sin seguimiento")
    ap.add_argument("--salida", default="inventario.json")


def _accion(ns):
    p = sync_playwright().start()
    b = p.chromium.connect_over_cdp(CDP)
    ctx = b.contexts[0]
    pg = [x for x in ctx.pages if "unicartagena" in x.url or "moodle" in x.url][0]

    items = []
    for sec in range(ns.secciones):
        pg.goto("%s/course/view.php?id=%s&section=%d" % (ns.base, ns.curso, sec),
                wait_until="domcontentloaded")
        pg.wait_for_timeout(3000)
        for a in pg.evaluate(JS_ACT):
            if not a["name"]:
                continue
            if ns.pendientes and a["completion"] and "Pendiente" not in a["completion"]:
                continue
            items.append({"sec": sec, **a})

    for it in items:
        it["tipo"] = ""
        if "/mod/hvp/" in it["href"]:
            it["tipo"] = pg.evaluate(JS_LIB, it["href"]) or ""
        print("%-28s %s" % (it["tipo"][:28], it["name"][:55]),
              file=sys.stderr, flush=True)

    json.dump(items, open(ns.salida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    p.stop()
    return exito(datos={"items": items, "total": len(items)},
                 meta={"curso": ns.curso, "base": ns.base},
                 artefactos=[artefacto("json", ns.salida)])


if __name__ == "__main__":
    sys.exit(cli.correr("navegacion_web", _construir, _accion, sys.argv[1:],
                        prog="inventario_moodle",
                        descripcion="Inventario de actividades Moodle."))
