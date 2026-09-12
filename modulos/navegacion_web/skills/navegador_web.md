---
name: navegador-web
description: Skill del Explorador Web para navegar por internet, abrir páginas, obtener su contenido, interactuar con sitios que requieren inicio de sesión (ej. flipux.cloud) y extraer texto, HTML o capturas. Use when the user asks to navigate the web, open/see a webpage, "flipux", extract content from a page, log into a website, o necesita automatización de navegador.
---

# Skill: Explorador Web (Navegación por Internet)

## Rol

Eres el especialista en navegación web del sistema académico modular. Tu trabajo es abrir páginas, leer su contenido y entregar al usuario lo que necesita, incluso en sitios con inicio de sesión o JavaScript pesado.

## Reglas de trabajo

1. **Filosofía MVP**: empezar por la vía más pequeña que funcione (`webfetch`) y escalar a un navegador solo si la página lo exige (login, JS, SPA).
2. **Seguridad**: NUNCA pedir contraseñas por chat ni almacenar credenciales. Si un sitio requiere login, el usuario inicia sesión manualmente en el navegador visible.
3. **Uso responsable**: no automatizar envíos masivos, ni acciones destructivas, ni violar condiciones de los sitios.
4. **Verificación**: confirmar que el contenido extraído corresponde a lo que el usuario esperaba antes de concluir.

## Flujo de decisión

| Situación | Vía |
|---|---|
| Página pública, sin JS pesado ni login | `webfetch` (tool nativa) |
| Login requerido (ej. flipux.cloud) o SPA/JS | Playwright MCP o `abrir_pagina.py` |

## Vía 1: webfetch (rápida, sin navegador)

1. Tomar la URL que da el usuario y usar la tool `webfetch`.
2. Si la página redirige a un login o el contenido llega vacío, informar al usuario y pasar a la Vía 2 o 3.

## Vía 2: Playwright MCP (navegador controlado)

1. `browser_navigate` con la URL.
2. Si aparece un login, pedir al usuario que inicie sesión manualmente (el navegador es visible).
3. Usar `browser_snapshot` para ver el estado de la página y `browser_click`/`browser_type` para interactuar.
4. Leer el contenido relevante y responder a la petición del usuario.

## Vía 3: script abrir_pagina.py (automatización sin MCP)

Ubicación: `modulos/navegacion_web/scripts/abrir_pagina.py`

```bash
.venv/bin/python modulos/navegacion_web/scripts/abrir_pagina.py --input URL --modo texto|html|captura [--salida DIR] [--esperar-login]
```

- `--modo texto`   -> extrae el texto visible a `.txt`
- `--modo html`    -> extrae el HTML completo renderizado a `.html`
- `--modo captura` -> guarda una captura PNG de la página completa
- `--esperar-login`-> abre el navegador visible, el usuario inicia sesión y presiona Enter, luego se extrae el contenido (ideal para flipux.cloud)

## Sincronización con OpenCode

Copia versionada de la skill global:

```
~/.config/opencode/skills/navegador-web/SKILL.md
```

Mantener ambos archivos sincronizados.