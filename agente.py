"""CLI unificado de HerramientasAgentes.

Un solo punto de entrada para todos los modulos:

    python agente.py pdf --input documento.pdf
    python agente.py pdf-buscar --input doc.pdf -q "flujos de potencia"
    python agente.py video editar --plan plan.json
    python agente.py audio mejorar --input video.mp4
    python agente.py ensayo --input borrador.md --pdf
    python agente.py sync

Cada comando delega en el script del modulo correspondiente.
"""

import argparse
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))

COMANDOS = {
    "pdf": ("modulos/documentos/scripts/leer_pdf.py", "Leer cualquier PDF (texto, tablas, escaneado)"),
    "pdf-buscar": ("modulos/documentos/scripts/buscar_pdf.py", "Buscar fragmentos relevantes en un PDF"),
    "pdf-resumir": ("modulos/documentos/scripts/resumir_pdf.py", "Resumen extractivo local de un PDF"),
    "video": ("modulos/edicion_video/scripts/editar_video.py", "Editar video (cortes, audio, conversion)"),
    "video-moderno": ("modulos/edicion_video/scripts/renderizar_moderno.py", "Render moderno (9:16 / 16:9, karaoke, B-roll)"),
    "subtitulos": ("modulos/edicion_video/scripts/subtitulos.py", "Subtitulos automaticos (whisper)"),
    "audio": ("modulos/edicion_audio/scripts/procesar_audio.py", "Mejorar voz y mezclar con musica"),
    "ensayo": ("modulos/literatura/scripts/generar_documento_apa.py", "Compilar borrador APA 7 a DOCX/PDF"),
    "infografia": ("modulos/artes_diseno/scripts/renderizador_playwright.py", "Render HTML -> PDF (infografias)"),
    "pptx": ("modulos/artes_diseno/scripts/motor_pptx_visual.py", "Inyectar texto/imagenes en plantillas PPTX"),
    "web": ("modulos/navegacion_web/scripts/abrir_pagina.py", "Abrir/extraer una pagina web"),
    "sync": ("sincronizar_skills.py", "Sincronizar skills del repo con OpenCode"),
}


def main(argv):
    ap = argparse.ArgumentParser(prog="agente", description="CLI unificado de HerramientasAgentes.")
    ap.add_argument("comando", nargs="?", choices=sorted(COMANDOS), help="Modulo a ejecutar")
    ap.add_argument("args", nargs=argparse.REMAINDER, help="Argumentos para el script del modulo")
    ns = ap.parse_args(argv)

    if not ns.comando:
        print("Comandos disponibles:\n")
        for nombre in sorted(COMANDOS):
            print("  %-14s %s" % (nombre, COMANDOS[nombre][1]))
        print("\nEjemplo: python agente.py pdf --input documento.pdf")
        return 0

    script = os.path.join(REPO, COMANDOS[ns.comando][0])
    if not os.path.exists(script):
        print("ERROR: no existe %s" % script, file=sys.stderr)
        return 1
    return subprocess.call([sys.executable, script] + ns.args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
