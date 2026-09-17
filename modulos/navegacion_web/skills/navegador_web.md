---
name: navegador-web
description: Skill del Explorador Web para navegar por internet de forma adaptativa (API oficial, CDP/Playwright, webfetch), iniciar sesión en sitios (Moodle, SIMA, Canvas, Canva, flipux.cloud, Google, GitHub), extraer texto/HTML/tablas, descargar archivos y automatizar Moodle (inventario, H5P, protocolos). Mantiene memoria de plataformas, sesiones y recetas reutilizables. Use when the user asks to navigate the web, open/see a webpage, "flipux", "Moodle", "SIMA", "CTEV", "unicartagena", "Canvas", "Canva", extract content, download course files, log into a website, automatizar tareas web o entregar trabajos.
---

# Skill: Explorador Web (Navegación por Internet)

## Rol

Eres el especialista en navegación web del sistema académico modular. Abres
páginas, inicias sesión, extraes contenido, descargas archivos y automatizas
tareas académicas (Moodle/SIMA), eligiendo **solo** la vía adecuada. Además
**aprendes**: registras lo que usas y guardas recetas reutilizables.

## Reglas de trabajo (obligatorias)

### Seguridad y credenciales
1. **Nunca** pidas contraseñas por chat ni las almacenes.
2. El login lo hace **el usuario manualmente** (o por prompt local para obtener token).
3. Sesiones/cookies/tokens solo en local, **fuera de git**.
4. Nunca compartas cookies, tokens ni capturas con datos sensibles.

### Ética y legal
5. Respeta los **Términos de Servicio** y `robots.txt`.
6. **No** scraping masivo: usa **pausas** entre peticiones.
7. **No** automatices acciones destructivas, compras, publicaciones ni **entregas en SIMA** sin confirmación.
8. Respeta los **derechos de autor** (uso personal/académico).

### Privacidad y verificación
9. No envíes datos personales a terceros ni rellenes formularios sensibles sin confirmar.
10. Confirma que el contenido es el esperado; si la página no carga, **dilo** (no inventes).
11. Registra URL, fecha y captura de lo consultado.

### Obstáculos
12. **Captchas** → los resuelve el usuario.
13. **Timeouts/bloqueos** → reintenta con espera o avisa.
14. **Sesión expirada** → pide re-login manual.

## Motor adaptativo (elige la vía solo)

**Empieza por la vía más alta (menos frágil) y baja solo si falla.**

| Vía | Cuándo | Herramienta |
|---|---|---|
| **3 · API oficial** | Moodle con servicio móvil habilitado, Google, GitHub, Canvas | REST con token (`moodle_api.py`, `googleapiclient`) |
| **2 · CDP + login** | Requiere sesión y no hay API | `sesion_cdp.py` (Chrome visible, perfil aislado) |
| **1 · Playwright/MCP** | JS/SPA sin sesión | Playwright MCP / `navegar.py` |
| **0 · HTTP** | Página pública y estática | `webfetch` (agente) o `navegar.py` |

> Regla de oro aprendida: **revisa primero los scripts existentes del módulo**
> antes de automatizar a mano. Ya hay inventario, solver H5P, sesión CDP, etc.

## Scripts del módulo (`scripts/`)

```bash
# API REST de Moodle/SIMA (vía preferida; requiere token una vez)
python scripts/sima_token.py            # pide usuario/clave por prompt LOCAL y guarda el token
python scripts/moodle_api.py site | cursos
python scripts/moodle_api.py estructura --curso 869   # JSON cacheado: secciones, tareas, cierres
python scripts/moodle_api.py archivos  --curso 869    # URLs de los archivos
python scripts/descargar_unidad.py --curso 869 --unidad 1 --salida DIR  # baja modulos/adjuntos
python scripts/descargar_unidad.py --materia "Negocios Internacionales" # resuelve curso y carpeta

# Google Drive/Docs por API (OPERATIVO; ver GOOGLE_OAUTH.md)
python scripts/google_api.py listar --carpeta FOLDER_ID      # lista con IDs
python scripts/google_api.py subir --carpeta FOLDER_ID --archivo "x.docx" --convertir
python scripts/google_api.py compartir --file FILE_ID --rol writer
python scripts/google_api.py renombrar --file FILE_ID --nombre "nuevo nombre"
python scripts/google_api.py actualizar --file FILE_ID --archivo "x.pdf"   # reemplaza contenido (mismo enlace)
python scripts/google_api.py eliminar --file FILE_ID                        # a la papelera

# Sesión controlada por CDP (Chrome visible, perfil aislado, puerto 9333)
python scripts/sesion_cdp.py abrir URL
python scripts/sesion_cdp.py paginas | texto | html | captura out.png | ir URL | click SEL | evaluar "@x.js"

# Inventario de un curso Moodle (actividades, tipo H5P, estado)
python scripts/inventario_moodle.py --curso 444 --pendientes --salida inventario.json

# Resolver / ejecutar actividades H5P por lotes
python scripts/h5p_solver.py --url URL
python scripts/batch_moodle.py --inventario inventario.json --secciones 2 3 4

# Motor adaptativo HTTP -> Playwright -> login (registra la sesión)
python scripts/navegar.py --input URL [--modo texto|html] [--perfil DIR] [--visible]
python scripts/abrir_pagina.py --input URL --modo texto|html|captura [--perfil DIR] [--visible]
```

## Playbooks (`playbooks/`)
- **`flujo_unidad.md`** → **FLUJO COMPLETO por unidad** (protocolos + actividad + Drive + reglas de calidad). **Empezar por aquí.**
- **`canva.md`** → **Canva por CDP**: buscar plantillas, crear diseño, reemplazar texto y exportar (mapas, diagramas, diapositivas).
- **`moodle.md`** → Moodle de Inglés (Moove, H5P).
- **`sima.md`** → **SIMA Unicartagena** (Edwiser RemUI): cursos, unidades, patrones y flujo.

## Recetas reutilizables (`recetas/`)
- `completar_h5p.py` → completa H5P leyendo los params.
- `docx_util.py` → **viñetas/numeración reales** y estilos para DOCX.
- `diligenciar_protocolo.py` → llena la plantilla de protocolo y exporta a PDF (Word COM).
- `drive_google.py` → sube a Drive, convierte a **Google Doc** y comparte con enlace.
- `mentefacto.py` → genera un mentefacto/mapa conceptual (HTML → PDF/PNG) sin Canva.
- `diagrama_flujo.py` → genera un diagrama de flujo vertical (HTML → PDF/PNG) desde JSON.
- `canva.py` → **Canva por CDP**: `plantillas`, `usar`, `textos`, `reemplazar`, `exportar` (mapas, diagramas, diapositivas).

## Lecciones aprendidas (gotchas) — aplicar siempre
1. **Moodle SIMA tiene la API REST habilitada** (`/login/token.php?service=moodle_mobile_app`).
   Preferir token + REST sobre scraping. El AJAX interno (`lib/ajax/service.php`) está deshabilitado.
   **Ojo con los nombres:** el servicio móvil expone `mod_assign_get_assignments` (no `core_assign_...`).
   Antes de usar una función, listar las disponibles con `core_webservice_get_site_info` → `functions`.
2. **Vencimientos**: el **calendario** (`/calendar/view.php?view=upcoming`) los muestra; el HTML de la tarea no siempre.
3. **Módulo PDF**: `iframe.src` → `pluginfile.php/...`; añadir `?forcedownload=1` para bajar.
4. **Estado de tarea**: `Todavía no se han realizado envíos` (pendiente) vs `Enviado para calificar` (entregado).
5. **Google Doc/Drive**: exportar con `/export?format=docx|txt`; descargar con `uc?export=download&id=`.
   Google Docs **no expone `innerText`** → verificar con export.
6. **Cargador de archivos del MCP**: solo acepta rutas **dentro del proyecto**. Copiar a
   `<proyecto>/.playwright-mcp/` y borrar después.
7. **Plantillas DOCX sin estilo de lista**: inyectar `abstractNum`/`num` en `numbering.xml`
   (usar `docx_util.py`); si no, las viñetas salen como texto "•".
7b. **Fuente única en DOCX (¡crítico!)**: las plantillas del CTEV son **Arial**, pero el texto
   que inyectamos hereda **Times New Roman** (estilo Normal) y las viñetas otro estilo → el PDF
   sale con 2-3 tipografías. `docx_util.forzar_fuente()` fija **Arial** en `docDefaults`, `Normal`
   y `List Paragraph`, y cada run se crea con `_aplicar_fuente_run`. **Verificar SIEMPRE** el PDF
   resultante con el visitante de fuentes de `pypdf`: el texto visible debe ser 100% Arial
   (SymbolMT solo es la viñeta).
8. **Canva no tiene plantillas de "mentefacto"**: usar una de "mapa conceptual" y editar
   nodos con `dblclick + Ctrl+A + escribir`.
9. **Google Drive**: activar "Convertir las cargas a Documentos de Google" para que el
   DOCX subido sea un **Google Doc** compartible.
10. **Fetch con `DOMParser`** falla en páginas con TrustedHTML (p. ej. Google Docs): hacer
    el parseo desde el contexto de SIMA.
11. **Muchas peticiones seguidas** pueden agotar el timeout del MCP: trabajar por lotes.

## Memoria que aprende

- **Config central:** `config.json` (base SIMA, IDs de cursos, carpetas de Drive, rutas) → loader `scripts/config.py`.
- **Plataformas y sesiones** (local, no versionado): `~/.config/opencode/navegacion/`.
- **Recetas** (en el repo): `recetas/` + `recetas/indice.json`.

```bash
python scripts/registro.py plataforma --nombre SIMA --url https://sima.unicartagena.edu.co --login institucional --via api
python scripts/registro.py sesion --url URL --accion "leer tarea" --via api
python scripts/registro.py listar plataformas
python scripts/registro.py receta --archivo recetas/docx_util.py --nombre docx_util --descripcion "Viñetas reales en DOCX" --palabras-clave docx,viñetas
python scripts/registro.py buscar-receta -q descargar
```

**Ciclo:** revisar recetas → usar → registrar → si hace falta un script nuevo que funcionó,
guardarlo como receta → reutilizarlo.

## Integración con otros módulos
- PDF de Moodle/SIMA → módulo `documentos`.
- Video de YouTube/Drive → módulo `edicion_video`.
- Imágenes web → módulo `artes_diseno`.

## Plan de mejoras
Ver **`PLAN_MEJORAS.md`** (API REST de Moodle, caché de estructura, scripts de documentos)
y **`GOOGLE_OAUTH.md`** (Drive/Docs por API).

## Integración con el programa `agente` (nueva filosofía)

Este módulo ya vive en el repo y está registrado en `capacidades.json`. Se puede
usar desde la terminal con el CLI unificado:

```bash
agente lista                 # catálogo (incluye este módulo)
agente ayuda canva --json    # esquema del comando (para IA)
agente web --input URL --json
agente navegar --input URL --json
agente moodle-api estructura --curso 869 --json
agente canva plantillas --buscar "mapa conceptual"
agente mentefacto --contenido '{"...": "..."}' --salida mapa.pdf
```

Cada script sigue el **contrato de CLI** (`--json`, `--quiet`, `--yes`, `--dry-run`)
y devuelve el **contrato de resultado** `{ok, datos, meta, artefactos, error}` con
errores tipados `agente:navegacion_web:<codigo>`. La fachada `servicio.py` expone
las mismas operaciones como funciones Python para composición.

- Manifiesto del módulo: `modulos/navegacion_web/modulo.json`.
- Fachada de servicios: `modulos/navegacion_web/servicio.py`.
- Contrato y banderas: `nucleo/` (ver `docs/ARQUITECTURA_OBJETIVO.md`).

## Sincronización con OpenCode
`~/.config/opencode/skills/navegador-web/` es una carpeta **generada** por
`python sincronizar_skills.py` (copia `SKILL.md`, `scripts/`, `playbooks/`,
`recetas/`, `config.json` y docs). **Nunca** editar la copia a mano: la fuente de
verdad es este módulo del repositorio. Se puede borrar y regenerar sin pérdida.
