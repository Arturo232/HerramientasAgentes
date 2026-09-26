# Plan de Migración — HerramientasAgentes

> Ruta por fases desde el estado actual (ver `INVESTIGACION.md`) hacia la
> arquitectura objetivo (ver `ARQUITECTURA_OBJETIVO.md`).
>
> **Principio rector:** no romper nada, SPT intacto, cambios incrementales y un
> **módulo piloto** primero. Cada fase tiene criterios de aceptación medibles.

---

## Reglas de migración

1. Cada fase deja el sistema **funcionando** (nunca se rompe un módulo para "arreglarlo").
2. Primero se construyen los "dientes" (contrato/núcleo), después el "eje" (CLI/REPL).
3. El piloto es `documentos` (el más maduro y con tests).
4. Las skills de OpenCode se regeneran, nunca se editan a mano.
5. Los binarios, credenciales y sesiones **nunca** entran a git.

---

## Fase 0 — Git y sincronización (seguridad primero)

**Objetivo:** eliminar el riesgo de pérdida y el enredo de repos.

Tareas:
1. **Respaldar el trabajo local de `navegador-web`** que falta en el repo:
   copiar `playbooks/` (canva, moodle, sima, flujo_unidad), `recetas/` (canva.py,
   docx_util.py, mentefacto.py, diagrama_flujo.py, completar_h5p.py, drive_google.py,
   indice.json), scripts extra (sesion_cdp, moodle_api, sima_token, config, h5p_solver,
   batch_moodle, inventario_moodle, descargar_unidad, google_api) y `config.json` /
   `GOOGLE_OAUTH.md` / `PLAN_MEJORAS.md` al repo `modulos/navegacion_web/`.
2. **Ampliar `sincronizar_skills.py`** para que copie también `playbooks/`, `recetas/`,
   `config.json` y documentación auxiliar (hoy solo copia `skills/*.md` y `scripts/*.py`).
3. **Confirmar `.gitignore`**: binarios (`bin/`, `models/`), `.venv/`, `__pycache__/`,
   sesiones/tokens/cookies, perfiles `chrome-*`.
4. **Sacar `HerramientasAgentes` de dentro de `SEP-PY`** (que sean repos hermanos)
   **o**, si se prefiere no mover nada, documentarlo explícitamente como decisión.
   Recomendación: hermanos (`Documents/agentes/` y `Documents/spt/`).
5. Commit de todo lo anterior (Conventional Commits).

**Criterios de aceptación:**
- `git status` en `HerramientasAgentes` no muestra trabajo valioso sin versionar.
- `sincronizar_skills.py --dry-run` lista **todos** los archivos (incl. playbooks/recetas).
- La carpeta `~\.config\opencode\skills` se puede borrar y regenerar sin perder nada.

---

## Fase 1 — Núcleo + catálogo (los dientes)

**Objetivo:** crear `nucleo/` y `capacidades.json`; el CLI empieza a ser generado.

Tareas:
1. `nucleo/contrato.py` → `Resultado` (`ok, datos, meta, artefactos, error`) + helpers.
2. `nucleo/errores.py` → `AgenteError` con `agente:<modulo>:<codigo>`.
3. `nucleo/config.py` → catálogo de mensajes, rutas, carga de `capacidades.json`.
4. `nucleo/cli.py` → parser común (`--json/--quiet/--yes/--dry-run/--help`, exit codes 0/1/2).
5. `capacidades.json` → inventario de comandos (una entrada por comando actual).
6. Reescribir `agente.py` para **leer `capacidades.json`** (adiós dict `COMANDOS` hardcodeado)
   y añadir `lista`, `ayuda <cmd>` y `--json` global.

**Criterios de aceptación:**
- `agente lista` imprime los comandos **desde el catálogo**.
- `agente lista --json` emite el catálogo en JSON válido.
- `agente ayuda pdf` muestra flags; `agente ayuda pdf --json` da el esquema.
- Los comandos existentes siguen funcionando igual (sin regresión).

---

## Fase 2 — Piloto: `documentos`

**Objetivo:** demostrar el contrato de punta a punta en un módulo real.

Tareas:
1. Añadir `modulos/documentos/modulo.json` (manifiesto).
2. Añadir `modulos/documentos/servicio.py` (fachada que captura errores y arma `Resultado`).
3. Adaptar `leer_pdf.py`, `buscar_pdf.py`, `resumir_pdf.py` a:
   - `nucleo.cli` (banderas comunes), `--json` unificado, `stderr` para logs.
   - salida por contrato §3 (sin `sys.exit("mensaje")`).
4. `tests/test_contratos.py` → verifica que los tres scripts cumplen el contrato
   (mismo shape en éxito y en error; exit codes correctos).

**Criterios de aceptación:**
- `agente pdf tarea.pdf` (humano) y `agente pdf tarea.pdf --json` (máquina) funcionan.
- `agente pdf noexiste.pdf --json` devuelve `{"ok":false,"error":{"codigo":"agente:pdf:noExiste"}}` con exit 1.
- `python -m pytest` en verde (tests previos + de contrato).

---

## Fase 3 — Despliegue al resto de módulos

**Objetivo:** aplicar el patrón del piloto a los demás módulos, uno por uno.

Orden sugerido (de mayor a menor uso/riesgo):
1. `navegacion_web` (13 scripts + recetas; aprovechar Fase 0).
2. `literatura` (`generar_documento_apa.py`).
3. `artes_diseno` (`motor_pptx_visual.py`, `renderizador_playwright.py`).
4. `edicion_audio` (`procesar_audio.py`).
5. `edicion_video` (9 scripts + `comun.py`).

Por cada módulo: `modulo.json` + `servicio.py` + adaptar scripts + test de contrato.

**Criterios de aceptación:**
- Todos los comandos aparecen en `agente lista` vía catálogo.
- Todo módulo responde con el contrato en `--json` y errores tipados.
- Ningún script pide input por defecto ni imprime datos en `stderr`.

---

## Fase 4 — Interfaces (el eje)

**Objetivo:** el REPL y la composición.

Tareas:
1. `interfaces/repl.py` → consola `agente>` (mismo estilo verbos+args que la consola
   de SPT, pero sobre `capacidades.json`).
2. `agente run flujo.json` → ejecuta un pipeline declarativo consumiendo artefactos.
3. Soporte de `|`/`--stdin` entre comandos.

**Criterios de aceptación:**
- `agente` abre el REPL; `agente> pdf tarea.pdf` funciona.
- `agente run flujo.json` encadena `pdf → resumir → ensayo` sin intervención.
- `agente pdf tarea.pdf --json | agente resumir --stdin` funciona.

---

## Fase 5 — Calidad (el reloj se mantiene solo)

**Objetivo:** robustez y repetibilidad.

Tareas:
1. CI (GitHub Actions) que corra `pytest` + `mypy` en cada push.
2. `pyproject.toml` con entry points (`agente`) y dependencias reales.
3. Test de contrato **para todos los módulos** (no solo documentos).
4. `mypy` y cobertura mínima.

**Criterios de aceptación:**
- El CI pasa en verde.
- `pip install -e .` deja `agente` disponible en el PATH.
- Añadir un módulo nuevo = 1 cambio en `capacidades.json` + su script + su test; nada más.

---

## Mapa resumen

| Fase | Qué entrega | Riesgo | Orden |
|---|---|---|---|
| 0 | Git ordenado + sincronizador completo | evita pérdida de datos | primero |
| 1 | `nucleo/` + `capacidades.json` + CLI generado | bajo (aditivo) | segundo |
| 2 | Piloto `documentos` con contrato | bajo (aislado) | tercero |
| 3 | Resto de módulos | medio (muchos scripts) | cuarto |
| 4 | REPL + `run flujo.json` | bajo | quinto |
| 5 | CI + empaquetado + tipado | bajo | último |

## Qué ganas al final (desde la terminal)

```powershell
agente lista                    # catálogo
agente ayuda pdf --json         # esquema para IA
agente pdf tarea.pdf            # humano
agente pdf tarea.pdf --json     # máquina / pipe
agente run flujo.json           # pipeline
agente                          # REPL: agente> pdf tarea.pdf
agente pdf tarea.pdf --json | agente resumir --stdin   # composición Unix
```
