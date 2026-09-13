"""Lector de PDF adaptativo: entiende PDFs de texto, escaneados y con tablas.

Analiza cada pagina y elige automaticamente la mejor via:

  * Texto extraible        -> PyMuPDF (rapido).
  * Tablas                 -> PyMuPDF find_tables -> Markdown.
  * Pagina escaneada       -> OCR con RapidOCR (fallback: Tesseract).
  * PDF complejo (opcional)-> Docling si esta instalado.

Genera Markdown estructurado + JSON con metadatos, secciones, tablas y figuras,
pensado para que el modelo de IA lea poco y bien (menos tokens).
"""

import argparse
import hashlib
import json
import os
import re
import statistics
import sys

UMBRAL_TEXTO_POR_PAGINA = 40


def _hash_archivo(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _cargar_dependencias():
    deps = {"pymupdf": None, "RapidOCR": None, "np": None,
            "pytesseract": None, "docling": None}
    try:
        import pymupdf
        deps["pymupdf"] = pymupdf
    except ImportError:
        try:
            import fitz as pymupdf
            deps["pymupdf"] = pymupdf
        except ImportError:
            raise SystemExit("Falta PyMuPDF. Instala con: pip install pymupdf")
    try:
        import numpy as np
        deps["np"] = np
    except ImportError:
        pass
    try:
        from rapidocr_onnxruntime import RapidOCR
        deps["RapidOCR"] = RapidOCR
    except ImportError:
        pass
    try:
        import pytesseract
        deps["pytesseract"] = pytesseract
    except ImportError:
        pass
    try:
        import docling  # noqa: F401
        deps["docling"] = docling
    except ImportError:
        pass
    return deps


_DEPS = None
_OCR_MOTOR = None


def deps():
    global _DEPS
    if _DEPS is None:
        _DEPS = _cargar_dependencias()
    return _DEPS


def _ocr_rapid(img):
    global _OCR_MOTOR
    if _OCR_MOTOR is None:
        _OCR_MOTOR = deps()["RapidOCR"]()
    resultado, _ = _OCR_MOTOR(img)
    if not resultado:
        return ""
    return "\n".join(linea[1] for linea in resultado)


def _ocr_pagina(page, idioma="spa"):
    d = deps()
    pix = page.get_pixmap(dpi=200)
    if d["RapidOCR"] is not None and d["np"] is not None:
        np = d["np"]
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n >= 3:
            img = img[:, :, :3][:, :, ::-1]
        return _ocr_rapid(img)
    if d["pytesseract"] is not None:
        img = d["pymupdf"].Pixmap(pix)
        return d["pytesseract"].image_to_string(img, lang=idioma)
    return ""


def _tablas_markdown(page):
    salidas = []
    try:
        encontradas = page.find_tables()
    except Exception:
        return salidas
    for tabla in getattr(encontradas, "tables", []):
        try:
            filas = tabla.extract()
        except Exception:
            continue
        filas = [[(c or "").replace("\n", " ").strip() for c in fila] for fila in filas]
        filas = [f for f in filas if any(f)]
        if len(filas) < 2:
            continue
        ncols = max(len(f) for f in filas)
        for f in filas:
            while len(f) < ncols:
                f.append("")
        md = ["| " + " | ".join(filas[0]) + " |",
              "| " + " | ".join(["---"] * ncols) + " |"]
        for fila in filas[1:]:
            md.append("| " + " | ".join(fila) + " |")
        salidas.append("\n".join(md))
    return salidas


def _pagina_a_markdown(page):
    d = page.get_text("dict")
    bloques = []
    tamanos = []
    for b in d.get("blocks", []):
        if b.get("type") != 0:
            continue
        texto = ""
        tamano = 0.0
        for linea in b.get("lines", []):
            for span in linea.get("spans", []):
                texto += span.get("text", "")
                tamano = max(tamano, span.get("size", 0))
            texto += " "
        texto = re.sub(r"\s+", " ", texto).strip()
        if texto:
            bloques.append((texto, tamano))
            tamanos.append(tamano)
    if not tamanos:
        return ""
    cuerpo = statistics.median(tamanos)
    md = []
    for texto, tamano in bloques:
        if tamano >= cuerpo * 1.5:
            md.append("## " + texto)
        elif tamano >= cuerpo * 1.2:
            md.append("### " + texto)
        else:
            md.append(texto)
    return "\n\n".join(md)


def _extraer_imagenes(page, dir_imgs, num_pag, doc):
    rutas = []
    try:
        imagenes = page.get_images(full=True)
    except Exception:
        return rutas
    for i, img in enumerate(imagenes):
        xref = img[0]
        try:
            pix = deps()["pymupdf"].Pixmap(doc, xref)
        except Exception:
            continue
        if pix.width < 80 or pix.height < 80:
            continue
        ruta = os.path.join(dir_imgs, "p%d_img%d.png" % (num_pag, i))
        try:
            pix.save(ruta)
            rutas.append(ruta)
        except Exception:
            pass
    return rutas


def _docling_markdown(pdf):
    d = deps()
    if d["docling"] is None:
        raise RuntimeError("Docling no esta instalado. Instala con: pip install docling")
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    from docling.document_converter import DocumentConverter
    convertidor = DocumentConverter()
    resultado = convertidor.convert(pdf)
    return resultado.document.export_to_markdown()


def leer(entrada, salida_dir=None, ocr="auto", idioma="spa", extraer_imgs=True,
         umbral=UMBRAL_TEXTO_POR_PAGINA, paginas=None, forzar=False, motor="auto"):
    d = deps()
    base = os.path.splitext(os.path.basename(entrada))[0]
    salida_dir = salida_dir or os.path.dirname(os.path.abspath(entrada))
    os.makedirs(salida_dir, exist_ok=True)
    ruta_md = os.path.join(salida_dir, base + ".md")
    ruta_json = os.path.join(salida_dir, base + ".json")
    h = _hash_archivo(entrada)
    if not forzar and os.path.exists(ruta_json):
        try:
            with open(ruta_json, "r", encoding="utf-8") as f:
                previo = json.load(f)
            if previo.get("hash") == h:
                return {"markdown": ruta_md, "json": ruta_json, "info": previo, "cache": True}
        except Exception:
            pass
    if motor == "docling":
        md = _docling_markdown(entrada)
        info = {"archivo": os.path.abspath(entrada), "motor": "docling",
                "paginas_procesadas": 0, "motores_usados": {"docling": 1},
                "hash": h, "paginas": []}
        with open(ruta_md, "w", encoding="utf-8") as f:
            f.write(md)
        with open(ruta_json, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=1)
        return {"markdown": ruta_md, "json": ruta_json, "info": info}
    doc = d["pymupdf"].open(entrada)
    dir_imgs = os.path.join(salida_dir, "imagenes")
    if extraer_imgs:
        os.makedirs(dir_imgs, exist_ok=True)

    usar_ocr = ocr in ("auto", "si", "sí", "rapidocr", "tesseract")
    rango = None
    if paginas:
        m = re.match(r"(\d+)\s*-\s*(\d+)", str(paginas))
        if m:
            rango = (int(m.group(1)) - 1, int(m.group(2)) - 1)

    paginas_datos = []
    md_partes = ["# " + base, ""]
    motores = {}

    for num in range(doc.page_count):
        if rango and not (rango[0] <= num <= rango[1]):
            continue
        page = doc.load_page(num)
        texto = page.get_text("text") or ""
        densidad = len(texto.strip())
        motor = "pymupdf"
        cuerpo_md = _pagina_a_markdown(page)

        if densidad < umbral and usar_ocr:
            ocr_txt = _ocr_pagina(page, idioma)
            if ocr_txt.strip():
                motor = "ocr:" + ("rapidocr" if d["RapidOCR"] is not None else "tesseract")
                cuerpo_md = ocr_txt.strip()
                texto = ocr_txt

        tablas = _tablas_markdown(page)
        imgs = _extraer_imagenes(page, dir_imgs, num + 1, doc) if extraer_imgs else []

        motores[motor] = motores.get(motor, 0) + 1
        paginas_datos.append({
            "pagina": num + 1,
            "motor": motor,
            "caracteres": len(texto.strip()),
            "tablas": len(tablas),
            "imagenes": [os.path.relpath(i, salida_dir) for i in imgs],
            "texto": texto.strip(),
        })

        md_partes.append("## Pagina %d" % (num + 1))
        if cuerpo_md:
            md_partes.append(cuerpo_md)
        for j, t in enumerate(tablas):
            md_partes.append("**Tabla %d**" % (j + 1))
            md_partes.append(t)
        for ruta in imgs:
            md_partes.append("![figura](%s)" % os.path.relpath(ruta, salida_dir))
        md_partes.append("")

    md = "\n".join(md_partes)
    info = {
        "archivo": os.path.abspath(entrada),
        "paginas_totales": doc.page_count,
        "paginas_procesadas": len(paginas_datos),
        "motores_usados": motores,
        "paginas": paginas_datos,
    }

    info["hash"] = h
    with open(ruta_md, "w", encoding="utf-8") as f:
        f.write(md)
    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=1)

    return {"markdown": ruta_md, "json": ruta_json, "info": info}


def main(argv):
    ap = argparse.ArgumentParser(description="Lee cualquier PDF (texto, tablas, escaneado).")
    ap.add_argument("--input", "-i", required=True, help="Archivo PDF")
    ap.add_argument("--salida", "-o", help="Carpeta de salida (por defecto, junto al PDF)")
    ap.add_argument("--ocr", choices=["auto", "si", "no"], default="auto",
                    help="Usar OCR en paginas sin texto")
    ap.add_argument("--idioma", default="spa", help="Idioma OCR (spa, eng)")
    ap.add_argument("--paginas", help="Rango de paginas, p.ej. 1-5")
    ap.add_argument("--sin-imagenes", action="store_true", help="No extraer imagenes")
    ap.add_argument("--umbral", type=int, default=UMBRAL_TEXTO_POR_PAGINA,
                    help="Caracteres minimos por pagina para no usar OCR")
    ap.add_argument("--forzar", action="store_true", help="Ignorar la cache y reprocesar")
    ap.add_argument("--motor", choices=["auto", "docling"], default="auto",
                    help="auto = PyMuPDF/OCR adaptativo; docling = PDFs complejos (requiere docling)")
    args = ap.parse_args(argv)

    if not os.path.exists(args.input):
        print("ERROR: no existe %s" % args.input, file=sys.stderr)
        return 1
    try:
        res = leer(args.input, args.salida, args.ocr, args.idioma,
                   not args.sin_imagenes, args.umbral, args.paginas, args.forzar,
                   args.motor)
    except Exception as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 1
    info = res["info"]
    if res.get("cache"):
        print("Cache: reutilizando extraccion previa")
    print("Markdown: %s" % res["markdown"])
    print("JSON:     %s" % res["json"])
    print("Paginas:  %d | Motores: %s" % (info["paginas_procesadas"], info["motores_usados"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
