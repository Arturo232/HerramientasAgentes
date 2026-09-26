#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Obtiene y guarda un token del servicio movil de Moodle (SIMA).

Las credenciales se piden por PROMPT LOCAL (getpass), nunca por chat, y no se
guardan: solo se guarda el TOKEN resultante en la memoria local
(~/.config/opencode/navegacion/sima_token.json), fuera de git.

Uso:
    python sima_token.py                      # pide usuario y clave
    python sima_token.py --usuario 123456     # pide solo la clave
    python sima_token.py --base https://sima.unicartagena.edu.co
    python sima_token.py --estado             # muestra si hay token guardado
    python sima_token.py --borrar
"""
import getpass
import json
import os
import ssl
import sys
import urllib.parse
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

LOCAL = os.path.join(os.path.expanduser("~"), ".config", "opencode", "navegacion")
TOKENS = os.path.join(LOCAL, "sima_token.json")
DEFAULT_BASE = "https://sima.unicartagena.edu.co"
SERVICE = "moodle_mobile_app"


def _post(url, datos, timeout=30):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    body = urllib.parse.urlencode(datos).encode()
    req = urllib.request.Request(url, data=body, headers={
        "User-Agent": "Mozilla/5.0", "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _leer():
    if os.path.exists(TOKENS):
        try:
            return json.load(open(TOKENS, encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _guardar(datos):
    os.makedirs(LOCAL, exist_ok=True)
    json.dump(datos, open(TOKENS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def obtener(base=DEFAULT_BASE, usuario=None, service=SERVICE):
    usuario = usuario or input("Usuario (numero de identificacion): ").strip()
    clave = getpass.getpass("Clave (no se muestra ni se guarda): ")
    res = _post(base.rstrip("/") + "/login/token.php",
                {"username": usuario, "password": clave, "service": service})
    if "token" not in res:
        raise AgenteError("navegacion_web", "auth",
                          "Error de autenticacion: %s" % res.get("error", res))
    reg = _leer()
    reg[base.rstrip("/")] = {"token": res["token"], "privatetoken": res.get("privatetoken", ""),
                             "usuario": usuario, "service": service}
    _guardar(reg)
    return res["token"]


def token_guardado(base=DEFAULT_BASE):
    return _leer().get(base.rstrip("/"), {}).get("token")


def _construir(ap):
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--usuario")
    ap.add_argument("--service", default=SERVICE)
    ap.add_argument("--estado", action="store_true")
    ap.add_argument("--borrar", action="store_true")


def _accion(ns):
    if ns.estado:
        t = token_guardado(ns.base)
        return exito(datos={"base": ns.base, "hay_token": bool(t),
                            "token": ("%s..." % t[:6]) if t else None})
    if ns.borrar:
        reg = _leer()
        reg.pop(ns.base.rstrip("/"), None)
        _guardar(reg)
        return exito(datos={"base": ns.base, "borrado": True})

    t = obtener(ns.base, ns.usuario, ns.service)
    return exito(datos={"base": ns.base, "token": "%s..." % t[:6], "guardado": True},
                 meta={"local": TOKENS})


if __name__ == "__main__":
    sys.exit(cli.correr("navegacion_web", _construir, _accion, sys.argv[1:],
                        prog="sima_token",
                        descripcion="Token del servicio movil de Moodle."))
