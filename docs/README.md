# HerramientasAgente

Backend académico automatizado para la elaboración de trabajos universitarios bajo el estándar de **Normas APA 7.ª edición** (ensayos, informes, proyectos y presentaciones).

Este repositorio convierte un borrador escrito en **Markdown** (`borrador.md`) en un documento final **.docx** (compatible con Google Docs) y opcionalmente **.pdf**, aplicando automáticamente todos los estilos APA 7 (portada institucional, márgenes, tipografía, interlineado, sangrías, paginación y referencias).

## Estructura del repositorio

```
HerramientasAgente/
├── .gitignore
├── docs/
│   └── README.md          # Esta guía
├── skills/
│   └── SKILL.md            # Instrucciones persistentes del agente redactor
├── scripts/
│   └── generar_documento_apa.py  # Compilador Markdown → .docx / .pdf
├── plantillas/
│   └── apa_base.docx      # Plantilla base con estilos APA 7 (regenerable)
└── requirements.txt       # Dependencias de Python
```

## Requisitos del sistema

- **Python 3.10+** con `venv` y `pip`
- **LibreOffice** (opcional, solo para generar el `.pdf`)
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
2. Redacta el texto completo en `borrador.md` cubriendo la extensión requerida (~250 palabras por página).
3. Compila con `generar_documento_apa.py` y entrega el `.docx` / `.pdf` final.

La skill `skills/SKILL.md` registra las reglas formales, los datos del estudiante y el protocolo de redacción.

## Skill global de OpenCode

La skill está además registrada globalmente en OpenCode para que esté disponible en cualquier terminal:

```
~/.config/opencode/skills/ensayo-apa/SKILL.md
```

Es la misma skill versionada en `skills/SKILL.md` de este repositorio. Al clonar el repo en otra máquina, para activarla globalmente:

```bash
mkdir -p ~/.config/opencode/skills/ensayo-apa
cp skills/SKILL.md ~/.config/opencode/skills/ensayo-apa/SKILL.md
```

Tras copiarla o modificarla, reiniciar OpenCode para que la skill se cargue.