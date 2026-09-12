"""Genera un proyecto .mlt (MLT/Shotcut) a partir de un plan de edición JSON.

El plan describe pistas (video/audio), recortes, velocidad, filtros,
transiciones de fundido, overlays y subtítulos. Este script traduce ese plan a
un XML .mlt que se puede abrir en Shotcut o renderizar con melt.
"""

import argparse
import json
import os
import re
import sys
from xml.sax.saxutils import escape

import comun

SERVICIO_IMAGEN = "qimage"


class _Clip:
    def __init__(self, producer_id, service, in_src, out_src, vel, out_len,
                 es_imagen, mudo):
        self.producer_id = producer_id
        self.service = service
        self.in_src = in_src
        self.out_src = out_src
        self.vel = vel
        self.out_len = out_len
        self.es_imagen = es_imagen
        self.mudo = mudo
        self.recurso = ""
        self.es_audio_solo = False
        self.filtros = []
        self.longitud = None
        self.info = None
        self.tipo = "clip"
        self.len = out_len


class _Join:
    def __init__(self, left, right):
        self.left = left
        self.right = right
        self.len = left.len + right.len
        self.tipo = "join"


class _Mix:
    def __init__(self, left, right, mix_len, tractor_id):
        self.left = left
        self.right = right
        self.mix_len = mix_len
        self.tractor_id = tractor_id
        self.len = left.len + right.len - mix_len
        self.tipo = "mix"


def _primer_clip(seg):
    while seg.tipo != "clip":
        seg = seg.left
    return seg


def _ultimo_clip(seg):
    while seg.tipo != "clip":
        seg = seg.right
    return seg


def _cola(seg, L):
    c = _ultimo_clip(seg)
    return (c.producer_id, c.out_len - L, c.out_len - 1)


def _cabeza(seg, L):
    c = _primer_clip(seg)
    return (c.producer_id, 0, L - 1)


def _filtro(f, fps):
    nombre = (f.get("nombre") or f.get("tipo") or "").strip().lower()
    props = {}
    if nombre in ("greyscale", "gris", "blancoynegro", "bn", "bw"):
        props["mlt_service"] = "greyscale"
    elif nombre in ("brightness", "brillo"):
        props["mlt_service"] = "brightness"
        props["level"] = str(f.get("nivel", f.get("level", 1.0)))
    elif nombre in ("crop", "recorte", "recortar"):
        props["mlt_service"] = "crop"
        props["active"] = "1"
        props["left"] = str(f.get("izquierda", f.get("left", 0)))
        props["right"] = str(f.get("derecha", f.get("right", 0)))
        props["top"] = str(f.get("arriba", f.get("top", 0)))
        props["bottom"] = str(f.get("abajo", f.get("bottom", 0)))
    elif nombre in ("texto", "text", "titulo", "title"):
        props["mlt_service"] = "text"
        props["argument"] = str(f.get("texto", f.get("text", "")))
        props["size"] = str(f.get("tamano", f.get("size", 48)))
        props["weight"] = str(f.get("peso", f.get("weight", 400)))
        props["style"] = str(f.get("estilo", f.get("style", "normal")))
        props["family"] = str(f.get("familia", f.get("family", "Sans")))
        color = comun.color_mlt(f.get("color", f.get("fgcolour")))
        fondo = comun.color_mlt(f.get("fondo", f.get("bgcolour")))
        if color:
            props["fgcolour"] = color
        if fondo:
            props["bgcolour"] = fondo
        x = f.get("x")
        y = f.get("y")
        if x is not None and y is not None:
            gx = int(float(x) * 100)
            gy = int(float(y) * 100)
            props["geometry"] = "%d%%/%d%%:100%%x100%%:100" % (gx, gy)
        else:
            props["geometry"] = "0%/0%:100%x100%:100"
        props["halign"] = str(f.get("halign", "center"))
        props["valign"] = str(f.get("valign", "middle"))
        if f.get("inicio") is not None:
            props["in"] = str(comun.tiempo_a_frames(f["inicio"], fps))
        if f.get("fin") is not None:
            props["out"] = str(max(comun.tiempo_a_frames(f["fin"], fps) - 1, 0))
    elif nombre in ("mirror", "espejo"):
        props["mlt_service"] = "mirror"
        props["mirror"] = "flip"
    elif nombre in ("sepia",):
        props["mlt_service"] = "sepia"
    else:
        return None
    return props


def _primer_recurso_video(pistas):
    for p in pistas:
        if str(p.get("tipo", "video")).lower() != "video":
            continue
        for c in p.get("clips", []):
            recurso = c.get("recurso", "")
            ext = os.path.splitext(recurso)[1].lower()
            if ext in comun.EXTS_IMAGEN:
                continue
            return recurso
    return None


def _resolver_perfil(plan, info_cache):
    perfil = plan.get("perfil", "auto")
    if isinstance(perfil, dict):
        w = int(perfil.get("ancho", perfil.get("width", 1280)))
        h = int(perfil.get("alto", perfil.get("height", 720)))
        fps = comun.parsear_fps(perfil.get("fps", 30))
        return w, h, fps
    if isinstance(perfil, str) and perfil.lower() not in ("auto", ""):
        m = re.match(r"(\d+)x(\d+)(?:@(\d+(?:[./]\d+)?))?", perfil)
        if m:
            w, h = int(m.group(1)), int(m.group(2))
            fps = comun.parsear_fps(m.group(3)) if m.group(3) else 30
            return w, h, fps
    recurso = _primer_recurso_video(plan.get("pistas", []))
    if recurso:
        if recurso not in info_cache:
            info_cache[recurso] = comun.inspeccionar_media(recurso)
        info = info_cache[recurso]
        w = info.get("ancho") or 1280
        h = info.get("alto") or 720
        fps = info.get("fps") or 30
        return w, h, fps
    return 1280, 720, 30


def _construir_pista(pista, fps, info_cache):
    tipo = str(pista.get("tipo", "video")).lower()
    es_audio = tipo == "audio"
    clips = []
    for c in pista.get("clips", []):
        recurso = os.path.abspath(c.get("recurso", ""))
        ext = os.path.splitext(recurso)[1].lower()
        es_imagen = ext in comun.EXTS_IMAGEN
        vel = float(c.get("velocidad", 1.0) or 1.0)
        if vel <= 0:
            vel = 1.0
        mudo = bool(c.get("mudo", False))
        if es_imagen:
            dur = c.get("duracion", c.get("longitud"))
            if dur is None:
                raise ValueError("El clip de imagen %s necesita 'duracion'" % recurso)
            frames = max(1, comun.tiempo_a_frames(dur, fps))
            clip = _Clip("", SERVICIO_IMAGEN, 0, frames - 1, 1.0, frames, True, mudo)
            clip.longitud = frames
        else:
            if recurso not in info_cache:
                info_cache[recurso] = comun.inspeccionar_media(recurso)
            info = info_cache[recurso]
            total_frames = max(1, int(round(info.get("duracion", 0) * fps)))
            in_src = comun.tiempo_a_frames(c["inicio"], fps) if c.get("inicio") is not None else 0
            out_src = (comun.tiempo_a_frames(c["fin"], fps) - 1
                       if c.get("fin") is not None else total_frames - 1)
            if in_src > out_src:
                raise ValueError("Recorte inválido en %s (inicio >= fin)" % recurso)
            out_len = max(1, int(round((out_src - in_src + 1) / vel)))
            clip = _Clip("", "avformat", in_src, out_src, vel, out_len, False, mudo)
            clip.info = info
        clip.recurso = recurso
        clip.es_audio_solo = es_audio
        clip.filtros = [x for x in (_filtro(f, fps) for f in c.get("filtros", [])) if x]
        clips.append(clip)
    return clips


def _emitir(seg, inicio, fin, salida):
    if inicio > fin:
        return
    if seg.tipo == "clip":
        salida.append(("entry", seg.producer_id, inicio, fin))
        return
    if seg.tipo == "join":
        l = seg.left.len
        if fin < l:
            _emitir(seg.left, inicio, fin, salida)
        elif inicio >= l:
            _emitir(seg.right, inicio - l, fin - l, salida)
        else:
            _emitir(seg.left, inicio, l - 1, salida)
            _emitir(seg.right, 0, fin - l, salida)
        return
    L = seg.mix_len
    la = seg.left.len
    mix_start = la - L
    mix_end = la - 1
    b_start = la
    if inicio < mix_start:
        _emitir(seg.left, inicio, min(fin, mix_start - 1), salida)
    if inicio <= mix_end and fin >= mix_start:
        t_in = max(inicio, mix_start) - mix_start
        t_out = min(fin, mix_end) - mix_start
        salida.append(("tractor", seg.tractor_id, t_in, t_out))
    if fin >= b_start:
        r_in = max(inicio, b_start) - b_start + L
        r_out = (fin - b_start) + L
        _emitir(seg.right, r_in, r_out, salida)


def _construir_linea(clips, duraciones_fundido, fps):
    if not clips:
        return None, 0, []
    seg = clips[0]
    tractores = []
    tid = 0
    for i in range(1, len(clips)):
        right = clips[i]
        L = duraciones_fundido[i - 1] if i - 1 < len(duraciones_fundido) else 0
        if L <= 0:
            seg = _Join(seg, right)
            continue
        L = min(L, seg.len - 1, right.out_len - 1)
        if L <= 0:
            seg = _Join(seg, right)
            continue
        left_tail = _cola(seg, L)
        right_head = _cabeza(right, L)
        tractor_id = "tractor%d" % tid
        tid += 1
        tractores.append((tractor_id, left_tail, right_head, L))
        seg = _Mix(seg, right, L, tractor_id)
    return seg, seg.len, tractores


def _producir_propiedades(clip):
    lineas = []
    lineas.append('    <property name="resource">%s</property>' % escape(clip.recurso))
    lineas.append('    <property name="mlt_service">%s</property>' % clip.service)
    if clip.vel != 1.0 and not clip.es_imagen:
        lineas.append('    <property name="warp_speed">%s</property>' % clip.vel)
    if clip.longitud is not None:
        lineas.append('    <property name="length">%d</property>' % clip.longitud)
    if clip.mudo:
        lineas.append('    <property name="audio_index">-1</property>')
    if clip.es_audio_solo:
        lineas.append('    <property name="video_index">-1</property>')
    for i, f in enumerate(clip.filtros):
        lineas.append('    <filter id="filter_%s_%d">' % (clip.producer_id, i))
        for k, v in f.items():
            lineas.append('        <property name="%s">%s</property>' % (k, escape(str(v))))
        lineas.append('    </filter>')
    return lineas


def _construir_mlt(plan):
    info_cache = {}
    pistas = plan.get("pistas", [])
    if not pistas:
        raise ValueError("El plan necesita al menos una pista")

    ancho, alto, fps_raw = _resolver_perfil(plan, info_cache)
    fps = max(1.0, round(comun.parsear_fps(fps_raw)))

    pistas_construidas = []
    for p in pistas:
        cs = _construir_pista(p, fps, info_cache)
        pistas_construidas.append((p, cs))

    idx = 0
    for _, cs in pistas_construidas:
        for c in cs:
            c.producer_id = "producer%d" % idx
            idx += 1

    video_pistas = [(p, cs) for p, cs in pistas_construidas
                    if str(p.get("tipo", "video")).lower() == "video"]
    audio_pistas = [(p, cs) for p, cs in pistas_construidas
                    if str(p.get("tipo", "video")).lower() == "audio"]

    base = video_pistas[0][1] if video_pistas else []
    overlays = [(p, cs) for p, cs in video_pistas[1:]]

    duraciones_fundido = []
    for t in plan.get("transiciones", []):
        if (t.get("tipo") or "").lower() in ("fundido", "crossfade", "disolver", "fade"):
            duraciones_fundido.append(max(1, comun.tiempo_a_frames(t.get("duracion", 1.0), fps)))

    base_seg, base_len, tractores = _construir_linea(base, duraciones_fundido, fps)

    audio_lens = [sum(c.out_len for c in cs) for _, cs in audio_pistas]
    total = base_len
    for l in audio_lens:
        total = max(total, l)
    if total <= 0:
        raise ValueError("El proyecto no tiene contenido (duración 0)")

    partes = []
    partes.append('<?xml version="1.0" encoding="utf-8"?>')
    partes.append('<mlt LC_NUMERIC="C" version="7.41.0">')

    dar = comun.gcd(int(ancho), int(alto)) or 1
    partes.append(
        '  <profile description="automatic" width="%d" height="%d" progressive="1" '
        'sample_aspect_num="1" sample_aspect_den="1" display_aspect_num="%d" '
        'display_aspect_den="%d" frame_rate_num="%d" frame_rate_den="1" '
        'colorspace="709"/>' % (ancho, alto, int(ancho // dar), int(alto // dar), int(fps))
    )

    for _, cs in pistas_construidas:
        for c in cs:
            lineas = ['  <producer id="%s" in="%d" out="%d">'
                      % (c.producer_id, c.in_src, c.out_src)]
            lineas.extend(_producir_propiedades(c))
            lineas.append('  </producer>')
            partes.append("\n".join(lineas))

    for tractor_id, left, right, L in tractores:
        lineas = ['<tractor id="%s" in="0" out="%d">' % (tractor_id, L - 1)]
        lineas.append('<track producer="%s" in="%d" out="%d"/>' % (left[0], left[1], left[2]))
        lineas.append('<track producer="%s" in="%d" out="%d"/>' % (right[0], right[1], right[2]))
        lineas.append('<transition id="transition_%s" in="0" out="%d">' % (tractor_id, L - 1))
        lineas.append('<property name="a_track">0</property>')
        lineas.append('<property name="b_track">1</property>')
        lineas.append('<property name="mlt_service">mix</property>')
        lineas.append('</transition>')
        lineas.append('</tractor>')
        partes.append("  " + "\n  ".join(lineas))

    n_track = 0
    track_refs = []
    composite_tracks = []

    if base:
        entradas = []
        _emitir(base_seg, 0, base_len - 1, entradas)
        playlist_id = "playlist%d" % n_track
        lineas = ['<playlist id="%s">' % playlist_id]
        for tipo, ref, i, o in entradas:
            lineas.append('<entry producer="%s" in="%d" out="%d"/>' % (ref, i, o))
        lineas.append('</playlist>')
        partes.append("  " + "\n  ".join(lineas))
        track_refs.append(playlist_id)
        n_track += 1

    for p, cs in overlays:
        playlist_id = "playlist%d" % n_track
        lineas = ['<playlist id="%s">' % playlist_id]
        for c in cs:
            lineas.append('<entry producer="%s" in="0" out="%d"/>'
                          % (c.producer_id, c.out_len - 1))
        lineas.append('</playlist>')
        partes.append("  " + "\n  ".join(lineas))
        track_refs.append(playlist_id)
        composite_tracks.append((n_track, p))
        n_track += 1

    for _, cs in audio_pistas:
        playlist_id = "playlist%d" % n_track
        lineas = ['<playlist id="%s">' % playlist_id]
        for c in cs:
            lineas.append('<entry producer="%s" in="0" out="%d"/>'
                          % (c.producer_id, c.out_len - 1))
        lineas.append('</playlist>')
        partes.append("  " + "\n  ".join(lineas))
        track_refs.append(playlist_id)
        n_track += 1

    subs = plan.get("subtitulos")
    if subs:
        estilo = plan.get("subtitulos_estilo", {})
        subs_id = "subtitle_producer"
        fg = comun.color_mlt(estilo.get("color", estilo.get("fgcolour", "#ffffff"))) or "0xffffffff"
        bg = comun.color_mlt(estilo.get("fondo", estilo.get("bgcolour", "#000000a0"))) or "0x000000a0"
        lineas = ['<producer id="%s" in="0" out="%d">' % (subs_id, total - 1)]
        lineas.append('<property name="resource">%s</property>' % escape(os.path.abspath(subs)))
        lineas.append('<property name="mlt_service">subtitle</property>')
        lineas.append('<property name="size">%s</property>'
                      % str(estilo.get("tamano", estilo.get("size", 40))))
        lineas.append('<property name="fgcolour">%s</property>' % fg)
        lineas.append('<property name="bgcolour">%s</property>' % bg)
        lineas.append('</producer>')
        partes.append("  " + "\n  ".join(lineas))
        playlist_id = "playlist%d" % n_track
        lineas = ['<playlist id="%s">' % playlist_id,
                  '<entry producer="%s" in="0" out="%d"/>' % (subs_id, total - 1),
                  '</playlist>']
        partes.append("  " + "\n  ".join(lineas))
        track_refs.append(playlist_id)
        composite_tracks.append((n_track, None))
        n_track += 1

    lineas = ['<tractor id="tractor_root" in="0" out="%d">' % (total - 1)]
    for pid in track_refs:
        lineas.append('<track producer="%s"/>' % pid)
    for ti, (track_idx, p) in enumerate(composite_tracks):
        geom = None
        if p is not None:
            geom = p.get("geometria")
        lineas.append('<transition id="composite%d" in="0" out="%d">' % (ti, total - 1))
        lineas.append('<property name="a_track">%d</property>' % track_idx)
        lineas.append('<property name="b_track">0</property>')
        lineas.append('<property name="mlt_service">composite</property>')
        if geom:
            lineas.append('<property name="geometry">%s</property>' % escape(str(geom)))
        lineas.append('</transition>')
    lineas.append('</tractor>')
    partes.append("  " + "\n  ".join(lineas))

    partes.append('</mlt>')
    return "\n".join(partes), total, fps


def generar_mlt(plan):
    return _construir_mlt(plan)[0]


def main(argv):
    ap = argparse.ArgumentParser(
        description="Genera un proyecto .mlt (MLT/Shotcut) desde un plan JSON."
    )
    ap.add_argument("--plan", "-p", required=True, help="Archivo JSON con el plan de edición")
    ap.add_argument("--salida", "-o", required=True, help="Archivo .mlt de salida")
    args = ap.parse_args(argv)

    with open(args.plan, "r", encoding="utf-8") as f:
        plan = json.load(f)

    xml = generar_mlt(plan)
    with open(args.salida, "w", encoding="utf-8") as f:
        f.write(xml)
    print("Proyecto .mlt generado en %s" % os.path.abspath(args.salida))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
