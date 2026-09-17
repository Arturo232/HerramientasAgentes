# -*- coding: utf-8 -*-
"""Alta de nuevos scripts como programas del sistema.

    agente nuevo <id> --modulo <mod> [--descripcion "..."] [--posicional cmd]
    agente integrar <archivo.py> --id <id> --modulo <mod> [--descripcion "..."]
    agente quitar <id>

Deja el script dentro del repo (en ``modulos/<mod>/scripts/``) y lo registra en
``capacidades.json``; desde ahí aparece en el CLI, el REPL y el MCP.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from nucleo import catalogo  # noqa: E402

PLANTILLA = '''# -*- coding: utf-8 -*-
"""{descripcion}

Uso:
    agente {id} {uso}
"""
import os
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(_AQUI)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
from nucleo import cli  # noqa: E402
from nucleo.contrato import exito  # noqa: E402
from nucleo.errores import AgenteError  # noqa: E402
from nucleo.registro import artefacto  # noqa: E402


def _construir(ap):
    {linea_posicional}ap.add_argument("--input", "-i", required=True, help="Archivo de entrada")
    ap.add_argument("--salida", "-o", help="Archivo o carpeta de salida")


def _accion(ns):
    # TODO: implementar la logica del script.
    #   - usa ns.input, ns.salida (y ns.{posicional} si aplica)
    #   - devuelve exito(datos=..., artefactos=[artefacto("tipo", ruta)])
    #   - ante un problema: raise AgenteError("{modulo}", "codigo", "mensaje")
    raise AgenteError("{modulo}", "noImplementado",
                      "El comando '{id}' aun no esta implementado.")


if __name__ == "__main__":
    sys.exit(cli.correr("{modulo}", _construir, _accion, sys.argv[1:],
                        prog="{id}", descripcion="{descripcion}"))
'''


def _rel(ruta):
    return os.path.relpath(ruta, RAIZ).replace("\\", "/")


def _asegurar_modulo(modulo, descripcion=None):
    mod_dir = os.path.join(RAIZ, "modulos", modulo)
    os.makedirs(os.path.join(mod_dir, "scripts"), exist_ok=True)
    mj = os.path.join(mod_dir, "modulo.json")
    if not os.path.exists(mj):
        with open(mj, "w", encoding="utf-8") as f:
            json.dump({"id": modulo, "descripcion": descripcion or modulo,
                       "produce": [], "delega_en": []}, f, ensure_ascii=False, indent=2)
            f.write("\n")
    return mod_dir


def cmd_nuevo(argv):
    ap = argparse.ArgumentParser(prog="agente nuevo",
                                 description="Crea un script nuevo como programa del sistema.")
    ap.add_argument("id", help="Identificador del comando (ej. resumen-clase)")
    ap.add_argument("--modulo", required=True, help="Modulo destino (ej. documentos)")
    ap.add_argument("--descripcion", default="", help="Descripcion del comando")
    ap.add_argument("--posicional", help="Argumento posicional obligatorio (ej. comando)")
    ap.add_argument("--reemplazar", action="store_true", help="Sobrescribir si existe")
    ns = ap.parse_args(argv)

    modulo_dir = _asegurar_modulo(ns.modulo, ns.descripcion)
    archivo = ns.id.replace("-", "_") + ".py"
    ruta = os.path.join(modulo_dir, "scripts", archivo)
    if os.path.exists(ruta) and not ns.reemplazar:
        print("Ya existe %s (usa --reemplazar)" % _rel(ruta), file=sys.stderr)
        return 1

    linea_posicional = (
        'ap.add_argument("%s", help="Argumento posicional")\n    ' % ns.posicional
        if ns.posicional else ""
    )
    uso = ("%s --input ARCHIVO" % ns.posicional) if ns.posicional else "--input ARCHIVO"
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(PLANTILLA.format(
            id=ns.id, modulo=ns.modulo,
            descripcion=ns.descripcion or ns.id,
            posicional=ns.posicional or "input",
            linea_posicional=linea_posicional, uso=uso,
        ))

    entradas = []
    if ns.posicional:
        entradas.append({"nombre": ns.posicional, "tipo": "cadena",
                         "posicional": True, "requerido": True})
    entradas.append({"nombre": "input", "tipo": "ruta", "requerido": True,
                     "descripcion": "Archivo de entrada"})
    entrada = {
        "id": ns.id, "modulo": ns.modulo, "script": _rel(ruta),
        "descripcion": ns.descripcion or ns.id,
        "entradas": entradas,
        "opciones": [{"nombre": "salida", "tipo": "ruta",
                      "descripcion": "Archivo o carpeta de salida"}],
        "produce": [], "delega_en": [],
    }
    catalogo.agregar(entrada, reemplazar=True)

    print("Script creado:   %s" % _rel(ruta))
    print("Registrado como: '%s' en capacidades.json" % ns.id)
    print("Visible en:      agente lista | agente ayuda %s | REPL | MCP" % ns.id)
    print("Siguiente:       implementa _accion() y corre 'agente sync'.")
    return 0


def cmd_integrar(argv):
    ap = argparse.ArgumentParser(prog="agente integrar",
                                 description="Integra un script existente como programa del sistema.")
    ap.add_argument("archivo", help="Ruta del script .py a integrar")
    ap.add_argument("--id", required=True, help="Identificador del comando")
    ap.add_argument("--modulo", required=True, help="Modulo destino")
    ap.add_argument("--descripcion", default="", help="Descripcion del comando")
    ap.add_argument("--reemplazar", action="store_true", help="Sobrescribir si existe")
    ns = ap.parse_args(argv)

    if not os.path.isfile(ns.archivo):
        print("No existe %s" % ns.archivo, file=sys.stderr)
        return 1

    modulo_dir = _asegurar_modulo(ns.modulo, ns.descripcion)
    archivo = ns.id.replace("-", "_") + ".py"
    destino = os.path.join(modulo_dir, "scripts", archivo)
    if os.path.exists(destino) and not ns.reemplazar:
        print("Ya existe %s (usa --reemplazar)" % _rel(destino), file=sys.stderr)
        return 1
    shutil.copy2(ns.archivo, destino)

    with open(destino, encoding="utf-8") as f:
        contenido = f.read()
    adaptado = ("from nucleo" in contenido) or ("import nucleo" in contenido)

    entrada = {
        "id": ns.id, "modulo": ns.modulo, "script": _rel(destino),
        "descripcion": ns.descripcion or ns.id,
        "entradas": [], "opciones": [], "produce": [], "delega_en": [],
    }
    if not adaptado:
        entrada["sin_json"] = True
    catalogo.agregar(entrada, reemplazar=True)

    print("Script guardado: %s" % _rel(destino))
    print("Registrado como: '%s' en capacidades.json" % ns.id)
    if adaptado:
        print("Contrato:        detectado (nucleo). OK.")
    else:
        print("Contrato:        NO adaptado; se registra como passthrough (sin --json).")
        print("                 Para el contrato completo, usa 'agente nuevo' o adaptalo")
        print("                 (ver docs/COMO_AGREGAR_SCRIPTS.md).")
    return 0


def cmd_quitar(argv):
    ap = argparse.ArgumentParser(prog="agente quitar",
                                 description="Quita un comando del catalogo.")
    ap.add_argument("id")
    ns = ap.parse_args(argv)
    if catalogo.quitar(ns.id):
        print("Quitado del catalogo: %s (el archivo del script NO se borra)" % ns.id)
        return 0
    print("No existe en el catalogo: %s" % ns.id, file=sys.stderr)
    return 1
