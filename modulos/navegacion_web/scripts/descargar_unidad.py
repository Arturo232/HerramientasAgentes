#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Descarga por lotes los archivos (modulos/adjuntos) de un curso de Moodle/SIMA.

Usa la API (moodle_api.estructura) para obtener las URLs y descarga con el token.
Organiza por curso/unidad. Requiere token (ver sima_token.py).

Uso:
    python descargar_unidad.py --curso 869
    python descargar_unidad.py --curso 869 --unidad 1 --salida "C:\\ruta\\materia"
    python descargar_unidad.py --curso 869 --solo-modulos
"""
import os
import re
import sys
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
import moodle_api  # noqa: E402
from nucleo import cli  # noqa: E402
from nucleo.contrato import exito  # noqa: E402
from nucleo.errores import AgenteError  # noqa: E402
from nucleo.registro import artefacto  # noqa: E402


def _slug(s):
    s = re.sub(r"[^\w\s.-]", "", s, flags=re.UNICODE)
    return re.sub(r"\s+", " ", s).strip()[:80]


def _descargar(url, destino, timeout=90):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    with open(destino, "wb") as f:
        f.write(data)
    return len(data)


def _construir(ap):
    ap.add_argument("--curso", type=int, help="ID del curso (o usar --materia)")
    ap.add_argument("--materia", help="Nombre de la materia (se resuelve con config.json)")
    ap.add_argument("--unidad", type=int, help="Numero de unidad/seccion (si se omite, todo)")
    ap.add_argument("--salida", default=None, help="Carpeta destino")
    ap.add_argument("--base", default=moodle_api.DEFAULT_BASE)
    ap.add_argument("--token")
    ap.add_argument("--solo-modulos", action="store_true", help="Solo modulos (resource), sin adjuntos de tareas")
    ap.add_argument("--sin-cache", action="store_true")


def _accion(ns):
    if not ns.curso and ns.materia:
        import config
        ns.curso = config.curso(ns.materia)
        if not ns.curso:
            raise AgenteError("navegacion_web", "materiaNoEncontrada",
                              "Materia no encontrada en config.json: %s" % ns.materia)
    if not ns.curso:
        raise AgenteError("navegacion_web", "sinCurso",
                          'Indica --curso N o --materia "Nombre"')

    data = moodle_api.estructura(ns.curso, ns.base, ns.token, cache=not ns.sin_cache)
    if ns.salida:
        base_dir = ns.salida
    else:
        try:
            import config
            base_dir = os.path.join(config.ruta("actividades"),
                                    (ns.materia or ("curso_%s" % ns.curso)).lower())
        except Exception:
            base_dir = os.path.join(os.getcwd(), "curso_%s" % ns.curso)
    descargados, fallidos = [], []

    for i, sec in enumerate(data["secciones"], 1):
        if ns.unidad is not None and i != ns.unidad:
            continue
        sec_dir = os.path.join(base_dir, "unidad %d" % i)
        for a in sec["actividades"]:
            urls = a.get("urls") or []
            if not urls and not ns.solo_modulos:
                continue
            for u in urls:
                nombre = os.path.basename(u.split("?")[0])
                destino = os.path.join(sec_dir, _slug(nombre))
                os.makedirs(sec_dir, exist_ok=True)
                try:
                    n = _descargar(u, destino)
                    descargados.append({"archivo": destino, "bytes": n})
                    print("OK  %-60s %d bytes" % (nombre[:60], n),
                          file=sys.stderr, flush=True)
                except Exception as e:
                    fallidos.append({"url": u, "error": str(e)[:80]})
                    print("ERR %-60s %s" % (nombre[:60], str(e)[:60]),
                          file=sys.stderr, flush=True)

    return exito(
        datos={"descargados": descargados, "fallidos": fallidos,
               "total": len(descargados), "carpeta": base_dir},
        meta={"curso": ns.curso},
        artefactos=[artefacto("archivo", d["archivo"]) for d in descargados],
    )


if __name__ == "__main__":
    sys.exit(cli.correr("navegacion_web", _construir, _accion, sys.argv[1:],
                        prog="descargar_unidad",
                        descripcion="Descarga archivos de un curso Moodle/SIMA."))
