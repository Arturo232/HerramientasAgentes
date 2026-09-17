# -*- coding: utf-8 -*-
"""Servidor MCP de HerramientasAgentes (sin dependencias).

Expone cada comando de ``capacidades.json`` como una **herramienta tipada** para
que una IA lo use de forma nativa. Implementa el transporte stdio de MCP
(JSON-RPC 2.0 delimitado por saltos de línea); no requiere el SDK.

El CLI sigue siendo la fuente de verdad; esto es un adaptador generado.

Métodos soportados: ``initialize``, ``tools/list``, ``tools/call``, ``ping``.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from nucleo import config  # noqa: E402

VERSION = "0.2.0"
PROTO_POR_DEFECTO = "2024-11-05"

TIPOS = {
    "ruta": "string",
    "url": "string",
    "cadena": "string",
    "json": "string",
    "entero": "integer",
    "numero": "number",
    "bandera": "boolean",
}


# --- Esquemas ----------------------------------------------------------------
def _prop(entrada):
    p = {
        "type": TIPOS.get(entrada.get("tipo"), "string"),
        "description": entrada.get("descripcion", entrada["nombre"]),
    }
    if entrada.get("valores"):
        p["enum"] = entrada["valores"]
    return p


def _esquema(cmd):
    props = {}
    required = []
    for e in list(cmd.get("entradas", [])) + list(cmd.get("opciones", [])):
        props[e["nombre"]] = _prop(e)
        if e.get("requerido"):
            required.append(e["nombre"])
    props["args"] = {"type": "array", "items": {"type": "string"},
                     "description": "Argumentos crudos adicionales (escape hatch)."}
    esquema = {"type": "object", "properties": props, "additionalProperties": False}
    if required:
        esquema["required"] = required
    return esquema


def _herramientas():
    return [
        {
            "name": cmd["id"],
            "description": "%s (módulo: %s)" % (cmd.get("descripcion", ""), cmd.get("modulo", "")),
            "inputSchema": _esquema(cmd),
        }
        for cmd in config.comandos()
    ]


# --- Ejecución ---------------------------------------------------------------
def _argv(cmd, args):
    out = []
    for e in cmd.get("entradas", []):
        if e["nombre"] not in args or args[e["nombre"]] is None:
            continue
        v = args[e["nombre"]]
        if e.get("posicional"):
            out.append(str(v))
        elif e.get("tipo") == "bandera":
            if v:
                out.append("--" + e["nombre"].replace("_", "-"))
        else:
            out += ["--" + e["nombre"].replace("_", "-"), str(v)]
    for o in cmd.get("opciones", []):
        if o["nombre"] not in args or args[o["nombre"]] is None:
            continue
        v = args[o["nombre"]]
        if o.get("tipo") == "bandera":
            if v:
                out.append("--" + o["nombre"].replace("_", "-"))
        else:
            out += ["--" + o["nombre"].replace("_", "-"), str(v)]
    out += [str(a) for a in (args.get("args") or [])]
    return out


def _ejecutar(comando_id, args):
    cmd = config.buscar(comando_id)
    if cmd is None:
        return {"ok": False, "error": {"codigo": "agente:mcp:desconocido",
                                       "mensaje": "Comando desconocido: %s" % comando_id}}
    argv = _argv(cmd, args)
    extra = [] if cmd.get("sin_json") else ["--json"]
    proc = subprocess.run(
        [sys.executable, os.path.join(RAIZ, "agente.py"), comando_id, *argv, *extra],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    for linea in reversed(proc.stdout.strip().splitlines()):
        try:
            return json.loads(linea)
        except Exception:
            continue
    return {"ok": False,
            "error": {"codigo": "agente:%s:salida" % cmd.get("modulo", "mcp"),
                      "mensaje": (proc.stderr or "sin salida").strip()[:500],
                      "causa": "exit=%s" % proc.returncode}}


# --- Transporte stdio --------------------------------------------------------
def _responder(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _resultado(mid, result):
    _responder({"jsonrpc": "2.0", "id": mid, "result": result})


def _error(mid, code, mensaje):
    _responder({"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": mensaje}})


def main():
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    for linea in sys.stdin:
        linea = linea.strip()
        if not linea:
            continue
        try:
            msg = json.loads(linea)
        except Exception:
            continue
        method = msg.get("method")
        mid = msg.get("id")

        if method == "initialize":
            proto = (msg.get("params") or {}).get("protocolVersion") or PROTO_POR_DEFECTO
            _resultado(mid, {
                "protocolVersion": proto,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "agente", "version": VERSION},
            })
        elif method in ("notifications/initialized", "initialized", "notifications/cancelled"):
            continue
        elif method == "ping":
            _resultado(mid, {})
        elif method == "tools/list":
            _resultado(mid, {"tools": _herramientas()})
        elif method == "tools/call":
            params = msg.get("params") or {}
            contrato = _ejecutar(params.get("name"), params.get("arguments") or {})
            _resultado(mid, {
                "content": [{"type": "text",
                             "text": json.dumps(contrato, ensure_ascii=False)}],
                "isError": not contrato.get("ok", False),
            })
        elif mid is not None:
            _error(mid, -32601, "Metodo no soportado: %s" % method)


if __name__ == "__main__":
    main()
