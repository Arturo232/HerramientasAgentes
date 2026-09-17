# Arquitectura Objetivo — HerramientasAgentes

> Diseño de destino. Define cómo debe quedar el sistema para que funcione
> **como un reloj**: cada pieza hace una cosa, todas comparten los mismos
> "dientes" (contrato) y un solo eje las mueve (el CLI/REPL).
>
> Este documento **no** toca SPT. SPT sigue siendo un proyecto independiente;
> aquí solo se reutilizan sus *patrones* de diseño.

---

## 1. Principios (filosofía Unix aplicada)

1. **Un programa, una tarea, bien hecha.** Cada script resuelve una cosa y la resuelve bien.
2. **Dientes iguales.** Todas las piezas devuelven el mismo contrato y usan los mismos flags.
3. **Un solo eje.** `agente` (CLI + REPL) es la única puerta; no calcula, enruta.
4. **Componible.** Entrada por args o `stdin`; salida a `stdout`; encadenable con `|`.
5. **Determinista y sin estado oculto.** Misma entrada → misma salida.
6. **Accesible para humanos e IA a la vez.** Un CLI bien hecho ya es la mejor interfaz para un modelo.
7. **Una sola fuente de verdad.** `capacidades.json` genera CLI, skill y esquema para IA.

---

## 2. Capas (copiadas de SPT como patrón)

```
+-------------------------------------------------------------+
|                    INTERFACES                               |
|   cli.py  (agente <comando> ...)                            |
|   repl.py (agente>  consola interactiva)                    |
|   skills/ (lo que invoca el agente LLM)                     |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                    SERVICIOS (fachadas)                     |
|   modulos/<x>/servicio.py  ->  contrato {ok,datos,...}      |
|   nunca lanzan al usuario; capturan y estructuran errores   |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                    MÓDULOS (dominio puro)                   |
|   modulos/<x>/scripts/*.py  (sin print/input, una tarea)    |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                    NÚCLEO                                   |
|   nucleo/contrato.py  errores.py  config.py  cli.py  registro.py |
+-------------------------------------------------------------+
```

Regla equivalente a la de SPT: **la lógica de dominio nunca imprime ni pide input**;
eso es de la capa de interfaces. Los scripts devuelven datos estructurados.

---

## 3. Contrato de resultado (los "dientes")

Todo servicio/script, en modo máquina (`--json`), emite **un solo objeto JSON** en `stdout`:

```json
{
  "ok": true,
  "datos": { "paginas": 12, "tablas": 3, "ocr": false },
  "meta":  { "modulo": "documentos", "tema": "lectura", "motor": "pymupdf" },
  "artefactos": [ { "tipo": "md", "ruta": "salida/tarea.md", "hash": "..." } ],
  "error": null
}
```

En fallo:

```json
{ "ok": false, "datos": null, "meta": {}, "artefactos": [],
  "error": { "codigo": "agente:pdf:noExiste", "mensaje": "El archivo no existe", "causa": null } }
```

- `ok` es el booleano que decide si la operación salió bien.
- `error.codigo` usa el formato `agente:<modulo>:<codigo>` (ver §4).
- Un módulo **nunca** revienta al usuario: captura la excepción y devuelve el error estructurado.
- En modo humano (sin `--json`), el CLI formatea este mismo objeto de forma legible.

---

## 4. Códigos de error tipados

Formato: `agente:<modulo>:<codigo>`. Catálogo canónico en `nucleo/config.py`.

| Código | Significado |
|---|---|
| `agente:pdf:noExiste` | archivo de entrada no encontrado |
| `agente:video:sinffmpeg` | binario de ffmpeg no instalado |
| `agente:uso:paramInvalido` | mal uso de flags (exit 2) |
| `agente:web:sesionExpirada` | sesión de login vencida |
| … | cada módulo declara los suyos |

Esto sustituye a los `sys.exit("mensaje")` sueltos: los errores de **uso** son exit 2,
los de **operación** son exit 1, y el detalle viaja en `error.codigo`/`error.mensaje`.

---

## 5. Contrato de CLI (banderas estándar)

Todo script expone las mismas banderas, heredadas de `nucleo/cli.py`:

```powershell
python script.py [entrada|-] [--json] [--quiet] [--yes] [--dry-run] [--help]
```

| Flag | Efecto |
|---|---|
| `entrada` / `--input` | archivo o `-` para leer de `stdin` |
| `--json` | emite el contrato §3 en `stdout` (máquina/IA) |
| `--quiet` | silencia logs (solo salida esencial) |
| `--yes` | auto-confirma acciones destructivas |
| `--dry-run` | previsualiza sin ejecutar (para que una IA proponga y tú apruebes) |
| `--help` | auto-documentación legible |
| `--output` / `--salida` | destino del artefacto |

Reglas:
- **Datos → `stdout`; logs/errores → `stderr`.**
- **Exit codes**: `0` ok · `1` error de operación · `2` mal uso.
- **Nunca pedir input** salvo flag explícito `--interactivo` (una IA no puede teclear).

---

## 6. `capacidades.json` (la fuente de verdad única)

Un catálogo declarativo que describe cada comando. De **este único archivo** se
generan: (a) el menú del CLI, (b) el `--help`, (c) la tabla de enrutado de la
skill del orquestador, y (d) el esquema JSON para IA.

```json
{
  "comandos": [
    {
      "id": "pdf",
      "modulo": "documentos",
      "script": "modulos/documentos/scripts/leer_pdf.py",
      "descripcion": "Lee cualquier PDF (texto, tablas, OCR)",
      "entradas":  [{ "nombre": "input", "tipo": "ruta", "requerido": true }],
      "opciones":  [{ "nombre": "ocr", "tipo": "cadena", "valores": ["auto","si","no"] }],
      "produce":   [{ "tipo": "markdown" }, { "tipo": "json" }],
      "delega_en": []
    }
  ]
}
```

Con esto, añadir un módulo nuevo es **un solo cambio**: se agrega su entrada al
catálogo y aparece automáticamente en CLI, REPL, skill y esquema IA.

---

## 7. `nucleo/` (los engranajes compartidos)

```
nucleo/
├── contrato.py    # Resultado(ok, datos, meta, artefactos, error) + helpers
├── errores.py     # AgenteError + agente:<modulo>:<codigo>
├── config.py      # catálogo de mensajes + rutas + carga de capacidades.json
├── cli.py         # parser común: --json/--quiet/--yes/--dry-run/--help + exit codes
└── registro.py    # artefactos y memoria (auditoría)
```

Los scripts importan `nucleo.cli` y **solo** se ocupan de su tarea; el resto lo
hereda. Ningún script reimplementa `--json` ni el contrato.

---

## 8. `modulo.json` (manifiesto por departamento)

Cada módulo declara su contrato en un archivo de metadatos:

```json
{
  "id": "documentos",
  "skill": "documentos.md",
  "descripcion": "Lector de PDF adaptativo",
  "requiere": ["pymupdf", "rapidocr"],
  "produce": ["markdown", "json"],
  "delega_en": []
}
```

Sirve para validar el módulo (que cumple lo que declara) y para el auto-esquema.

---

## 9. Accesibilidad para IA

El mismo CLI que usa el humano es la interfaz del modelo:

1. **`agente lista --json`** → la IA descubre qué comandos existen.
2. **`agente ayuda pdf --json`** → devuelve el esquema JSON del comando = **definición de herramienta** lista para *function calling*.
3. **No interactivo por defecto** → el modelo nunca se cuelga esperando input.
4. **Errores estructurados** → el modelo entiende `error.codigo` y puede reintentar o avisar.
5. **Determinista** → misma entrada, misma salida; el modelo puede predecir y verificar.
6. **`--dry-run`** → el modelo propone la acción, el humano confirma.
7. **Servidor MCP** (`interfaces/mcp_servidor.py`), **generado desde `capacidades.json`**:
   cada comando se expone como herramienta nativa tipada (JSON Schema). El CLI sigue
   siendo la fuente de verdad; el MCP es otra puerta sobre el mismo motor.

---

## 10. Composición (la cinta transportadora)

Además de ejecutar un comando, `agente` encadena módulos declarativamente:

```json
{ "flujo": ["pdf", "resumir", "ensayo", "infografia"] }
```

```powershell
agente run flujo.json
agente pdf tarea.pdf --json | agente resumir --stdin
```

Cada paso consume los artefactos del anterior (por `artefactos[].ruta`), así que el
pipeline es reproducible y auditable.

---

## 11. Qué NO cambia

- **SPT** permanece intacto e independiente (`analizador` / `analizador-gui`).
- Los **binarios** (`ffmpeg.exe`, modelos whisper) siguen fuera de git.
- Las **credenciales/sesiones** (`~\.config\opencode\navegacion\`, perfiles `chrome-*`) siguen fuera de git.
- Las **skills** de OpenCode siguen siendo copias generadas (nunca editadas a mano).
