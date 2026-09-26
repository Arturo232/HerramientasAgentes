# Plan de mejoras · Módulo Navegación Web (foco SIMA)

> Investigación hecha el 2026-09-14. Objetivo: automatizar más, gastar menos tokens
> y depender de scripts/APIs en lugar de clics.

## 1. Investigación (hallazgos verificados)

| Hallazgo | Evidencia | Impacto |
|---|---|---|
| **API REST de Moodle habilitada** | `/login/token.php?service=moodle_mobile_app` → `invalidlogin` (no `servicenotavailable`); `webservice/rest/server.php` → `invalidtoken` | Con credenciales se obtiene token y se usa la API (sin scraping) |
| Web service genérico por AJAX (`lib/ajax/service.php`) deshabilitado | devuelve `servicenotavailable` | Hay que usar REST con token, no el AJAX interno |
| **Infraestructura CDP ya existe** | `scripts/sesion_cdp.py`, `inventario_moodle.py`, `batch_moodle.py`, `h5p_solver.py`, `playbooks/moodle.md` | Reutilizar en vez de re-navegar |
| Herramientas locales | Python 3.14, node 24, Playwright (py), `python-docx`, `pypdf`, **Word** (COM para PDF) | Generar DOCX/PDF sin depender del navegador |
| No hay gcloud ni librerías de Google | sin `googleapiclient`, sin credenciales | Falta configurar OAuth para la API de Drive/Docs |
| Límite del cargador MCP | solo rutas dentro de `...\ingles` | Copiar a `.playwright-mcp\` y borrar |
| Plantillas sin estilo de lista | `styles.xml` sin `List Bullet`; `numbering.xml` vacío | Inyectar `abstractNum`/`num` (ya resuelto) |

## 2. Plan por fases

### Fase 0 · Base ✅
- [x] `config.json` del módulo: base SIMA, IDs de cursos, carpetas de Drive y rutas locales.
- [x] `scripts/config.py` (loader) y scripts que lo consumen (`moodle_api.py`, `descargar_unidad.py`, `google_api.py`).
- [x] `playbooks/sima.md` y enlace desde `playbooks/moodle.md`.

### Fase 1 · Acceso por API (mayor ahorro) ✅
- [x] `sima_token.py`: pide credenciales por **prompt local** (nunca por chat), obtiene el token
      (`/login/token.php`), lo guarda en `~/.config/opencode/navegacion/` (fuera de git).
- [x] `moodle_api.py`: cliente REST con el token (`site_info`, `cursos`, `contenidos`, `tareas`,
      `estructura`, `archivos`).
- [x] `estructura` integrada en `moodle_api.py`: **JSON cacheado** (1 h) con secciones, tareas,
      vencimientos y archivos. `moodle_estructura.py` separado ya no es necesario.

### Fase 2 · Descargas ✅
- [x] `descargar_unidad.py --curso N --unidad N`: baja módulos/adjuntos (vía API) y los organiza por unidad.
- [x] Subida a Drive por lotes: cubierta por `recetas/drive_google.py subir`.

### Fase 3 · Generación de documentos (parcial ✅)
- [x] `recetas/docx_util.py`: **viñetas/numeración reales** + relleno de plantilla + export PDF (Word COM).
- [x] `recetas/drive_google.py`: subir → **convertir a Google Doc** → compartir enlace.
- [~] `diligenciar_protocolo.py`: cubierto por `docx_util.py` (JSON + plantilla).

### Fase 4 · Diseño y contenido ✅
- [x] `recetas/mentefacto.py`: genera el mentefacto como HTML → **PDF/PNG** con Playwright (sin Canva).
- [x] Reutilizar `h5p_solver.py` / `batch_moodle.py` para las actividades H5P de Inglés y de SIMA.

### Fase 5 · APIs de Google (elimina fragilidad) ✅
- [x] Guía paso a paso: `GOOGLE_OAUTH.md`.
- [x] `scripts/google_api.py`: `auth`, `subir` (con `--convertir` a Google Doc), `compartir`, `listar`, `renombrar`, `materias`.
- [x] El usuario creó las credenciales y autorizó (`google_api.py auth`). **Drive/Docs por API operativo.**

## 3. Ahorro de tokens / menos clics
- Preferir **REST + JSON** y devolver **resúmenes**; nunca volcar HTML completo.
- **Cachear** estructura de cursos y plantillas en `~/.config/opencode/navegacion/`.
- **Encapsular** flujos multi-paso en un script (una sola invocación) en vez de muchos clics MCP.
- Usar el **calendario** de Moodle para vencimientos (evita abrir tarea por tarea).
- Estandarizar plantillas DOCX **con listas reales** para no corregir viñetas luego.

## 4. Riesgos y control
- **Credenciales:** solo prompt local + token en local, nunca en git ni por chat.
- **Entregas:** mantener humano en el bucle (no auto-enviar a SIMA).
- **Cambios de la plataforma:** los selectores pueden cambiar; por eso se prioriza la API.
- **Ética:** respetar TOS, pausas entre peticiones y uso académico/personal.

## 5. Orden de implementación sugerido
1. `moodle_api.py` + `sima_token.py` (habilitan todo lo demás).
2. `moodle_estructura.py` con caché.
3. `diligenciar_protocolo.py` + `docx_util.py`.
4. `google_doc.py` (API de Google si se configura OAuth).
5. `descargar_unidad.py` / `subir_drive.py`.
6. `mentefacto.py`.
