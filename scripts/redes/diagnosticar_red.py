#!/usr/bin/env python3
"""Diagnóstico y recuperación automática de red para Arch Linux.

Comprueba conectividad externa (1.1.1.1) y la API local de Ollama,
detecta interfaz y servicios de red, intenta reconexión automática
en caso de desconexión y emite JSON con la recomendación de motor.
"""

import argparse
import json
import subprocess
import time
from urllib import request

DNS_PUBLICO = "1.1.1.1"
OLLAMA_URL = "http://127.0.0.1:11434/api/tags"
MODELO_LOCAL_CODIGO = "ollama/qwen2.5-coder:7b"
MODELO_LOCAL_GENERAL = "ollama/llama3.1:8b"


def _ejecutar(comando, timeout=10):
    try:
        resultado = subprocess.run(
            comando, capture_output=True, text=True, timeout=timeout
        )
        return resultado.returncode, resultado.stdout.strip(), resultado.stderr.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return 1, "", ""


def probar_internet():
    """Devuelve (activo, latencia_ms) haciendo ping al DNS público."""
    codigo, salida, _ = _ejecutar(["ping", "-c", "2", "-W", "2", DNS_PUBLICO])
    if codigo != 0:
        return False, None
    latencia = None
    for linea in salida.splitlines():
        if "rtt min/avg/max/mdev" in linea:
            try:
                latencia = float(linea.split("=")[1].split("/")[1])
            except (IndexError, ValueError):
                latencia = None
    return True, latencia


def probar_ollama():
    """Devuelve (activo, [modelos]) consultando /api/tags de Ollama."""
    try:
        with request.urlopen(OLLAMA_URL, timeout=3) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
        return True, [modelo.get("name") for modelo in datos.get("models", [])]
    except (OSError, ValueError):
        return False, []


def detectar_interfaz():
    """Devuelve (nombre, estado) de la interfaz por defecto."""
    interfaces = {}
    codigo, salida, _ = _ejecutar(["ip", "-br", "address"])
    if codigo == 0:
        for linea in salida.splitlines():
            partes = linea.split()
            if len(partes) >= 2:
                interfaces[partes[0]] = partes[1]

    interfaz_principal = None
    codigo_ruta, salida_ruta, _ = _ejecutar(["ip", "route"])
    if codigo_ruta == 0:
        for linea in salida_ruta.splitlines():
            if linea.startswith("default") and "dev" in linea:
                partes = linea.split()
                interfaz_principal = partes[partes.index("dev") + 1]
                break

    candidatas = [interfaz_principal] if interfaz_principal else []
    candidatas += [
        nombre
        for nombre, estado in interfaces.items()
        if nombre != "lo" and estado == "UP"
    ]
    interfaz = candidatas[0] if candidatas else interfaz_principal
    estado = interfaces.get(interfaz, "desconocido") if interfaz else "sin interfaz"
    return interfaz, estado


def detectar_servicios():
    """Devuelve {servicio: estado} para NetworkManager, systemd-networkd e iwd."""
    servicios = {}
    for nombre in ("NetworkManager", "systemd-networkd", "iwd"):
        _, salida, _ = _ejecutar(["systemctl", "is-active", nombre])
        servicios[nombre] = salida or "desconocido"
    return servicios


def reconectar(interfaz, servicios):
    """Intenta reconectar la interfaz y reiniciar el servicio de red.

    Devuelve (exito, detalle). Primero usa nmcli como usuario y,
    como respaldo, sudo -n systemctl restart del servicio activo.
    """
    intentos = []
    if interfaz:
        codigo, _, error = _ejecutar(
            ["nmcli", "device", "disconnect", interfaz], timeout=15
        )
        if codigo == 0:
            time.sleep(2)
            codigo, _, error = _ejecutar(
                ["nmcli", "device", "connect", interfaz], timeout=20
            )
            if codigo == 0:
                return True, f"nmcli: interfaz {interfaz} reconectada"
            intentos.append(f"nmcli connect falló: {error}")
        else:
            intentos.append(f"nmcli disconnect falló: {error}")

    servicio_activo = (
        "NetworkManager"
        if servicios.get("NetworkManager") == "active"
        else "iwd" if servicios.get("iwd") == "active" else None
    )
    if servicio_activo:
        codigo, _, error = _ejecutar(
            ["sudo", "-n", "systemctl", "restart", servicio_activo], timeout=30
        )
        if codigo == 0:
            return True, f"sudo systemctl restart {servicio_activo} exitoso"
        intentos.append(
            f"sudo -n restart {servicio_activo} falló: "
            f"{error or 'sin credenciales cacheadas'}"
        )

    return False, "; ".join(intentos) if intentos else "sin método de reconexión"


def recomendar_modelo(internet_activo, ollama_activo):
    """Devuelve (recomendacion, mensaje) según disponibilidad de motores."""
    if internet_activo:
        return "internet/nube", "Conexión externa activa. Motor en nube disponible."
    if ollama_activo:
        return MODELO_LOCAL_CODIGO, (
            "Sin conexión externa. Conmutando a motor local offline."
        )
    return "sin_motor", (
        "Sin conexión externa y Ollama local no responde. "
        "Verificar el servicio ollama.service."
    )


def diagnosticar(reconectar_automatico=True, dry_run=False, simular_offline=False):
    """Ejecuta el diagnóstico completo y devuelve el dict de resultados."""
    internet_activo, latencia = probar_internet()
    if simular_offline:
        internet_activo, latencia = False, None
    ollama_activo, modelos = probar_ollama()
    interfaz, estado_interfaz = detectar_interfaz()
    servicios = detectar_servicios()

    detalle_reconexion = ""
    reconexion_intentada = False
    if not internet_activo and reconectar_automatico:
        if dry_run:
            detalle_reconexion = "dry-run: reconexión simulada, no ejecutada"
        else:
            reconexion_intentada, detalle_reconexion = reconectar(interfaz, servicios)
            if reconexion_intentada:
                time.sleep(3)
                internet_activo, latencia = probar_internet()

    recomendacion, mensaje = recomendar_modelo(internet_activo, ollama_activo)
    resultado = {
        "internet_activo": internet_activo,
        "ollama_local_activo": ollama_activo,
        "interfaz_red": interfaz,
        "estado_interfaz": estado_interfaz,
        "estado_red": "conectado" if internet_activo else "desconectado",
        "recomendacion_modelo": recomendacion,
        "mensaje": mensaje,
        "latencia_ms": latencia,
        "servicios_red": servicios,
        "modelos_ollama": modelos,
        "reconexion_intentada": reconexion_intentada,
    }
    if detalle_reconexion:
        resultado["detalle_reconexion"] = detalle_reconexion
    return resultado


def main():
    parser = argparse.ArgumentParser(
        description="Diagnóstico y recuperación de red en Arch Linux (salida JSON)"
    )
    parser.add_argument(
        "--sin-reconexion",
        dest="reconectar",
        action="store_false",
        help="no intentar reconexión automática",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="simular la reconexión sin tocar la red",
    )
    parser.add_argument(
        "--simular-offline",
        action="store_true",
        help="forzar modo offline para probar el fallback local",
    )
    parser.set_defaults(reconectar=True)
    args = parser.parse_args()

    resultado = diagnosticar(
        reconectar_automatico=args.reconectar,
        dry_run=args.dry_run,
        simular_offline=args.simular_offline,
    )
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
