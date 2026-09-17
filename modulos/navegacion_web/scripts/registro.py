"""Memoria del modulo de navegacion web: plataformas, sesiones y recetas.

- Plataformas y sesiones se guardan en LOCAL (~/.config/opencode/navegacion/).
- Las recetas (scripts reutilizables) se guardan en el repo (recetas/), para
  compartir el aprendizaje. La ruta se puede cambiar con HERRAMIENTAS_RECETAS.
"""

import datetime
import json
import os
import sys

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
from nucleo import cli  # noqa: E402
from nucleo.contrato import exito  # noqa: E402

LOCAL = os.path.join(os.path.expanduser("~"), ".config", "opencode", "navegacion")
PLATAFORMAS = os.path.join(LOCAL, "plataformas.json")
SESIONES = os.path.join(LOCAL, "sesiones.jsonl")
MODULO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECETAS = os.environ.get("HERRAMIENTAS_RECETAS", os.path.join(MODULO, "recetas"))
INDICE = os.path.join(RECETAS, "indice.json")


def _ahora():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _leer_json(ruta, defecto):
    if os.path.exists(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return defecto


def _escribir_json(ruta, datos):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)


def registrar_plataforma(nombre, url="", login="", via="", notas=""):
    plataformas = _leer_json(PLATAFORMAS, {})
    reg = plataformas.get(nombre, {})
    reg.update({"url": url or reg.get("url", ""),
                "login": login or reg.get("login", ""),
                "via": via or reg.get("via", ""),
                "notas": notas or reg.get("notas", ""),
                "ultima_vez": _ahora()})
    plataformas[nombre] = reg
    _escribir_json(PLATAFORMAS, plataformas)
    return reg


def registrar_sesion(url, accion, via, resultado, notas=""):
    os.makedirs(LOCAL, exist_ok=True)
    linea = {"fecha": _ahora(), "url": url, "accion": accion, "via": via,
             "resultado": resultado, "notas": notas}
    with open(SESIONES, "a", encoding="utf-8") as f:
        f.write(json.dumps(linea, ensure_ascii=False) + "\n")
    return linea


def guardar_receta(nombre, descripcion, codigo, palabras_clave=None):
    os.makedirs(RECETAS, exist_ok=True)
    archivo = nombre if nombre.endswith(".py") else nombre + ".py"
    ruta = os.path.join(RECETAS, archivo)
    cabecera = ('"""%s\n\nGenerada automaticamente por el modulo de navegacion web.\n'
                "No versionar credenciales. Uso academico/personal.\n\"\"\"\n\n" % descripcion)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(cabecera + codigo.rstrip() + "\n")
    indice = _leer_json(INDICE, {})
    indice[archivo] = {"descripcion": descripcion,
                       "palabras_clave": palabras_clave or [],
                       "fecha": _ahora()}
    _escribir_json(INDICE, indice)
    return ruta


def listar_recetas():
    return _leer_json(INDICE, {})


def buscar_receta(consulta):
    consulta = consulta.lower()
    hallazgos = []
    for archivo, meta in listar_recetas().items():
        texto = (archivo + " " + meta.get("descripcion", "") + " " +
                 " ".join(meta.get("palabras_clave", []))).lower()
        if consulta in texto:
            hallazgos.append({"archivo": archivo, **meta})
    return hallazgos


def _construir(ap):
    sub = ap.add_subparsers(dest="comando")

    p = sub.add_parser("plataforma", help="Registrar/actualizar una plataforma")
    p.add_argument("--nombre", required=True)
    p.add_argument("--url", default="")
    p.add_argument("--login", default="")
    p.add_argument("--via", default="")
    p.add_argument("--notas", default="")
    cli.agregar_flags_comunes(p)

    p = sub.add_parser("sesion", help="Registrar una sesion de navegacion")
    p.add_argument("--url", required=True)
    p.add_argument("--accion", required=True)
    p.add_argument("--via", required=True)
    p.add_argument("--resultado", default="ok")
    p.add_argument("--notas", default="")
    cli.agregar_flags_comunes(p)

    p = sub.add_parser("listar", help="Listar plataformas, sesiones o recetas")
    p.add_argument("que", choices=["plataformas", "sesiones", "recetas"])
    p.add_argument("--n", type=int, default=20)
    cli.agregar_flags_comunes(p)

    p = sub.add_parser("receta", help="Guardar una receta desde un archivo .py")
    p.add_argument("--archivo", required=True, help="Script .py a guardar")
    p.add_argument("--nombre", required=True)
    p.add_argument("--descripcion", required=True)
    p.add_argument("--palabras-clave", default="")
    cli.agregar_flags_comunes(p)

    p = sub.add_parser("buscar-receta", help="Buscar recetas por palabra clave")
    p.add_argument("--consulta", "-q", required=True)
    cli.agregar_flags_comunes(p)


def _accion(ns):
    if ns.comando == "plataforma":
        reg = registrar_plataforma(ns.nombre, ns.url, ns.login, ns.via, ns.notas)
        return exito(datos={"plataforma": ns.nombre, "registro": reg})
    if ns.comando == "sesion":
        return exito(datos=registrar_sesion(
            ns.url, ns.accion, ns.via, ns.resultado, ns.notas))
    if ns.comando == "listar":
        if ns.que == "plataformas":
            return exito(datos=_leer_json(PLATAFORMAS, {}))
        if ns.que == "recetas":
            return exito(datos=listar_recetas())
        sesiones = []
        if os.path.exists(SESIONES):
            with open(SESIONES, "r", encoding="utf-8") as f:
                for linea in f.readlines()[-ns.n:]:
                    if linea.strip():
                        sesiones.append(json.loads(linea))
        return exito(datos={"sesiones": sesiones})
    if ns.comando == "receta":
        with open(ns.archivo, "r", encoding="utf-8") as f:
            codigo = f.read()
        claves = [k.strip() for k in ns.palabras_clave.split(",") if k.strip()]
        ruta = guardar_receta(ns.nombre, ns.descripcion, codigo, claves)
        return exito(datos={"receta": ruta})
    if ns.comando == "buscar-receta":
        return exito(datos=buscar_receta(ns.consulta))
    return exito(datos={"uso": "subcomandos: plataforma | sesion | listar | receta | buscar-receta"})


if __name__ == "__main__":
    sys.exit(cli.correr("navegacion_web", _construir, _accion, sys.argv[1:],
                        prog="registro",
                        descripcion="Memoria del modulo de navegacion web."))
