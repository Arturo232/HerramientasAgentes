#!/usr/bin/env bash
# Prepara la estación para operar 24/7: enmascara suspensión e ignora la tapa.
# Por defecto SOLO MUESTRA EL PLAN. No aplica nada hasta pasar --aplicar.
# Uso: sudo ./potencia-24-7.sh --aplicar
set -euo pipefail

MODULO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARCHIVO="/etc/systemd/logind.conf.d/99-agente-correo.conf"
OBJETIVOS=(sleep.target suspend.target hibernate.target hybrid-sleep.target)
APLICAR=0

for arg in "$@"; do
    case "$arg" in
        --aplicar) APLICAR=1 ;;
        -h|--help)
            echo "Uso: sudo $0 [--aplicar]"
            echo "Sin --aplicar solo imprime el plan."
            exit 0
            ;;
        *)
            echo "Opción desconocida: $arg" >&2
            exit 2
            ;;
    esac
done

if [[ "$APLICAR" -eq 0 ]]; then
    cat <<EOF
PLAN (no se ha modificado nada):
  1. systemctl mask ${OBJETIVOS[*]}
  2. crear $ARCHIVO con:
       [Login]
       HandleLidSwitch=ignore
       HandleLidSwitchExternalPower=ignore
       HandleLidSwitchDocked=ignore
  3. systemctl reload systemd-logind.service
Para aplicar: sudo $0 --aplicar
Para revertir: sudo $MODULO/bin/potencia-revertir.sh --aplicar
EOF
    exit 0
fi

if [[ "$EUID" -ne 0 ]]; then
    echo "ERROR: ejecuta con sudo $0 --aplicar" >&2
    exit 1
fi
if ! command -v systemctl >/dev/null 2>&1; then
    echo "ERROR: no se encontró systemctl" >&2
    exit 1
fi

echo "==> Enmascarando objetivos de suspensión"
systemctl mask "${OBJETIVOS[@]}"

echo "==> Escribiendo $ARCHIVO"
install -d -m 755 /etc/systemd/logind.conf.d
cat > "$ARCHIVO" <<'EOF'
# Generado por agente_correo/bin/potencia-24-7.sh
[Login]
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
EOF
chmod 644 "$ARCHIVO"

echo "==> Recargando systemd-logind"
systemctl reload systemd-logind.service || {
    echo "AVISO: no se pudo recargar logind; reinicia la sesión o el equipo." >&2
}

cat <<EOF
Aplicado. Comprueba con:
  systemctl status sleep.target suspend.target
  systemctl show -p HandleLidSwitch
Reversión:
  sudo $MODULO/bin/potencia-revertir.sh --aplicar
EOF
