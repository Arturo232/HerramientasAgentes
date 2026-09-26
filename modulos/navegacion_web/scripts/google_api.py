#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cliente de Google Drive/Docs por API (OAuth). Ver GOOGLE_OAUTH.md.

Ventaja: subir, convertir a Google Doc y compartir en UNA llamada, sin UI.

Requisitos (una vez):
    pip install google-api-python-client google-auth-oauthlib
    python google_api.py auth          # autoriza y guarda el token

Uso:
    python google_api.py subir --carpeta FOLDER_ID --archivo "x.docx" [--convertir]
    python google_api.py compartir --file FILE_ID [--rol writer|reader]
    python google_api.py materias
"""
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)
from nucleo import cli  # noqa: E402
from nucleo.contrato import exito  # noqa: E402
from nucleo.errores import AgenteError  # noqa: E402

LOCAL = os.path.join(os.path.expanduser("~"), ".config", "opencode", "navegacion")
CREDS = os.path.join(LOCAL, "google_credentials.json")
TOKEN = os.path.join(LOCAL, "google_token.json")
SCOPES = ["https://www.googleapis.com/auth/drive"]
DOC_MIME = "application/vnd.google-apps.document"


def _libs():
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        return Credentials, InstalledAppFlow, Request, build, MediaFileUpload
    except Exception as e:
        raise AgenteError("navegacion_web", "faltanLibs",
                          "Faltan librerias. Ejecuta:\n  python -m pip install "
                          "google-api-python-client google-auth-oauthlib\n(%s)" % e)


def auth():
    Credentials, InstalledAppFlow, Request, build, _ = _libs()
    if not os.path.exists(CREDS):
        raise AgenteError("navegacion_web", "sinCredenciales",
                          "Falta %s (ver GOOGLE_OAUTH.md)" % CREDS)
    flow = InstalledAppFlow.from_client_secrets_file(CREDS, SCOPES)
    creds = flow.run_local_server(port=0)
    os.makedirs(LOCAL, exist_ok=True)
    json.dump(json.loads(creds.to_json()), open(TOKEN, "w", encoding="utf-8"))
    print("Autorizado. Token en", TOKEN)
    return creds


def creds():
    Credentials, InstalledAppFlow, Request, build, _ = _libs()
    if os.path.exists(TOKEN):
        c = Credentials.from_authorized_user_file(TOKEN, SCOPES)
        if c and c.expired and c.refresh_token:
            c.refresh(Request())
            json.dump(json.loads(c.to_json()), open(TOKEN, "w", encoding="utf-8"))
        if c and c.valid:
            return c
    raise AgenteError("navegacion_web", "sinAuth",
                      "No autorizado. Ejecuta: python google_api.py auth")


def servicio():
    _, _, _, build, _ = _libs()
    return build("drive", "v3", credentials=creds())


def subir(carpeta_id, archivo, convertir=False, nombre=None):
    _, _, _, _, MediaFileUpload = _libs()
    svc = servicio()
    meta = {"name": nombre or os.path.basename(archivo)}
    if carpeta_id:
        meta["parents"] = [carpeta_id]
    if convertir:
        meta["mimeType"] = DOC_MIME
    media = MediaFileUpload(archivo, resumable=True)
    f = svc.files().create(body=meta, media_body=media, fields="id,name,mimeType,webViewLink").execute()
    return f


def compartir(file_id, rol="writer"):
    svc = servicio()
    perm = {"type": "anyone", "role": rol}
    svc.permissions().create(fileId=file_id, body=perm).execute()
    f = svc.files().get(fileId=file_id, fields="id,name,webViewLink").execute()
    return f


def listar(carpeta_id):
    svc = servicio()
    q = "'%s' in parents and trashed=false" % carpeta_id
    res = svc.files().list(q=q, fields="files(id,name,mimeType,webViewLink)",
                           orderBy="name", pageSize=200).execute()
    return res.get("files", [])


def renombrar(file_id, nuevo_nombre):
    svc = servicio()
    f = svc.files().update(fileId=file_id, body={"name": nuevo_nombre},
                           fields="id,name,webViewLink").execute()
    return f


def actualizar(file_id, archivo):
    """Reemplaza el contenido de un archivo existente (mismo ID y enlace)."""
    _, _, _, _, MediaFileUpload = _libs()
    svc = servicio()
    media = MediaFileUpload(archivo, resumable=True)
    f = svc.files().update(fileId=file_id, media_body=media,
                           fields="id,name,mimeType,webViewLink").execute()
    return f


def eliminar(file_id):
    """Envia el archivo a la papelera (recuperable)."""
    svc = servicio()
    svc.files().update(fileId=file_id, body={"trashed": True}).execute()
    return {"id": file_id, "trashed": True}


def _construir(ap):
    ap.add_argument("cmd", choices=["auth", "subir", "compartir", "materias", "listar", "renombrar", "actualizar", "eliminar"])
    ap.add_argument("--carpeta")
    ap.add_argument("--archivo")
    ap.add_argument("--nombre")
    ap.add_argument("--convertir", action="store_true")
    ap.add_argument("--file")
    ap.add_argument("--rol", default="writer", choices=["writer", "reader", "commenter"])


def _accion(ns):
    if ns.cmd == "auth":
        auth()
        return exito(datos={"autorizado": True, "token": TOKEN})
    if ns.cmd == "materias":
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import config
        return exito(datos=config.get("drive", "materias_quinto", defecto={}) or {})
    if ns.cmd == "listar":
        return exito(datos={"archivos": listar(ns.carpeta)})
    if ns.cmd == "renombrar":
        return exito(datos=renombrar(ns.file, ns.nombre))
    if ns.cmd == "actualizar":
        return exito(datos=actualizar(ns.file, ns.archivo))
    if ns.cmd == "eliminar":
        return exito(datos=eliminar(ns.file))
    if ns.cmd == "subir":
        return exito(datos=subir(ns.carpeta, ns.archivo, ns.convertir, ns.nombre))
    return exito(datos=compartir(ns.file, ns.rol))


if __name__ == "__main__":
    sys.exit(cli.correr("navegacion_web", _construir, _accion, sys.argv[1:],
                        prog="google_api",
                        descripcion="Google Drive/Docs por API."))
