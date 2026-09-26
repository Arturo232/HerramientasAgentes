# HerramientasAgente — Suite Académica Modular

Backend académico automatizado para la elaboración de trabajos universitarios: ensayos e informes en **Normas APA 7.ª edición**, presentaciones e infografías con plantillas PPTX, y módulos especializados por facultades (Literatura, Matemáticas, Biología/Ciencias, Programación/Tecnología y Artes/Diseño).

El sistema se organiza alrededor de un **Orquestador Maestro** ("Decano") que recibe la petición del usuario y la delega al módulo especializado correspondiente.

## Documentación de arquitectura y plan

| Documento | Contenido |
|---|---|
| [`INVESTIGACION.md`](INVESTIGACION.md) | Estado actual: repos, inventario de módulos, deriva local vs repo y hallazgos |
| [`ARQUITECTURA_OBJETIVO.md`](ARQUITECTURA_OBJETIVO.md) | Diseño de destino: capas, contrato, CLI ABI, errores y accesibilidad para IA |
| [`PLAN_MIGRACION.md`](PLAN_MIGRACION.md) | Ruta por fases (0–5) con criterios de aceptación para llegar al objetivo |
| [`ESTADO_IMPLEMENTACION.md`](ESTADO_IMPLEMENTACION.md) | Qué ya se ejecutó, cómo verificarlo y qué falta |
| [`COMO_AGREGAR_SCRIPTS.md`](COMO_AGREGAR_SCRIPTS.md) | Cómo convertir un script nuevo en programa del sistema |

## El Orquestador Maestro

El usuario solo interactúa con el Orquestador (skill `orquestador-maestro`). Este analiza la petición y enruta al módulo adecuado:

| Petición | Módulo | Skill |
|---|---|---|
| Ensayo, resumen o texto formal | `literatura` | `ensayo_apa.md` |
| Infografía, diapositivas o visual | `artes_diseno` | `director_creativo.md` |
| Problemas numéricos o estadística | `matematicas` | `analista_logico.md` |
| Fenómenos naturales, ecosistemas, cuerpo humano | `biologia_y_ciencias` | `investigador_cientifico.md` |
| Código, scripts, ayuda con Arch Linux | `programacion_y_tech` | `ingeniero_software.md` |
| Navegar web, abrir páginas, login | `navegacion_web` | `navegador_web.md` |
| Editar video (cortes, transiciones, subtítulos) | `edicion_video` | `editor_video.md` |
| Mejorar audio, quitar ruido, mezclar música | `edicion_audio` | `editor_audio.md` |
| Leer/entender cualquier PDF (texto, tablas, OCR) | `documentos` | `documentos.md` |

## CLI unificado

Un solo punto de entrada para todos los módulos:

```bash
.venv/bin/python agente.py                 # lista los comandos
.venv/bin/python agente.py pdf --input documento.pdf
.venv/bin/python agente.py pdf-buscar --input doc.pdf -q "flujo de potencia"
.venv/bin/python agente.py pdf-resumir --input doc.pdf
.venv/bin/python agente.py video editar --plan plan.json
.venv/bin/python agente.py audio mejorar --input video.mp4
.venv/bin/python agente.py sync            # sincroniza las skills con OpenCode
```

## Módulo de Documentos: lector de PDF adaptativo

Lee **cualquier PDF** (texto, tablas, escaneado) eligiendo la herramienta según
la página: PyMuPDF para texto/tablas, RapidOCR (fallback Tesseract) para
escaneados y, opcionalmente, Docling para PDFs complejos. Genera Markdown + JSON
con secciones, tablas y figuras, con **caché por hash**.

```bash
.venv/bin/python modulos/documentos/scripts/leer_pdf.py --input doc.pdf
.venv/bin/python modulos/documentos/scripts/buscar_pdf.py --input doc.pdf -q "consulta" -k 5
.venv/bin/python modulos/documentos/scripts/resumir_pdf.py --input doc.pdf --max 10
```

## Sincronización de skills

`modulos/*/skills/*.md` y `skills/*.md` son la fuente; las copias globales de
OpenCode se generan con:

```bash
.venv/bin/python sincronizar_skills.py
```

## Pruebas

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## Estructura del repositorio

```
HerramientasAgente/
├── .gitignore
├── docs/
│   └── README.md                     # Esta guía
├── skills/
│   ├── orquestador_maestro.md        # Decano: enrutador central del sistema
│   └── comunes/
│       └── agente_local_wrapper.md   # Ejecutor local ultraligero sub-2B
├── scripts/
│   ├── agente_local/                 # Wrapper CLI `ha` (config.json, manifiestos.json, wrapper.py, ha.sh)
│   ├── orquestador/selector_herramientas.py
│   ├── redes/diagnosticar_red.py     # Diagnóstico y reconexión de red
│   ├── datos/generar_excel.py        # Reportes Excel profesionales
│   └── sistema/mantenimiento_pc.py   # Monitoreo y limpieza del sistema
├── modulos/
│   ├── literatura/
│   │   ├── skills/ensayo_apa.md      # Redactor Académico APA 7
│   │   └── scripts/generar_documento_apa.py   # Compilador Markdown → .docx / .pdf
│   ├── matematicas/
│   │   ├── skills/analista_logico.md # Ecuaciones, cálculo y estadística
│   │   └── scripts/                  # (por definir)
│   ├── biologia_y_ciencias/
│   │   ├── skills/investigador_cientifico.md  # Método científico y ecosistemas
│   │   └── scripts/                  # (por definir)
│   ├── programacion_y_tech/
│   │   ├── skills/ingeniero_software.md  # Python, bash de Arch, arquitectura
│   │   └── scripts/                  # (por definir)
│   └── artes_diseno/
│       ├── skills/director_creativo.md      # Director Creativo (fotografía + JS)
│       ├── scripts/motor_pptx_visual.py     # Inyección en plantillas PPTX (texto e imágenes)
│       ├── scripts/renderizador_playwright.py  # Render HTML → PDF A4 (CDN + JS)
│       ├── plantillas/pptx/                 # Plantillas PPTX con etiquetas {{LLAVE}}
│       └── plantillas/html/                 # Plantillas HTML base (Tailwind, Chart.js, Mermaid, Lucide)
├── plantillas/
│   └── apa_base.docx                 # Plantilla base APA 7 (regenerable)
└── requirements.txt                  # Dependencias de Python
```

## Requisitos del sistema

- **Python 3.10+** con `venv` y `pip`
- **LibreOffice** (opcional, para generar el `.pdf` de ensayos y presentaciones)
- Fuente Times New Roman (o Liberation Serif, métricamente idéntica)

## Instalación en otra máquina

```bash
git clone git@github.com:Arturo232/HerramientasAgentes.git HerramientasAgente
cd HerramientasAgente
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

> Nota: el entorno virtual `.venv/` no se versiona; debe recrearse en cada máquina.

Para activar las skills globales de OpenCode (ver sección final):

```bash
mkdir -p ~/.config/opencode/skills/{ensayo-apa,director-creativo,analista-logico,investigador-cientifico,ingeniero-software,orquestador-maestro,agente-local}
cp modulos/literatura/skills/ensayo_apa.md ~/.config/opencode/skills/ensayo-apa/SKILL.md
cp modulos/artes_diseno/skills/director_creativo.md ~/.config/opencode/skills/director-creativo/SKILL.md
cp modulos/matematicas/skills/analista_logico.md ~/.config/opencode/skills/analista-logico/SKILL.md
cp modulos/biologia_y_ciencias/skills/investigador_cientifico.md ~/.config/opencode/skills/investigador-cientifico/SKILL.md
cp modulos/programacion_y_tech/skills/ingeniero_software.md ~/.config/opencode/skills/ingeniero-software/SKILL.md
cp skills/orquestador_maestro.md ~/.config/opencode/skills/orquestador-maestro/SKILL.md
cp skills/comunes/agente_local_wrapper.md ~/.config/opencode/skills/agente-local/SKILL.md
```

## Módulo de Literatura: compilador APA 7

Se admiten dos formas equivalentes: la posicional o las opciones `--input`/`--output`.

```bash
# Generar solo el .docx (forma posicional)
.venv/bin/python modulos/literatura/scripts/generar_documento_apa.py ruta/al/borrador.md

# Forma explícita con --input y --output
.venv/bin/python modulos/literatura/scripts/generar_documento_apa.py --input ruta/al/borrador.md --output salida/ensayo_final.docx

# Generar .docx y .pdf en la misma carpeta del borrador
.venv/bin/python modulos/literatura/scripts/generar_documento_apa.py ruta/al/borrador.md --pdf

# Estimar páginas del borrador (~250 palabras/página)
.venv/bin/python modulos/literatura/scripts/generar_documento_apa.py --input ruta/al/borrador.md --estimar

# Regenerar la plantilla base apa_base.docx
.venv/bin/python modulos/literatura/scripts/generar_documento_apa.py --plantilla
```

Sin `--output`, el `.docx` se guarda junto al borrador con el mismo nombre (`borrador.docx`). El `.pdf` se genera con LibreOffice en modo headless en la misma carpeta.

### Formato del borrador (front-matter)

El borrador comienza con un bloque de metadatos, seguido del cuerpo en Markdown:

```markdown
---
titulo: Título del trabajo
curso: Nombre de la asignatura
docente: Nombre del profesor
fecha: 17 de agosto de 2026
---

## Introducción

Texto del párrafo con citas parentéticas (Apellido, año).

## Desarrollo

### Eje temático 1

...
```

Markdown soportado: encabezados (`#`/`##`/`###`), negrita, cursiva, listas ordenadas y no ordenadas, citas en bloque (con `>` para citas de 40+ palabras) y la sección final `## Referencias` (con sangría francesa automática).

## Módulo de Artes y Diseño: motor PPTX

Inyecta texto en una plantilla de PowerPoint (`.pptx`) a partir de un JSON de etiquetas y exporta el resultado a `.pdf`:

```bash
.venv/bin/python modulos/artes_diseno/scripts/motor_pptx_visual.py \
  --plantilla modulos/artes_diseno/plantillas/pptx/plantilla_finanzas_doodle.pptx \
  --input datos_diseno.json \
  --salida diseno_generado.pptx
```

### Cómo etiquetar una plantilla

1. En cada cuadro de texto que quieras reemplazar, escribe una etiqueta entre dobles llaves: `{{TITULO}}`, `{{SUBTITULO}}`, `{{TEXTO_1}}`, `{{CELDA_A}}`, etc.
2. Guarda la plantilla en `modulos/artes_diseno/plantillas/pptx/`.
3. Crea `datos_diseno.json` con los pares etiqueta → texto:

```json
{
  "{{TITULO}}": "El Sistema Financiero",
  "{{SUBTITULO}}": "Una visión desde Colombia",
  "{{TEXTO_1}}": "El Banco de la República controla la inflación...",
  "{{TEXTO_2}}": "La Superintendencia Financiera vigila el sistema."
}
```

El reemplazo **preserva exactamente el objeto font** de cada cuadro (nombre, tamaño, negrita, cursiva, color) y funciona en cuadros de texto, placeholders, tablas, grupos y notas del orador. También reemplaza imágenes: renombra la imagen de la plantilla como `{{IMAGEN_1}}` y pon su URL en el JSON. El script advierte sobre etiquetas del JSON no usadas o etiquetas de la plantilla sin reemplazo. Con `--no-pdf` se omite la conversión a PDF.

## Módulo de Artes y Diseño: renderizador HTML/Playwright

Renderiza un HTML local a PDF vectorial A4, esperando la carga completa de los CDN (Tailwind, Chart.js, Mermaid, Lucide) antes de imprimir:

```bash
.venv/bin/python modulos/artes_diseno/scripts/renderizador_playwright.py \
  --input infografia.html \
  --salida infografia.pdf
```

La plantilla de referencia `modulos/artes_diseno/plantillas/html/base_infografia.html` muestra el uso de los cuatro frameworks. El renderizador usa Chromium del sistema (fallback al de Playwright), espera `networkidle` más 1500 ms adicionales y exporta con `print_background=True`. Requiere conexión a internet para los CDN.

## Agente Local Ultraligero (sub-2B, ~1 GB RAM)

Para no bloquear la CPU por inferencia, un modelo local de Ollama sub-2B actúa
solo como **ejecutor de terminal determinista** (enrutar → ejecutar → reportar),
delegando cualquier tarea pesada al modelo Cloud vía el Orquestador Maestro.

### Instalar los modelos sub-2B (una sola vez)

```bash
ollama pull qwen2.5-coder:1.5b   # ~1.1 GB: ejecutor/enrutador
ollama pull llama3.2:1b          # ~1.3 GB: chat/fallback
```

### Wrapper CLI `ha`

El modelo local solo memoriza 6 comandos cortos con salida JSON
(`scripts/agente_local/ha.sh`):

```bash
ha listar
ha enrutar "tengo problemas de internet"
ha ejecutar "revisa los recursos de la pc"
ha estado
ha redirigir "hazme un ensayo de 10 paginas"   # → delega al Cloud
ha chat "hola"
```

El wrapper resuelve el intérprete del repositorio (`.venv/bin/python` si
existe) y reutiliza `scripts/orquestador/selector_herramientas.py` para el
enrutamiento determinista.

### Fallback / redirección

`ha redirigir "texto"` devuelve `"redireccion": true` con el módulo destino
(literatura, artes_diseno, matematicas, biologia_y_ciencias, programacion_y_tech)
cuando la petición excede la capacidad del modelo local; el modelo local jamás
intenta esas tareas.

### Gestión de dependencias por demanda (filosofía on-demand)

Ningún módulo o script permanece cargado de forma permanente. Cada herramienta
actúa como un servicio efímero: permanece **INACTIVA** hasta que una tarea
requiere su dependencia, momento en el que se **ACTIVA**, ejecuta y se
**AUTO-LIMPIA**.

- El manifiesto de dependencias vive en
  `scripts/agente_local/manifiestos.json` (librerías, plantillas y nivel de RAM
  por script y módulo). Las skills de módulo declaran además sus dependencias
  en el frontmatter YAML (`dependencias:`).
- `ha deps` muestra el estado de activación por demanda: qué script/módulo está
  `ACTIVABLE`, `SIN_SCRIPTS` o `FALTA_DEPENDENCIA`.
- `ha ejecutar` hace un **Cold Start Check** antes de lanzar el script (valida
  que las librerías del `.venv` y las plantillas existan) y se auto-limpia de
  procesos secundarios al terminar (p. ej. Playwright/Chromium headless).

```bash
ha deps                 # estado de activacion por demanda
ha ejecutar "genera un documento apa"   # cold start + auto-limpieza
```

## Skills globales de OpenCode

Todas las skills están registradas globalmente para estar disponibles en cualquier terminal:

```
~/.config/opencode/skills/orquestador-maestro/SKILL.md   # Decano (punto de entrada)
~/.config/opencode/skills/agente-local/SKILL.md          # Ejecutor local ultraligero
~/.config/opencode/skills/ensayo-apa/SKILL.md
~/.config/opencode/skills/director-creativo/SKILL.md
~/.config/opencode/skills/analista-logico/SKILL.md
~/.config/opencode/skills/investigador-cientifico/SKILL.md
~/.config/opencode/skills/ingeniero-software/SKILL.md
```

Tras copiarlas o modificarlas, reiniciar OpenCode para que se carguen.

## Flujo de trabajo

1. El usuario hace su petición al **Orquestador Maestro**.
2. El Orquestador identifica el módulo y delega a la skill especializada.
3. El especialista lee los insumos, redacta o resuelve y ejecuta los scripts de su módulo.
4. El entregable final (.docx, .pdf, .pptx) queda en la carpeta del trabajo.