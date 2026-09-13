"""Motor adaptativo de navegacion: elige la via segun la pagina.

Escalera:
  0. HTTP simple (urllib)            -> paginas publicas y estaticas.
  1. Playwright (headless)           -> JS/SPA.
  2. Playwright visible + login      -> requiere inicio de sesion manual.

Registra la sesion (via, resultado) en la memoria del modulo.
"""

import argparse
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import registro

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

NAVEGADORES = [
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    "/usr/bin/chromium", "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome-stable", "/usr/bin/google-chrome",
]


def _buscar_navegador():
    import shutil
    for ruta in NAVEGADORES:
        if os.path.isfile(ruta) or shutil.which(ruta):
            return ruta
    return None


def _texto_de_html(html):
    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    texto = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"[ \t]+", " ", re.sub(r"\s*\n\s*", "\n", texto)).strip()


def _intento_http(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if getattr(r, "status", 200) != 200:
                return None
            return r.read().decode("utf-8", "replace")
    except Exception:
        return None


def _parece_dinamico(html):
    bajo = html.lower()
    if "enable javascript" in bajo or "please enable javascript" in bajo:
        return True
    texto = _texto_de_html(html)
    if len(texto) < 80:
        return True
    if re.search(r'id="(root|app|__next|__nuxt)"', bajo) and len(texto) < 1500:
        return True
    return False


def _con_playwright(url, perfil, visible, esperar_selector, timeout):
    from playwright.sync_api import sync_playwright
    navegador = _buscar_navegador()
    with sync_playwright() as p:
        if perfil:
            ctx = p.chromium.launch_persistent_context(
                perfil, headless=not visible, executable_path=navegador)
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            cerrar = ctx.close
        else:
            browser = p.chromium.launch(headless=not visible, executable_path=navegador)
            page = browser.new_page()
            cerrar = browser.close
        page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
        if esperar_selector:
            try:
                page.wait_for_selector(esperar_selector, timeout=timeout * 1000)
            except Exception:
                pass
        page.wait_for_timeout(1500)
        requiere_login = (page.locator("input[type=password]").count() > 0
                          or re.search(r"(login|signin|sign-in|auth|accounts\.google)",
                                       page.url, re.I) is not None)
        if requiere_login and visible:
            print("Se detecto un login en %s. Inicia sesion y presiona Enter aqui..." % page.url)
            input("> Enter para continuar: ")
            page.wait_for_timeout(1000)
        contenido = {
            "texto": lambda: page.evaluate("document.body.innerText"),
            "html": lambda: page.evaluate("document.documentElement.outerHTML"),
        }
        resultado = {"url_final": page.url, "requiere_login": requiere_login}
        if not requiere_login:
            resultado["texto"] = contenido["texto"]()
            resultado["html"] = contenido["html"]()
        cerrar()
    return resultado


def navegar(url, modo="texto", salida=".", perfil=None, visible=False,
            esperar_selector=None, timeout=30, registrar=True):
    os.makedirs(salida, exist_ok=True)
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", re.sub(r"^https?://", "", url))[:60]
    ext = {"texto": "txt", "html": "html", "captura": "png"}[modo]
    archivo = os.path.join(salida, base + "." + ext)

    html = _intento_http(url, timeout)
    via = "http"
    requiere_login = False
    if html is not None and not _parece_dinamico(html):
        contenido = _texto_de_html(html) if modo == "texto" else html
        url_final = url
    else:
        via = "playwright"
        res = _con_playwright(url, perfil, visible, esperar_selector, timeout)
        url_final = res["url_final"]
        requiere_login = res.get("requiere_login", False)
        if requiere_login:
            via = "login-manual"
            contenido = ""
        else:
            contenido = res.get("texto", "") if modo == "texto" else res.get("html", "")

    if contenido:
        with open(archivo, "w", encoding="utf-8") as f:
            f.write(contenido)
    if registrar:
        try:
            registro.registrar_sesion(url, "navegar:" + modo, via,
                                      "login-requerido" if requiere_login else "ok")
        except Exception:
            pass
    return {"archivo": archivo if contenido else None, "via": via,
            "requiere_login": requiere_login, "url_final": url_final,
            "caracteres": len(contenido)}


def main(argv):
    ap = argparse.ArgumentParser(description="Navegacion adaptativa (HTTP/Playwright/login).")
    ap.add_argument("--input", "-i", required=True, help="URL")
    ap.add_argument("--modo", choices=["texto", "html"], default="texto")
    ap.add_argument("--salida", "-o", default=".")
    ap.add_argument("--perfil", help="Carpeta de perfil persistente (cookies/sesion)")
    ap.add_argument("--visible", action="store_true", help="Abrir el navegador visible")
    ap.add_argument("--esperar-selector", help="Esperar a que aparezca un selector CSS")
    ap.add_argument("--timeout", type=int, default=30)
    args = ap.parse_args(argv)

    res = navegar(args.input, args.modo, args.salida, args.perfil, args.visible,
                  args.esperar_selector, args.timeout)
    if res["requiere_login"]:
        print("La pagina requiere inicio de sesion. Reintenta con --visible --perfil CARPETA.")
    print("Via usada: %s" % res["via"])
    if res["archivo"]:
        print("Guardado: %s (%d caracteres)" % (res["archivo"], res["caracteres"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
