# Investigación — Estado actual y hallazgos

> Documento de diagnóstico. Describe **qué hay hoy**, qué está en git y qué no, y
> cuáles son los huecos antes de aplicar el rediseño. No propone cambios todavía
> (eso está en `ARQUITECTURA_OBJETIVO.md` y `PLAN_MIGRACION.md`).

---

## 1. Los repositorios

| Ruta | Repo git | Remoto | Rama | Estado |
|---|---|---|---|---|
| `Documents\SEP-PY` | sí | `Arturo232/SPT.git` | `main` | limpio; untracked: `.playwright-mcp/`, `HerramientasAgentes/`, `bavaria-model.png` |
| `Documents\SEP-PY\HerramientasAgentes` | sí (anidado) | `Arturo232/HerramientasAgentes.git` | `main` | limpio; **47 archivos** versionados |
| `Documents\SEP` | sí | **ninguno** | `master` | untracked: `Calculadora_CA/` |
| `~\.config\opencode\` | **no** | — | — | solo un `.gitignore` huérfano |

### Problema de estructura detectado

`HerramientasAgentes` vive **dentro** de `SEP-PY`. Por eso el repo padre (`SPT`) lo
muestra como "untracked" (es un repo anidado, un *gitlink*): Git no lo sigue, no
sube su contenido, y es fácil olvidarlo. Lo correcto es que sean **repos hermanos**,
no uno dentro del otro. Ver `PLAN_MIGRACION.md` → Fase 0.

---

## 2. Inventario de módulos

Fuente de verdad: `modulos/<facultad>/`. Las skills globales de OpenCode
(`~\.config\opencode\skills\<nombre>\`) son **copias** generadas por
`sincronizar_skills.py`.

| Módulo (repo) | Skill | Scripts versionados | Estado |
|---|---|---|---|
| `literatura` | `ensayo_apa.md` | `generar_documento_apa.py` | completo |
| `artes_diseno` | `director_creativo.md` | `motor_pptx_visual.py`, `renderizador_playwright.py` | completo |
| `documentos` | `documentos.md` | `leer_pdf.py`, `buscar_pdf.py`, `resumir_pdf.py` | completo |
| `edicion_video` | `editor_video.md` | `comun.py` + 9 scripts | completo |
| `edicion_audio` | `editor_audio.md` | `procesar_audio.py` | completo |
| `navegacion_web` | `navegador_web.md` | `abrir_pagina.py`, `navegar.py`, `registro.py` | **desincronizado** (ver §4) |
| `matematicas` | `analista_logico.md` | — (solo `README.md`) | **vacío** |
| `biologia_y_ciencias` | `investigador_cientifico.md` | — (solo `README.md`) | **vacío** |
| `programacion_y_tech` | `ingeniero_software.md` | — (solo `README.md`) | **vacío** |

`skills/orquestador_maestro.md` es la skill raíz (el "Decano").

---

## 3. El CLI actual (`agente.py`)

Un solo punto de entrada que **despacha por subproceso**:

```python
COMANDOS = {
    "pdf": ("modulos/documentos/scripts/leer_pdf.py", ...),
    "video": ("modulos/edicion_video/scripts/editar_video.py", ...),
    ...
}
# hace: subprocess.call([sys.executable, script] + args)
```

Qué **sí** hace bien:
- Una entrada única (`python agente.py <comando> ...`).
- Delega en los scripts de cada módulo.

Qué **falta**:
- No hay **REPL** (consola interactiva tipo `agente>`).
- No hay **contrato** de salida: pasa los args crudos y muestra lo que el script imprima.
- No hay `--json` unificado, ni `lista`, ni `ayuda` generada.
- El **enrutado está triplicado**: en `agente.py` (`COMANDOS`), en `skills/orquestador_maestro.md` (prosa) y en `docs/README.md` (tabla). Tres fuentes que se desincronizan.
- No permite **componer** módulos (pipeline).
- No hay exit codes estandarizados: cada script hace `sys.exit(...)` con su propio criterio.

---

## 4. Convenciones actuales de los scripts

Auditoría de `modulos/*/scripts/*.py`:

| Aspecto | Estado |
|---|---|
| `argparse` con flags `--input/--output` | **sí**, en casi todos |
| Salida `--json` | **parcial**: `buscar_pdf.py`, `inspeccionar_media.py`, `registro.py` |
| Exit codes (0/1/2) | **inconsistente**: varios hacen `sys.exit("mensaje")` (exit 1 + texto en stderr) |
| `stderr` para logs / `stdout` para datos | no está garantizado |
| Contrato único de resultado `{ok, datos, meta, artefactos, error}` | **no existe** |
| Errores tipados `agente:<modulo>:<codigo>` | **no existe** (solo excepciones y `sys.exit`) |
| Lectura desde `stdin` (`-`) | **no existe** |
| `--dry-run` / `--yes` para acciones destructivas | **no existe** |

Conclusión: los scripts ya usan `argparse`, que es la base correcta, pero **no
hablan un idioma común**. Esto impide encadenarlos con `|` y complica que una IA
los llame con confianza.

---

## 5. Deriva entre el repo y las skills locales (el hallazgo más importante)

`sincronizar_skills.py` solo copia `skills/*.md` → `SKILL.md` y `scripts/*.py` →
`scripts/`. **No copia** `playbooks/`, `recetas/`, `config.json` ni documentación
auxiliar.

Consecuencia: el módulo `navegacion_web` evolucionó **solo en local** y está
**muy por delante del repo**.

| | Repo (`modulos/navegacion_web/`) | Local (`~\.config\opencode\skills\navegador-web/`) |
|---|---|---|
| Playbooks | solo `README.md` | `canva.md`, `moodle.md`, `sima.md`, `flujo_unidad.md` |
| Recetas | solo `README.md` | `canva.py`, `docx_util.py`, `mentefacto.py`, `diagrama_flujo.py`, `completar_h5p.py`, `drive_google.py`, `indice.json` |
| Scripts | 3 | **13**: añade `sesion_cdp.py`, `moodle_api.py`, `sima_token.py`, `config.py`, `h5p_solver.py`, `batch_moodle.py`, `inventario_moodle.py`, `descargar_unidad.py`, `google_api.py` |
| Config | — | `config.json`, `GOOGLE_OAUTH.md`, `PLAN_MEJORAS.md` |

**Riesgo:** todo el trabajo de Canva / Moodle / SIMA / H5P / Drive existe **solo**
en `~\.config\opencode\skills\navegador-web\`. Si se pierde esa carpeta, no se
recupera del repo.

Otros archivos **solo locales** (correctamente excluidos por `.gitignore`):
`editor-video\bin\ffmpeg.exe`, `ffprobe.exe`, `models\ggml-*.bin` (binarios pesados).

---

## 6. Pruebas y calidad

| Aspecto | Estado |
|---|---|
| Tests | solo `tests/test_documentos.py` (4 casos, `unittest`) |
| CI | **no hay** (`SEP-PY` sí tiene `.github/workflows/ci.yml`) |
| Empaquetado | **no hay** (`requirements.txt` + `.venv` manual; sin `pyproject.toml`) |
| Tipado | **no hay** mypy |
| Cobertura | no medida |
| Test de contratos | **no existe** |

---

## 7. Referencia: lo que SPT ya hace (y los agentes no)

SPT (`Documents\SEP-PY`) es un proyecto **independiente** y no se mezcla. Se usa
solo como **patrón** de diseño, no como dependencia:

1. **Capas**: `core → modules → services → interfaces` (CLI, REPL, GUI).
2. **Contrato de datos** formal (`docs/contratos.md`, bloque `.meta`).
3. **Errores tipados** `analizador:<modulo>:<codigo>` con catálogo en `config.py`.
4. **Fachada de servicios** que nunca lanza al usuario: captura y devuelve error estructurado.
5. **Dominio puro** (sin `print`/`input` en `core`/`modules`).
6. **Una sola lógica, varias interfaces** sobre el mismo backend.
7. **Una tabla** (`main.py`, `_OPCIONES`) que maneja el menú → patrón a replicar como `capacidades.json`.
8. Tests (~150), CI, mypy, `pyproject.toml` con entry points.

---

## 8. Hallazgos clave (resumen)

1. **Enrutado triplicado** (skill, `agente.py`, `README`) → fuente de verdad única pendiente.
2. **Sin contrato común** entre scripts → no hay composición ni uso fiable por IA.
3. **Sin errores tipados** → tracebacks en vez de `agente:<modulo>:<codigo>`.
4. **Sin `--json` unificado ni exit codes** → no encadenable con `|`.
5. **Sin REPL ni composición** (`run flujo.json`).
6. **3 módulos vacíos** (`matematicas`, `biologia_y_ciencias`, `programacion_y_tech`).
7. **Deriva grave** en `navegacion_web` (trabajo solo en local, sin backup).
8. **Estructura de git enredada** (`HerramientasAgentes` anidado en `SEP-PY`).
9. **Sin CI / empaquetado / mypy** y casi sin tests.
10. **Sincronizador incompleto** (no copia `playbooks/`, `recetas/`, `config.json`).
