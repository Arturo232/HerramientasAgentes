#!/usr/bin/env python3
"""Construye un libro PDF traducido a partir de capítulos Markdown.

Flujo completo automatizado (módulo unificado de traducción y compilación):
  1. (Opcional) Extrae el Markdown de un PDF original con pdf_inspector.
  2. (--traducir) Divide el markdown en capítulos y bloques grandes
     (~50k caracteres, cortes en límites seguros) y genera lotes.json
     con la orden de traducción; el agente Cloud traduce cada lote y
     el flujo continúa con --solo-compilar.
  3. (--solo-compilar) Concatena los lotes traducidos en capítulos .md.
  4. Convierte cada capítulo Markdown a LaTeX escapando caracteres especiales
     sin romper bloques \\texttt{...} ni entornos lstlisting. Usa
     \\section*{...} + \\addcontentsline para evitar numeración duplicada.
  5. Extrae portada e imágenes del PDF original (PyMuPDF + Pillow) y estampa
     la banda de edición en español sobre la portada.
  6. Ensambla un preámbulo determinista (libro.tex): formato 6x9 pulgadas,
     Liberation Serif, Noto Sans Mono, \\emergencystretch, \\tolerance y
     \\RaggedRight para evitar desbordamientos.
  7. Compila con XeLaTeX (3 pasadas vía subprocess), mueve el PDF a la raíz
     del proyecto y limpia archivos temporales (.aux, .log, .toc, .out).

Ejecución:
  python3 construir_libro_pdf.py --proyecto /ruta/al/proyecto [--pdf original.pdf] \
      [--traducir | --solo-compilar] [--capitulos 01,02] [--idioma espanol] \
      [--salida How-Linux-Works_es.pdf] [--instalar-deps]
"""

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time

try:
    import pdf_inspector
    PDF_INSPECTOR_DISPONIBLE = True
except ImportError:
    PDF_INSPECTOR_DISPONIBLE = False

try:
    import fitz
    FITZ_DISPONIBLE = True
except ImportError:
    FITZ_DISPONIBLE = False

try:
    from PIL import Image, ImageDraw, ImageFont
    PILLOW_DISPONIBLE = True
except ImportError:
    PILLOW_DISPONIBLE = False


# ---------------------------------------------------------------------------
# Rutas por defecto
# ---------------------------------------------------------------------------
PROYECTO_DEFAULT = os.path.join(
    os.path.expanduser("~"),
    "Documentos/pineda/Documents/How-Linux-Works-es",
)
CAPITULOS_DIR = os.path.join("capitulos", "traducidos")
EXTRACCION_DIR = os.path.join("capitulos", "extraidos")
LATEX_DIR = "latex"
SALIDA_DEFAULT = "How-Linux-Works_es.pdf"

# Mapeo de archivos .md -> nombre de archivo .tex (orden del libro)
ORDEN_CAPITULOS = [
    ("00_prefacio.md", "cap_prefacio.tex"),
    ("01.md", "cap01.tex"),
    ("02.md", "cap02.tex"),
    ("03.md", "cap03.tex"),
    ("04.md", "cap04.tex"),
    ("05.md", "cap05.tex"),
    ("06.md", "cap06.tex"),
    ("07.md", "cap07.tex"),
    ("08.md", "cap08.tex"),
    ("09.md", "cap09.tex"),
    ("10.md", "cap10.tex"),
    ("11.md", "cap11.tex"),
    ("12.md", "cap12.tex"),
    ("13.md", "cap13.tex"),
    ("14.md", "cap14.tex"),
    ("15.md", "cap15.tex"),
    ("16.md", "cap16.tex"),
    ("17.md", "cap17.tex"),
    ("18_bibliografia.md", "cap_biblio.tex"),
    ("19_indice.md", "cap_indice.tex"),
]


# ---------------------------------------------------------------------------
# pdf_inspector
# ---------------------------------------------------------------------------
def _importar_pdf_inspector():
    """Localiza pdf_inspector: import normal, venv de HerramientasAgente o pip."""
    global PDF_INSPECTOR_DISPONIBLE
    if PDF_INSPECTOR_DISPONIBLE:
        return True
    venv = os.path.expanduser(
        "~/Documentos/HerramientasAgente/.venv/lib/python3.14/site-packages"
    )
    for ruta in (venv,):
        if os.path.isdir(ruta) and ruta not in sys.path:
            sys.path.insert(0, ruta)
            try:
                import pdf_inspector  # noqa: F401
                PDF_INSPECTOR_DISPONIBLE = True
                return True
            except ImportError:
                sys.path.remove(ruta)
    return False


def _instalar_pdf_inspector():
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pip", "install", "pdf-inspector>=1.15.0"],
            capture_output=True, text=True, timeout=300,
        )
        if r.returncode == 0:
            import pdf_inspector  # noqa: F401
            global PDF_INSPECTOR_DISPONIBLE
            PDF_INSPECTOR_DISPONIBLE = True
            return True
    except (subprocess.TimeoutExpired, OSError):
        pass
    return False


def extraer_markdown(pdf_original, destino_txt):
    """Extrae el Markdown del PDF con pdf_inspector y lo guarda en texto plano."""
    resultado = pdf_inspector.process_pdf(pdf_original)
    markdown = resultado.markdown or ""
    os.makedirs(os.path.dirname(destino_txt), exist_ok=True)
    with open(destino_txt, "w", encoding="utf-8") as f:
        f.write(markdown)
    return resultado.page_count


# ---------------------------------------------------------------------------
# Portada e imágenes (PyMuPDF + Pillow)
# ---------------------------------------------------------------------------
def _importar_fitz():
    """Localiza fitz: import normal o venv de HerramientasAgente."""
    global FITZ_DISPONIBLE
    if FITZ_DISPONIBLE:
        return True
    venv = os.path.expanduser(
        "~/Documentos/HerramientasAgente/.venv/lib/python3.14/site-packages"
    )
    for ruta in (venv,):
        if os.path.isdir(ruta) and ruta not in sys.path:
            sys.path.insert(0, ruta)
            try:
                import fitz  # noqa: F401
                FITZ_DISPONIBLE = True
                return True
            except ImportError:
                sys.path.remove(ruta)
    return False


def extraer_portada_png(pdf_original, destino_png, dpi=300):
    """Renderiza la primera página del PDF como imagen PNG de la portada."""
    if not _importar_fitz():
        raise RuntimeError("PyMuPDF (fitz) no disponible. Instala con pip install PyMuPDF")
    doc = fitz.open(pdf_original)
    try:
        pagina = doc[0]
        pix = pagina.get_pixmap(dpi=dpi)
        os.makedirs(os.path.dirname(destino_png), exist_ok=True)
        pix.save(destino_png)
    finally:
        doc.close()
    return destino_png


def _cargar_fuente_estampado(tamano):
    """Carga Liberation Sans Bold con fallback a la fuente por defecto de Pillow."""
    candidatas = [
        "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/TTF/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for ruta in candidatas:
        if os.path.isfile(ruta):
            try:
                return ImageFont.truetype(ruta, tamano)
            except OSError:
                continue
    return ImageFont.load_default()


def estampar_portada(original_png, destino_png, texto="Edición en Español"):
    """Añade una banda diagonal semitransparente con el texto de la edición.

    Coloca una banda negra al 75% de opacidad en la esquina superior derecha,
    rotada 45 grados, con el texto en blanco, y guarda el resultado en PNG.
    """
    if not PILLOW_DISPONIBLE:
        raise RuntimeError("Pillow no disponible. Instala con pip install Pillow")
    imagen = Image.open(original_png).convert("RGBA")
    ancho, alto = imagen.size
    capa = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    dibujo = ImageDraw.Draw(capa)

    diagonal = math.hypot(ancho, alto)
    grosor = max(28, int(diagonal * 0.055))
    largo = diagonal * 0.62

    cx = int(ancho * 0.80)
    cy = int(alto * 0.15)
    angulo = math.radians(-45)
    cos_a, sin_a = math.cos(angulo), math.sin(angulo)
    hw, hh = largo / 2.0, grosor / 2.0
    esquinas = [
        (cx + (ex * cos_a - ey * sin_a), cy + (ex * sin_a + ey * cos_a))
        for ex, ey in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))
    ]
    dibujo.polygon(esquinas, fill=(0, 0, 0, 191))

    tamano_fuente = max(18, int(ancho * 0.020))
    fuente = _cargar_fuente_estampado(tamano_fuente)
    img_texto = Image.new("RGBA", (int(largo), grosor), (0, 0, 0, 0))
    td = ImageDraw.Draw(img_texto)
    caja = td.textbbox((0, 0), texto, font=fuente)
    tw, th = caja[2] - caja[0], caja[3] - caja[1]
    td.text(
        ((largo - tw) / 2 - caja[0], (grosor - th) / 2 - caja[1]),
        texto, font=fuente, fill=(255, 255, 255, 255),
    )
    img_texto = img_texto.rotate(45, resample=Image.Resampling.BICUBIC, expand=False)
    capa.alpha_composite(
        img_texto, (int(cx - img_texto.width / 2), int(cy - img_texto.height / 2))
    )

    resultado = Image.alpha_composite(imagen, capa).convert("RGB")
    resultado.save(destino_png)
    return destino_png


def _indice_capitulo_libro(titulo):
    """Mapa un título del TOC del PDF original a un índice de ORDEN_CAPITULOS.

    Reconoce "Chapter N", "Preface", "Bibliography" e "Index" (inglés).
    Devuelve None si el título no corresponde a un capítulo del libro.
    """
    t = (titulo or "").strip().lower()
    m = re.search(r"\bchapter\s+(\d+)\b", t)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 17:
            return n
        return None
    if t.startswith("preface") or "acknowledgment" in t:
        return 0
    if t.startswith("bibliograph"):
        return 18
    if t.startswith("index"):
        return 19
    return None


def _construir_mapa_capitulos(toc):
    """Devuelve [(pagina_inicio, indice_libro)] ordenado por página."""
    mapa = []
    for nivel, titulo, pagina in toc:
        indice = _indice_capitulo_libro(titulo)
        if indice is not None:
            mapa.append((pagina, indice))
    mapa.sort(key=lambda x: x[0])
    return mapa


def _indice_capitulo_de_pagina(mapa, num_pagina):
    """Devuelve el índice de ORDEN_CAPITULOS que contiene la página, o None."""
    indice = None
    for pagina_inicio, idx in mapa:
        if pagina_inicio <= num_pagina:
            indice = idx
        else:
            break
    return indice


def extraer_imagenes_internas(pdf_original, carpeta_imagenes, minimo_px=100):
    """Extrae las imágenes del PDF mayores a minimo_px, deduplicadas por hash.

    Usa el TOC (get_toc) para asociar cada imagen al capítulo que la contiene.
    Devuelve una lista de dicts: {archivo, pagina, capitulo, ancho, alto}.
    """
    if not _importar_fitz():
        raise RuntimeError("PyMuPDF (fitz) no disponible. Instala con pip install PyMuPDF")
    os.makedirs(carpeta_imagenes, exist_ok=True)
    doc = fitz.open(pdf_original)
    mapa = _construir_mapa_capitulos(doc.get_toc())
    vistos = {}
    metadatos = []
    for num in range(1, doc.page_count):
        pagina = doc[num]
        num_real = num + 1
        for info in pagina.get_images(full=True):
            xref = info[0]
            ancho = info[2]
            alto = info[3]
            if ancho < minimo_px or alto < minimo_px:
                continue
            if xref in vistos:
                continue
            vistos[xref] = True
            try:
                datos = doc.extract_image(xref)
            except Exception:  # noqa: BLE001
                continue
            if not datos:
                continue
            ext = datos["ext"]
            img_bytes = datos["image"]
            sha = hashlib.sha256(img_bytes).hexdigest()[:12]
            nombre = f"img_p{num_real:03d}_{sha}.{ext}"
            ruta = os.path.join(carpeta_imagenes, nombre)
            with open(ruta, "wb") as f:
                f.write(img_bytes)
            indice = _indice_capitulo_de_pagina(mapa, num_real)
            metadatos.append({
                "archivo": nombre,
                "pagina": num_real,
                "indice_capitulo": indice if indice is not None else -1,
                "ancho": ancho,
                "alto": alto,
            })
    doc.close()
    return metadatos


def extraer_visuales(pdf_original, latex_dir, texto_estampado="Edición en Español",
                     extraer_portada=True, extraer_imagenes=True):
    """Extrae portada, estampa la versión en español y extrae imágenes internas.

    Devuelve un dict con las rutas generadas y los metadatos de imágenes.
    """
    ruta_imagenes = os.path.join(latex_dir, "imagenes")
    resultado = {
        "portada_original": None,
        "portada_espanol": None,
        "carpeta_imagenes": ruta_imagenes,
        "imagenes": [],
    }
    if extraer_portada:
        ruta_portada = os.path.join(latex_dir, "portada_original.png")
        ruta_espanol = os.path.join(latex_dir, "portada_espanol.png")
        extraer_portada_png(pdf_original, ruta_portada)
        estampar_portada(ruta_portada, ruta_espanol, texto=texto_estampado)
        resultado["portada_original"] = ruta_portada
        resultado["portada_espanol"] = ruta_espanol
    if extraer_imagenes:
        metadatos = extraer_imagenes_internas(pdf_original, ruta_imagenes)
        resultado["imagenes"] = metadatos
    return resultado


# ---------------------------------------------------------------------------
# Traducción por lotes
# ---------------------------------------------------------------------------
_CONVENCIONES_DEFAULT = """# Convenciones de traducción

## Reglas lingüísticas
1. Traduce toda la prosa al español neutro, claro y fluido. Sin jerga de IA, sin anglicismos innecesarios.
2. **NO traducir**: comandos, nombres de archivos, rutas, opciones de línea de comandos, salidas de terminal, nombres de programas/herramientas, variables de entorno, literales de código, nombres de paquetes ni nombres de tecnologías. Todo eso se conserva **exactamente igual**.
3. Los encabezados de sección (números como "2.3 Basic Commands") se traducen SOLO la parte textual (ej. "2.3 Comandos básicos"), manteniendo la numeración.
4. Mantén el tono didáctico y conversacional del autor.

## Reglas de formato (Markdown)
1. Estructura de encabezados:
   - Capítulo: `# Capítulo N: <Título traducido>`
   - Sección: `## N.M <Título traducido>`
   - Subsección: `### N.M.K <Título traducido>`
2. Todo bloque de terminal/código va en ``` con la salida tal cual (sin traducir).
3. Las opciones/ejemplos en línea (rutas, flags) van en backticks.
4. Notas ("NOTE:", "TIP:", "WARNING:") → **NOTA:**, **CONSEJO:**, **ADVERTENCIA:**
5. Preserva viñetas, listas y tablas.
6. Nombres propios de personas se mantienen.

## Calidad
- Traducción completa, sin omitir párrafos ni secciones.
- No añadir comentarios ni resúmenes propios; solo traducir el contenido.
"""


def _nombre_capitulo(indice):
    """Devuelve el nombre base del capítulo (sin .md) según ORDEN_CAPITULOS."""
    return ORDEN_CAPITULOS[indice][0][:-3]


def _es_entrada_toc(linea):
    """Detecta líneas del índice: puntos conductores espaciados o contiguos."""
    if re.search(r"\.{4,}", linea):
        return True
    return bool(re.search(r"\.\s+\.\s+\.", linea))


def _es_titulo_caps(linea):
    """True si la línea parece un título en mayúsculas (>=4 letras, casi sin minúsculas)."""
    letras = [c for c in linea if c.isalpha()]
    if len(letras) < 4:
        return False
    minusculas = sum(1 for c in letras if c.islower())
    return minusculas <= len(letras) * 0.1


def _siguiente_no_vacia(lineas, desde):
    """Devuelve (indice, texto) de la siguiente línea no vacía desde `desde`."""
    j = desde
    while j < len(lineas):
        s = lineas[j].strip()
        if s:
            return j, s
        j += 1
    return None, ""


def _tiene_puntos_en_ventana(lineas, desde, ventana=4):
    """True si alguna de las siguientes `ventana` líneas no vacías tiene puntos."""
    vistos = 0
    j = desde
    while j < len(lineas) and vistos < ventana:
        s = lineas[j].strip()
        if s:
            if _es_entrada_toc(s):
                return True
            vistos += 1
        j += 1
    return False


def _normalizar_linea(linea):
    """Normaliza una línea del markdown extraído para la detección de marcadores.

    Quita los marcadores de negrita (**) y el prefijo de encabezado Markdown
    cuando el resto del texto es un título en mayúsculas o una palabra clave.
    """
    s = linea.strip()
    if "**" in s:
        s = s.replace("**", "")
    m = re.match(r"^#{1,6}\s+(.*)$", s)
    if m:
        resto = m.group(1).strip()
        if (_es_titulo_caps(resto)
                or re.match(r"(PREFACE|ACKNOWLEDGMENTS|BIBLIOGRAPHY|INDEX)\b", resto)):
            s = resto
    return s


def dividir_en_capitulos(markdown):
    """Divide el markdown extraído del PDF en capítulos {indice: texto}.

    Detecta dos órdenes de marcador en el cuerpo del libro: número solo
    (1-17) seguido del título en mayúsculas, o título en mayúsculas seguido
    del número (la extracción a veces invierte el orden). También reconoce
    las líneas PREFACE, ACKNOWLEDGMENTS, BIBLIOGRAPHY e INDEX. Las entradas
    del CONTENTS se descartan porque llevan puntos conductores en las
    líneas siguientes al título. Si no hay marcador de prefacio, el hueco
    entre el final del CONTENTS y el capítulo 1 se asigna al prefacio.
    """
    lineas = markdown.splitlines()
    lineas = [_normalizar_linea(l) for l in lineas]
    n = len(lineas)
    marcadores = []
    vistos_numericos = set()

    def _es_digito_capitulo(s):
        return bool(re.fullmatch(r"\d{1,2}", s)) and 1 <= int(s) <= 17

    i = 0
    while i < n:
        limpia = lineas[i]
        if not limpia or _es_entrada_toc(limpia):
            i += 1
            continue

        if _es_digito_capitulo(limpia):
            num = int(limpia)
            if num not in vistos_numericos:
                j, titulo = _siguiente_no_vacia(lineas, i + 1)
                if (titulo and j is not None and j <= i + 4
                        and _es_titulo_caps(titulo)
                        and not _es_entrada_toc(titulo)
                        and not _tiene_puntos_en_ventana(lineas, j + 1)):
                    marcadores.append((i, num))
                    vistos_numericos.add(num)
            i += 1
            continue

        m_pref = re.match(r"(PREFACE|ACKNOWLEDGMENTS|BIBLIOGRAPHY|INDEX)\b", limpia)
        if (m_pref and _es_titulo_caps(limpia)
                and not _tiene_puntos_en_ventana(lineas, i + 1)):
            palabra = m_pref.group(1)
            if palabra in ("PREFACE", "ACKNOWLEDGMENTS"):
                indice = 0
            elif palabra == "BIBLIOGRAPHY":
                indice = 18
            else:
                indice = 19
            marcadores.append((i, indice))
            i += 1
            continue

        if _es_titulo_caps(limpia):
            j, digito = _siguiente_no_vacia(lineas, i + 1)
            if (digito and j is not None and j <= i + 4
                    and _es_digito_capitulo(digito)
                    and int(digito) not in vistos_numericos
                    and not _tiene_puntos_en_ventana(lineas, j + 1)):
                marcadores.append((i, int(digito)))
                vistos_numericos.add(int(digito))
            i += 1
            continue

        i += 1

    marcadores.sort(key=lambda m: m[0])

    primeros_numericos = [pos for pos, indice in marcadores if 1 <= indice <= 17]
    if primeros_numericos:
        p1 = primeros_numericos[0]
        marcadores = [(pos, indice) for pos, indice in marcadores
                      if indice not in (18, 19) or pos > p1]

    if not any(indice == 0 for _, indice in marcadores):
        primeros = [pos for pos, indice in marcadores if indice == 1]
        if primeros:
            p1 = primeros[0]
            ultimo_puntos = -1
            for j in range(p1):
                if _es_entrada_toc(lineas[j]):
                    ultimo_puntos = j
            if ultimo_puntos >= 0:
                marcadores.append((ultimo_puntos + 1, 0))
                marcadores.sort(key=lambda m: m[0])

    capitulos = {}
    for k, (idx, indice) in enumerate(marcadores):
        fin = marcadores[k + 1][0] if k + 1 < len(marcadores) else n
        cuerpo = "\n".join(lineas[idx:fin]).strip()
        if indice in capitulos:
            capitulos[indice] += "\n" + cuerpo
        else:
            capitulos[indice] = cuerpo
    return capitulos


def dividir_en_bloques(texto, bloque_chars=50000):
    """Divide el texto en bloques grandes cortando en líneas vacías.

    Nunca corta dentro de un bloque de código (fences ``` balanceados) ni
    a mitad de línea salvo que un solo párrafo exceda el presupuesto.
    """
    if len(texto) <= bloque_chars:
        return [texto]
    lineas = texto.splitlines(keepends=True)
    total = len(lineas)
    bloques = []
    inicio = 0
    while inicio < total:
        tamano = 0
        fences = 0
        corte = total
        ultimo_vacio = None
        i = inicio
        while i < total:
            stripped = lineas[i].strip()
            if fences % 2 == 0 and not stripped:
                ultimo_vacio = i
            if i > inicio and tamano + len(lineas[i]) > bloque_chars:
                if fences % 2 == 0:
                    if ultimo_vacio is not None and ultimo_vacio > inicio:
                        corte = ultimo_vacio
                    else:
                        corte = i
                    break
            if stripped.startswith("```"):
                fences += 1
            tamano += len(lineas[i])
            i += 1
        bloques.append("".join(lineas[inicio:corte]))
        inicio = corte
    return [b for b in bloques if b.strip()]


def _instruccion_traduccion(proyecto, idioma):
    """Devuelve la orden de traducción; crea CONVENCIONES.md si no existe."""
    ruta = os.path.join(proyecto, "CONVENCIONES.md")
    if os.path.isfile(ruta):
        with open(ruta, encoding="utf-8") as f:
            convenciones = f.read()
    else:
        convenciones = _CONVENCIONES_DEFAULT
        try:
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(convenciones)
        except OSError:
            pass
    return (
        f"Traduce al {idioma} el contenido del bloque siguiendo estrictamente "
        f"estas convenciones:\n\n{convenciones}\n\n"
        "Entrega ÚNICAMENTE el bloque traducido en Markdown, sin comentarios "
        "ni explicaciones. No omitas ningún párrafo."
    )


def preparar_lotes(pdf_original, proyecto, capitulos_filtro="", idioma="espanol",
                   bloque_chars=50000):
    """Divide el markdown extraído en capítulos y bloques, y genera lotes.json.

    Conserva los lotes ya existentes (traducidos) y solo añade los faltantes.
    Devuelve (manifiesto, ruta_lotes).
    """
    ruta_md = os.path.join(proyecto, EXTRACCION_DIR, "markdown_completo.md")
    if not os.path.isfile(ruta_md):
        if not _importar_pdf_inspector():
            raise RuntimeError(
                "pdf_inspector no disponible. Usa --instalar-deps."
            )
        extraer_markdown(pdf_original, ruta_md)
    with open(ruta_md, encoding="utf-8") as f:
        markdown = f.read()

    capitulos = dividir_en_capitulos(markdown)
    if not capitulos:
        raise RuntimeError(
            "No se detectaron capítulos en el markdown extraído."
        )

    deseados = None
    if capitulos_filtro:
        deseados = {c.strip() for c in capitulos_filtro.split(",") if c.strip()}

    partes_dir = os.path.join(proyecto, CAPITULOS_DIR, "partes")
    os.makedirs(partes_dir, exist_ok=True)

    ruta_lotes = os.path.join(proyecto, "lotes.json")
    previos = {}
    if os.path.isfile(ruta_lotes):
        with open(ruta_lotes, encoding="utf-8") as f:
            previos = {l["id"]: l for l in json.load(f).get("lotes", [])}

    lotes = []
    for indice in sorted(capitulos):
        nombre = _nombre_capitulo(indice)
        if deseados and not any(d in nombre for d in deseados):
            continue
        bloques = dividir_en_bloques(capitulos[indice], bloque_chars)
        for orden, bloque in enumerate(bloques):
            bid = f"{nombre}_b{orden:02d}"
            ruta = os.path.join(partes_dir, bid + ".md")
            previo = previos.get(bid)
            if previo and os.path.isfile(ruta):
                lotes.append(previo)
                continue
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(bloque)
            lotes.append({
                "id": bid,
                "ruta": os.path.relpath(ruta, proyecto),
                "capitulo": nombre,
                "orden": orden,
                "caracteres": len(bloque),
                "estado": "pendiente",
            })

    manifiesto = {
        "idioma": idioma,
        "bloque_chars": bloque_chars,
        "instruccion": _instruccion_traduccion(proyecto, idioma),
        "lotes": lotes,
    }
    with open(ruta_lotes, "w", encoding="utf-8") as f:
        json.dump(manifiesto, f, ensure_ascii=False, indent=2)
    return manifiesto, ruta_lotes


def concatenar_lotes(proyecto):
    """Une los lotes traducidos en los capítulos .md finales.

    Devuelve {"generados": [...], "pendientes": [...]} o None si no hay lotes.
    """
    ruta_lotes = os.path.join(proyecto, "lotes.json")
    if not os.path.isfile(ruta_lotes):
        return None
    with open(ruta_lotes, encoding="utf-8") as f:
        manifiesto = json.load(f)
    por_capitulo = {}
    pendientes = []
    for lote in manifiesto.get("lotes", []):
        ruta = os.path.join(proyecto, lote["ruta"])
        if not os.path.isfile(ruta):
            pendientes.append(lote["id"])
            continue
        por_capitulo.setdefault(lote["capitulo"], []).append((lote["orden"], ruta))
    capitulos_dir = os.path.join(proyecto, CAPITULOS_DIR)
    generados = []
    for cap, partes in sorted(por_capitulo.items()):
        partes.sort()
        destino = os.path.join(capitulos_dir, cap + ".md")
        nueva_parte = max(os.path.getmtime(ruta) for _, ruta in partes)
        if os.path.isfile(destino) and os.path.getmtime(destino) > nueva_parte:
            continue
        contenido = "\n\n".join(
            open(ruta, encoding="utf-8").read().strip() for _, ruta in partes
        )
        with open(destino, "w", encoding="utf-8") as f:
            f.write(contenido + "\n")
        generados.append(os.path.relpath(destino, proyecto))
    return {"generados": generados, "pendientes": pendientes}


# ---------------------------------------------------------------------------
# Escape y conversión Markdown -> LaTeX
# ---------------------------------------------------------------------------
_TEX_ESPECIALES = {
    "\\": r"\textbackslash{}",
    "{": r"\{",
    "}": r"\}",
    "$": r"\$",
    "&": r"\&",
    "#": r"\#",
    "_": r"\_",
    "%": r"\%",
    "^": r"\textasciicircum{}",
    "~": r"\textasciitilde{}",
    "`": r"\textasciigrave{}",
    "|": r"\textbar{}",
}

_TEX_ESPECIALES_TT = {
    "\\": r"\textbackslash{}",
    "{": r"\{",
    "}": r"\}",
    "$": r"\$",
    "&": r"\&",
    "#": r"\#",
    "_": r"\_",
    "%": r"\%",
    "^": r"\textasciicircum{}",
    "~": r"\textasciitilde{}",
    "`": r"\textasciigrave{}",
    "|": r"\textbar{}",
}

_NIVEL_HEADING = {
    "#": ("chapter", "chapter"),
    "##": ("section", "section"),
    "###": ("subsection", "subsection"),
    "####": ("subsubsection", "subsubsection"),
}

_NOTA_PREFIX = {
    "**NOTA:**": "NOTA:",
    "**CONSEJO:**": "CONSEJO:",
    "**ADVERTENCIA:**": "ADVERTENCIA:",
    "**TIP:**": "CONSEJO:",
    "**WARNING:**": "ADVERTENCIA:",
    "**NOTA**": "NOTA",
}


def _escapar_prosa(texto):
    """Escapa caracteres especiales LaTeX en texto plano."""
    out = []
    for ch in texto:
        out.append(_TEX_ESPECIALES.get(ch, ch))
    return "".join(out)


def _escapar_texttt(texto):
    """Escapa caracteres para el interior de \\texttt{...}."""
    out = []
    for ch in texto:
        out.append(_TEX_ESPECIALES_TT.get(ch, ch))
    return "".join(out)


def _convertir_inline(texto):
    """Convierte inline markdown (code, bold, italic, links) a LaTeX.

    Procesa por alternancia de regex para nunca escapar dentro de los
    comandos \\texttt/\\textbf/\\textit generados.
    """
    if not texto:
        return ""
    if texto.strip() in ("*", "**", "***"):
        return texto

    patron = re.compile(
        r"(``.+?``)"                      # 1: código inline con doble backtick
        r"|(`[^`]+`)"                      # 2: código inline
        r"|(\*\*[^*]+\*\*)"                # 3: negrita
        r"|(\*[^*]+\*)"                    # 4: cursiva
        r"|(\[[^\]]+\]\([^)]+\))"          # 5: enlace markdown
    )

    resultado = []
    pos = 0
    for m in patron.finditer(texto):
        if m.start() > pos:
            resultado.append(_escapar_prosa(texto[pos:m.start()]))
        if m.group(1):
            contenido = m.group(1)[2:-2]
            resultado.append(r"\texttt{" + _escapar_texttt(contenido) + "}")
        elif m.group(2):
            contenido = m.group(2)[1:-1]
            resultado.append(r"\texttt{" + _escapar_texttt(contenido) + "}")
        elif m.group(3):
            resultado.append(r"\textbf{" + _convertir_inline(m.group(3)[2:-2]) + "}")
        elif m.group(4):
            resultado.append(r"\textit{" + _convertir_inline(m.group(4)[1:-1]) + "}")
        elif m.group(5):
            etiqueta, url = m.group(5)[1:-1].split("](", 1)
            url = url[:-1].replace("\\", r"\textbackslash{}").replace("_", r"\_")
            resultado.append(r"\href{" + url + "}{" + _convertir_inline(etiqueta) + "}")
        pos = m.end()
    if pos < len(texto):
        resultado.append(_escapar_prosa(texto[pos:]))
    return "".join(resultado)


def _celda_a_latex(celda):
    """Convierte una celda de tabla markdown a contenido LaTeX."""
    celda = celda.strip()
    return _convertir_inline(celda)


def _titulo_limpio(titulo):
    """Limpia el título para \\addcontentsline (sin asteriscos ni backticks)."""
    t = titulo.strip()
    t = re.sub(r"`([^`]+)`", r"\1", t)
    t = t.replace("**", "").replace("*", "")
    return t.strip()


def _es_linea_tabla(linea):
    return linea.lstrip().startswith("|") and linea.rstrip().endswith("|")


def _dividir_fila_tabla(linea):
    """Divide una fila de tabla markdown en celdas, respetando `\\|` escapado."""
    contenido = linea.strip()
    if contenido.startswith("|"):
        contenido = contenido[1:]
    if contenido.endswith("|"):
        contenido = contenido[:-1]
    celdas = []
    actual = []
    i = 0
    n = len(contenido)
    while i < n:
        ch = contenido[i]
        if ch == "|" and (i == 0 or contenido[i - 1] != "\\"):
            celdas.append("".join(actual))
            actual = []
            i += 1
            continue
        actual.append(ch)
        i += 1
    celdas.append("".join(actual))
    return [c.strip() for c in celdas]


def _convertir_tabla(lineas, i):
    """Convierte un bloque de tabla markdown empezando en lineas[i].

    Devuelve (texto_tex, nuevo_indice). """
    inicio = i
    filas = []
    while i < len(lineas) and _es_linea_tabla(lineas[i]):
        filas.append(lineas[i].strip())
        i += 1

    celdas_primera = _dividir_fila_tabla(filas[0])
    ncols = len(celdas_primera)

    # Detectar fila separadora (|---|)
    cuerpo = filas[1:]
    if cuerpo and re.match(r"^[\s:\-|]+$", cuerpo[0]) and "---" in cuerpo[0]:
        cuerpo = cuerpo[1:]

    cols = "l" * ncols
    out = [r"\begin{tabular}{" + cols + "}", r"\hline"]
    for j, celda in enumerate(celdas_primera):
        out.append(_celda_a_latex(celda) + (" & " if j < ncols - 1 else r" \\ \hline"))
    for fila in cuerpo:
        celdas = _dividir_fila_tabla(fila)
        celdas = celdas[:ncols]
        while len(celdas) < ncols:
            celdas.append("")
        for j, celda in enumerate(celdas):
            out.append(_celda_a_latex(celda) + (" & " if j < ncols - 1 else r" \\ \hline"))
    out.append(r"\end{tabular}")
    return "\n".join(out) + "\n", i


def convertir_markdown_a_latex(texto_md):
    """Convierte el Markdown de un capítulo completo a LaTeX."""
    lineas = texto_md.splitlines()
    out = []
    en_codigo = False
    lista_actual = None  # 'itemize' | 'enumerate'
    i = 0
    fences = 0

    while i < len(lineas):
        linea = lineas[i]

        if en_codigo:
            if linea.strip().startswith("```"):
                en_codigo = False
                fences += 1
                out.append("\\end{lstlisting}")
                i += 1
                continue
            out.append(linea)
            i += 1
            continue

        # Fence de apertura
        if linea.strip().startswith("```"):
            en_codigo = True
            fences += 1
            out.append("\\begin{lstlisting}")
            i += 1
            continue

        # Cerrar lista abierta si la línea no es de lista
        if lista_actual:
            if not (linea.strip().startswith("- ") or re.match(r"^\d+\.\s", linea.strip())):
                out.append("\\end{" + lista_actual + "}")
                lista_actual = None
            elif linea.strip() in ("", "-"):
                i += 1
                continue

        # Heading
        if re.match(r"^#{1,4} ", linea):
            nivel = linea.split(" ", 1)[0]
            titulo = linea[len(nivel) + 1:]
            tex_nivel, toc_nivel = _NIVEL_HEADING[nivel]
            out.append("\\" + tex_nivel + "*{" + _convertir_inline(titulo) + "}")
            out.append("\\addcontentsline{toc}{" + toc_nivel + "}{"
                       + _escapar_prosa(_titulo_limpio(titulo)) + "}")
            i += 1
            continue

        # Tabla
        if _es_linea_tabla(linea):
            bloque, nuevo_i = _convertir_tabla(lineas, i)
            out.append(bloque)
            i = nuevo_i
            continue

        # Nota (bloque quote de una línea)
        nota = False
        for prefijo, etiqueta in _NOTA_PREFIX.items():
            if linea.startswith(prefijo):
                contenido = linea[len(prefijo):].strip()
                out.append(r"\begin{quote}\textbf{" + _escapar_prosa(etiqueta) + "} "
                           + _convertir_inline(contenido) + r"\end{quote}")
                nota = True
                i += 1
                break
        if nota:
            continue

        # Lista de viñetas
        if linea.strip().startswith("- "):
            if lista_actual != "itemize":
                if lista_actual:
                    out.append("\\end{" + lista_actual + "}")
                out.append("\\begin{itemize}")
                lista_actual = "itemize"
            out.append("  \\item " + _convertir_inline(linea.strip()[2:]))
            i += 1
            continue

        # Lista numerada
        m_num = re.match(r"^(\d+)\.\s+(.*)$", linea.strip())
        if m_num:
            if lista_actual != "enumerate":
                if lista_actual:
                    out.append("\\end{" + lista_actual + "}")
                out.append("\\begin{enumerate}")
                lista_actual = "enumerate"
            out.append("  \\item " + _convertir_inline(m_num.group(2)))
            i += 1
            continue

        # Línea de separación
        if linea.strip() in ("---", "***", "___"):
            out.append("\\medskip\\hrule\\medskip")
            i += 1
            continue

        # Párrafo normal / vacío
        if linea.strip() == "":
            out.append("")
        else:
            out.append(_convertir_inline(linea))
        i += 1

    # Cerrar listas y código abiertos al final
    if lista_actual:
        out.append("\\end{" + lista_actual + "}")
    if en_codigo:
        out.append("\\end{lstlisting}")
        fences += 1

    if fences % 2 != 0:
        print(f"  [ADVERTENCIA] Fences de código desbalanceados ({fences}).",
              file=sys.stderr)

    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# Preámbulo determinista
# ---------------------------------------------------------------------------
def generar_preambulo():
    return r"""% How Linux Works - Edición en español
% Compilación con XeLaTeX
\documentclass[11pt,openany]{book}

\usepackage[paperwidth=6in,paperheight=9in,margin=0.9in,top=0.9in,bottom=1.0in,headheight=14pt]{geometry}
\usepackage{fontspec}
\usepackage{graphicx}
\usepackage{xcolor}
\usepackage{titlesec}
\usepackage{fancyhdr}
\usepackage{listings}
\usepackage{upquote}
\usepackage{enumitem}
\usepackage{hyperref}
\usepackage{tocloft}
\usepackage{url}
\usepackage{ragged2e}

% ---- Evitar desbordamientos de línea ----
\emergencystretch=3em
\tolerance=1000
\hbadness=10000
% Permitir saltos de línea en URLs
\PassOptionsToPackage{hyphens}{url}
\def\UrlBreaks{\do\/\do-}

% ---- Títulos de sección sin numeración automática (los números ya están en los títulos) ----
\titleformat{\section}{\normalfont\Large\bfseries\RaggedRight}{}{0em}{}
\titleformat{\subsection}{\normalfont\large\bfseries\RaggedRight}{}{0em}{}
\titleformat{\subsubsection}{\normalfont\normalsize\bfseries\RaggedRight}{}{0em}{}

% ---- Tipografía ----
\setmainfont{Liberation Serif}
\setsansfont{Liberation Sans}
\setmonofont{Noto Sans Mono}[Scale=0.85]

% ---- Colores ----
\definecolor{codebg}{RGB}{245,245,245}
\definecolor{codeframe}{RGB}{200,200,200}
\definecolor{notebg}{RGB}{240,245,255}
\definecolor{warnbg}{RGB}{255,243,224}
\definecolor{linkcol}{RGB}{0,80,160}

% ---- Enlaces ----
\hypersetup{
  colorlinks=true,
  linkcolor=linkcol,
  urlcolor=linkcol,
  pdftitle={How Linux Works - Edición en español},
  pdfauthor={Brian Ward}
}

% ---- Títulos de capítulo ----
\titleformat{\chapter}[display]
  {\normalfont\huge\bfseries\color{black}}
  {\filleft\Large\chaptertitlename\ \thechapter}
  {20pt}
  {\Huge}
  [\vspace{10pt}\titlerule]
\titlespacing*{\chapter}{0pt}{-30pt}{30pt}

% ---- Encabezados y pies de página ----
\pagestyle{fancy}
\fancyhf{}
\fancyhead[LE]{\small\itshape\nouppercase{\leftmark}}
\fancyhead[RO]{\small\itshape\nouppercase{\rightmark}}
\fancyfoot[C]{\thepage}
\renewcommand{\headrulewidth}{0.4pt}
\fancypagestyle{plain}{
  \fancyhf{}
  \fancyfoot[C]{\thepage}
  \renewcommand{\headrulewidth}{0pt}
}

% ---- Código ----
\lstset{
  basicstyle=\ttfamily\small,
  backgroundcolor=\color{codebg},
  frame=single,
  rulecolor=\color{codeframe},
  breaklines=true,
  breakatwhitespace=false,
  postbreak=\mbox{\textcolor{codeframe}{$\hookrightarrow$}\space},
  showstringspaces=false,
  columns=fullflexible,
  keepspaces=true,
  upquote=true,
  aboveskip=8pt,
  belowskip=8pt,
  xleftmargin=6pt,
  xrightmargin=6pt,
  extendedchars=true,
}

% ---- Listas ----
\setlist[itemize]{leftmargin=1.2em, itemsep=2pt, topsep=4pt}
\setlist[enumerate]{leftmargin=1.2em, itemsep=2pt, topsep=4pt}

% ---- Tablas ----
\setlength{\tabcolsep}{6pt}
\renewcommand{\arraystretch}{1.2}

\begin{document}

% ================= PORTADA =================
\begin{titlepage}
  \IfFileExists{portada_espanol.png}{%
    \newgeometry{margin=0pt,top=0pt,bottom=0pt}
    \noindent\includegraphics[width=\paperwidth,height=\paperheight,keepaspectratio=false]{portada_espanol.png}
    \restoregeometry
  }{%
    \begin{center}
      \vspace*{1.8cm}
      {\large\scshape Edición en español}\\[0.8cm]
      {\Huge\bfseries How Linux Works}\\[0.5cm]
      {\LARGE Cómo funciona Linux}\\[1.0cm]
      \rule{0.6\textwidth}{1.2pt}\\[0.8cm]
      {\large\itshape Lo que todo superusuario debería saber}\\[2.2cm]
      {\large Tercera edición}\\[0.6cm]
      {\large\bfseries Brian Ward}\\[2.8cm]
      \rule{0.6\textwidth}{1.2pt}\\[0.6cm]
      {\small Traducido del original ``How Linux Works,\\ What Every Superuser Should Know''}\\[0.6cm]
      {\small\itshape No Starch Press, 2021}\\[0.4cm]
      {\footnotesize\itshape Traducción al español para uso personal}
      \vfill
    \end{center}
  }%
\end{titlepage}

% ================= PÁGINA DE CRÉDITOS =================
\newpage
\thispagestyle{empty}
\begin{center}
  \vspace*{2cm}
  {\large\bfseries How Linux Works}\\[0.3cm]
  {\large Cómo funciona Linux}\\[1.2cm]
  {\normalsize Tercera edición}\\[0.3cm]
  {\normalsize Brian Ward}\\[2cm]
  \begin{flushleft}
    \small
    Este documento es una traducción al español del libro\\
    \textit{How Linux Works, What Every Superuser Should Know}, 3.ª edición,\\
    de Brian Ward (No Starch Press, 2021).\\[1em]
    La traducción se ha realizado con fines personales y de estudio.\\
    Todos los derechos del contenido original pertenecen a su autor\\
    y a No Starch Press.\\[1em]
    Esta edición en español se ha generado a partir de la versión\\
    en formato digital del libro original.
  \end{flushleft}
  \vfill
\end{center}

% ================= ÍNDICE DE CONTENIDOS =================
\frontmatter
\tableofcontents

% ================= CUERPO =================
\mainmatter
"""


def generar_fin():
    return r"""
\backmatter

\end{document}
"""


# ---------------------------------------------------------------------------
# Ensamblado y compilación
# ---------------------------------------------------------------------------
def localizar_xelatex():
    ruta = shutil.which("xelatex")
    if ruta:
        return ruta
    candidatos = [
        os.path.expanduser("~/.local/bin/xelatex"),
        os.path.expanduser("~/.TinyTeX/bin/x86_64-linux/xelatex"),
        "/usr/bin/xelatex",
    ]
    for c in candidatos:
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def compilar(latex_dir, pasadas=3):
    xelatex = localizar_xelatex()
    if not xelatex:
        raise RuntimeError("xelatex no encontrado. Instala TinyTeX/XeLaTeX.")
    for pasada in range(1, pasadas + 1):
        r = subprocess.run(
            [xelatex, "-interaction=nonstopmode", "-halt-on-error=false", "libro.tex"],
            cwd=latex_dir,
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            log = os.path.join(latex_dir, "libro.log")
            detalle = ""
            if os.path.isfile(log):
                with open(log, encoding="utf-8", errors="replace") as f:
                    detalle = f.read()[-4000:]
            raise RuntimeError(
                f"xelatex falló en la pasada {pasada}.\n{detalle}"
            )


def limpiar_temporales(latex_dir):
    for ext in (".aux", ".log", ".toc", ".out", ".lof", ".lot"):
        ruta = os.path.join(latex_dir, "libro" + ext)
        if os.path.isfile(ruta):
            os.remove(ruta)


def encontrar_pdf_original(proyecto):
    for nombre in os.listdir(proyecto):
        if nombre.lower().endswith(".pdf") and "es" not in os.path.splitext(nombre)[0].lower():
            return os.path.join(proyecto, nombre)
    return None


def _bloque_figura(meta):
    """Genera el LaTeX de una figura a partir de sus metadatos."""
    ruta = os.path.join("imagenes", meta["archivo"])
    if meta["alto"] > meta["ancho"]:
        tamano = "height=0.7\\textheight"
    else:
        tamano = "width=0.8\\textwidth"
    return (
        r"\begin{figure}[h]" "\n"
        r"  \centering" "\n"
        r"  \includegraphics[" + tamano + "]{" + ruta + "}" "\n"
        r"\end{figure}"
    )


def agrupar_imagenes_por_capitulo(metadatos):
    """Agrupa los metadatos de imágenes por indice_capitulo del TOC."""
    por_indice = {}
    for meta in metadatos:
        por_indice.setdefault(meta.get("indice_capitulo", -1), []).append(meta)
    return por_indice


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Construye un libro PDF traducido desde capítulos Markdown."
    )
    parser.add_argument("--proyecto", default=PROYECTO_DEFAULT,
                        help="raíz del proyecto del libro")
    parser.add_argument("--extraer", action="store_true",
                        help="extraer Markdown del PDF original con pdf_inspector")
    parser.add_argument("--pdf", default="",
                        help="ruta del PDF original (por defecto se busca en el proyecto)")
    parser.add_argument("--sin-portada", action="store_true",
                        help="no extraer ni estampar la portada del PDF original")
    parser.add_argument("--sin-imagenes", action="store_true",
                        help="no extraer las imágenes internas del PDF original")
    parser.add_argument("--texto-estampado", default="",
                        help="texto de la banda de la portada (def: 'Edición en Español')")
    parser.add_argument("--traducir", action="store_true",
                        help="generar lotes de traducción desde el PDF original y salir")
    parser.add_argument("--solo-compilar", action="store_true",
                        help="concatenar lotes traducidos y compilar sin regenerar lotes")
    parser.add_argument("--idioma", default="espanol",
                        help="idioma destino de la traducción (def: espanol)")
    parser.add_argument("--bloque-chars", type=int, default=50000,
                        help="tamaño objetivo de cada lote en caracteres (def: 50000)")
    parser.add_argument("--capitulos", default="",
                        help="lista de capítulos a procesar (p.ej. '01,02'); vacío = todos")
    parser.add_argument("--salida", default=SALIDA_DEFAULT,
                        help="nombre del PDF final en la raíz")
    parser.add_argument("--pasadas", type=int, default=3,
                        help="número de pasadas de xelatex (def: 3)")
    parser.add_argument("--instalar-deps", action="store_true",
                        help="instala pdf-inspector si falta")
    args = parser.parse_args()

    inicio = time.time()
    proyecto = os.path.abspath(os.path.expanduser(args.proyecto))
    if not os.path.isdir(proyecto):
        print(json.dumps({"exito": False, "mensaje": f"No existe el proyecto: {proyecto}"},
                         ensure_ascii=False, indent=2))
        return 1

    latex_dir = os.path.join(proyecto, LATEX_DIR)
    os.makedirs(latex_dir, exist_ok=True)

    # Localizar PDF original
    pdf_original = args.pdf
    if not pdf_original:
        pdf_original = encontrar_pdf_original(proyecto)

    # Extracción de visuales (portada e imágenes internas)
    visuales = None
    if pdf_original and (not args.sin_portada or not args.sin_imagenes):
        try:
            visuales = extraer_visuales(
                pdf_original, latex_dir,
                texto_estampado=args.texto_estampado or "Edición en Español",
                extraer_portada=not args.sin_portada,
                extraer_imagenes=not args.sin_imagenes,
            )
            if visuales.get("portada_espanol"):
                print(f"[portada] estampada -> {visuales['portada_espanol']}")
            if visuales.get("imagenes"):
                print(f"[imagenes] {len(visuales['imagenes'])} extraídas -> "
                      f"{visuales['carpeta_imagenes']}")
        except RuntimeError as exc:
            print(json.dumps({"exito": False, "mensaje": str(exc)},
                             ensure_ascii=False, indent=2))
            return 1

    # Extracción opcional de markdown (pdf_inspector)
    if args.extraer:
        if not _importar_pdf_inspector():
            if args.instalar_deps and _instalar_pdf_inspector():
                pass
            else:
                print(json.dumps(
                    {"exito": False,
                     "mensaje": "pdf_inspector no disponible. Usa --instalar-deps."},
                    ensure_ascii=False, indent=2))
                return 1
        if not pdf_original:
            print(json.dumps({"exito": False, "mensaje": "No se encontró PDF original."},
                             ensure_ascii=False, indent=2))
            return 1
        destino = os.path.join(proyecto, EXTRACCION_DIR, "markdown_completo.md")
        paginas = extraer_markdown(pdf_original, destino)
        print(f"[extracción] {paginas} páginas -> {destino}")

    # Traducción por lotes: genera lotes.json y sale sin compilar
    if args.traducir:
        if not pdf_original:
            print(json.dumps({"exito": False,
                              "mensaje": ("--traducir requiere el PDF original "
                                          "(--pdf o presente en el proyecto).")},
                             ensure_ascii=False, indent=2))
            return 1
        if not _importar_pdf_inspector():
            if not (args.instalar_deps and _instalar_pdf_inspector()):
                print(json.dumps(
                    {"exito": False,
                     "mensaje": "pdf_inspector no disponible. Usa --instalar-deps."},
                    ensure_ascii=False, indent=2))
                return 1
        try:
            manifiesto, ruta_lotes = preparar_lotes(
                pdf_original, proyecto, args.capitulos, args.idioma,
                args.bloque_chars)
        except RuntimeError as exc:
            print(json.dumps({"exito": False, "mensaje": str(exc)},
                             ensure_ascii=False, indent=2))
            return 1
        pendientes = [l["id"] for l in manifiesto["lotes"]
                      if l["estado"] == "pendiente"]
        print(json.dumps({
            "exito": True,
            "modo": "traducir_lotes",
            "lotes_json": ruta_lotes,
            "total_lotes": len(manifiesto["lotes"]),
            "lotes_pendientes": pendientes,
            "instruccion": manifiesto["instruccion"],
            "mensaje": ("Lotes generados. El agente Cloud traduce cada bloque "
                        "pendiente y reejecuta con --solo-compilar."),
        }, ensure_ascii=False, indent=2))
        return 0

    # Concatenación de lotes traducidos
    resultado_lotes = None
    if args.solo_compilar or os.path.isfile(os.path.join(proyecto, "lotes.json")):
        resultado_lotes = concatenar_lotes(proyecto)
    if resultado_lotes:
        if resultado_lotes["pendientes"]:
            if args.solo_compilar:
                print(json.dumps({"exito": False,
                                  "mensaje": "Hay lotes sin traducir.",
                                  "pendientes": resultado_lotes["pendientes"]},
                                 ensure_ascii=False, indent=2))
                return 1
            print(f"[lotes] AVISO: {len(resultado_lotes['pendientes'])} lotes "
                  f"sin traducir; se conservan los capítulos existentes.")
        elif resultado_lotes["generados"]:
            print(f"[lotes] capítulos generados: {resultado_lotes['generados']}")

    # Selección de capítulos
    if args.capitulos:
        deseado = {c.strip() for c in args.capitulos.split(",") if c.strip()}
        parejas = [(md, tex) for md, tex in ORDEN_CAPITULOS
                   if any(d in md for d in deseado) or any(d == tex.replace(".tex", "") for d in deseado)]
    else:
        parejas = list(ORDEN_CAPITULOS)

    capitulos_dir = os.path.join(proyecto, CAPITULOS_DIR)

    faltantes = [md for md, _ in parejas
                 if not os.path.isfile(os.path.join(capitulos_dir, md))]
    if faltantes:
        omitibles = [md for md in faltantes
                     if not (resultado_lotes
                             and any(l["capitulo"] == md[:-3]
                                     for l in json.load(open(
                                         os.path.join(proyecto, "lotes.json"),
                                         encoding="utf-8"))["lotes"]))]
        if omitibles:
            print(f"[aviso] capítulos sin contenido detectado (se omiten): "
                  f"{omitibles}")
            parejas = [(md, tex) for md, tex in parejas if md not in omitibles]
            faltantes = [md for md, _ in parejas
                         if not os.path.isfile(os.path.join(capitulos_dir, md))]
    if faltantes:
        print(json.dumps({"exito": False, "mensaje": "Capítulos faltantes",
                          "faltantes": faltantes}, ensure_ascii=False, indent=2))
        return 1

    # Conversión de cada capítulo
    for md, tex in parejas:
        ruta_md = os.path.join(capitulos_dir, md)
        with open(ruta_md, encoding="utf-8") as f:
            contenido = f.read()
        latex = convertir_markdown_a_latex(contenido)
        ruta_tex = os.path.join(latex_dir, tex)
        with open(ruta_tex, "w", encoding="utf-8") as f:
            f.write(latex)
        print(f"[convertido] {md} -> {tex}")

    # Ensamblado de libro.tex
    imagenes_por_capitulo = {}
    if visuales and visuales.get("imagenes"):
        imagenes_por_capitulo = agrupar_imagenes_por_capitulo(visuales["imagenes"])

    indice_global = {md: i for i, (md, _) in enumerate(ORDEN_CAPITULOS)}
    cuerpo = []
    for md, tex in parejas:
        cuerpo.append(r"\input{" + tex.replace(".tex", "") + "}")
        figuras = imagenes_por_capitulo.get(indice_global.get(md, -1), [])
        for meta in figuras:
            cuerpo.append(_bloque_figura(meta))
    libro_tex = (generar_preambulo()
                 + "\n".join(cuerpo) + "\n"
                 + generar_fin())
    ruta_libro = os.path.join(latex_dir, "libro.tex")
    with open(ruta_libro, "w", encoding="utf-8") as f:
        f.write(libro_tex)

    # Compilación
    compilar(latex_dir, args.pasadas)

    pdf_temp = os.path.join(latex_dir, "libro.pdf")
    if not os.path.isfile(pdf_temp):
        print(json.dumps({"exito": False, "mensaje": "No se generó libro.pdf"},
                         ensure_ascii=False, indent=2))
        return 1

    pdf_final = os.path.join(proyecto, args.salida)
    shutil.copyfile(pdf_temp, pdf_final)
    limpiar_temporales(latex_dir)

    tamano = os.path.getsize(pdf_final)
    print(json.dumps({
        "exito": True,
        "pdf": pdf_final,
        "tamano_bytes": tamano,
        "capitulos": [md for md, _ in parejas],
        "tiempo_s": round(time.time() - inicio, 2),
        "mensaje": "PDF final generado en la raíz del proyecto.",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
