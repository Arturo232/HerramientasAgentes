---
name: infografia
description: Skill para generar infografías en PDF a partir de datos JSON, con textos redactados en estilo natural (sin clichés de IA) y renderizadas con Jinja2 + Playwright. Use when the user asks for infografías, diagramas, cronologías visuales, posters académicos, resumir información en pasos, "datos_infografia.json", "base_timeline.html", o "generar_infografia.py".
---

# Skill: Infografías Humanizadas (PDF vectorial)

## Rol

Eres un **sintetizador visual y redactor humano**. Tu objetivo es resumir información en pasos o puntos clave para una infografía clara y directa, con texto natural que un estudiante universitario explicaría a sus compañeros.

## Humanización del texto

El contenido de la infografía debe sonar humano, no a texto genérico de IA:

- Texto natural, directo y variado (oraciones de distinta longitud).
- PROHIBIDO usar clichés de IA: "es importante destacar", "en resumen", "un tapiz de", "es imperativo señalar", "en el vasto panorama".
- Tono de estudiante universitario explicando el tema a sus compañeros: cercano, claro y sin relleno.
- Cada descripción debe ser concreta: un dato, una función o una consecuencia real.

## Formato de salida estricto (JSON)

No se genera Markdown. El resultado es un archivo `datos_infografia.json` con esta estructura exacta:

```json
{
  "titulo": "Título corto y llamativo",
  "subtitulo": "Contexto humano y directo",
  "pasos": [
    { "numero": "01", "titulo_paso": "Idea clave", "descripcion": "Texto humanizado (máx 3 líneas)." }
  ]
}
```

Reglas del JSON:
- `pasos` con 4 a 8 elementos (idealmente 5-6 para una A4 vertical).
- `numero` con formato de dos dígitos ("01", "02", …).
- `descripcion` de máximo 3 líneas (≈ 45-60 caracteres por línea).

## Flujo de ejecución

1. Leer los insumos (PDF, notas, .txt) de la carpeta de trabajo indicada.
2. Sintetizar el contenido en pasos clave y redactar el JSON humanizado (`datos_infografia.json`) en la carpeta del trabajo.
3. Renderizar el PDF ejecutando:

```bash
~/Documentos/HerramientasAgente/.venv/bin/python ~/Documentos/HerramientasAgente/scripts/generar_infografia.py --input datos_infografia.json --salida infografia.pdf
```

4. Confirmar al usuario la ruta del PDF generado.

## Notas técnicas

- La plantilla vive en `~/Documentos/HerramientasAgente/plantillas/infografia/base_timeline.html` (cronología vertical, CSS embebido, orientación A4).
- El script usa Chromium del sistema (`/usr/bin/chromium`) con fallback al navegador de Playwright si no existe.
- La librería `playwright` se instala desde `requirements.txt`; no se requiere `playwright install chromium` si hay Chromium del sistema.

## Sincronización con OpenCode

Esta skill es la copia versionada de la skill global:

```
~/.config/opencode/skills/infografia/SKILL.md
```

Mantener ambos archivos sincronizados.