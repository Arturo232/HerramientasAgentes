"""Sincroniza las skills del repositorio con las skills globales de OpenCode.

Copia cada `modulos/<facultad>/skills/<skill>.md` (y `skills/<skill>.md`) a
`~/.config/opencode/skills/<skill-con-guiones>/SKILL.md`, y ademas copia los
scripts del modulo a la carpeta `scripts/` de la skill para que quede
autocontenida.
"""

import argparse
import os
import shutil
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
DESTINO_POR_DEFECTO = os.path.join(os.path.expanduser("~"), ".config", "opencode", "skills")


def nombre_skill(stem):
    return stem.replace("_", "-")


def recolectar(repo):
    tareas = []
    modulos = os.path.join(repo, "modulos")
    if os.path.isdir(modulos):
        for mod in sorted(os.listdir(modulos)):
            sk = os.path.join(modulos, mod, "skills")
            if not os.path.isdir(sk):
                continue
            scripts = os.path.join(modulos, mod, "scripts")
            for f in sorted(os.listdir(sk)):
                if f.endswith(".md"):
                    stem = os.path.splitext(f)[0]
                    tareas.append((os.path.join(sk, f), nombre_skill(stem), scripts))
    skroot = os.path.join(repo, "skills")
    if os.path.isdir(skroot):
        for f in sorted(os.listdir(skroot)):
            if f.endswith(".md"):
                stem = os.path.splitext(f)[0]
                tareas.append((os.path.join(skroot, f), nombre_skill(stem), None))
    return tareas


def sincronizar(destino, dry_run=False):
    tareas = recolectar(REPO)
    for origen, nombre, scripts in tareas:
        ddir = os.path.join(destino, nombre)
        marca = "[dry] " if dry_run else ""
        print("%s%s -> %s" % (marca, origen, os.path.join(ddir, "SKILL.md")))
        if dry_run:
            continue
        os.makedirs(ddir, exist_ok=True)
        shutil.copy2(origen, os.path.join(ddir, "SKILL.md"))
        if scripts and os.path.isdir(scripts):
            sdst = os.path.join(ddir, "scripts")
            os.makedirs(sdst, exist_ok=True)
            for sf in sorted(os.listdir(scripts)):
                if sf.endswith(".py"):
                    shutil.copy2(os.path.join(scripts, sf), os.path.join(sdst, sf))
    print("Sincronizadas %d skills en %s" % (len(tareas), destino))
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description="Sincroniza skills del repo con OpenCode.")
    ap.add_argument("--destino", default=DESTINO_POR_DEFECTO)
    ap.add_argument("--dry-run", action="store_true", help="Solo mostrar lo que haria")
    args = ap.parse_args(argv)
    return sincronizar(args.destino, args.dry_run)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
