#!/usr/bin/env python3
"""Selector de herramientas del repositorio HerramientasAgente.

Lee la intención del usuario en lenguaje natural y devuelve un JSON con
el script a ejecutar (redes, datos o sistema) y los argumentos CLI sugeridos.
"""

import argparse
import json
import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HERRAMIENTAS = {
    "redes": {
        "script": "scripts/redes/diagnosticar_red.py",
        "descripcion": "Diagnostico y reconexion automatica de red (internet y Ollama local)",
        "palabras_clave": [
            "internet", "red", "wifi", "wi-fi", "conexion", "desconectado",
            "offline", "reconectar", "latencia", "dns", "navegar", "en linea",
            "senal", "sin senal", "red caida", "falla de red",
        ],
        "argumentos": ["--sin-reconexion"],
        "gatillos": {
            "reconectar": [],
            "diagnostico": ["--sin-reconexion"],
        },
        "gatillos_reconectar": [
            "reconectar", "arreglar", "solucionar", "reparar", "problemas",
            "problema", "falla", "caida", "se cayo", "cayo",
        ],
    },
    "datos": {
        "script": "scripts/datos/generar_excel.py",
        "descripcion": "Generacion de reportes Excel profesionales desde JSON",
        "palabras_clave": [
            "excel", "xlsx", "hoja de calculo", "reporte", "tabla", "ventas",
            "finanzas", "presupuesto", "inventario", "datos", "csv", "json",
        ],
        "argumentos": ["--test"],
        "gatillos": {
            "prueba": ["--test"],
            "generar": ["--test"],
        },
        "gatillos_reconectar": [],
    },
    "sistema": {
        "script": "scripts/sistema/mantenimiento_pc.py",
        "descripcion": "Monitoreo de recursos (RAM, CPU, disco, Ollama) y limpieza del sistema",
        "palabras_clave": [
            "ram", "cpu", "disco", "memoria", "recursos", "mantenimiento",
            "limpiar", "limpieza", "cache", "pacman", "espacio", "pc lenta",
            "huerfano", "huerfanos", "sistema", "monitoreo", "estado de la pc",
            "pc", "computador", "equipo",
        ],
        "argumentos": ["--info"],
        "gatillos": {
            "limpiar": ["--limpiar"],
            "info": ["--info"],
        },
        "gatillos_reconectar": [],
    },
    "libro": {
        "script": "scripts/datos/construir_libro_pdf.py",
        "descripcion": "Modulo unificado de libros PDF: extraccion con pdf-inspector, traduccion por lotes, portada e imagenes con PyMuPDF, conversion Markdown a LaTeX y compilacion con XeLaTeX",
        "palabras_clave": [
            "traducir libro pdf", "compilar libro pdf", "construir libro",
            "traducir y generar libro", "construir libro pdf", "compilar libro",
            "generar libro", "maquetar libro", "libro pdf", "traducir libro",
        ],
        "argumentos": [],
        "gatillos": {},
        "gatillos_reconectar": [],
        "idiomas": [
            "espanol", "español", "ingles", "inglés", "frances", "francés",
            "portugues", "portugués", "aleman", "alemán", "italiano", "chino",
            "japones", "japonés", "ruso",
        ],
    },
}


def _emparejar(intencion):
    """Devuelve {herramienta: puntaje} según palabras clave encontradas."""
    texto = intencion.lower()
    puntajes = {}
    for nombre, herramienta in HERRAMIENTAS.items():
        puntaje = sum(
            1 for palabra in herramienta["palabras_clave"] if palabra in texto
        )
        if puntaje:
            puntajes[nombre] = puntaje
    return puntajes


def _extraer_pdf(intencion):
    """Devuelve la ruta .pdf encontrada en la intencion, o None."""
    coincidencias = re.findall(r"[\w./~-]+\.pdf", intencion, flags=re.IGNORECASE)
    return coincidencias[0] if coincidencias else None


def _extraer_idioma(intencion, herramienta):
    """Devuelve el idioma de destino detectado en la intencion, o default."""
    texto = intencion.lower()
    for idioma in herramienta.get("idiomas", []):
        if idioma in texto:
            return idioma.replace("é", "e").replace("ñ", "n")
    return "espanol"


def _argumentos_sugeridos(nombre, intencion):
    """Devuelve los argumentos CLI según matices de la intención."""
    herramienta = HERRAMIENTAS[nombre]
    texto = intencion.lower()
    if nombre == "redes":
        if any(p in texto for p in herramienta["gatillos_reconectar"]):
            return []
        return ["--sin-reconexion"]
    if nombre == "datos":
        return ["--test"]
    if nombre == "sistema":
        if any(p in texto for p in ("limpiar", "limpieza", "cache", "huerfano", "huerfanos", "mantenimiento")):
            return ["--limpiar"]
        return ["--info"]
    if nombre == "libro":
        ruta = _extraer_pdf(intencion)
        if not ruta:
            return None
        argumentos = ["--pdf", ruta]
        if any(p in texto for p in ("traducir", "traduce", "traduccion")):
            idioma = _extraer_idioma(intencion, herramienta)
            argumentos += ["--traducir", "--idioma", idioma]
        return argumentos
    return herramienta["argumentos"]


def seleccionar(intencion):
    """Devuelve el dict JSON de enrutamiento para la intención dada."""
    intencion = intencion.strip()
    if not intencion:
        return {
            "exito": False,
            "herramienta": "desconocido",
            "mensaje": "La intencion esta vacia.",
        }
    puntajes = _emparejar(intencion)
    if not puntajes:
        return {
            "exito": False,
            "herramienta": "desconocido",
            "herramientas_disponibles": list(HERRAMIENTAS.keys()),
            "mensaje": (
                "No se pudo clasificar la intencion. Usar --listar para ver "
                "las herramientas disponibles."
            ),
        }
    nombre = max(puntajes, key=puntajes.get)
    herramienta = HERRAMIENTAS[nombre]
    argumentos = _argumentos_sugeridos(nombre, intencion)
    if argumentos is None:
        return {
            "exito": False,
            "herramienta": nombre,
            "script": herramienta["script"],
            "mensaje": (
                "No se indico la ruta del PDF. Indica el archivo, por ejemplo: "
                'ha ejecutar "traduce el pdf ruta/al/archivo.pdf a ingles".'
            ),
        }
    script_relativo = herramienta["script"]
    script_absoluto = os.path.normpath(os.path.join(BASE_DIR, "..", script_relativo))
    comando = ["python3", script_relativo, *argumentos]
    return {
        "exito": True,
        "intencion": intencion,
        "herramienta": nombre,
        "script": script_relativo,
        "script_absoluto": script_absoluto,
        "argumentos": argumentos,
        "comando_sugerido": " ".join(comando),
        "descripcion": herramienta["descripcion"],
        "mensaje": f"Intencion enrutada al modulo de {nombre}.",
    }


def _listar():
    return {
        "exito": True,
        "herramientas": [
            {
                "nombre": nombre,
                "script": herramienta["script"],
                "descripcion": herramienta["descripcion"],
                "argumentos_por_defecto": herramienta["argumentos"],
            }
            for nombre, herramienta in HERRAMIENTAS.items()
        ],
        "mensaje": "Herramientas disponibles en HerramientasAgente.",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Enruta una intencion del usuario a la herramienta adecuada (salida JSON)"
    )
    parser.add_argument(
        "intencion",
        nargs="*",
        help="intencion u orden del usuario en lenguaje natural",
    )
    parser.add_argument(
        "--intencion",
        dest="intencion_opcion",
        help="intencion u orden del usuario (alternativa al argumento posicional)",
    )
    parser.add_argument(
        "--listar",
        action="store_true",
        help="listar las herramientas disponibles",
    )
    args = parser.parse_args()

    if args.listar:
        resultado = _listar()
    else:
        intencion = args.intencion_opcion or " ".join(args.intencion)
        resultado = seleccionar(intencion)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0 if resultado.get("exito") else 1


if __name__ == "__main__":
    raise SystemExit(main())
