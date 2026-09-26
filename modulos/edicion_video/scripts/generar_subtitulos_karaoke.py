"""Genera subtítulos karaoke (ASS) desde el JSON de whisper o desde un guion.

- Modo whisper: usa los timestamps por token del JSON de whisper-cli.
- Modo guion: usa un texto correcto con tiempos (inicio/fin) y reparte las
  palabras proporcionalmente dentro de cada frase.

El estilo es moderno: la palabra activa se resalta y hace un pequeño "pop".
"""

import argparse
import json
import os
import re
import sys

import comun

CABECERA = """[Script Info]
ScriptType: v4.00+
PlayResX: {ancho}
PlayResY: {alto}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,{fuente},{tamano},{primario},{secundario},{contorno},{backcolour},-1,0,0,0,100,100,0,0,{estilo_borde},{grosor},2,2,70,70,{margen_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _ts(ms):
    ms = max(0, int(round(ms)))
    h = ms // 3600000
    ms %= 3600000
    m = ms // 60000
    ms %= 60000
    s = ms // 1000
    cs = (ms % 1000) // 10
    return "%d:%02d:%02d.%02d" % (h, m, s, cs)


def _color(hexcol):
    hexcol = hexcol.lstrip("#")
    if len(hexcol) == 6:
        hexcol += "ff"
    r, g, b, a = (hexcol[i:i + 2] for i in (0, 2, 4, 6))
    a_ass = "%02x" % (255 - int(a, 16))
    return "&H%s%s%s%s" % (a_ass, b, g, r)


def _cargar_palabras(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        d = json.load(f)
    segs = d.get("transcription") or d.get("segments") or []
    palabras = []
    for seg in segs:
        tokens = seg.get("tokens")
        if not tokens:
            txt = (seg.get("text") or "").strip()
            off = seg.get("offsets") or {}
            if txt and off.get("from") is not None:
                for w in txt.split():
                    palabras.append({"txt": w, "ini": off["from"], "fin": off["to"]})
            continue
        for tok in tokens:
            txt = tok.get("text", "")
            if not txt or "[" in txt:
                continue
            off = tok.get("offsets") or {}
            if off.get("from") is None or off.get("to") is None:
                continue
            if txt.startswith(" ") or not palabras:
                palabras.append({"txt": txt.strip(), "ini": off["from"], "fin": off["to"]})
            else:
                palabras[-1]["txt"] += txt.strip()
                palabras[-1]["fin"] = off["to"]
    return [p for p in palabras if p["txt"]]


def _aplicar_correcciones(palabras, correcciones):
    if not correcciones:
        return palabras
    mapa = {k.lower(): v for k, v in correcciones.items()}
    for p in palabras:
        clave = re.sub(r"[^\wáéíóúñü]", "", p["txt"]).lower()
        if clave in mapa:
            p["txt"] = mapa[clave]
    return palabras


def _agrupar(palabras, max_palabras, max_dur_ms):
    frases = []
    cur = []
    for p in palabras:
        if cur and (len(cur) >= max_palabras or (p["fin"] - cur[0]["ini"]) > max_dur_ms):
            frases.append(cur)
            cur = []
        cur.append(p)
        if re.search(r"[.!?]$", p["txt"]):
            frases.append(cur)
            cur = []
    if cur:
        frases.append(cur)
    return frases


def _frases_desde_guion(guion):
    frases = []
    for item in guion:
        ini = comun.parsear_tiempo(item["inicio"]) * 1000.0
        fin = comun.parsear_tiempo(item["fin"]) * 1000.0
        palabras = item["texto"].split()
        if not palabras or fin <= ini:
            continue
        pesos = [max(len(w), 1) for w in palabras]
        total = float(sum(pesos))
        t = ini
        frase = []
        for w, peso in zip(palabras, pesos):
            dur = (fin - ini) * (peso / total)
            frase.append({"txt": w, "ini": t, "fin": t + dur})
            t += dur
        frases.append(frase)
    return frases


def _escribir_ass(frases, salida, ancho, alto, fuente, tamano, color, resalte,
                  contorno, grosor, margen_v, banda=False, banda_color="#000000a0"):
    primario = _color(color)
    secundario = _color(resalte)
    contorno_c = _color(contorno)
    if banda:
        estilo_borde = 3
        backcolour = _color(banda_color)
        grosor_ef = max(grosor, 8)
    else:
        estilo_borde = 1
        backcolour = "&H80000000"
        grosor_ef = grosor
    partes = [CABECERA.format(ancho=ancho, alto=alto, fuente=fuente, tamano=tamano,
                              primario=primario, secundario=secundario,
                              contorno=contorno_c, backcolour=backcolour,
                              estilo_borde=estilo_borde,
                              grosor=grosor_ef, margen_v=margen_v)]
    n_pal = 0
    for frase in frases:
        n_pal += len(frase)
        for i, palabra in enumerate(frase):
            inicio = palabra["ini"]
            fin = frase[i + 1]["ini"] if i + 1 < len(frase) else palabra["fin"] + 140
            if fin <= inicio:
                fin = inicio + 140
            trozos = []
            for j, w in enumerate(frase):
                if j == i:
                    trozos.append(
                        "{\\c%s&\\fscx114\\fscy114\\t(0,110,\\fscx100\\fscy100)}%s"
                        "{\\c%s&\\fscx100\\fscy100}" % (secundario, w["txt"], primario))
                else:
                    trozos.append(w["txt"])
            partes.append("Dialogue: 0,%s,%s,Karaoke,,0,0,0,,%s"
                          % (_ts(inicio), _ts(fin), " ".join(trozos)))
    with open(salida, "w", encoding="utf-8") as f:
        f.write("\n".join(partes) + "\n")
    return os.path.abspath(salida), n_pal, len(frases)


def generar(json_path, salida, ancho=1080, alto=1920, fuente="Arial Black",
            tamano=76, color="#ffffff", resalte="#ffd400", contorno="#000000",
            grosor=4, margen_v=300, max_palabras=4, max_dur=2.6,
            correcciones=None, guion=None, mapa_tiempos=None,
            banda=False, banda_color="#000000a0"):
    if guion is not None:
        frases = _frases_desde_guion(guion)
    else:
        palabras = _cargar_palabras(json_path)
        if not palabras:
            raise RuntimeError("No se encontraron palabras con timestamps en %s" % json_path)
        palabras = _aplicar_correcciones(palabras, correcciones)
        frases = _agrupar(palabras, max_palabras, int(max_dur * 1000))

    if mapa_tiempos:
        for frase in frases:
            for w in frase:
                w["ini"] = mapa_tiempos(w["ini"])
                w["fin"] = mapa_tiempos(w["fin"])

    return _escribir_ass(frases, salida, ancho, alto, fuente, tamano, color,
                         resalte, contorno, grosor, margen_v, banda, banda_color)


def main(argv):
    ap = argparse.ArgumentParser(description="Genera subtítulos karaoke (ASS).")
    ap.add_argument("--json", "-j", help="JSON de whisper (-ojf)")
    ap.add_argument("--guion", help="JSON [{inicio, fin, texto}, ...] con texto correcto")
    ap.add_argument("--salida", "-o", required=True)
    ap.add_argument("--ancho", type=int, default=1080)
    ap.add_argument("--alto", type=int, default=1920)
    ap.add_argument("--fuente", default="Arial Black")
    ap.add_argument("--tamano", type=int, default=76)
    ap.add_argument("--color", default="#ffffff")
    ap.add_argument("--resalte", default="#ffd400")
    ap.add_argument("--contorno", default="#000000")
    ap.add_argument("--grosor", type=int, default=4)
    ap.add_argument("--margen-v", type=int, default=300)
    ap.add_argument("--max-palabras", type=int, default=4)
    ap.add_argument("--max-dur", type=float, default=2.6)
    ap.add_argument("--correcciones")
    ap.add_argument("--banda", action="store_true", help="Franja semitransparente detrás del texto")
    ap.add_argument("--banda-color", default="#000000a0")
    args = ap.parse_args(argv)

    correcciones = None
    if args.correcciones:
        with open(args.correcciones, "r", encoding="utf-8") as f:
            correcciones = json.load(f)
    guion = None
    if args.guion:
        with open(args.guion, "r", encoding="utf-8") as f:
            guion = json.load(f)

    ruta, npal, nfr = generar(
        args.json, args.salida, args.ancho, args.alto, args.fuente, args.tamano,
        args.color, args.resalte, args.contorno, args.grosor, args.margen_v,
        args.max_palabras, args.max_dur, correcciones, guion,
        banda=args.banda, banda_color=args.banda_color)
    print("ASS generado: %s (%d palabras, %d frases)" % (ruta, npal, nfr))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
