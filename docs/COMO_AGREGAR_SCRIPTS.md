# Cómo agregar scripts nuevos al sistema

> Guía para convertir cualquier script nuevo (de un trabajo nuevo) en un
> **programa del sistema**: se guarda en el repo, se registra en el catálogo y
> queda disponible por terminal (CLI/REPL) y para la IA (MCP).

---

## 1. La idea

`capacidades.json` es la **fuente única**. Un comando registrado ahí aparece
automáticamente en:

- **CLI**: `agente <id> ...`
- **Ayuda**: `agente ayuda <id>`
- **REPL**: `agente> <id> ...`
- **MCP (IA)**: herramienta nativa (tras reiniciar opencode)
- **Skills**: tras `agente sync`

No hay que tocar el CLI ni el MCP: se generan del catálogo.

---

## 2. Formas de agregar un programa

### A) Script nuevo desde cero (recomendado)

```bash
agente nuevo resumen-clase --modulo documentos --descripcion "Resume una clase a partir de un PDF"
```

Crea `modulos/documentos/scripts/resumen_clase.py` con la plantilla del contrato
y lo registra. Luego editas `_accion()` y listo.

Con argumento posicional (estilo subcomando):

```bash
agente nuevo mi-tool --modulo programacion_y_tech --posicional comando
```

### B) Integrar un script que ya existe

```bash
agente integrar C:\ruta\mi_script.py --id mi-tool --modulo programacion_y_tech --descripcion "Mi script"
```

Copia el script al módulo y lo registra. Si el script **no** usa el núcleo, se
registra como *passthrough* (se ejecuta tal cual, sin contrato). Para el contrato
completo, adáptalo (ver §3) o usa la opción A.

### C) Manual

Añade una entrada a `capacidades.json` (misma estructura que las demás) y coloca
el script donde apunte `script`.

### Baja

```bash
agente quitar mi-tool      # lo saca del catálogo (no borra el archivo)
```

---

## 3. El contrato de un script (obligatorio para el contrato completo)

```python
import os
import sys

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
from nucleo import cli
from nucleo.contrato import exito
from nucleo.errores import AgenteError
from nucleo.registro import artefacto


def _construir(ap):
    ap.add_argument("--input", "-i", required=True)
    ap.add_argument("--salida", "-o")


def _accion(ns):
    # ... tu lógica ...
    return exito(datos={"resultado": 42}, artefactos=[artefacto("texto", "salida.txt")])


if __name__ == "__main__":
    sys.exit(cli.correr("mi_modulo", _construir, _accion, sys.argv[1:],
                        prog="mi-tool", descripcion="Mi herramienta"))
```

Reglas:
- **Una tarea por script**.
- Datos → `stdout`; logs/errores → `stderr`.
- Devuelve siempre el contrato `{ok, datos, meta, artefactos, error}`.
- Errores con `raise AgenteError("<modulo>", "<codigo>", "mensaje")`.
- Banderas comunes (`--json/--quiet/--yes/--dry-run`) las aporta `cli.correr`.

---

## 4. Ejemplo completo

```bash
# 1) crear
agente nuevo contar-palabras --modulo documentos --descripcion "Cuenta palabras de un PDF"

# 2) implementar modulos/documentos/scripts/contar_palabras.py

# 3) probar
agente contar-palabras --input tarea.pdf
agente contar-palabras --input tarea.pdf --json

# 4) publicar
agente sync            # actualiza las skills de OpenCode
git add -A && git commit -m "feat(documentos): comando contar-palabras"
# 5) reiniciar opencode para que el MCP lo vea
```

---

## 5. Después de agregar

| Acción | Efecto |
|---|---|
| `agente lista` | el comando ya aparece |
| `agente ayuda <id>` | ayuda y esquema del comando |
| `agente sync` | copia la skill actualizada a OpenCode |
| reiniciar opencode | el MCP publica el comando como herramienta de IA |
| `git commit` | deja el trabajo versionado |

> Nota: al registrar/editar comandos, `capacidades.json` se reescribe con formato
> expandido (contenido idéntico). Es normal.
