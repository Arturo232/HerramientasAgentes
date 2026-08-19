#!/usr/bin/env python3
"""Traductor de documentos PDF usando pdf-inspector (Firecrawl).

Extrae el contenido de un PDF a Markdown con pdf-inspector y emite un JSON
con el Markdown extraido junto a una instruccion de traduccion preparada
para que el agente (modelo Cloud / Orquestador) realice la traduccion al
idioma indicado. El script NO traduce por si mismo; prepara el insumo y la
orden de traduccion, respetando la arquitectura on-demand (servicio efimero).
"""

import argparse
import json
import os
import subprocess
import sys

try:
    import pdf_inspector
    PDF_INSPECTOR_DISPONIBLE = True
except ImportError:
    PDF_INSPECTOR_DISPONIBLE = False


def _emitir_resultado(exito, datos):
    print(json.dumps({"exito": exito, **datos}, ensure_ascii=False, indent=2))
    sys.exit(0 if exito else 1)


def _instalar_dependencia():
    """Instala pdf-inspector en el intérprete activo. Devuelve True si tuvo éxito."""
    try:
        resultado = subprocess.run(
            [sys.executable, "-m", "pip", "install", "pdf-inspector>=1.15.0"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        return resultado.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def _garantizar_pdf_inspector(instalar_auto=False):
    """Asegura que pdf-inspector este importable. Sale con error si no."""
    global PDF_INSPECTOR_DISPONIBLE
    if PDF_INSPECTOR_DISPONIBLE:
        return True
    if instalar_auto:
        if _instalar_dependencia():
            try:
                import pdf_inspector  # noqa: F811
                PDF_INSPECTOR_DISPONIBLE = True
                return True
            except ImportError:
                pass
    _emitir_resultado(
        False,
        {
            "mensaje": (
                "Dependencia faltante: pdf_inspector. Instalela con "
                "pip install pdf-inspector o ejecute con --instalar-deps."
            ),
            "error": "pdf_inspector no disponible",
        },
    )
    return False


def _construir_instruccion(idioma, paginas):
    """Prompt preparado para que el agente traduzca el markdown extraido."""
    return (
        "Instruccion de traduccion: traduce el siguiente documento Markdown al "
        f"idioma '{idioma}' ({paginas} pagina(s)). Conserva la estructura de "
        "titulos, listas, tablas, enlaces y formato Markdown original. No "
        "inventes contenido: traduce fielmente. Entrega el resultado en "
        "Markdown."
    )


def traducir(input_pdf, idioma):
    """Extrae el PDF con pdf-inspector y devuelve el markdown + instruccion."""
    if not os.path.isfile(input_pdf):
        return {
            "exito": False,
            "mensaje": "El archivo PDF no existe.",
            "error": input_pdf,
        }
    try:
        resultado = pdf_inspector.process_pdf(input_pdf)
    except Exception as exc:  # noqa: BLE001
        return {
            "exito": False,
            "mensaje": "No se pudo procesar el PDF con pdf-inspector.",
            "error": str(exc),
        }

    markdown = resultado.markdown or ""
    paginas = resultado.page_count
    return {
        "exito": True,
        "input": input_pdf,
        "idioma": idioma,
        "paginas": paginas,
        "pdf_tipo": resultado.pdf_type,
        "confianza": resultado.confidence,
        "tiempo_ms": resultado.processing_time_ms,
        "markdown": markdown,
        "instruccion_traduccion": _construir_instruccion(idioma, paginas),
        "mensaje": "Contenido extraido. Listo para traduccion por el agente.",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Traductor de PDFs: extrae con pdf-inspector y prepara la traduccion"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="ruta del archivo PDF original",
    )
    parser.add_argument(
        "--idioma",
        default="espanol",
        help="idioma de destino de la traduccion (por defecto: espanol)",
    )
    parser.add_argument(
        "--instalar-deps",
        action="store_true",
        help="instala pdf-inspector automaticamente si falta",
    )
    args = parser.parse_args()

    _garantizar_pdf_inspector(instalar_auto=args.instalar_deps)

    datos = traducir(args.input, args.idioma)
    _emitir_resultado(datos["exito"], datos)


if __name__ == "__main__":
    main()
