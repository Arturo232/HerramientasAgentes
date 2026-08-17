# Plantillas PPTX

Guarda aquí tus plantillas de PowerPoint para diapositivas e infografías.

## Cómo etiquetar una plantilla

1. Abre la plantilla en PowerPoint o Google Slides.
2. En el cuadro de texto que quieras reemplazar, escribe la etiqueta entre dobles llaves:
   - `{{TITULO}}`
   - `{{SUBTITULO}}`
   - `{{TEXTO_1}}`, `{{TEXTO_2}}`, `{{TEXTO_3}}`, ...
   - `{{CELDA_A}}`, `{{CELDA_B}}`, ... (dentro de tablas)
3. Guarda el archivo aquí (ej. `plantilla_diapositivas.pptx`, `plantilla_infografia_vertical.pptx`).
4. Crea un `datos_presentacion.json` con los pares etiqueta → texto y ejecuta:

```bash
.venv/bin/python ~/Documentos/HerramientasAgente/scripts/generar_pptx.py \
  --plantilla plantilla_diapositivas.pptx \
  --input datos_presentacion.json \
  --salida presentacion_generada.pptx
```

## Notas

- El reemplazo respeta el formato del cuadro original (fuente, color, tamaño).
- Las etiquetas funcionan en cuadros de texto, placeholders, tablas, grupos y notas del orador.
- Sin `--no-pdf`, el script convierte el resultado a PDF con LibreOffice en modo headless.