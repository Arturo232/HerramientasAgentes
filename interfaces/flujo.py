# -*- coding: utf-8 -*-
"""Composición de flujos (la "cinta transportadora").

Ejecuta una lista de comandos declarada en un JSON, encadenando los artefactos
del paso anterior con el siguiente. Es la versión ejecutable de los playbooks.

Formato del flujo::

    {
      "flujo": [
        {"comando": "pdf", "args": ["--input", "tarea.pdf", "--salida", "tmp"]},
        {"comando": "pdf-resumir", "args": ["--input", "{{ultimo}}"]},
        {"comando": "ensayo", "args": ["--input", "borrador.md"]}
      ]
    }

``{{ultimo}}`` se sustituye por la ruta del primer artefacto del paso anterior.
Se detiene en el primer paso que falle (``ok: false``).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from nucleo.contrato import exito, fallo  # noqa: E402


def _ejecutar_paso(comando, args):
    proc = subprocess.run(
        [sys.executable, os.path.join(RAIZ, "agente.py"), comando, *args, "--json"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    for linea in reversed(proc.stdout.strip().splitlines()):
        try:
            return json.loads(linea)
        except Exception:
            continue
    return {"ok": False,
            "error": {"codigo": "agente:flujo:salida",
                      "mensaje": (proc.stderr or "sin salida").strip()[:500],
                      "causa": "exit=%s" % proc.returncode}}


def ejecutar(ruta_flujo):
    with open(ruta_flujo, encoding="utf-8") as f:
        flujo = json.load(f)
    pasos = flujo.get("flujo", [])

    resultados = []
    ultimo = None
    for i, paso in enumerate(pasos):
        comando = paso.get("comando")
        if not comando:
            return fallo(("flujo", "pasoSinComando"), "El paso %d no tiene 'comando'" % i)
        args = [
            str(a).replace("{{ultimo}}", ultimo or "").replace("{{paso%d}}" % (i - 1), ultimo or "")
            for a in paso.get("args", [])
        ]
        data = _ejecutar_paso(comando, args)
        resultados.append({"paso": i, "comando": comando, "resultado": data})
        if not data.get("ok"):
            return fallo(("flujo", "pasoFallido"),
                         "Fallo el paso %d (%s)" % (i, comando),
                         data.get("error"))
        arts = data.get("artefactos") or []
        if arts:
            ultimo = arts[0].get("ruta")
    return exito(datos={"pasos": resultados, "total": len(resultados)})


def main(argv):
    if not argv:
        print("Uso: agente run <flujo.json> [--json]", file=sys.stderr)
        return 2
    ruta = argv[0]
    json_mode = "--json" in argv[1:]
    if not os.path.exists(ruta):
        res = fallo(("flujo", "noExiste"), "No existe el flujo: %s" % ruta)
    else:
        try:
            res = ejecutar(ruta)
        except Exception as e:  # noqa: BLE001
            res = fallo(("flujo", "interno"), str(e), repr(e))
    if json_mode:
        print(res.a_json())
    else:
        if res.ok:
            for p in res.datos["pasos"]:
                r = p["resultado"]
                print("[%d] %-14s ok=%s" % (p["paso"], p["comando"], r.get("ok")))
        else:
            err = res.error or {}
            print("[%s] %s" % (err.get("codigo"), err.get("mensaje")), file=sys.stderr)
    return 0 if res.ok else 1
