# Playbook · SIMA (Universidad de Cartagena)

Plataforma: `https://sima.unicartagena.edu.co` (Moodle 5.x, tema Edwiser RemUI).
Login: institucional — **usuario = número de identificación**, **contraseña = la del SMA**.
Modalidad: programas a distancia (CTEV). Sesión 2026-2.

## Reglas
- El **login lo hace el usuario**. Nunca pedir/guardar contraseñas por chat.
- Reutilizar perfil con sesión (`chrome-flipux`) o el perfil aislado de `sesion_cdp.py`.
- **No entregar** tareas en SIMA sin confirmación explícita del usuario.
- Registrar cada sesión con `registro.py sesion`.

## Cursos 2026-2 (IDs verificados)
| ID | Curso |
|---|---|
| 862 | Comportamiento Organizacional |
| 863 | Fundamentos de Mercado |
| 864 | Geografía Económica |
| 865 | Gestión Ambiental |
| 867 | Investigación de Operaciones |
| 868 | Mercados Financieros |
| 869 | Negocios Internacionales |
| — | Inglés V → `ingles.unicartagena.edu.co` (otro Moodle) |

CIPAS: el usuario está solo en `kamikaze` en casi todas; en **Mercados Financieros** está en **Cipa 1** (3 integrantes).

## Estructura típica de una unidad
- `Módulo de la unidad N` → **resource** (PDF en `iframe`)
- `Recursos bibliográficos y digitales unidad N` → **page** (lista de lecturas y videos)
- `Protocolo individual de la unidad N` → **assign**
- `Protocolo colaborativo de la unidad N` → **assign** (Google Doc compartido)
- `Actividad de la unidad N` → **assign** (p. ej. mentefacto)
- `Evaluación de la unidad N` → **quiz** (la resuelve el usuario)

## Patrones verificados
- **URL del módulo PDF:** `document.querySelector('iframe').src` → `pluginfile.php/<ctx>/mod_resource/content/<rev>/Unidad_N.pdf`
- **Descarga directa:** añadir `?forcedownload=1` al `pluginfile.php`.
- **Estado de entrega:** buscar `Todavía no se han realizado envíos` (pendiente) vs `Enviado para calificar` (entregado).
- **Fechas:** el calendario `/calendar/view.php?view=upcoming` sí muestra los vencimientos (el HTML de la tarea no siempre).
- **Plantillas/instructivos:** enlaces `docs.google.com` / `drive.google.com` dentro del enunciado.
  - Google Doc → exportar con `/export?format=docx` o `/export?format=txt`
  - Drive file → `https://drive.google.com/uc?export=download&id=<ID>`
- **Web services:** el servicio móvil **está habilitado** (`/login/token.php?service=moodle_mobile_app` responde `invalidlogin`, no `servicenotavailable`) → con credenciales se puede obtener **token** y usar la **API REST** (`core_course_get_contents`, `core_assign_get_assignments`, `core_files_get_files`), evitando el scraping.

## Acceso por API (vía preferida)
El servicio móvil está habilitado. Una sola vez (el usuario escribe sus datos en la terminal):
```bash
python scripts/sima_token.py          # pide usuario y clave por prompt local; guarda el TOKEN
python scripts/moodle_api.py site      # verifica
python scripts/moodle_api.py cursos    # lista cursos con IDs
```
Luego, sin navegador ni scraping:
```bash
python scripts/moodle_api.py estructura --curso 869    # JSON cacheado (1 h): secciones, tareas y cierres
python scripts/moodle_api.py archivos  --curso 869     # URLs de los archivos (módulos)
```
El token se guarda en `~/.config/opencode/navegacion/sima_token.json` (local, fuera de git).

## Flujo recomendado
1. `sima_token.py` (una vez) y luego **`moodle_api.py`** para todo lo consultable.
2. `estructura --curso N` → JSON cacheado (secciones, tareas, vencimientos, archivos).
3. Descargar unidad: usar `urls` del JSON + `&forcedownload=1`.
4. Redactar protocolo: `recetas/docx_util.py` (plantilla + viñetas reales + **fuente única Arial** → PDF).
5. **Subir a Drive SIEMPRE**: individual y colaborativo → **Google Doc** (`google_api.py subir --convertir` + `compartir`).
   - **Protocolo individual**: dejar también el **Google Doc editable** (para que el estudiante ajuste si falta algo) + el **PDF** para entregar.
   - **Protocolo colaborativo**: el Google Doc es la entrega (enlace editable).
6. Entregar **solo con confirmación**.
7. Si la API no cubre algo (p. ej. subir entrega), usar la vía CDP (`sesion_cdp.py`).

## Detalles técnicos
- El cargador de archivos del MCP **solo acepta rutas dentro del proyecto** (`...\ingles` y `...\ingles\.playwright-mcp`): copiar allí antes de subir y borrar después.
- Google Docs no expone `innerText`: verificar con `/export?format=txt`.
- Canva no tiene plantillas de "mentefacto"; usar una de "mapa conceptual" y editar nodos con `dblclick + Ctrl+A + escribir`.
- La plantilla de protocolo **no trae estilo de viñetas**: hay que inyectar `abstractNum`/`num` en `numbering.xml` (ver utilidad de viñetas).
