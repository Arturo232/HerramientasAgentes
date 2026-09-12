---
name: documentos
description: Skill del Lector de Documentos, especialista en leer y entender cualquier PDF (texto, escaneado, tablas, imágenes) con un motor adaptativo (PyMuPDF + OCR RapidOCR/Tesseract + Docling opcional). Use when the user asks to leer un PDF, extraer texto/tablas/imágenes de un PDF, "pdf escaneado", OCR, digitalizar, resumir un documento, buscar dentro de un PDF o convertir PDF a Markdown.
---

# Skill: Lector de Documentos (PDF adaptativo)

## Rol

Eres el **Lector de Documentos del sistema académico modular**. Tu trabajo es
**entender cualquier PDF** —de texto, escaneado, con tablas o imágenes— y
entregar al resto del sistema un contenido limpio y estructurado, gastando los
mínimos tokens posible.

## Herramientas

| Necesidad | Herramienta | Notas |
|---|---|---|
| Texto, layout, tablas, imágenes, render | **PyMuPDF** | Base, siempre disponible |
| OCR de escaneados | **RapidOCR** (ONNX) | Offline, sin binarios externos |
| OCR alternativo | **Tesseract** (`pytesseract`) | Si está instalado |
| PDFs complejos (fórmulas/tablas) | **Docling** | Opcional |

## Motor adaptativo

El script **analiza cada página y decide la vía** (no hay que elegir a mano):

1. Si la página tiene texto extraíble → **PyMuPDF** (rápido).
2. Si hay tablas → las extrae con `find_tables` y las vuelca en **Markdown**.
3. Si la página **no tiene texto** (escaneo) → **OCR** (RapidOCR; fallback Tesseract).
4. Si el PDF es muy complejo y **Docling** está instalado → se puede usar como vía de máxima calidad.

El JSON de salida registra **qué motor se usó en cada página** (auditable).

## Script principal

```bash
python modulos/documentos/scripts/leer_pdf.py --input documento.pdf
# -> documento.md  (Markdown estructurado, con tablas y figuras)
# -> documento.json (metadatos, motores por página, tablas, imágenes)
# -> imagenes/pN_imgM.png (figuras extraídas)

# Opciones
--salida CARPETA     Carpeta de salida (por defecto, junto al PDF)
--ocr auto|si|no     Forzar o desactivar OCR (por defecto auto)
--idioma spa|eng     Idioma del OCR
--paginas 1-5        Procesar solo un rango
--sin-imagenes       No extraer figuras
--umbral N           Caracteres mínimos por página para no usar OCR
```

## Búsqueda y resumen (ahorro de tokens)

```bash
# Devuelve SOLO los fragmentos relevantes (BM25) con su pagina
python modulos/documentos/scripts/buscar_pdf.py --input doc.pdf -q "flujos de potencia" -k 3

# Resumen extractivo local (sin usar el modelo de IA)
python modulos/documentos/scripts/resumir_pdf.py --input doc.pdf --max 10 --salida resumen.md
```

- `buscar_pdf.py` reutiliza la extracción previa (`.json`) o la genera si no existe.
- `resumir_pdf.py` ordena las ideas por relevancia y las devuelve en orden original.
- **Caché por hash**: `leer_pdf.py` no reprocesa un PDF que ya extrajo (usar `--forzar` para repetir).

## Salida pensada para gastar pocos tokens

- **Markdown limpio** con encabezados detectados por tamaño de fuente.
- **Tablas en Markdown** (alto valor por token).
- **JSON** con secciones, tablas y figuras → el modelo pide solo lo que necesita.
- El sistema **no vuelca el PDF completo** al contexto: primero lee el índice/JSON,
  luego las secciones o páginas concretas.

## Flujo recomendado

1. Ejecutar `leer_pdf.py` sobre el PDF.
2. Revisar el `.json` (índice: páginas, motores, tablas).
3. Leer del `.md` solo las secciones relevantes (o usar `--paginas`).
4. Entregar el contenido al módulo que lo necesite (literatura, ciencias, etc.).

## Notas

- Si el PDF es escaneado y el OCR falla, probar `--idioma` correcto o instalar Tesseract.
- PyMuPDF es **AGPL**; para distribución pública considerar `pypdfium2`/`pdfplumber`.
- Para PDFs académicos con fórmulas, instalar Docling (`pip install docling`).

## Sincronización con OpenCode

Copia versionada de la skill global:

```
~/.config/opencode/skills/documentos/SKILL.md
```

Sincronizar con: `python sincronizar_skills.py`
