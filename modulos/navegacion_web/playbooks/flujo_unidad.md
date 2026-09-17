# Flujo de trabajo por UNIDAD (protocolos + actividad) — automatizado

Flujo estándar y repetitivo para cualquier materia/unidad del SIMA. Todos los comandos
son **no interactivos** (API oficial de Moodle + API de Google). El único paso que requiere
criterio humano es redactar el contenido; el resto está automatizado.

## 0. Diagnóstico de la materia (API SIMA)
```bash
python scripts/moodle_api.py cursos                         # id de cada materia
python scripts/moodle_api.py tareas  --curso 869            # tareas + fechas de cierre
# estado de entrega (new = pendiente, submitted = entregado):
#   mod_assign_get_submission_status  (individual) / teamsubmission (colaborativa)
# cuestionarios: mod_quiz_get_quizzes_by_courses + mod_quiz_get_user_attempts
```
Regla: **primero saber qué falta y cuándo vence**, antes de producir.

## 1. Materiales de la unidad
```bash
python scripts/descargar_unidad.py --curso 869 --unidad 2   # modulo, recursos, plantillas
```
Guardar en `...\<materia>\unidad N\`. Extraer el texto del módulo con `pypdf`.

## 2. Entregables (3 por unidad)
| Entregable | Plantilla | Producto |
|---|---|---|
| **Protocolo individual** | `Plantilla_protocolo_individual.docx` | DOCX + **PDF** + **Google Doc editable** |
| **Protocolo colaborativo** | `Plantilla_protocolo_colaborativo.docx` | DOCX + **Google Doc editable** (es la entrega) |
| **Actividad** (mentefacto / diagrama de flujo) | `Plantilla_actividad_unidadN.docx` | gráfico (PNG) + DOCX + **PDF** + **Google Doc** |

Redacción con `recetas/docx_util.py` (viñetas reales + **fuente única**):
```python
import docx_util
docx_util.rellenar(PLANTILLA, OUT, encabezado, secciones,
                   titulo="Protocolo individual", anexo=anexo)   # anexo = al final
docx_util.exportar_pdf(OUT)
```
Gráficos con `recetas/mentefacto.py` (mapa conceptual) o `recetas/diagrama_flujo.py` (flujo):
```bash
python recetas/diagrama_flujo.py --contenido d.json --salida diagrama.png
```

## 3. Subir a Drive (mismo enlace, sin duplicados)
```bash
API=scripts/google_api.py
# PDF/PNG nuevos:
python $API subir --carpeta FOLDER_ID --archivo "x.pdf"
# Google Doc (convierte el DOCX):
python $API subir --carpeta FOLDER_ID --archivo "x.docx" --convertir
python $API compartir --file FILE_ID --rol writer
# Reemplazar contenido sin cambiar el enlace:
python $API actualizar --file FILE_ID --archivo "x.pdf"
# Borrar duplicados/obsoletos:
python $API eliminar --file FILE_ID
python $API listar --carpeta FOLDER_ID        # verificar
```

## 4. Reglas de calidad (OBLIGATORIAS, aprender de errores pasados)
1. **Una sola tipografía**: `docx_util.forzar_fuente()` → Arial en todo. Verificar el PDF:
   el texto visible debe ser **100% Arial** (SymbolMT solo para la viñeta).
2. **El diagrama/imagen va al FINAL** (parámetro `anexo=`), nunca en medio del texto.
3. **Sin páginas en blanco**: `docx_util` elimina párrafos vacíos finales; el anexo usa
   `cantSplit`. Ajustar el ancho de la imagen para que quepa en una página.
4. **Nombres de archivo SIN guiones bajos** (`_`).
5. **Protocolo individual → siempre dejar Google Doc editable** (para corregir a mano).
6. **No entregar en SIMA sin confirmación del usuario.**

## 5. Entrega en SIMA
```bash
# Subir entrega: core_files_upload + mod_assign_save_submission  (o vía CDP si no está expuesto)
```
Confirmar con el usuario **antes** de enviar.

## Carpetas de Drive por materia
`python scripts/google_api.py materias` → IDs de las carpetas (subcarpetas `Unidad 1..4`).
