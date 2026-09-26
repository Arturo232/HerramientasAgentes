# Playbook · Canva (automatización por CDP)

Canva se controla con **Chrome + CDP** (Playwright `connect_over_cdp`). El perfil de Chrome
mantiene la sesión iniciada, así que **no hay que loguearse** cada vez.

## 0. Requisito: abrir Chrome con el perfil y sesión
```bash
python scripts/sesion_cdp.py abrir "https://www.canva.com/" --perfil "$env:USERPROFILE\.config\opencode\chrome-flipux"
```
- Verificar sesión: la home muestra "¿Qué vamos a diseñar hoy?" y el usuario arriba.
- **Importante**: las pestañas en segundo plano **no se renderizan** (viewport 0) y las
  capturas fallan. Siempre `page.bring_to_front()` antes de capturar o interactuar.

## 1. Cómo está construido el editor (lo que hay que saber)
- El lienzo del diseño **NO** es `<canvas>`: Canva expone los textos como **`span.a_GcMg`**
  dentro de un `<p>`, posicionados por CSS (`getBoundingClientRect`).
- Al **doble clic** sobre un texto, Canva abre un editor **Quill**: `div.ql-editor[contenteditable=true]`
  con el texto seleccionado. Ahí se puede `Ctrl+A` + escribir y `Escape` para confirmar.
- Los íconos de la interfaz son `<svg>` de 24×24 (no confundir con el contenido).
- Los botones clave: **Compartir** (arriba a la derecha) → menú con **Descargar**.

## 2. Flujo completo (receta `recetas/canva.py`)
```bash
# a) Buscar plantillas por palabra clave -> URLs
python recetas/canva.py plantillas --buscar "mapa conceptual"
python recetas/canva.py plantillas --buscar "diagrama de flujo"
python recetas/canva.py plantillas --buscar "presentacion"        # diapositivas

# b) Crear un diseno a partir de una plantilla (abre el editor)
python recetas/canva.py usar --plantilla "https://www.canva.com/templates/<ID>-<slug>/"

# c) Ver los textos del diseno (texto + posición)
python recetas/canva.py textos

# d) Reemplazar textos (mapa texto_actual -> texto_nuevo)
python recetas/canva.py reemplazar --mapa '{"Concept Map":"PROCESO DE IMPORTACION","Subtitle":"Unidad 2"}'

# e) Exportar (PNG por defecto; tambien pdf/jpg)
python recetas/canva.py exportar --formato png --salida "C:\ruta\diagrama.png"
python recetas/canva.py exportar --formato pdf --salida "C:\ruta\diagrama.pdf"
```

## 3. Reglas y gotchas (aprendidos)
1. **Sesión**: usar el perfil `chrome-flipux`; si no hay sesión, abrir Canva y loguearse una vez.
2. **bring_to_front**: sin esto el editor tiene viewport 0 → no se puede capturar ni interactuar.
3. **Doble clic + Quill**: la única forma fiable de editar texto. `Ctrl+A` selecciona TODO el
   texto del elemento; luego escribir y `Escape`.
4. **Reemplazo por texto exacto**: `canva.py reemplazar` busca el `span` cuyo texto coincida
   exactamente. Para cajas vacías, primero hay que añadirles texto (doble clic en la caja).
5. **Exportar**: el botón final es `button[type='submit']:has-text('Descargar')`. NO tocar el
   selector de formato si es PNG (abrirlo y no cerrarlo bloquea el botón). Para PDF, elegir el
   formato en el desplegable y luego pulsar Descargar.
6. **`page.title()` puede colgar** en el editor: usar `page.url` y evitar `title()`.
7. **Escape** cierra el panel de descarga: usarlo solo para cerrar el dropdown, no el panel.

## 4. Uso dentro del flujo de unidad
Cuando una actividad pida **mapa conceptual, mentefacto, diagrama o diapositivas**:
1. `canva.py plantillas --buscar "<tipo>"` → elegir una plantilla adecuada.
2. `canva.py usar --plantilla URL` → crear el diseño.
3. `canva.py textos` → ver los campos y mapear el contenido de la unidad.
4. `canva.py reemplazar --mapa '{...}'` → volcar el contenido.
5. `canva.py exportar --formato png --salida <materia>/unidad N/<nombre>.png`.
6. Insertar la imagen en el documento (al final, con `docx_util` `anexo=`) y subir a Drive.
