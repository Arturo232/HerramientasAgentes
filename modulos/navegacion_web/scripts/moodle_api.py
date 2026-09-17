#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cliente REST de Moodle (SIMA) usando el token del servicio movil.

Requiere un token guardado (ver sima_token.py). Evita el scraping: consulta la
API oficial (core_*).

Uso:
    python moodle_api.py site
    python moodle_api.py cursos
    python moodle_api.py contenidos --curso 869
    python moodle_api.py tareas --curso 869
    python moodle_api.py estructura --curso 869 [--salida est.json]
    python moodle_api.py archivos --curso 869

Opciones: --base URL, --token TOKEN (si no, se lee de sima_token.json)
"""
import json
import os
import ssl
import sys
import time
import urllib.parse
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _AQUI)
_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(_AQUI)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
try:
    import config
    DEFAULT_BASE = config.base_sima()
except Exception:
    config = None
    DEFAULT_BASE = "https://sima.unicartagena.edu.co"
from nucleo import cli  # noqa: E402
from nucleo.contrato import exito  # noqa: E402
from nucleo.errores import AgenteError  # noqa: E402
from nucleo.registro import artefacto  # noqa: E402

LOCAL = os.path.join(os.path.expanduser("~"), ".config", "opencode", "navegacion")
TOKENS = os.path.join(LOCAL, "sima_token.json")
CACHE_TTL = 3600  # segundos


def token_guardado(base=DEFAULT_BASE):
    try:
        return json.load(open(TOKENS, encoding="utf-8")).get(base.rstrip("/"), {}).get("token")
    except Exception:
        return None


def _flatten(params, prefijo=None):
    out = {}
    for k, v in params.items():
        key = ("%s[%s]" % (prefijo, k)) if prefijo else k
        if isinstance(v, (list, tuple)):
            for i, x in enumerate(v):
                out["%s[%d]" % (key, i)] = x
        elif isinstance(v, dict):
            out.update(_flatten(v, key))
        elif v is not None:
            out[key] = v
    return out


def call(wsfunction, base=DEFAULT_BASE, token=None, **params):
    token = token or token_guardado(base)
    if not token:
        raise AgenteError("navegacion_web", "sinToken",
                          "No hay token. Ejecuta: python sima_token.py")
    datos = {"wstoken": token, "wsfunction": wsfunction, "moodlewsrestformat": "json"}
    datos.update(_flatten(params))
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(base.rstrip("/") + "/webservice/rest/server.php",
                                 data=urllib.parse.urlencode(datos).encode(),
                                 headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
        data = json.loads(r.read().decode("utf-8", "replace"))
    if isinstance(data, dict) and data.get("exception"):
        raise AgenteError("navegacion_web", "api",
                          "API error (%s): %s" % (data.get("errorcode"), data.get("message")))
    return data


# ---------- funciones de alto nivel ----------
def site_info(base=DEFAULT_BASE, token=None):
    return call("core_webservice_get_site_info", base, token)


def cursos(base=DEFAULT_BASE, token=None):
    info = site_info(base, token)
    return call("core_enrol_get_users_courses", base, token, userid=info["userid"])


def contenidos(curso, base=DEFAULT_BASE, token=None):
    return call("core_course_get_contents", base, token, courseid=curso)


def tareas(curso, base=DEFAULT_BASE, token=None):
    # El servicio movil expone mod_assign_get_assignments (no core_assign_...)
    return call("mod_assign_get_assignments", base, token, courseids=[curso])


def estructura(curso, base=DEFAULT_BASE, token=None, cache=True, salida=None):
    """JSON compacto: secciones, actividades, tareas (con vencimiento) y archivos."""
    cache_path = os.path.join(LOCAL, "estructura_%s_%s.json" % (
        base.replace("https://", "").replace("/", "_"), curso))
    if cache and os.path.exists(cache_path) and (time.time() - os.path.getmtime(cache_path)) < CACHE_TTL:
        return json.load(open(cache_path, encoding="utf-8"))

    secs = contenidos(curso, base, token)
    asgs = tareas(curso, base, token)
    tareas_por_id = {}
    for c in asgs.get("courses", []):
        for a in c.get("assignments", []):
            tareas_por_id[a["id"]] = {
                "nombre": a["name"],
                "apertura": a.get("allowsubmissionsfromdate"),
                "cierre": a.get("duedate"),
                "archivos_intro": [f.get("filename") for f in a.get("introattachments", [])],
            }

    data = {"curso": curso, "secciones": []}
    for s in secs:
        mods = []
        for m in s.get("modules", []):
            item = {"tipo": m.get("modname"), "nombre": m.get("name"), "id": m.get("id")}
            if m.get("modname") == "assign":
                item.update(tareas_por_id.get(m.get("instance"), {}))
            if m.get("modname") in ("resource", "folder") and m.get("contents"):
                item["archivos"] = [c.get("filename") for c in m["contents"]]
                item["urls"] = [c.get("fileurl") for c in m["contents"]]
            mods.append(item)
        data["secciones"].append({"seccion": s.get("name") or ("Tema %s" % s.get("section")), "actividades": mods})

    os.makedirs(LOCAL, exist_ok=True)
    json.dump(data, open(cache_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if salida:
        json.dump(data, open(salida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return data


def _construir(ap):
    ap.add_argument("cmd", choices=["site", "cursos", "contenidos", "tareas", "estructura", "archivos"])
    ap.add_argument("--curso", type=int)
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--token")
    ap.add_argument("--salida")
    ap.add_argument("--sin-cache", action="store_true")


def _accion(ns):
    if ns.cmd == "site":
        info = site_info(ns.base, ns.token)
        return exito(datos={k: info.get(k) for k in ("sitename", "release", "username", "userid")})
    if ns.cmd == "cursos":
        return exito(datos=cursos(ns.base, ns.token))
    if ns.cmd == "contenidos":
        return exito(datos=contenidos(ns.curso, ns.base, ns.token))
    if ns.cmd == "tareas":
        return exito(datos=tareas(ns.curso, ns.base, ns.token))
    if ns.cmd == "estructura":
        data = estructura(ns.curso, ns.base, ns.token, cache=not ns.sin_cache, salida=ns.salida)
        arts = [artefacto("json", ns.salida)] if ns.salida else []
        return exito(datos=data, meta={"curso": ns.curso}, artefactos=arts)
    data = estructura(ns.curso, ns.base, ns.token)
    urls = [u for s in data["secciones"] for a in s["actividades"] for u in a.get("urls", [])]
    return exito(datos={"urls": urls, "total": len(urls)}, meta={"curso": ns.curso})


if __name__ == "__main__":
    sys.exit(cli.correr("navegacion_web", _construir, _accion, sys.argv[1:],
                        prog="moodle_api",
                        descripcion="Cliente REST de Moodle."))
