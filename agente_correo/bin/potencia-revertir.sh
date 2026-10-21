#!/usr/bin/env bash
# Revierte los cambios de potencia-24-7.sh.
# Por defecto SOLO MUESTRA EL PLAN; aplica con --aplicar.
set -euo pipefail

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
PLAN DE REVERSIÓN (no se ha modificado nada):
  1. rm -f $ARCHIVO
  2. systemctl unmask ${OBJETIVOS[*]}
  3. systemctl reload systemd-logind.service
Para aplicar: sudo $0 --aplicar
EOF
    exit 0
fi

if [[ "$EUID" -ne 0 ]]; then
    echo "ERROR: ejecuta con sudo $0 --aplicar" >&2
    exit 1
fi

echo "==> Eliminando $ARCHIVO"
rm -f "$ARCHIVO"
rmdir --ignore-fail-on-non-empty /etc/systemd/logind.conf.d 2>/dev/null || true

echo "==> Desenmascarando objetivos"
systemctl unmask "${OBJETIVOS[@]}" || true

echo "==> Recargando systemd-logind"
systemctl reload systemd-logind.service || {
    echo "AVISO: no se pudo recargar logind; reinicia la sesión o el equipo." >&2
}

echo "Reversión aplicada. Comprueba con: systemctl show -p HandleLidSwitch"
