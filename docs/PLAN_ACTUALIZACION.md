# Plan de Actualización — HerramientasAgentes

> Documento de planificación. No ejecuta cambios: define qué vamos a construir.

## 1. Estado actual (git)

- **Repositorio:** `github.com/Arturo232/HerramientasAgentes` — rama `main`, último commit `579c1b3`.
- **Ruta local:** `Documents/SEP-PY/HerramientasAgentes/`
- **Cambios sin commitear:**
  - Modificados: `modulos/literatura/scripts/generar_documento_apa.py`, `plantillas/apa_base.docx`, `skills/orquestador_maestro.md`.
  - Sin seguimiento: `modulos/navegacion_web/`.
- **Estructura:** `modulos/<facultad>/{scripts,skills}` + `skills/orquestador_maestro.md` + `plantillas/` + `docs/` + `requirements.txt` + `.venv/` (no versionado).
- **Dependencias:** `requirements.txt` declara `python-docx, mistune, python-pptx, jinja2, playwright`. **Faltan declarar** (aunque están instaladas en `.venv`): `pymupdf`, `pillow`, `lxml`, `xlsxwriter`.
- **Desincronización importante:** los módulos nuevos **`editor-video` y `editor-audio`** (con ffmpeg completo, modelos whisper y scripts) viven **solo** en `~/.config/opencode/skills/`; **no están en el repositorio**.
- **Skills globales:** son **copias** de `modulos/*/skills/*.md`. Hoy la sincronización es manual (riesgo de divergencia).

## 2. Objetivo

1. **Módulo de lectura de PDF** que entienda **cualquier PDF** (texto, escaneados, imágenes, tablas, fórmulas), no solo texto plano.
2. **Reducir el trabajo del modelo de IA**: que los scripts extraigan, resuman e indexen, y que el modelo solo reciba lo mínimo necesario (**menos tokens**).

## 3. Módulo nuevo: `modulos/documentos/` (Lector de PDF)

### Herramientas propuestas

| Necesidad | Herramienta | Estado | Licencia |
|---|---|---|---|
| Texto, layout, tablas, imágenes, render de páginas | **PyMuPDF** | **ya instalado** (`pymupdf 1.28.2`) | AGPL-3.0 / comercial |
| OCR de escaneados (offline, sin binarios externos) | **RapidOCR** (ONNX) | descargar (~15 MB) | Apache-2.0 |
| OCR alternativo muy probado | **Tesseract** + `pytesseract` | descargar binario | Apache-2.0 |
| Altísima calidad en PDFs académicos (tablas + fórmulas → Markdown) | **Docling** (IBM) | opcional | MIT |
| Alternativa permisiva a PyMuPDF | `pypdfium2` / `pdfplumber` | opcional | Apache/BSD · MIT |

> Nota de licencia: PyMuPDF es **AGPL**. Si el repo se va a distribuir públicamente, conviene migrar a `pypdfium2`/`pdfplumber`. Para uso personal no hay problema.

### Motor adaptativo (elige la herramienta según el PDF)

El script **analiza cada PDF y decide la mejor vía**, escalando solo si hace falta
(primero lo ligero, y solo sube a modelos pesados cuando es necesario):

1. **Análisis previo:** densidad de texto por página, si hay texto extraíble, si hay
   imágenes a página completa (escaneo), si hay tablas, y heurísticas de fórmulas.
2. **Enrutado:**
   - Texto extraíble y simple → **PyMuPDF** (rápido).
   - Texto con tablas → **PyMuPDF `find_tables`** (y a **Docling** si son complejas).
   - Escaneado (sin texto, imagen a página completa) → **RapidOCR**; si falla o es
     muy sucio → **Tesseract**; si el layout es complejo → **Docling**.
   - Académico con fórmulas/tablas complejas → **Docling**.
3. **Escalado progresivo:** si la vía ligera produce poco texto o baja confianza,
   reintenta automáticamente con la siguiente herramienta.
4. **Registro de la decisión:** el JSON de salida indica qué motor se usó y por qué
   (auditable y reproducible).

### Scripts propuestos

1. `leer_pdf.py` — PDF → **Markdown estructurado** + `JSON` con: metadatos, nº de páginas, encabezados/secciones, tablas (en Markdown), figuras (extraídas a PNG), y texto por página.
2. `ocr_pdf.py` — detecta páginas sin texto y les aplica OCR (RapidOCR); reconstruye el texto.
3. `buscar_pdf.py` — búsqueda por relevancia (BM25 y/o embeddings) que devuelve **solo los fragmentos relevantes** con su página.
4. `indice_documentos.py` — indexa una carpeta de PDFs (RAG local) para consultas posteriores.

### Salida pensada para gastar pocos tokens

- Markdown limpio, tablas en Markdown y fórmulas en LaTeX (alto valor por token).
- **Índice de secciones** + "chunks" numerados → el agente pide *"dame la sección 3"* o *"busca X"* y recibe solo eso.
- Nunca se vuelca el PDF completo al contexto: primero índice, luego fragmentos.

## 4. Mejoras transversales (que el script haga más y el modelo menos)

1. **`core/` compartido**: un solo `comun.py` (detección de binarios, utilidades). Hoy `editor-video` y `editor-audio` duplican esa lógica.
2. **Caché por hash de archivo**: no re-extraer un PDF/imagen ya procesado (resultados en `.cache/`).
3. **Resumen extractivo local** (TextRank/algoritmo propio) antes de pasar texto al modelo.
4. **RAG local** sobre los documentos del usuario (embeddings con `sentence-transformers` o BM25 con `rank_bm25`) → respuestas con solo el contexto relevante.
5. **Plantillas/slots deterministas**: ensayos, PPTX e infografías con estructura fija que el modelo solo rellena.
6. **CLI unificado** `agente.py` con subcomandos por módulo (un solo punto de entrada).
7. **Validadores/tests** por módulo (`pytest`) para no depender del modelo para verificar.
8. **`sincronizar_skills.py`**: copia `modulos/*/skills/*.md` → `~/.config/opencode/skills/*/SKILL.md` automáticamente (adiós sincronización manual).
9. **Orquestador**: añadir enrutado a `documentos` (PDF) y a `edicion_video`/`edicion_audio`.
10. **Pre-procesado de imágenes** (Pillow): recorte, miniaturas y OCR de capturas.

## 5. Integración con git

1. **Commitear lo pendiente** (literatura, plantilla APA, orquestador, navegacion_web).
2. **Agregar al repo** los módulos `editor-video` y `editor-audio` → `modulos/edicion_video/` y `modulos/edicion_audio/` (scripts + skills). Excluir del repo los binarios pesados (`bin/ffmpeg.exe`, `models/*.bin`) con `.gitignore` y documentar su descarga.
3. **Actualizar `requirements.txt`** con las dependencias reales y las nuevas.
4. **Actualizar `docs/README.md`** y `skills/orquestador_maestro.md`.
5. **Convención de commits** (Conventional Commits) y quizá ramas por feature.

## 6. Roadmap por fases

| Fase | Contenido | Resultado |
|---|---|---|
| 0 | Limpieza git + `sincronizar_skills.py` | Repo ordenado y skills sincronizadas |
| 1 | `modulos/documentos/` con PyMuPDF + OCR | Leer cualquier PDF → Markdown |
| 2 | `buscar_pdf.py` + caché + resúmenes | Menos tokens por trabajo |
| 3 | `core/` compartido + CLI unificado + tests | Mantenimiento y robustez |
| 4 (opcional) | Docling para PDFs complejos | Calidad máxima en tablas/fórmulas |

## 7. Decisiones tomadas

- **PDF/OCR:** usar **todas** las herramientas con un **motor adaptativo** que elige
  la vía según lo que necesite cada PDF (PyMuPDF → RapidOCR/Tesseract → Docling).
- **Módulos `editor-video`/`editor-audio`:** **sí se agregan al repositorio** (scripts +
  skills), excluyendo binarios pesados (`bin/ffmpeg.exe`, `models/*.bin`) vía `.gitignore`.
- **Ejecución:** por ahora **solo el plan**; la Fase 0 se ejecuta después.
