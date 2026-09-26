#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Controla un Chrome visible con perfil aislado via CDP.

Permite abrir un navegador propio (sin chocar con el navegador compartido de
otros chats) y controlarlo: navegar, leer texto, capturar, hacer click, etc.

Uso:
    python sesion_cdp.py abrir https://sitio/login
    python sesion_cdp.py paginas
    python sesion_cdp.py texto [indice]
    python sesion_cdp.py html [indice]
    python sesion_cdp.py captura salida.png [indice]
    python sesion_cdp.py ir https://sitio [indice]
    python sesion_cdp.py click "selector" [indice]
    python sesion_cdp.py escribir "selector" "texto" [indice]
    python sesion_cdp.py esperar "selector" [ms]
    python sesion_cdp.py evaluar "@archivo.js" | "js"
    python sesion_cdp.py links
    python sesion_cdp.py frames
    python sesion_cdp.py ftexto N
    python sesion_cdp.py feval N "@archivo.js"
    python sesion_cdp.py fclick N "selector"
    python sesion_cdp.py fkey N "Space"

Opciones:
    --puerto 9333     puerto de depuracion
    --perfil RUTA     carpeta de perfil persistente (cookies/sesion)
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

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

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DEFAULT_PROFILE = os.path.join(os.path.expanduser("~"), ".config", "opencode", "chrome-moodle")
DEFAULT_PORT = 9333


def cdp_vivo(port):
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/json/version" % port, timeout=2) as r:
            return json.load(r)
    except Exception:
        return None


def lanzar(url, port, perfil):
    if cdp_vivo(port):
        return
    os.makedirs(perfil, exist_ok=True)
    args = [CHROME, "--remote-debugging-port=%d" % port, "--user-data-dir=%s" % perfil,
            "--no-first-run", "--no-default-browser-check", "--disable-features=Translate",
            "--start-maximized", url]
    subprocess.Popen(args)
    for _ in range(30):
        time.sleep(0.5)
        if cdp_vivo(port):
            break


def conectar(port):
    from playwright.sync_api import sync_playwright
    p = sync_playwright().start()
    b = p.chromium.connect_over_cdp("http://127.0.0.1:%d" % port)
    ctx = b.contexts[0] if b.contexts else b.new_context()
    return p, ctx


def pag_activa(ctx, idx=0):
    ps = [pg for pg in ctx.pages if pg.url and pg.url != "about:blank"] or ctx.pages
    if not ps:
        ps = [ctx.new_page()]
    return ps[idx] if idx < len(ps) else ps[-1]


def _construir(ap):
    ap.add_argument("cmd")
    ap.add_argument("args", nargs="*")
    ap.add_argument("--puerto", type=int, default=DEFAULT_PORT)
    ap.add_argument("--perfil", default=DEFAULT_PROFILE)


def _accion(ns):
    cmd, rest = ns.cmd, ns.args

    if cmd == "abrir":
        lanzar(rest[0], ns.puerto, ns.perfil)
        p, ctx = conectar(ns.puerto)
        try:
            pg = pag_activa(ctx, 0)
            try:
                pg.goto(rest[0], wait_until="domcontentloaded", timeout=45000)
            except Exception:
                pass
            pg.wait_for_timeout(1500)
            return exito(datos={"url": pg.url, "titulo": pg.title()})
        finally:
            p.stop()

    p, ctx = conectar(ns.puerto)
    try:
        if cmd == "paginas":
            pags = [{"indice": i, "titulo": pg.title(), "url": pg.url}
                    for i, pg in enumerate(ctx.pages)]
            return exito(datos={"paginas": pags})
        if cmd == "texto":
            pg = pag_activa(ctx, int(rest[0]) if rest else 0)
            return exito(datos={"texto": pg.evaluate("document.body.innerText")})
        if cmd == "html":
            pg = pag_activa(ctx, int(rest[0]) if rest else 0)
            return exito(datos={"html": pg.evaluate("document.documentElement.outerHTML")})
        if cmd == "captura":
            pg = pag_activa(ctx, int(rest[1]) if len(rest) > 1 else 0)
            try:
                pg.screenshot(path=rest[0], full_page=True, timeout=8000, animations="disabled")
            except Exception:
                pg.screenshot(path=rest[0], timeout=8000, animations="disabled")
            return exito(datos={"archivo": rest[0]}, artefactos=[artefacto("png", rest[0])])
        if cmd == "ir":
            pg = pag_activa(ctx, int(rest[1]) if len(rest) > 1 else 0)
            pg.goto(rest[0], wait_until="domcontentloaded", timeout=45000)
            pg.wait_for_timeout(1200)
            return exito(datos={"url": pg.url, "titulo": pg.title()})
        if cmd == "click":
            pg = pag_activa(ctx, int(rest[1]) if len(rest) > 1 else 0)
            pg.click(rest[0], timeout=15000)
            pg.wait_for_timeout(1200)
            return exito(datos={"url": pg.url, "titulo": pg.title()})
        if cmd == "escribir":
            pg = pag_activa(ctx, int(rest[2]) if len(rest) > 2 else 0)
            pg.fill(rest[0], rest[1], timeout=15000)
            return exito(datos={"ok": True})
        if cmd == "esperar":
            pg = pag_activa(ctx, 0)
            pg.wait_for_selector(rest[0], timeout=int(rest[1]) if len(rest) > 1 else 30000)
            return exito(datos={"ok": True})
        if cmd == "evaluar":
            pg = pag_activa(ctx, 0)
            js = rest[0]
            if js.startswith("@"):
                js = open(js[1:], encoding="utf-8").read()
            return exito(datos={"resultado": pg.evaluate(js)})
        if cmd == "links":
            pg = pag_activa(ctx, 0)
            res = pg.evaluate(
                "Array.from(document.querySelectorAll('a'))"
                ".map(a=>({t:a.innerText.trim(),h:a.href})).filter(x=>x.t)")
            return exito(datos={"links": res})
        if cmd == "frames":
            pg = pag_activa(ctx, 0)
            frs = [{"indice": i, "nombre": fr.name or "-", "url": fr.url}
                   for i, fr in enumerate(pg.frames)]
            return exito(datos={"frames": frs})
        if cmd == "ftexto":
            pg = pag_activa(ctx, 0)
            return exito(datos={"texto": pg.frames[int(rest[0])].evaluate("document.body.innerText")})
        if cmd == "feval":
            pg = pag_activa(ctx, 0)
            js = rest[1]
            if js.startswith("@"):
                js = open(js[1:], encoding="utf-8").read()
            return exito(datos={"resultado": pg.frames[int(rest[0])].evaluate(js)})
        if cmd == "fclick":
            pg = pag_activa(ctx, 0)
            pg.frames[int(rest[0])].click(rest[1], timeout=15000)
            return exito(datos={"ok": True})
        if cmd == "fkey":
            pg = pag_activa(ctx, 0)
            pg.keyboard.press(rest[1])
            return exito(datos={"ok": True})
        raise AgenteError("navegacion_web", "comandoDesconocido",
                          "Comando desconocido: %s" % cmd)
    finally:
        p.stop()


if __name__ == "__main__":
    sys.exit(cli.correr("navegacion_web", _construir, _accion, sys.argv[1:],
                        prog="sesion_cdp",
                        descripcion="Control de Chrome por CDP."))
