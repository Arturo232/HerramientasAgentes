# Guía · OAuth de Google (Drive/Docs API) — Fase 5

Con esto, subir a Drive, convertir a Google Doc y compartir se hace en **una sola
llamada** (sin automatizar la interfaz). Es opcional: la vía CDP ya funciona.

## 1. Crear el proyecto y habilitar APIs
1. Entra a <https://console.cloud.google.com/> y crea un proyecto (p. ej. `academico-udec`).
2. **APIs y servicios → Biblioteca**: habilita
   - **Google Drive API**
   - **Google Docs API**

## 2. Pantalla de consentimiento
1. **APIs y servicios → Pantalla de consentimiento de OAuth**.
2. Tipo: **Externo**. Nombre de la app: `Academico`.
3. En **Usuarios de prueba**, agrega tu correo `abaenaa1@unicartagena.edu.co`.
4. Ámbitos: agrega `.../auth/drive` (o `drive.file`).

## 3. Crear credenciales
1. **APIs y servicios → Credenciales → Crear credenciales → ID de cliente de OAuth**.
2. Tipo de aplicación: **Aplicación de escritorio**.
3. Descarga el JSON y guárdalo como:
   `C:\Users\ARTURO ANDRES\.config\opencode\navegacion\google_credentials.json`

## 4. Instalar librerías y autorizar
```bash
python -m pip install google-api-python-client google-auth-oauthlib
python "C:\Users\ARTURO ANDRES\.config\opencode\skills\navegador-web\scripts\google_api.py" auth
```
Se abrirá el navegador para autorizar; el token queda en
`~/.config/opencode/navegacion/google_token.json` (local, fuera de git).

## 5. Usar
```bash
# Subir (y opcionalmente convertir a Google Doc) a una carpeta de Drive
python scripts/google_api.py subir --carpeta <FOLDER_ID> --archivo "ruta.docx" --convertir

# Compartir un documento con enlace editable
python scripts/google_api.py compartir --file <FILE_ID> --rol writer

# Ver carpetas/materias configuradas
python scripts/google_api.py materias
```

## Notas
- `drive.file` solo da acceso a archivos creados/abiertos por la app; `drive`
  da acceso completo. Para el uso académico, `drive` es lo más cómodo.
- Los IDs de carpetas de Drive están en `config.json` (`drive.materias_quinto`).
- Nunca subas `google_credentials.json` ni `google_token.json` a git.
