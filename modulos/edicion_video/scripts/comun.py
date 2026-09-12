"""Utilidades compartidas del Departamento de Edición de Video (Shotcut/MLT).

Detecta los binarios de Shotcut/MLT de forma multiplataforma (Windows y Arch
Linux), convierte unidades de tiempo y fotogramas, e inspecciona medios con
ffprobe.
"""

import json
import os
import re
import shutil
import subprocess
import sys

_CACHE = {}


def _configurar_utf8():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


_configurar_utf8()

EXTS_IMAGEN = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg")
EXTS_AUDIO = (".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".opus")


def es_windows():
    return sys.platform == "win32"


def _candidatos_shotcut():
    rutas = []
    if es_windows():
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        la = os.environ.get("LOCALAPPDATA", "")
        rutas = [
            os.path.join(pf, "Shotcut"),
            os.path.join(pf86, "Shotcut"),
            os.path.join(la, "Programs", "Shotcut"),
        ]
    return rutas


def _candidatos_propios():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return [os.path.join(base, "bin")]


def _buscar(nombres, var_env):
    env = os.environ.get(var_env)
    if env and os.path.exists(env):
        return env
    for d in _candidatos_propios() + _candidatos_shotcut():
        for n in nombres:
            cand = os.path.join(d, n)
            if os.path.exists(cand):
                return cand
    for n in nombres:
        ruta = shutil.which(n)
        if ruta:
            return ruta
    return None


def encontrar_binarios():
    if "bin" in _CACHE:
        return _CACHE["bin"]
    res = {
        "melt": _buscar(["melt.exe", "melt"], "MELT"),
        "ffmpeg": _buscar(["ffmpeg.exe", "ffmpeg"], "FFMPEG"),
        "ffprobe": _buscar(["ffprobe.exe", "ffprobe"], "FFPROBE"),
        "whisper": _buscar(
            ["whisper-cli.exe", "whisper-cli", "whisper.exe", "whisper"], "WHISPER"
        ),
    }
    _CACHE["bin"] = res
    return res


def ruta_bin(nombre):
    b = encontrar_binarios()
    r = b.get(nombre)
    if not r:
        raise FileNotFoundError(
            "No se encontró el binario '%s'. Instala Shotcut o define la "
            "variable de entorno correspondiente." % nombre
        )
    return r


def ejecutar(cmd, timeout=None):
    p = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    return p


def parsear_tiempo(val):
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if s == "":
        return 0.0
    s = s.replace(",", ".")
    if ":" in s:
        partes = s.split(":")
        if len(partes) == 3:
            h, m, sec = partes
            return int(h) * 3600 + int(m) * 60 + float(sec)
        if len(partes) == 2:
            m, sec = partes
            return int(m) * 60 + float(sec)
    return float(s)


def parsear_fps(val):
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if "/" in s:
        a, b = s.split("/")
        try:
            return float(a) / float(b)
        except (ValueError, ZeroDivisionError):
            return 30.0
    try:
        return float(s)
    except ValueError:
        return 30.0


def segundos_a_cadena(seg):
    seg = float(seg)
    ms = int(round((seg - int(seg)) * 1000))
    if ms >= 1000:
        seg = int(seg) + 1
        ms = 0
    h = int(seg) // 3600
    m = (int(seg) % 3600) // 60
    s = int(seg) % 60
    return "%02d:%02d:%02d.%03d" % (h, m, s, ms)


def tiempo_a_frames(t, fps):
    return int(round(parsear_tiempo(t) * fps))


def inspeccionar_media(ruta):
    fp = ruta_bin("ffprobe")
    cmd = [
        fp,
        "-v",
        "error",
        "-show_entries",
        "format=duration,size,bit_rate:"
        "stream=index,codec_type,codec_name,width,height,r_frame_rate,"
        "sample_rate,channels,duration",
        "-of",
        "json",
        ruta,
    ]
    p = ejecutar(cmd)
    try:
        datos = json.loads(p.stdout)
    except json.JSONDecodeError:
        raise RuntimeError("ffprobe no pudo leer el medio: %s" % ruta)
    fmt = datos.get("format", {})
    streams = datos.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    duracion = 0.0
    try:
        duracion = float(fmt.get("duration") or 0)
    except (TypeError, ValueError):
        duracion = 0.0
    res = {
        "ruta": ruta,
        "duracion": duracion,
        "tamano_bytes": int(fmt.get("size") or 0),
        "bitrate": fmt.get("bit_rate"),
        "tiene_video": video is not None,
        "tiene_audio": audio is not None,
    }
    if video:
        res["ancho"] = int(video.get("width") or 0)
        res["alto"] = int(video.get("height") or 0)
        res["fps"] = parsear_fps(video.get("r_frame_rate") or 30)
        res["codec_video"] = video.get("codec_name")
    if audio:
        res["codec_audio"] = audio.get("codec_name")
        res["sample_rate"] = audio.get("sample_rate")
        res["canales"] = audio.get("channels")
    return res


def color_mlt(c):
    if c is None:
        return None
    c = str(c).strip()
    if c.startswith("0x"):
        return c
    h = c[1:] if c.startswith("#") else c
    if len(h) == 6:
        h += "ff"
    elif len(h) == 3:
        h = "".join(ch * 2 for ch in h) + "ff"
    return "0x" + h


def gcd(a, b):
    while b:
        a, b = b, a % b
    return a
