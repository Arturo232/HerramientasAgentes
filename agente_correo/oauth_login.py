"""Autorización OAuth 2.0 de Gmail/Drive por loopback.

    python -m agente_correo.oauth_login
    python -m agente_correo.oauth_login --check

Abre el navegador en http://localhost:8765, pide consentimiento con los scopes
mínimos y guarda ``secrets/token.json`` con permisos 600.
"""

from __future__ import annotations

# Permite ejecutar el archivo directamente además de `python -m agente_correo.oauth_login`.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path

    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
    from agente_correo.oauth_login import main as _main

    raise SystemExit(_main())

import argparse
import sys
from pathlib import Path

from . import gmail_client
from .config import SCOPES, Config, ErrorConfig


def _comprobar(cfg: Config) -> int:
    try:
        servicio = gmail_client.construir_servicio(cfg)
        perfil = gmail_client.perfil(servicio)
    except (gmail_client.ErrorGmail, gmail_client.ErrorAuth) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR al validar el token: {exc}", file=sys.stderr)
        return 1
    print("Token válido.")
    print(f"Cuenta: {perfil.get('emailAddress', '(desconocida)')}")
    print(f"Token:  {cfg.token}")
    print("Scopes:")
    for scope in SCOPES:
        print(f"  - {scope}")
    return 0


def _autorizar(cfg: Config, client_secret: Path, puerto: int) -> int:
    if not client_secret.is_file():
        print(
            f"ERROR: falta {client_secret}\n"
            "Descarga el OAuth Client ID tipo Desktop desde Google Cloud "
            "Console y guárdalo ahí (ver README).",
            file=sys.stderr,
        )
        return 2
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        print(
            "ERROR: faltan librerías. Ejecuta:\n"
            "  python -m pip install -r agente_correo/requirements.txt",
            file=sys.stderr,
        )
        return 2

    try:
        flujo = InstalledAppFlow.from_client_secrets_file(
            str(client_secret), list(SCOPES)
        )
        credenciales = flujo.run_local_server(
            port=puerto,
            open_browser=True,
            access_type="offline",
            prompt="consent",
            authorization_prompt_message=(
                "Abre este enlace para autorizar el agente: {url}"
            ),
            success_message=(
                "Autorización completada. Ya puedes cerrar esta pestaña."
            ),
        )
    except Exception as exc:
        print(f"ERROR durante la autorización: {exc}", file=sys.stderr)
        return 1

    gmail_client.guardar_token(credenciales, cfg.token, obligatorio=True)
    print(f"Token guardado en {cfg.token} (permisos 600).")
    print("Comprueba con: python -m agente_correo.oauth_login --check")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Autorización OAuth 2.0 del agente de correo (loopback)"
    )
    parser.add_argument(
        "--check", action="store_true", help="valida el token existente y sale"
    )
    parser.add_argument(
        "--reauth", action="store_true", help="fuerza un consentimiento nuevo"
    )
    parser.add_argument(
        "--client-secret",
        help="ruta alternativa a client_secret.json",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="puerto loopback (por defecto OAUTH_PORT=8765)",
    )
    args = parser.parse_args(argv)

    try:
        cfg = Config.cargar()
    except ErrorConfig as exc:
        print(f"ERROR de configuración: {exc}", file=sys.stderr)
        return 2
    cfg.preparar_directorios()

    if args.check and not args.reauth:
        return _comprobar(cfg)

    client_secret = (
        Path(args.client_secret).expanduser().resolve()
        if args.client_secret
        else cfg.client_secret
    )
    if client_secret.exists():
        try:
            if client_secret.stat().st_mode & 0o077:
                print(
                    "AVISO: client_secret.json tiene permisos amplios; se "
                    "recomienda chmod 600.",
                    file=sys.stderr,
                )
        except OSError:
            pass
    puerto = args.port or cfg.oauth_port
    return _autorizar(cfg, client_secret, puerto)


if __name__ == "__main__":
    raise SystemExit(main())
