# Playbook · Moodle (Unicartagena / CAMPUS INGLÉS)

Plataforma: `https://ingles.unicartagena.edu.co` (Moodle 5.x, tema Moove).
Login: institucional (usuario = número de identificación, contraseña = la de SIMA).

## Reglas
- El **login lo hace el usuario** en el navegador visible. Nunca pedir/guardar contraseñas.
- Usar **perfil aislado** (`sesion_cdp.py`, puerto 9333) para no chocar con otros chats.
- Foros y evaluaciones (Tareas): **solo tras confirmación** del usuario.
- Registrar URL, fecha y resultado en la memoria (`registro.py`).

## Flujo

### 1. Abrir sesión
```bash
python scripts/sesion_cdp.py abrir "https://ingles.unicartagena.edu.co/login/index.php"
```
Pedir al usuario que inicie sesión. Verificar:
```bash
python scripts/sesion_cdp.py paginas   # debe aparecer /my/ (Área personal)
```
Si aparece "Your session has timed out", pedir re-login.

### 2. Inventario del curso
```bash
python scripts/inventario_moodle.py --curso 444 --pendientes --salida inventario.json
```
Salida: nombre, URL, estado de finalización y `tipo` H5P de cada actividad.

### 3. Completar actividades de aprendizaje
```bash
python scripts/h5p_solver.py --url "https://ingles.unicartagena.edu.co/mod/hvp/view.php?id=NNN"
python scripts/batch_moodle.py --inventario inventario.json --secciones 2 3 4
```
El solver detecta el tipo y aplica la estrategia:
- **Ver**: CoursePresentation (slides), Accordion, Dialogcards, InteractiveBook (navegar).
- **Nota**: Blanks, MultiChoice, TrueFalse, MarkTheWords, SortParagraphs, DragQuestion, QuestionSet (responder y Check).

### 4. Verificar
Volver a `course/view.php?id=444&section=N` y leer el estado por actividad
(`js_actividades` / `inventario_moodle.py` sin `--pendientes`).

### 5. Foros y evaluaciones
Preparar el contenido, mostrarlo al usuario y publicar/enviar **solo** con su confirmación.

## Detalles técnicos
- El contenido H5P vive en un `iframe`; las instancias están en `H5P.instances`
  y las anidadas en `inst.getInstances()`. Los params pueden estar en
  `inst.params` o en `H5PIntegration.contents[id].jsonContent`.
- Para arrastrar (DragQuestion) usar mouse manual con pasos (jQuery UI no responde a `drag_to`).
- SortParagraphs se reordena con teclado: `focus` → `Space` → flechas → `Space`.
- QuestionSet muestra todas las preguntas en el DOM; avanzar con `a.h5p-question-next`.
- Evitar re-responder: si los inputs están `disabled` (ya respondidos), omitir.
