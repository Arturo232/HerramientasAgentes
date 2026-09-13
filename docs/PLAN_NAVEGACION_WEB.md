# Plan — Módulo de Navegación Web (v2)

> Módulo dedicado a todo lo relacionado con navegar por internet: directrices,
> reglas, playbooks por plataforma y **memoria que aprende** para automatizar más
> cada vez.

## 1. Estado actual

- Módulo `navegacion_web` con `scripts/abrir_pagina.py` y `skills/navegador_web.md`.
- **Playwright MCP** ya configurado en `~/.config/opencode/opencode.jsonc` con
  **perfil persistente** de Chrome (`chrome-flipux`).
- Playwright instalado en el `.venv`.
- Vías actuales: `webfetch` → Playwright MCP → `abrir_pagina.py`.

## 2. Objetivo

Un módulo completo de navegación que:

1. **Elija solo la vía** según la página (motor adaptativo, como el de PDF).
2. Tenga **directrices y reglas** claras (seguridad, ética, verificación).
3. Traiga **playbooks** de las plataformas que usas.
4. **Aprenda**: registre lo que se usa y guarde **recetas reutilizables** para
   automatizar más la próxima vez.

## 3. Motor adaptativo multi-vía (igual que el de PDF)

El módulo **analiza el objetivo y elige la vía** automáticamente, escalando si falla:

| Vía | Cuándo | Cómo decide |
|---|---|---|
| 0 · `webfetch` | Página pública, sin JS pesado | Primero, siempre |
| 1 · **Playwright MCP** | Login, SPA, JS, interacción | Si webfetch viene vacío o redirige a login |
| 2 · **Scripts** | Tareas repetibles, descargas | Si hay receta guardada o el usuario lo pide |
| 3 · **API oficial** | Canvas, GitHub, Wikimedia… | Si la plataforma ofrece API |

- **Escalado progresivo:** si una vía falla (timeout, bloqueo, vacío), prueba la siguiente.
- **Registro de la decisión:** cada sesión anota qué vía se usó y por qué (auditable).

## 4. Directrices y reglas (núcleo)

### Seguridad y credenciales
- **Nunca** pedir contraseñas por chat ni almacenarlas.
- El login lo hace **el usuario manualmente** en el navegador visible.
- Sesiones/cookies solo en local y **fuera de git**.
- Nunca compartir cookies, tokens ni capturas con datos sensibles.

### Ética y legal
- Respetar **Términos de Servicio** y `robots.txt`.
- **No** scraping masivo; usar **pausas** (rate limiting).
- **No** automatizar acciones destructivas, compras ni publicaciones.
- Respetar **derechos de autor** (uso personal/académico).

### Privacidad
- No enviar datos personales a terceros.
- No rellenar formularios con datos sensibles sin confirmación.

### Verificación y reproducibilidad
- Confirmar que el contenido es el esperado; **no inventar** si la página no carga.
- Registrar **URL, fecha y captura** de lo consultado.

### Obstáculos
- **Captchas** → los resuelve el usuario (no se automatizan).
- **Timeouts/bloqueos** → reintentar con espera o avisar.
- **Sesión expirada** → pedir re-login manual.

## 5. Playbooks por plataforma (las que usas)

| Plataforma | Login | Acciones comunes | Vía preferida |
|---|---|---|---|
| **Canvas (LMS)** | Institucional (SSO) | Cursos, tareas, notas, descargar archivos | API de Canvas si hay token |
| **Moodle** (`ingles.unicartagena.edu.co`) | Institucional | Leer tareas, subir enlace, descargar recursos | Playwright MCP |
| **Canva** | Cuenta propia | Editar/exportar diseños (PDF/PNG/PPTX) | Playwright MCP |
| **flipux.cloud** | Manual | Navegar, extraer contenido | Perfil `chrome-flipux` |
| **YouTube** | No requiere (ver) | Buscar, ver, extraer transcripciones | Script |
| **Google (Docs/Drive)** | Cuenta Google | Exportar a PDF/DOCX | Playwright MCP |
| **GitHub** | Token/SSH | Repos, issues, PR | API / `gh` |

## 6. Memoria de navegación (el módulo **aprende**)

El objetivo: que cada vez haga **más cosas con scripts** y menos a mano.

```
modulos/navegacion_web/
├── registro/
│   ├── plataformas.json     # catálogo de plataformas (url, login, playbook, última vez)
│   └── sesiones.jsonl       # bitácora: fecha, url, acción, vía, resultado
├── playbooks/
│   ├── canvas.md            # recetas paso a paso por plataforma
│   ├── moodle.md
│   ├── canva.md
│   └── ...
└── recetas/                 # scripts reutilizables que ya funcionaron
    └── descargar_archivos_curso.py
```

- **Registro de plataformas:** cada plataforma usada queda anotada (con su tipo de login y notas).
- **Bitácora de sesiones:** qué se hizo, con qué vía y si funcionó.
- **Recetas reutilizables:** cuando una tarea requiera pasos nuevos que funcionan,
  se **guardan como receta** (script + notas). La próxima vez se reutilizan y se
  automatiza más.
- **Ciclo de mejora:** usar → registrar → si hizo falta script, guardarlo → reutilizar.

## 7. Scripts propuestos

- `abrir_pagina.py` (mejorar): `--perfil`, `--esperar-selector`, `--cookies`, `--headless`.
- `sesion.py`: crear/borrar perfil, guardar/restaurar `storage_state`.
- `descargar.py`: descargar archivos enlazados (PDFs, imágenes) de una página.
- `extraer_tabla.py`: tablas HTML → Markdown/CSV.
- `buscar_web.py`: búsqueda simple y extracción de resultados.
- `playbook.py`: ejecutar recetas por plataforma.
- `captura.py`: capturas de página completa o de un elemento.
- `registro.py`: consultar/actualizar el catálogo de plataformas y la bitácora.
- `recetas/`: scripts reutilizables guardados.

## 8. Integración con otros módulos

- **Moodle/Canvas → PDF** → módulo `documentos` (leer, tablas, OCR).
- **YouTube/Drive → video** → módulo `edicion_video`.
- **Imágenes web** → módulo `artes_diseno`.
- **Tablas web** → datos para informes.

## 9. Almacenamiento y seguridad

- Perfiles y cookies en `~/.config/opencode/` (fuera del repo).
- Añadir a `.gitignore`: `**/chrome-*/`, `**/storage_state.json`, `**/cookies*.json`.
- El `registro/` y las `recetas/` **sí** se versionan (no contienen credenciales).

## 10. Roadmap

| Fase | Contenido | Resultado |
|---|---|---|
| 1 | Reglas + motor adaptativo + `registro.py` + mejorar `abrir_pagina.py` | Navegación guiada y registrada |
| 2 | `sesion.py` + `descargar.py` + `extraer_tabla.py` | Automatización y descargas |
| 3 | Playbooks Canvas / Moodle / Canva + primeras recetas | Flujos universitarios listos |
| 4 | Integración con `documentos` y `edicion_video` | Flujo web→trabajo completo |

## 11. Decisiones pendientes

- ¿El `registro/` y las `recetas/` se guardan en el repo (versionados) o en local?
- ¿Empezamos los playbooks por **Canvas y Moodle**?
