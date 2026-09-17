"""Genera subtítulos (SRT/VTT/TXT) con whisper-cli y opcionalmente los quema.

whisper-cli solo admite audio (flac, mp3, ogg, wav), así que primero se extrae
el audio del video con ffmpeg y luego se transcribe. Con --quemar, se arma un
proyecto .mlt con la pista de subtítulos y se renderiza.
"""

import json
import os
import subprocess
import sys

_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(_SCRIPTS)))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
import comun  # noqa: E402
from nucleo import cli  # noqa: E402
from nucleo.contrato import exito  # noqa: E402
from nucleo.registro import artefacto  # noqa: E402

MODELOS = ["tiny", "base", "small", "medium", "large"]


def _resolver_modelo(modelo):
    if modelo and os.path.exists(modelo):
        return os.path.abspath(modelo)
    m = (modelo or "base").replace(".bin", "").replace("ggml-", "")
    base = m.split(".")[0]
    if base in MODELOS:
        nombre = "ggml-%s.bin" % base
    else:
        nombre = modelo if modelo else "ggml-base.bin"
    for d in [os.getcwd(),
              os.path.join(os.getcwd(), "models"),
              os.path.dirname(comun.ruta_bin("whisper"))]:
        cand = os.path.join(d, nombre)
        if os.path.exists(cand):
            return cand
    return nombre


def transcribir(video, modelo=None, idioma="es", salida=None, formato="srt"):
    ff = comun.ruta_bin("ffmpeg")
    whisper = comun.ruta_bin("whisper")

    if not os.path.exists(video):
        raise FileNotFoundError("No existe el video %s" % video)

    base = os.path.abspath(salida or os.path.splitext(video)[0] + "_subtitulos")
    wav = base + ".wav"

    p = comun.ejecutar([ff, "-y", "-i", video, "-vn", "-ar", "16000", "-ac", "1",
                        "-c:a", "pcm_s16le", wav])
    if p.returncode != 0 or not os.path.exists(wav):
        raise RuntimeError("No se pudo extraer el audio:\n" + (p.stderr or "")[-1500:])

    model_path = _resolver_modelo(modelo)
    flag = {"srt": "-osrt", "vtt": "-ovtt", "txt": "-otxt"}.get(formato, "-osrt")
    cmd = [whisper, "-m", model_path, "-f", wav, "-l", idioma, "-np",
           flag, "-of", base]
    p = comun.ejecutar(cmd)
    try:
        os.remove(wav)
    except OSError:
        pass
    if p.returncode != 0:
        raise RuntimeError("whisper falló:\n" + (p.stderr or p.stdout)[-2000:])

    result = base + "." + formato
    if not os.path.exists(result):
        raise RuntimeError("No se generó el archivo de subtítulos %s" % result)
    return result


def quemar(video, srt, salida, estilo=None):
    scripts = os.path.dirname(os.path.abspath(__file__))
    plan = {
        "nombre": "subtitulos",
        "perfil": "auto",
        "pistas": [{"nombre": "video", "tipo": "video",
                    "clips": [{"recurso": os.path.abspath(video)}]}],
        "subtitulos": os.path.abspath(srt),
    }
    if estilo:
        plan["subtitulos_estilo"] = estilo

    base = os.path.abspath(salida or os.path.splitext(video)[0] + "_subtitulado.mp4")
    mlt = base + ".mlt"
    with open(mlt, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False)

    gen = os.path.join(scripts, "generar_proyecto_mlt.py")
    ren = os.path.join(scripts, "renderizar_mlt.py")
    p = subprocess.run([sys.executable, gen, "--plan", mlt, "--salida", mlt],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise RuntimeError("generar falló:\n" + (p.stderr or p.stdout)[-2000:])
    p = subprocess.run([sys.executable, ren, "--input", mlt, "--salida", base],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise RuntimeError("renderizar falló:\n" + (p.stderr or p.stdout)[-2000:])
    return base


def _construir(ap):
    ap.add_argument("--input", "-i", required=True, help="Video de entrada")
    ap.add_argument("--modelo", "-m", default="base",
                    help="Modelo whisper (tiny/base/small/medium/large o ruta a .bin)")
    ap.add_argument("--idioma", "-l", default="es", help="Idioma (es, en, auto...)")
    ap.add_argument("--formato", choices=["srt", "vtt", "txt"], default="srt")
    ap.add_argument("--salida", "-o", help="Ruta base de salida (sin extensión)")
    ap.add_argument("--quemar", action="store_true",
                    help="Además de generar el SRT, quemarlo en el video de salida")
    ap.add_argument("--salida-video", help="Video final con subtítulos (con --quemar)")
    ap.add_argument("--tamano", type=int, default=40, help="Tamaño de letra al quemar")


def _accion(ns):
    srt = transcribir(ns.input, ns.modelo, ns.idioma, ns.salida, ns.formato)
    arts = [artefacto("subtitulos", srt)]
    datos = {"subtitulos": srt}
    if ns.quemar:
        out = quemar(ns.input, srt, ns.salida_video, {"tamano": ns.tamano})
        datos["video"] = out
        arts.append(artefacto("video", out))
    return exito(datos=datos, artefactos=arts)


if __name__ == "__main__":
    sys.exit(cli.correr("edicion_video", _construir, _accion, sys.argv[1:],
                        prog="subtitulos",
                        descripcion="Subtítulos automáticos con whisper-cli."))
