#!/usr/bin/env bash
# Instala dependencias, directorios, pruebas y la unidad systemd de usuario.
# No arranca el servicio salvo que se pase --arrancar.
set -euo pipefail

MODULO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$(dirname "$MODULO")"
PY="$REPO/.venv/bin/python"
ARRANCAR=0

for arg in "$@"; do
    case "$arg" in
        --arrancar) ARRANCAR=1 ;;
        --sin-tests) SIN_TESTS=1 ;;
        -h|--help)
            echo "Uso: $0 [--arrancar] [--sin-tests]"
            exit 0
            ;;
        *)
            echo "Opción desconocida: $arg" >&2
            exit 2
            ;;
    esac
done

if [[ ! -x "$PY" ]]; then
    echo "==> Creando venv del repositorio en $REPO/.venv"
    python3 -m venv "$REPO/.venv"
    "$PY" -m pip install --upgrade pip
    if [[ -f "$REPO/requirements.txt" ]]; then
        "$PY" -m pip install -r "$REPO/requirements.txt"
    fi
    "$PY" -m pip install pytest
fi

echo "==> Instalando dependencias del agente de correo"
"$PY" -m pip install -r "$MODULO/requirements.txt"

echo "==> Creando directorios con permisos 700"
install -d -m 700 "$MODULO/data" "$MODULO/out" "$MODULO/entrada" "$MODULO/secrets"

if [[ ! -f "$MODULO/.env" ]]; then
    install -m 600 "$MODULO/.env.example" "$MODULO/.env"
    echo "==> Creado $MODULO/.env desde .env.example"
    echo "    EDÍTALO antes de arrancar: AUTORIZADO_FROM, GMAIL_USER y Drive."
else
    chmod 600 "$MODULO/.env"
    echo "==> .env existente; se mantiene (permisos 600)"
fi

echo "==> Compilando"
"$PY" -m compileall -q "$MODULO"

if [[ "${SIN_TESTS:-0}" -eq 0 ]]; then
    echo "==> Ejecutando pruebas sin red"
    "$PY" -m pytest -q "$MODULO/tests"
fi

if ! command -v systemctl >/dev/null 2>&1; then
    echo "AVISO: no hay systemctl; se omite la instalación de la unidad."
    exit 0
fi

echo "==> Instalando unidad systemd de usuario"
install -d -m 700 "$HOME/.config/systemd/user"
install -m 644 "$MODULO/service/agente-correo.service" \
    "$HOME/.config/systemd/user/agente-correo.service"
if systemctl --user daemon-reload 2>/dev/null; then
    echo "==> systemd de usuario recargado"
else
    echo "AVISO: no se pudo recargar systemd de usuario; revisa la sesión." >&2
fi

if [[ "$ARRANCAR" -eq 1 ]]; then
    if grep -q '^AUTORIZADO_FROM=tu-correo-personal@gmail.com$' "$MODULO/.env"; then
        echo "ERROR: edita AUTORIZADO_FROM en $MODULO/.env antes de arrancar." >&2
        exit 1
    fi
    echo "==> Habilitando y arrancando agente-correo.service"
    systemctl --user enable --now agente-correo.service
    systemctl --user --no-pager status agente-correo.service || true
else
    echo "==> Unidad instalada pero no arrancada."
    echo "    Edita .env y ejecuta: systemctl --user enable --now agente-correo.service"
fi

cat <<EOF

Siguientes pasos:
  1. Autoriza OAuth (una vez, desde la raíz del repo):
       cd "$REPO" && $PY -m agente_correo.oauth_login
       cd "$REPO" && $PY -m agente_correo.oauth_login --check
  2. Prueba sin red ni credenciales:
       cd "$REPO" && $PY -m agente_correo.listener --once --dry-run --fixture agente_correo/tests/fixtures
  3. Arranque real:
       systemctl --user enable --now agente-correo.service
  4. Para que siga tras cerrar sesión:
       sudo loginctl enable-linger $USER
  5. Registro:
       journalctl --user -u agente-correo.service -f
EOF
