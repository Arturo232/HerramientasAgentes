#!/usr/bin/env python3
"""Agente local ultraligero: CLI de comandos cortos con salida JSON.

Invocado por el modelo local de Ollama (sub-2B) a través del wrapper `ha`.
Reutiliza el selector de herramientas del repositorio para enrutar
intenciones a los scripts existentes, ejecutarlos y leer su JSON de salida.
"""

import argparse
import json
import os
import subprocess
import sys

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
HA_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(BASE_DIR, ".venv", "bin", "python")

sys.path.insert(0, os.path.join(BASE_DIR, "scripts", "orquestador"))
from selector_herramientas import HERRAMIENTAS, seleccionar  # noqa: E402

with open(os.path.join(HA_DIR, "config.json"), encoding="utf-8") as _archivo:
    CONFIG = json.load(_archivo)

MODELO_EJECUTOR = CONFIG["modelo_ejecutor"]
MODELO_CHAT = CONFIG["modelo_chat"]
TIEMPO_MAX = CONFIG["tiempo_max_s"]

TAREAS_PESADAS = {
    "literatura": {
        "skill": "ensayo-apa",
        "palabras": [
            "ensayo", "ensayos", "informe", "informes", "redaccion", "redactar",
            "redacta", "tesis", "monografia", "articulo", "texto extenso",
            "resumen", "resumenes", "cuento", "novela",
        ],
    },
    "artes_diseno": {
        "skill": "director-creativo",
        "palabras": [
            "infografia", "infografias", "diapositiva", "diapositivas",
            "presentacion", "ppt", "pptx", "html", "css", "diseno", "diseño",
            "maquetar", "maquetacion", "cartel", "poster", "visual", "logo",
        ],
    },
    "matematicas": {
        "skill": "analista-logico",
        "palabras": [
            "matematica", "matematicas", "ecuacion", "ecuaciones", "derivada",
            "integral", "integrales", "estadistica", "probabilidad", "calculo",
            "algebra", "geometria",
        ],
    },
    "biologia_y_ciencias": {
        "skill": "investigador-cientifico",
        "palabras": [
            "biologia", "ecosistema", "ecosistemas", "celula", "celulas",
            "cuerpo humano", "fenomeno natural", "taxonomia", "quimica",
            "adn", "genetica", "fauna", "flora",
        ],
    },
    "programacion_y_tech": {
        "skill": "ingeniero-software",
        "palabras": [
            "codigo complejo", "script grande", "arquitectura de software",
            "refactorizar", "aplicacion web", "aplicacion movil",
            "crear un programa", "crear una aplicacion", "crear un script",
            "desarrollar un programa",
        ],
    },
}


def _python():
    """Devuelve el intérprete preferido (venv del repo si existe)."""
    if os.path.isfile(VENV_PYTHON):
        return VENV_PYTHON
    return sys.executable


def _ejecutar(comando, timeout=TIEMPO_MAX):
    try:
        resultado = subprocess.run(
            comando, capture_output=True, text=True, timeout=timeout
        )
        return resultado.returncode, resultado.stdout.strip(), resultado.stderr.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as error:
        return 1, "", str(error)


def listar():
    """Devuelve los comandos `ha` y las herramientas enrutables."""
    herramientas = [
        {
            "nombre": nombre,
            "script": herramienta["script"],
            "descripcion": herramienta["descripcion"],
            "argumentos_por_defecto": herramienta["argumentos"],
        }
        for nombre, herramienta in HERRAMIENTAS.items()
    ]
    return {
        "exito": True,
        "comandos_ha": [
            {"comando": "ha listar", "uso": "lista herramientas"},
            {"comando": 'ha decidir "texto"', "uso": "devuelve la accion exacta"},
            {"comando": 'ha enrutar "texto"', "uso": "obtiene el comando CLI"},
            {"comando": 'ha ejecutar "texto"', "uso": "enruta y ejecuta"},
            {"comando": "ha estado", "uso": "monitorea recursos y Ollama"},
            {"comando": 'ha redirigir "texto"', "uso": "detecta tarea pesada"},
            {"comando": 'ha chat "mensaje"', "uso": "responde desde el modelo local"},
        ],
        "herramientas": herramientas,
        "modelo_ejecutor": MODELO_EJECUTOR,
        "modelo_chat": MODELO_CHAT,
        "mensaje": "Lista de comandos del Agente Local Ultraligero.",
    }


def _clasificar_pesada(texto):
    """Devuelve (modulo, skill, motivo) si el texto es una tarea pesada."""
    minusculas = texto.lower()
    for modulo, datos in TAREAS_PESADAS.items():
        for palabra in datos["palabras"]:
            if palabra in minusculas:
                return modulo, datos["skill"], f"tarea pesada: {palabra}"
    return None, None, None


def redirigir(texto):
    """Detecta si la intención excede la capacidad del modelo local."""
    texto = texto.strip()
    if not texto:
        return {
            "exito": False,
            "redireccion": False,
            "mensaje": "La intencion esta vacia.",
        }
    enrutamiento = seleccionar(texto)
    if enrutamiento.get("exito"):
        return {
            "exito": True,
            "redireccion": False,
            "herramienta": enrutamiento["herramienta"],
            "mensaje": "Intencion operativa: ejecutable con el modelo local.",
        }
    modulo, skill, motivo = _clasificar_pesada(texto)
    if modulo:
        return {
            "exito": True,
            "redireccion": True,
            "modulo": modulo,
            "skill": skill,
            "motivo": motivo,
            "mensaje": (
                f"Tarea pesada detectada ({motivo}). El modelo local solo "
                f"ejecuta terminal; delega al modelo Cloud via el Orquestador "
                f"Maestro (skill {skill})."
            ),
        }
    return {
        "exito": False,
        "redireccion": False,
        "mensaje": (
            "No se pudo clasificar la intencion. Ejecutar `ha listar` para "
            "ver las herramientas disponibles."
        ),
    }


def enrutar(texto):
    """Devuelve el comando CLI sugerido para la intencion."""
    previo = redirigir(texto)
    if previo.get("redireccion"):
        return previo
    enrutamiento = seleccionar(texto)
    if not enrutamiento.get("exito"):
        return enrutamiento
    enrutamiento["comando_sugerido"] = (
        f"{os.path.basename(_python())} {enrutamiento['script']} "
        f"{' '.join(enrutamiento['argumentos'])}"
    )
    enrutamiento["ha_ejecutar"] = f'ha ejecutar "{texto}"'
    return enrutamiento


def ejecutar(texto):
    """Enruta, ejecuta el script local y devuelve su salida JSON."""
    previo = redirigir(texto)
    if previo.get("redireccion"):
        return previo
    enrutamiento = seleccionar(texto)
    if not enrutamiento.get("exito"):
        return enrutamiento
    script = os.path.join(BASE_DIR, enrutamiento["script"])
    comando = [_python(), script, *enrutamiento["argumentos"]]
    codigo, salida, error = _ejecutar(comando, timeout=TIEMPO_MAX)
    if codigo != 0:
        return {
            "exito": False,
            "herramienta": enrutamiento["herramienta"],
            "script": enrutamiento["script"],
            "returncode": codigo,
            "stderr": error or salida,
            "mensaje": "El script local fallo; reportando el error tal cual.",
        }
    try:
        datos = json.loads(salida)
    except (json.JSONDecodeError, ValueError):
        datos = {"salida_cruda": salida}
    datos["herramienta"] = enrutamiento["herramienta"]
    datos["script"] = enrutamiento["script"]
    datos["comando_ejecutado"] = " ".join(comando)
    return datos


def estado():
    """Monitorea recursos del sistema y modelos de Ollama."""
    python = _python()
    script = os.path.join(BASE_DIR, "scripts", "sistema", "mantenimiento_pc.py")
    codigo, salida, _error = _ejecutar([python, script, "--info"], timeout=TIEMPO_MAX)
    if codigo == 0:
        try:
            datos = json.loads(salida)
        except (json.JSONDecodeError, ValueError):
            datos = {"salida_cruda": salida}
    else:
        datos = {"mensaje": "No se pudo leer el estado del sistema."}
    _codigo, lista, _ = _ejecutar(["ollama", "list"], timeout=15)
    instalados = []
    if _codigo == 0:
        for linea in lista.splitlines()[1:]:
            if linea.strip():
                instalados.append(linea.split()[0])
    _codigo, ps, _ = _ejecutar(["ollama", "ps"], timeout=15)
    cargados = []
    if _codigo == 0:
        for linea in ps.splitlines()[1:]:
            if linea.strip():
                cargados.append(linea.split()[0])
    datos["modelos_recomendados"] = [MODELO_EJECUTOR, MODELO_CHAT]
    datos["modelos_instalados"] = instalados
    datos["modelos_cargados"] = cargados
    datos["modelos_faltantes"] = [
        modelo for modelo in (MODELO_EJECUTOR, MODELO_CHAT) if modelo not in instalados
    ]
    return datos


def _comando_bash(partes):
    """Construye el comando bash absoluto para copiar en la terminal."""
    ha = os.path.join(HA_DIR, "ha.sh")
    texto = " ".join(partes)
    if texto:
        return f'bash "{ha}" {texto}'
    return f'bash "{ha}"'


def decidir(texto):
    """Devuelve la acción exacta a ejecutar, sin usar ningún modelo.

    Lógica 100% determinista: si la intención es operativa, ordena ejecutar
    el script; si es pesada, ordena reportar la redirección; si no encaja,
    ordena consultar `ha chat`.
    """
    texto = texto.strip()
    if not texto:
        return {
            "exito": False,
            "accion": "chat",
            "comando": _comando_bash(["chat", '"dime que quieres hacer"']),
            "mensaje": "La intencion esta vacia; consultar al usuario.",
        }
    previo = redirigir(texto)
    if previo.get("redireccion"):
        return {
            "exito": True,
            "accion": "reportar_redireccion",
            "modulo": previo["modulo"],
            "skill": previo["skill"],
            "comando": None,
            "respuesta_al_usuario": (
                f"Esa es una tarea pesada para el modelo local. La delego al "
                f"modulo {previo['modulo']} (skill {previo['skill']}) para que "
                f"la resuelva el modelo Cloud via el Orquestador Maestro."
            ),
            "mensaje": previo["mensaje"],
        }
    if previo.get("exito"):
        return {
            "exito": True,
            "accion": "terminal",
            "herramienta": previo["herramienta"],
            "comando": _comando_bash(["ejecutar", f'"{texto}"']),
            "respuesta_al_usuario": None,
            "mensaje": (
                f"Ejecutar en la terminal el comando devuelto y responder al "
                f"usuario con una frase resumiendo su JSON."
            ),
        }
    return {
        "exito": True,
        "accion": "chat",
        "comando": _comando_bash(["chat", f'"{texto}"']),
        "mensaje": (
            "Intencion no operativa ni pesada; responder con `ha chat`."
        ),
    }


def chat(mensaje):
    """Responde desde el modelo local ultraligero sin ejecutar nada."""
    if not mensaje.strip():
        return {"exito": False, "respuesta": "El mensaje esta vacio."}
    consigna = (
        "Eres un asistente de terminal ultraligero en Arch Linux. "
        "IMPORTANTE: responde SOLO texto plano en español, maximo 3 lineas. "
        "NUNCA emitas tool calls, llamadas a funciones ni JSON. "
        "Si la peticion es una tarea pesada (ensayo, informe, diseno visual, "
        "HTML/CSS, codigo complejo, matematicas o ciencias), responde "
        "exactamente: TAREA PESADA: delega al Orquestador Maestro en modo "
        "Cloud. "
    )
    prompt = f"{consigna}\n\nUsuario: {mensaje}"
    codigo, salida, error = _ejecutar(
        ["ollama", "run", MODELO_CHAT, prompt], timeout=TIEMPO_MAX
    )
    if codigo != 0:
        return {
            "exito": False,
            "modelo": MODELO_CHAT,
            "respuesta": (
                "No se pudo invocar el modelo local. Verificar el servicio "
                "ollama.service."
            ),
            "stderr": error,
        }
    return {
        "exito": True,
        "modelo": MODELO_CHAT,
        "respuesta": salida,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Agente Local Ultraligero: comandos cortos con salida JSON"
    )
    sub = parser.add_subparsers(dest="comando")

    sub.add_parser("listar", help="lista los comandos y herramientas")

    p_decidir = sub.add_parser("decidir", help="devuelve la accion exacta")
    p_decidir.add_argument("texto", help="peticion del usuario")

    p_enrutar = sub.add_parser("enrutar", help="devuelve el comando CLI")
    p_enrutar.add_argument("texto", help="intencion del usuario")

    p_ejecutar = sub.add_parser("ejecutar", help="enruta y ejecuta el script")
    p_ejecutar.add_argument("texto", help="intencion del usuario")

    sub.add_parser("estado", help="monitorea recursos y Ollama")

    p_redirigir = sub.add_parser("redirigir", help="detecta tarea pesada")
    p_redirigir.add_argument("texto", help="peticion del usuario")

    p_chat = sub.add_parser("chat", help="responde desde el modelo local")
    p_chat.add_argument("mensaje", help="mensaje para el modelo local")

    args = parser.parse_args()

    if args.comando == "listar":
        resultado = listar()
    elif args.comando == "decidir":
        resultado = decidir(args.texto)
    elif args.comando == "enrutar":
        resultado = enrutar(args.texto)
    elif args.comando == "ejecutar":
        resultado = ejecutar(args.texto)
    elif args.comando == "estado":
        resultado = estado()
    elif args.comando == "redirigir":
        resultado = redirigir(args.texto)
    elif args.comando == "chat":
        resultado = chat(args.mensaje)
    else:
        parser.print_help()
        return 0

    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0 if resultado.get("exito", resultado.get("redireccion") is not None) else 1


if __name__ == "__main__":
    raise SystemExit(main())