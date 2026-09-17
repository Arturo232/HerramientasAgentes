"""Sincroniza las skills del repositorio con las skills globales de OpenCode.

Copia, por cada módulo:
  - `modulos/<mod>/skills/<skill>.md`  ->  `~/.config/opencode/skills/<skill>/SKILL.md`
  - `modulos/<mod>/scripts/*.py`       ->  `.../<skill>/scripts/`
  - `modulos/<mod>/playbooks/**`       ->  `.../<skill>/playbooks/`
  - `modulos/<mod>/recetas/*`          ->  `.../<skill>/recetas/`
  - `modulos/<mod>/config.json`        ->  `.../<skill>/config.json`
  - `modulos/<mod>/*.md` (docs)        ->  `.../<skill>/`
  - `skills/<skill>.md` (raíz)         ->  `~/.config/opencode/skills/<skill>/SKILL.md`

La carpeta destino es **generada**: se puede borrar y recrear sin pérdida.
"""

import argparse
import os
import shutil
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
DESTINO_POR_DEFECTO = os.path.join(os.path.expanduser("~"), ".config", "opencode", "skills")


def nombre_skill(stem):
    return stem.replace("_", "-")


def _copiar_py(origen_dir, destino_dir):
    if not os.path.isdir(origen_dir):
        return 0
    os.makedirs(destino_dir, exist_ok=True)
    n = 0
    for f in sorted(os.listdir(origen_dir)):
        ruta = os.path.join(origen_dir, f)
        if os.path.isfile(ruta) and f.endswith((".py", ".json")):
            shutil.copy2(ruta, os.path.join(destino_dir, f))
            n += 1
    return n


def _copiar_md(origen_dir, destino_dir):
    if not os.path.isdir(origen_dir):
        return 0
    os.makedirs(destino_dir, exist_ok=True)
    n = 0
    for f in sorted(os.listdir(origen_dir)):
        ruta = os.path.join(origen_dir, f)
        if os.path.isfile(ruta) and f.endswith(".md"):
            shutil.copy2(ruta, os.path.join(destino_dir, f))
            n += 1
    return n


def recolectar(repo):
    """Devuelve tareas: (origen_skill, nombre, modulo_dir|None)."""
    tareas = []
    modulos = os.path.join(repo, "modulos")
    if os.path.isdir(modulos):
        for mod in sorted(os.listdir(modulos)):
            mod_dir = os.path.join(modulos, mod)
            sk = os.path.join(mod_dir, "skills")
            if not os.path.isdir(sk):
                continue
            for f in sorted(os.listdir(sk)):
                if f.endswith(".md"):
                    stem = os.path.splitext(f)[0]
                    tareas.append((os.path.join(sk, f), nombre_skill(stem), mod_dir))
    skroot = os.path.join(repo, "skills")
    if os.path.isdir(skroot):
        for f in sorted(os.listdir(skroot)):
            if f.endswith(".md"):
                stem = os.path.splitext(f)[0]
                tareas.append((os.path.join(skroot, f), nombre_skill(stem), None))
    return tareas


def sincronizar(destino, dry_run=False):
    tareas = recolectar(REPO)
    total = 0
    for origen, nombre, mod_dir in tareas:
        ddir = os.path.join(destino, nombre)
        marca = "[dry] " if dry_run else ""
        print("%s%s -> %s" % (marca, origen, os.path.join(ddir, "SKILL.md")))
        if not dry_run:
            os.makedirs(ddir, exist_ok=True)
            shutil.copy2(origen, os.path.join(ddir, "SKILL.md"))
            if mod_dir:
                _copiar_py(os.path.join(mod_dir, "scripts"), os.path.join(ddir, "scripts"))
                _copiar_md(os.path.join(mod_dir, "playbooks"), os.path.join(ddir, "playbooks"))
                _copiar_py(os.path.join(mod_dir, "recetas"), os.path.join(ddir, "recetas"))
                cfg = os.path.join(mod_dir, "config.json")
                if os.path.isfile(cfg):
                    shutil.copy2(cfg, os.path.join(ddir, "config.json"))
                # docs sueltas del módulo (excepto la skill)
                for f in sorted(os.listdir(mod_dir)):
                    ruta = os.path.join(mod_dir, f)
                    if os.path.isfile(ruta) and f.endswith(".md"):
                        shutil.copy2(ruta, os.path.join(ddir, f))
        total += 1
    print("Sincronizadas %d skills en %s" % (total, destino))
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description="Sincroniza skills del repo con OpenCode.")
    ap.add_argument("--destino", default=DESTINO_POR_DEFECTO)
    ap.add_argument("--dry-run", action="store_true", help="Solo mostrar lo que haria")
    args = ap.parse_args(argv)
    return sincronizar(args.destino, args.dry_run)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
