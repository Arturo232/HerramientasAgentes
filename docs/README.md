# HerramientasAgente — Suite Académica Modular

Backend académico automatizado para la elaboración de trabajos universitarios: ensayos e informes en **Normas APA 7.ª edición**, presentaciones e infografías con plantillas PPTX, y módulos especializados por facultades (Literatura, Matemáticas, Biología/Ciencias, Programación/Tecnología y Artes/Diseño).

El sistema se organiza alrededor de un **Orquestador Maestro** ("Decano") que recibe la petición del usuario y la delega al módulo especializado correspondiente.

## El Orquestador Maestro

El usuario solo interactúa con el Orquestador (skill `orquestador-maestro`). Este analiza la petición y enruta al módulo adecuado:

| Petición | Módulo | Skill |
|---|---|---|
| Ensayo, resumen o texto formal | `literatura` | `ensayo_apa.md` |
| Infografía, diapositivas o visual | `artes_diseno` | `director_creativo.md` |
| Problemas numéricos o estadística | `matematicas` | `analista_logico.md` |
| Fenómenos naturales, ecosistemas, cuerpo humano | `biologia_y_ciencias` | `investigador_cientifico.md` |
| Código, scripts, ayuda con Arch Linux | `programacion_y_tech` | `ingeniero_software.md` |

## Estructura del repositorio

```
HerramientasAgente/
├── .gitignore
├── docs/
│   └── README.md                     # Esta guía
├── skills/
│   └── orquestador_maestro.md        # Decano: enrutador central del sistema
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
mkdir -p ~/.config/opencode/skills/{ensayo-apa,director-creativo,analista-logico,investigador-cientifico,ingeniero-software,orquestador-maestro}
cp modulos/literatura/skills/ensayo_apa.md ~/.config/opencode/skills/ensayo-apa/SKILL.md
cp modulos/artes_diseno/skills/director_creativo.md ~/.config/opencode/skills/director-creativo/SKILL.md
cp modulos/matematicas/skills/analista_logico.md ~/.config/opencode/skills/analista-logico/SKILL.md
cp modulos/biologia_y_ciencias/skills/investigador_cientifico.md ~/.config/opencode/skills/investigador-cientifico/SKILL.md
cp modulos/programacion_y_tech/skills/ingeniero_software.md ~/.config/opencode/skills/ingeniero-software/SKILL.md
cp skills/orquestador_maestro.md ~/.config/opencode/skills/orquestador-maestro/SKILL.md
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

## Skills globales de OpenCode

Todas las skills están registradas globalmente para estar disponibles en cualquier terminal:

```
~/.config/opencode/skills/orquestador-maestro/SKILL.md   # Decano (punto de entrada)
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