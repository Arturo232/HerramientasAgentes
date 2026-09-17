# Estado de Implementación — Migración a la nueva filosofía

> Registro de lo ya ejecutado (Fases 0, 1 y arranque de la 3), cómo verificarlo y
> qué falta. Complementa `INVESTIGACION.md`, `ARQUITECTURA_OBJETIVO.md` y
> `PLAN_MIGRACION.md`.

---

## 1. Lo que ya está hecho

### Núcleo del sistema (`nucleo/`) — Fase 1
| Archivo | Contenido |
|---|---|
| `nucleo/contrato.py` | `Resultado` (`ok, datos, meta, artefactos, error`) + `Artefacto` + `exito()` / `fallo()` |
| `nucleo/errores.py` | `AgenteError` con identificador `agente:<modulo>:<codigo>` |
| `nucleo/config.py` | Rutas raíz y carga de `capacidades.json` |
| `nucleo/cli.py` | Banderas comunes (`--json/--quiet/--yes/--dry-run/--help`) y `correr()` con exit codes 0/1/2 |
| `nucleo/registro.py` | Hash de archivos, `artefacto()` y escritura de `manifest.json` |

### Catálogo único (`capacidades.json`) — Fase 1
Fuente de verdad del enrutado: **27 comandos**. Genera el CLI, la ayuda y el
esquema para IA. Añadir un comando = una entrada más.

### CLI unificado (`agente.py`) — Fase 1
Reescrito para **leer el catálogo** (ya no hay tabla hardcodeada). Nuevos modos:

```bash
python agente.py lista [--json]        # catálogo (humano o máquina)
python agente.py ayuda <cmd> [--json]  # ayuda / esquema para IA
python agente.py <cmd> ... [--json]    # ejecuta el módulo
```

### Módulo `navegacion_web` integrado — Fase 0 + Fase 3 (parcial)
- **Todo el contenido que estaba solo en `~/.config/opencode/skills/navegador-web`
  se copió al repo**: `playbooks/` (canva, moodle, sima, flujo_unidad), `recetas/`
  (canva, docx_util, mentefacto, diagrama_flujo, completar_h5p, drive_google,
  indice.json), `scripts/` extra (sesion_cdp, moodle_api, sima_token, config,
  h5p_solver, batch_moodle, inventario_moodle, descargar_unidad, google_api),
  `config.json`, `GOOGLE_OAUTH.md` y `PLAN_MEJORAS.md`.
- **Manifiesto** `modulos/navegacion_web/modulo.json`.
- **Fachada** `modulos/navegacion_web/servicio.py` (devuelve `Resultado`; import perezoso).
- **Scripts adaptados al contrato (todos)**: `navegar.py`, `abrir_pagina.py`,
  `registro.py`, `sima_token.py`, `moodle_api.py`, `inventario_moodle.py`,
  `descargar_unidad.py`, `sesion_cdp.py`, `google_api.py`, `h5p_solver.py`,
  `batch_moodle.py` y las recetas `canva.py`, `mentefacto.py`, `diagrama_flujo.py`,
  `docx_util.py`, `drive_google.py`, `completar_h5p.py`.
- **Skill actualizada** `modulos/navegacion_web/skills/navegador_web.md`.

### Módulo `documentos` integrado — Fase 2 (piloto)
- **Manifiesto** `modulos/documentos/modulo.json`.
- **Fachada** `modulos/documentos/servicio.py` (`leer`, `buscar`, `resumir` → `Resultado`).
- **Scripts adaptados al contrato**: `leer_pdf.py`, `buscar_pdf.py`, `resumir_pdf.py`
  (con `--json` unificado, errores tipados y artefactos con hash).

### Módulos `literatura`, `artes_diseno`, `edicion_audio` y `edicion_video`
Cada uno con `modulo.json` + `servicio.py` (fachada → `Resultado`) y sus scripts
adaptados al contrato:
- `literatura`: `generar_documento_apa.py` (`docx`/`pdf`, `--estimar`).
- `artes_diseno`: `renderizador_playwright.py`, `motor_pptx_visual.py`.
  **Bug corregido**: el renderizador solo buscaba Chrome en Linux; ahora también en Windows.
- `edicion_audio`: `procesar_audio.py` (`mejorar`/`mezclar`/`masterizar`/`produccion`).
- `edicion_video`: `editar_video.py` (`editar`/`extraer-audio`/`convertir`),
  `renderizar_moderno.py`, `subtitulos.py`.

### Interfaces y composición — Fase 4
- `interfaces/repl.py` → consola interactiva `agente>` (enruta por `capacidades.json`).
- `interfaces/flujo.py` → `agente run flujo.json` (pipeline declarativo; encadena
  artefactos con `{{ultimo}}`; se detiene en el primer paso que falle).
- `agente.py` reconoce `repl`, `consola`, `shell` y `run`.

### Empaquetado y calidad — Fase 5
- `pyproject.toml` (setuptools): dependencias, extras (`ocr`, `google`, `dev`),
  entry point **`agente`**, configuración de `mypy` y cobertura.
- `.github/workflows/ci.yml`: instala `.[dev]`, corre `unittest` y `mypy` en cada push/PR.
- `.gitignore` ampliado (build, dist, `*.egg-info`, caches).
- Verificado: `pip install -e . --no-deps` → comando `agente` disponible;
  `mypy nucleo interfaces agente.py` → **sin errores**.

### Acceso nativo para IA — servidor MCP
- `interfaces/mcp_servidor.py`: servidor **MCP sin dependencias** (JSON-RPC 2.0 por
  stdio) **generado desde `capacidades.json`**. Expone cada comando como herramienta
  tipada (JSON Schema con tipos, `enum` y campos requeridos) + escape hatch `args`.
- Registrado en `~/.config/opencode/opencode.jsonc` como MCP **`agente`**.
- Verificado: `initialize` OK · `tools/list` → **28 herramientas** ·
  `tools/call` (`registro`, `pdf-buscar`) → contrato correcto.
- Ventaja: la IA llama herramientas nativas (sin subproceso manual ni parseo),
  y añadir un módulo en `capacidades.json` lo publica también por MCP.

### Alta de scripts nuevos (extensible)
- `nucleo/catalogo.py`: alta/baja de comandos en `capacidades.json`.
- `interfaces/nuevo.py` y comandos `agente nuevo | integrar | quitar`:
  un script nuevo se guarda en el repo y se registra en el catálogo → aparece en
  CLI, ayuda, REPL y MCP (tras reiniciar) automáticamente.
- Guía: `docs/COMO_AGREGAR_SCRIPTS.md`.

### Sincronizador completo
`sincronizar_skills.py` ahora copia también `playbooks/`, `recetas/`, `config.json`
y docs del módulo. La carpeta `~/.config/opencode/skills` es **generada** y se puede
borrar/regenerar sin pérdida.

### Pruebas
`tests/test_contratos.py` verifica: forma del contrato, códigos de error, validez
del catálogo, existencia de todos los scripts, y que el CLI emite el contrato.
**Total: 11 tests en verde.**

---

## 2. Cómo verificarlo

```bash
.venv\Scripts\python agente.py lista --json
.venv\Scripts\python agente.py ayuda canva
.venv\Scripts\python agente.py registro listar plataformas --json
.venv\Scripts\python agente.py navegar --input https://example.com --json
.venv\Scripts\python -m unittest discover -s tests -v
.venv\Scripts\python sincronizar_skills.py --dry-run
```

Salida esperada del contrato (ejemplo real):

```json
{"ok": true, "datos": {"via": "http", "requiere_login": false},
 "meta": {"via": "http"}, "artefactos": [{"tipo": "texto", "ruta": "...", "hash": "..."}],
 "error": null}
```

---

## 3. Qué falta (siguiente)

1. **Fase 3 (interno de `edicion_video`)**: adaptar `generar_proyecto_mlt.py`,
   `renderizar_mlt.py`, `inspeccionar_media.py`, `mapear_tiempos.py`,
   `recortar_silencios.py`, `generar_subtitulos_karaoke.py` (hoy son librería
   interna que invocan los scripts principales; ya funcionan).
2. **Fase 0 (resuelta)**: se mantiene la ubicación actual (mover el repo rompería
   el `.venv` y la ruta del MCP registrada en `opencode.jsonc`). `SEP-PY/.gitignore`
   ya ignora el repo anidado. Commits: `ad52716` (agentes) y `105995a` (SPT).

---

## 4. Reglas que ya rigen

- Todo módulo devuelve el **contrato** y errores `agente:<modulo>:<codigo>`.
- Todo script acepta `--json`; datos a `stdout`, logs a `stderr`.
- El **enrutado** vive solo en `capacidades.json`.
- La carpeta de skills locales es **generada** (nunca editada a mano).
- **SPT no se toca**: es independiente y solo aportó el patrón de diseño.
