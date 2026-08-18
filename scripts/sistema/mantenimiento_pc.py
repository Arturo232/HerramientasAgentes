#!/usr/bin/env python3
"""Mantenimiento y monitoreo de recursos para Arch Linux.

Diagnostica uso de RAM, CPU, espacio en disco y modelos de Ollama.
Con --limpiar elimina caché de Pacman, paquetes huérfanos y archivos
temporales de /tmp. Emite siempre un JSON estructurado.
"""

import argparse
import json
import os
import subprocess
import time


def _ejecutar(comando, timeout=30):
    try:
        resultado = subprocess.run(
            comando, capture_output=True, text=True, timeout=timeout
        )
        return resultado.returncode, resultado.stdout.strip(), resultado.stderr.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return 1, "", ""


def ram_info():
    """Devuelve dict con uso de RAM en GB y porcentaje desde /proc/meminfo."""
    total = 0
    disponible = 0
    try:
        with open("/proc/meminfo", encoding="utf-8") as archivo:
            for linea in archivo:
                if linea.startswith("MemTotal:"):
                    total = int(linea.split()[1]) * 1024
                elif linea.startswith("MemAvailable:"):
                    disponible = int(linea.split()[1]) * 1024
    except (OSError, ValueError):
        return {"ram_total_gb": 0, "ram_usada_gb": 0, "ram_porcentaje": 0}
    usada = total - disponible
    return {
        "ram_total_gb": round(total / 1024**3, 2),
        "ram_usada_gb": round(usada / 1024**3, 2),
        "ram_porcentaje": round(usada / total * 100, 1) if total else 0,
    }


def _leer_estadisticas_cpu():
    try:
        with open("/proc/stat", encoding="utf-8") as archivo:
            linea = archivo.readline()
        if not linea.startswith("cpu "):
            return None
        valores = [int(v) for v in linea.split()[1:]]
        total = sum(valores)
        inactivo = valores[3] + valores[4]
        return total, inactivo
    except (OSError, ValueError):
        return None


def cpu_info():
    """Devuelve el porcentaje de uso de CPU entre dos lecturas de /proc/stat."""
    primera = _leer_estadisticas_cpu()
    time.sleep(0.5)
    segunda = _leer_estadisticas_cpu()
    if not primera or not segunda:
        return {"cpu_porcentaje": 0}
    delta_total = segunda[0] - primera[0]
    delta_inactivo = segunda[1] - primera[1]
    if delta_total <= 0:
        return {"cpu_porcentaje": 0}
    return {"cpu_porcentaje": round((1 - delta_inactivo / delta_total) * 100, 1)}


def disco_info():
    """Devuelve uso de disco de la raíz en GB y porcentaje."""
    try:
        stat = os.statvfs("/")
        total = stat.f_blocks * stat.f_frsize
        libre = stat.f_bavail * stat.f_frsize
        return {
            "disco_total_gb": round(total / 1024**3, 2),
            "espacio_libre_gb": round(libre / 1024**3, 2),
            "disco_uso_porcentaje": round(
                (1 - libre / total) * 100, 1
            ) if total else 0,
        }
    except OSError:
        return {"disco_total_gb": 0, "espacio_libre_gb": 0, "disco_uso_porcentaje": 0}


def ollama_info():
    """Devuelve modelos cargados (ollama ps) e instalados (ollama list)."""
    cargados = []
    instalados = []
    codigo, salida, _ = _ejecutar(["ollama", "ps"])
    if codigo == 0:
        lineas = salida.splitlines()
        if lineas:
            for linea in lineas[1:]:
                partes = linea.split()
                if partes:
                    cargados.append(partes[0])
    codigo, salida, _ = _ejecutar(["ollama", "list"])
    if codigo == 0:
        lineas = salida.splitlines()
        if lineas:
            for linea in lineas[1:]:
                partes = linea.split()
                if partes:
                    instalados.append(partes[0])
    return {
        "modelos_ollama_cargados": cargados,
        "modelos_ollama_instalados": instalados,
    }


def cache_pacman_mb():
    """Devuelve el tamaño en MB de la caché de Pacman."""
    cache_dir = "/var/cache/pacman/pkg"
    total = 0
    for root, _dirs, archivos in os.walk(cache_dir):
        for nombre in archivos:
            try:
                total += os.path.getsize(os.path.join(root, nombre))
            except OSError:
                pass
    return round(total / 1024**2, 2)


def paquetes_huerfanos():
    """Devuelve la lista de paquetes huérfanos de Pacman."""
    codigo, salida, _ = _ejecutar(["pacman", "-Qtdq"])
    if codigo != 0:
        return []
    return [linea for linea in salida.splitlines() if linea]


def archivos_temporales(antiguedad_horas=24):
    """Devuelve archivos regulares de /tmp con mtime mayor a la antigüedad."""
    limite = time.time() - antiguedad_horas * 3600
    encontrados = []
    try:
        for nombre in os.listdir("/tmp"):
            ruta = os.path.join("/tmp", nombre)
            try:
                if os.path.isfile(ruta) and not os.path.islink(ruta):
                    if os.path.getmtime(ruta) < limite:
                        encontrados.append(ruta)
            except OSError:
                pass
    except OSError:
        pass
    return encontrados


def limpiar_sistema(dry_run=False):
    """Ejecuta la limpieza de caché, huérfanos y temporales.

    Devuelve un dict con el detalle de la limpieza realizada.
    """
    resultado = {"cache_liberada_mb": 0, "huerfanos_eliminados": 0, "temporales_eliminados": 0}
    cache_inicial = cache_pacman_mb()
    huerfanos = paquetes_huerfanos()
    temporales = archivos_temporales()
    resultado["cache_pacman_antes_mb"] = cache_inicial
    resultado["huerfanos_lista"] = huerfanos
    resultado["temporales_lista"] = temporales

    if dry_run:
        return resultado

    if huerfanos:
        _ejecutar(["sudo", "pacman", "-Rns", "--noconfirm", *huerfanos], timeout=120)
        resultado["huerfanos_eliminados"] = len(huerfanos)

    _ejecutar(["sudo", "pacman", "-Sc", "--noconfirm"], timeout=120)
    cache_final = cache_pacman_mb()
    resultado["cache_liberada_mb"] = round(cache_inicial - cache_final, 2)
    resultado["cache_pacman_despues_mb"] = cache_final

    for ruta in temporales:
        try:
            os.remove(ruta)
            resultado["temporales_eliminados"] += 1
        except OSError:
            pass
    return resultado


def diagnosticar():
    """Recopila el estado del sistema y devuelve el dict de salida."""
    resultado = {
        "ram_total_gb": 0,
        "ram_usada_gb": 0,
        "ram_porcentaje": 0,
        "cpu_porcentaje": 0,
        "disco_total_gb": 0,
        "espacio_libre_gb": 0,
        "disco_uso_porcentaje": 0,
        "modelos_ollama_cargados": [],
        "modelos_ollama_instalados": [],
        "paquetes_huerfanos": 0,
        "cache_pacman_mb": 0,
        "limpieza_realizada": False,
        "mensaje": "Monitoreo de recursos completo.",
    }
    resultado.update(ram_info())
    resultado.update(cpu_info())
    resultado.update(disco_info())
    resultado.update(ollama_info())
    resultado["paquetes_huerfanos"] = len(paquetes_huerfanos())
    resultado["cache_pacman_mb"] = cache_pacman_mb()
    return resultado


def main():
    parser = argparse.ArgumentParser(
        description="Mantenimiento y monitoreo de recursos de Arch Linux (salida JSON)"
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="modo solo lectura: diagnosticar recursos (por defecto)",
    )
    parser.add_argument(
        "--limpiar",
        action="store_true",
        help="limpiar caché de Pacman, huérfanos y /tmp",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="con --limpiar, previsualizar acciones sin ejecutarlas",
    )
    args = parser.parse_args()

    resultado = diagnosticar()
    if args.limpiar:
        resultado.update(limpiar_sistema(dry_run=args.dry_run))
        resultado["limpieza_realizada"] = not args.dry_run
        if args.dry_run:
            resultado["mensaje"] = "Previsualización de limpieza (nada se ejecutó)."
        else:
            resultado["mensaje"] = "Limpieza del sistema completada."
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()