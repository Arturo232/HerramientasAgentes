# HerramientasAgente

Backend académico automatizado para la elaboración de trabajos universitarios bajo el estándar de **Normas APA 7.ª edición** (ensayos, informes, proyectos y presentaciones).

Este repositorio convierte un borrador escrito en **Markdown** (`borrador.md`) en un documento final **.docx** (compatible con Google Docs) y opcionalmente **.pdf**, aplicando automáticamente todos los estilos APA 7 (portada institucional, márgenes, tipografía, interlineado, sangrías, paginación y referencias).

## Estructura del repositorio

```
HerramientasAgente/
├── .gitignore
├── docs/
│   └── README.md              # Esta guía
├── skills/
│   ├── SKILL.md               # Instrucciones del agente redactor (ensayos APA 7)
│   └── presentador.md         # Instrucciones del agente de presentaciones/infografías
├── scripts/
│   ├── generar_documento_apa.py   # Compilador Markdown → .docx / .pdf
│   └── generar_pptx.py            # Inyección de texto en plantillas PPTX → .pptx / .pdf
├── plantillas/
│   ├── apa_base.docx               # Plantilla base con estilos APA 7 (regenerable)
│   └── pptx/                       # Plantillas PPTX del usuario (con etiquetas {{LLAVE}})
└── requirements.txt       # Dependencias de Python
```

## Requisitos del sistema

- **Python 3.10+** con `venv` y `pip`
- **LibreOffice** (opcional, para generar el `.pdf` de ensayos y presentaciones)
- Fuente Times New Roman (o Liberation Serif, métricamente idéntica)

## Instalación en otra máquina

```bash
git clone <ruta-o-url-del-repositorio> HerramientasAgente
cd HerramientasAgente
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

> Nota: el entorno virtual `.venv/` no se versiona; debe recrearse en cada máquina.

## Uso del compilador

Se admiten dos formas equivalentes: la posicional o las opciones `--input`/`--output`.

```bash
# Generar solo el .docx (forma posicional)
.venv/bin/python scripts/generar_documento_apa.py ruta/al/borrador.md

# Forma explícita con --input y --output
.venv/bin/python scripts/generar_documento_apa.py --input ruta/al/borrador.md --output salida/ensayo_final.docx

# Generar .docx y .pdf en la misma carpeta del borrador
.venv/bin/python scripts/generar_documento_apa.py ruta/al/borrador.md --pdf

# Estimar páginas del borrador (~250 palabras/página)
.venv/bin/python scripts/generar_documento_apa.py --input ruta/al/borrador.md --estimar

# Regenerar la plantilla base apa_base.docx
.venv/bin/python scripts/generar_documento_apa.py --plantilla
```

Sin `--output`, el `.docx` se guarda junto al borrador con el mismo nombre (`borrador.docx`). El `.pdf` se genera con LibreOffice en modo headless en la misma carpeta.

## Motor de plantillas PPTX (diapositivas e infografías)

Inyecta texto en una plantilla de PowerPoint (`.pptx`) a partir de un JSON de etiquetas y exporta el resultado a `.pdf`:

```bash
.venv/bin/python scripts/generar_pptx.py \
  --plantilla plantillas/pptx/plantilla_diapositivas.pptx \
  --input datos_presentacion.json \
  --salida presentacion_generada.pptx
```

### Cómo etiquetar una plantilla

1. En cada cuadro de texto que quieras reemplazar, escribe una etiqueta entre dobles llaves: `{{TITULO}}`, `{{SUBTITULO}}`, `{{TEXTO_1}}`, `{{CELDA_A}}`, etc.
2. Guarda la plantilla en `plantillas/pptx/`.
3. Crea `datos_presentacion.json` con los pares etiqueta → texto:

```json
{
  "{{TITULO}}": "El Sistema Financiero",
  "{{SUBTITULO}}": "Una visión desde Colombia",
  "{{TEXTO_1}}": "El Banco de la República controla la inflación...",
  "{{TEXTO_2}}": "La Superintendencia Financiera vigila el sistema."
}
```

El reemplazo respeta el formato original de cada cuadro (fuente, color, tamaño) y funciona en cuadros de texto, placeholders, tablas, grupos y notas del orador. El script advierte sobre etiquetas del JSON no usadas o etiquetas de la plantilla sin reemplazo.

Con `--no-pdf` se omite la conversión a PDF. La skill `skills/presentador.md` define el rol de creador de contenido, las reglas de redacción humanizada y las normas del JSON.

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

## Flujo de trabajo

1. El agente lee los insumos (PDF, notas, .txt) de la carpeta del trabajo.
2. Redacta el texto completo en `borrador.md` cubriendo la extensión requerida (~250 palabras por página) y aplicando las reglas de **refinamiento de estilo** de la skill (variabilidad sintáctica, ritmo natural, transiciones variadas y sin muletillas de IA). El borrador nace con estilo natural; no hay pasos intermedios de reescritura.
3. Compila con `generar_documento_apa.py` y entrega el `.docx` / `.pdf` final.

La skill `skills/SKILL.md` registra las reglas formales, los datos del estudiante y el protocolo de redacción.

## Skills globales de OpenCode

Las skills están además registradas globalmente en OpenCode para estar disponibles en cualquier terminal:

```
~/.config/opencode/skills/ensayo-apa/SKILL.md
~/.config/opencode/skills/presentador/SKILL.md
```

Son las mismas skills versionadas en `skills/SKILL.md` y `skills/presentador.md` de este repositorio. Al clonar el repo en otra máquina, para activarlas globalmente:

```bash
mkdir -p ~/.config/opencode/skills/ensayo-apa ~/.config/opencode/skills/presentador
cp skills/SKILL.md ~/.config/opencode/skills/ensayo-apa/SKILL.md
cp skills/presentador.md ~/.config/opencode/skills/presentador/SKILL.md
```

Tras copiarlas o modificarlas, reiniciar OpenCode para que se carguen.