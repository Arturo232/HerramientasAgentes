#!/usr/bin/env python3
"""Auditoría WiFi para este PC (Realtek RTL8852BE / driver rtw89).

Módulo de seguridad WiFi orientado al adaptador integrado del equipo:
  - RTL8852BE (802.11ax) con driver rtw89_8852be.
  - Modo monitor: soportado (captura de beacons/frames confirmada).
  - Inyección (aireplay/deauth/WPS): NO fiable en rtw89 → el módulo usa
    captura pasiva + ataque offline por diccionario (WPA2/WPA3-SAE).

Subcomandos:
  status            Estado del adaptador, interfaz, driver y modo.
  monitor on|off    Activa/desactiva el modo monitor (con reversión segura).
  scan              Enumeración de APs cercanos (barrido de canales con tshark).
  capture           Captura un handshake WPA2/WPA3 de un AP objetivo a .cap.
  crack             Ataque offline por diccionario contra una captura .cap.
  words             Lista los diccionarios disponibles.
  lab               Genera config de hostapd para un AP de prueba legal.

SOLO auditar redes propias o con autorización explícita. Ver LEGAL.md.
Salida JSON en stdout para el Agente Local / Orquestador.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time

PROYECTO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DICCIONARIOS = os.path.join(PROYECTO, "diccionarios")
CAPTURAS_DIR = os.path.join(os.path.expanduser("~"), "Documentos", "auditoria_wifi", "capturas")
CANALES_2GHZ = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
CANALES_5GHZ = [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 149, 153, 157, 161, 165]
ADVERTENCIA = (
    "ADVERTENCIA: esta herramienta solo debe usarse en redes propias o con "
    "autorización explícita del propietario. El uso sin permiso es ilegal."
)


def _sudo_base():
    """Devuelve la base del comando sudo: -n, o -S si SUDO_PASS está definida."""
    if os.environ.get("SUDO_PASS"):
        return ["sudo", "-S"]
    return ["sudo", "-n"]


def _ejecutar(comando, timeout=30, stdin_datos=None):
    """Ejecuta un comando y devuelve (returncode, stdout, stderr)."""
    try:
        resultado = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            timeout=timeout,
            input=stdin_datos,
        )
        return resultado.returncode, resultado.stdout.strip(), resultado.stderr.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return 1, "", "error al ejecutar el comando"


def _ejecutar_sudo(comando, timeout=60):
    """Ejecuta un comando con sudo (usa SUDO_PASS si está definida)."""
    base = _sudo_base()
    stdin_datos = None
    if base == ["sudo", "-S"]:
        stdin_datos = os.environ["SUDO_PASS"] + "\n"
    return _ejecutar(base + comando, timeout=timeout, stdin_datos=stdin_datos)


def estado_adaptador():
    """Devuelve el estado actual de la interfaz WiFi."""
    interfaz = "wlan0"
    modo = None
    ssid = None
    codigo, salida, _ = _ejecutar(["iw", "dev"])
    for linea in salida.splitlines():
        if linea.startswith("Interface"):
            interfaz = linea.split()[1]
        if "type" in linea and "ssid" not in linea:
            modo = linea.split("type")[-1].strip()
        if "ssid" in linea:
            ssid = linea.split("ssid")[-1].strip()
    codigo, salida, _ = _ejecutar(["lspci", "-nn"])
    chip = "desconocido"
    for linea in salida.splitlines():
        if "Network controller" in linea:
            chip = linea.split("]:")[-1].strip() if "]: " in linea else linea.strip()
            break
    codigo, salida, _ = _ejecutar(["lsmod"])
    driver = ""
    for linea in salida.splitlines():
        if linea.startswith("rtw89"):
            driver = linea.split()[0]
            break
    codigo, salida, _ = _ejecutar(["rfkill", "list"])
    bloqueado = "no"
    seccion_phy0 = False
    for linea in salida.splitlines():
        if "phy0" in linea:
            seccion_phy0 = True
        elif linea.strip() and not linea.startswith((" ", "\t")):
            seccion_phy0 = False
        if seccion_phy0 and ("Soft blocked: yes" in linea or "Hard blocked: yes" in linea):
            bloqueado = "si"
    codigo, salida, _ = _ejecutar(["ip", "-br", "address"])
    estado_ip = "sin_ip"
    for linea in salida.splitlines():
        if linea.startswith(interfaz):
            partes = linea.split()
            estado_ip = partes[1] if len(partes) >= 2 else "sin_ip"
            break
    return {
        "interfaz": interfaz,
        "driver": driver or "no cargado",
        "chipset": chip,
        "modo": modo or "desconocido",
        "ssid_conectado": ssid or None,
        "rfkill_bloqueado": bloqueado,
        "estado_interfaz": estado_ip,
    }


def modo_monitor(on_off, advertencia_ok=False):
    """Activa/desactiva el modo monitor en wlan0 con reversión segura.

    Devuelve dict con el resultado. Si activar, advierte del corte de WiFi
    gestionado (salvo que exista otra vía, p.ej. tethering USB).
    """
    if on_off == "on" and not advertencia_ok:
        return {
            "exito": False,
            "mensaje": "No se confirmó la advertencia. Usa --autorizado.",
            "nota": ADVERTENCIA,
            "internet_puede_cortarse": (
                "Poner wlan0 en modo monitor desactiva el WiFi gestionado. "
                "Si no hay otra vía de red (USB/ethernet), perderás internet."
            ),
        }
    estado = estado_adaptador()
    acciones = []
    if on_off == "on":
        if estado["modo"] == "monitor":
            return {"exito": True, "mensaje": "ya estaba en modo monitor", "estado": estado}
        # No detener iwd: en rtw89 iwd registra la interfaz wlan0 y al
        # detenerlo desaparece el dispositivo. Solo se detiene NetworkManager
        # para que no vuelva a poner la interfaz en managed.
        codigo, _, err = _ejecutar_sudo(["systemctl", "stop", "NetworkManager"])
        acciones.append(f"detener NetworkManager: {'ok' if codigo == 0 else err}")
        codigo, _, err = _ejecutar_sudo(["ip", "link", "set", "wlan0", "down"])
        acciones.append(f"bajar interfaz: {'ok' if codigo == 0 else err}")
        codigo, _, err = _ejecutar_sudo(["iw", "dev", "wlan0", "set", "type", "monitor"])
        acciones.append(f"tipo monitor: {'ok' if codigo == 0 else err}")
        if codigo != 0:
            _restaurar_red()
            return {"exito": False, "mensaje": f"no se pudo activar monitor: {err}", "acciones": acciones}
        codigo, _, err = _ejecutar_sudo(["ip", "link", "set", "wlan0", "up"])
        acciones.append(f"subir interfaz: {'ok' if codigo == 0 else err}")
    else:
        if estado["modo"] != "monitor":
            return {"exito": True, "mensaje": "ya estaba en modo managed", "estado": estado}
        _restaurar_red()
    estado_final = estado_adaptador()
    return {
        "exito": True,
        "modo": on_off,
        "mensaje": f"modo {on_off} aplicado",
        "acciones": acciones,
        "estado_final": estado_final,
    }


def _restaurar_red():
    """Vuelve wlan0 a modo managed y reinicia los servicios de red."""
    _ejecutar_sudo(["ip", "link", "set", "wlan0", "down"])
    _ejecutar_sudo(["iw", "dev", "wlan0", "set", "type", "managed"])
    _ejecutar_sudo(["ip", "link", "set", "wlan0", "up"])
    _ejecutar_sudo(["systemctl", "start", "NetworkManager"])
    time.sleep(2)


def _en_monitor(duracion=8, canal_fijo=None):
    """Ejecuta una función con wlan0 en modo monitor y restaura al final.

    Contexto: pone la interfaz en monitor, espera `duracion` segundos y
    devuelve el resultado; SIEMPRE restaura la red (try/finally).
    """
    prep = modo_monitor("on", advertencia_ok=True)
    if not prep.get("exito"):
        return {"exito": False, "mensaje": prep.get("mensaje", "no se pudo entrar en monitor")}
    try:
        if canal_fijo:
            _ejecutar_sudo(["iw", "dev", "wlan0", "set", "channel", str(canal_fijo)])
        time.sleep(1)
        return {"exito": True, "monitor_ok": True}
    finally:
        _restaurar_red()


def _decodificar_ssid(valor):
    """Decodifica el SSID: tshark lo emite como bytes hex."""
    if not valor:
        return "(oculto)"
    if all(c in "0123456789abcdefABCDEF" for c in valor) and len(valor) % 2 == 0:
        try:
            texto = bytes.fromhex(valor).decode("utf-8", errors="replace")
            if texto.strip():
                return texto
        except ValueError:
            pass
    return valor


def scan(duracion=8, bandas="abg"):
    """Barrido de canales en modo monitor con tshark; devuelve APs únicos.

    En rtw89 airodump-ng no gira canales solo, por eso se recorre cada canal
    fijándolo y capturando beacons (wlan.fc.type_subtype == 8). El cifrado
    se deduce de los Information Elements (wlan.tag.number): 48=RSN/WPA2,
    221=Vendor (WPA/WME).
    """
    canales = []
    if bandas in ("b", "bg", "abg"):
        canales += list(CANALES_2GHZ)
    if bandas in ("a", "ag", "abg"):
        canales += CANALES_5GHZ
    if not canales:
        canales = list(CANALES_2GHZ)
    apes = {}
    total_frames = 0
    errores = []
    estado = estado_adaptador()
    preparacion = modo_monitor("on", advertencia_ok=True)
    if not preparacion.get("exito"):
        return {"exito": False, "mensaje": preparacion.get("mensaje", "no se pudo entrar en monitor")}
    try:
        time.sleep(3)
        for canal in canales:
            _ejecutar_sudo(["iw", "dev", "wlan0", "set", "channel", str(canal)])
            time.sleep(1.5)
            campos = ("-e", "wlan.sa", "-e", "wlan.ssid", "-e", "wlan.ds.current_channel",
                      "-e", "wlan_radio.signal_dbm", "-e", "wlan.tag.number")
            segundos = max(3, duracion // 3)
            codigo, salida, err = _ejecutar_sudo(
                ["timeout", str(segundos), "tshark", "-i", "wlan0",
                 "-Y", "wlan.fc.type_subtype == 8", "-T", "fields"] + list(campos),
                timeout=segundos + 10)
            if codigo != 0 and codigo != 124:
                errores.append(f"canal {canal}: {err[:80]}")
                continue
            if codigo == 124 and not salida:
                continue
            for linea in salida.splitlines():
                partes = linea.split("\t")
                if len(partes) < 2 or not partes[0]:
                    continue
                bssid = partes[0].upper()
                ssid = _decodificar_ssid(partes[1]) if len(partes) > 1 else "(oculto)"
                canal_det = partes[2] if len(partes) > 2 and partes[2] else canal
                rssi = None
                try:
                    if len(partes) > 3 and partes[3]:
                        rssi = int(round(float(partes[3])))
                except ValueError:
                    rssi = None
                tags = []
                if len(partes) > 4 and partes[4]:
                    tags = [int(t) for t in partes[4].split(",") if t.strip().isdigit()]
                cifrado = _detectar_cifrado_por_tags(tags)
                if bssid not in apes:
                    apes[bssid] = {
                        "bssid": bssid, "ssid": ssid, "canal": int(canal_det),
                        "rssi": rssi, "cifrado": cifrado,
                    }
                else:
                    prev = apes[bssid]
                    if prev["rssi"] is None and rssi is not None:
                        prev["rssi"] = rssi
                    if prev["cifrado"] == "desconocido/abierto":
                        prev["cifrado"] = cifrado
                total_frames += 1
    finally:
        _restaurar_red()
    lista = sorted(apes.values(), key=lambda a: (a["rssi"] is None, -(a["rssi"] or -100)))
    return {
        "exito": True,
        "aps_encontrados": len(lista),
        "frames_beacon": total_frames,
        "canales_2ghz": len(CANALES_2GHZ),
        "canales_5ghz": sum(1 for c in canales if c in CANALES_5GHZ),
        "aps": lista,
        "errores": errores[:5],
        "nota": "Modo monitor restaurado automáticamente al finalizar.",
    }


def _detectar_cifrado_por_tags(tags):
    """Clasifica el cifrado desde los Information Elements del beacon.

    48 = RSN (WPA2/WPA3), 221 = Vendor (WPA-PSK o WME), 3 = Current channel.
    Sin tag de seguridad -> red abierta.
    """
    if 48 in tags:
        return "WPA2/WPA3"
    if 221 in tags:
        return "WPA-PSK"
    if tags:
        return "probablemente abierta"
    return "desconocido/abierto"


def capture(bssid, canal, duracion=60, salida=None):
    """Captura un handshake (EAPOL 4-way) de un AP objetivo a un .cap.

    Fija el canal del AP y captura con tshark filtrando EAPOL
    (wlan_rsna_eapol.keydes.msgs), incluida la reintento de autenticación
    pasiva. Guarda en CAPTURAS_DIR o en `salida`.
    """
    bssid = bssid.upper()
    if not re.fullmatch(r"([0-9A-F]{2}:){5}[0-9A-F]{2}", bssid):
        return {"exito": False, "mensaje": f"BSSID inválido: {bssid}"}
    if not salida:
        os.makedirs(CAPTURAS_DIR, exist_ok=True)
        salida = os.path.join(CAPTURAS_DIR, f"captura_{bssid.replace(':', '')}.cap")
    # dumpcap/tshark como root no puede escribir en rutas de usuario por
    # su perfil de seguridad; se captura en /tmp (root) y se mueve al final.
    temp_archivo = f"/tmp/auditoria_wifi_{int(time.time())}.cap"
    prep = modo_monitor("on", advertencia_ok=True)
    if not prep.get("exito"):
        return {"exito": False, "mensaje": prep.get("mensaje", "no se pudo entrar en monitor")}
    try:
        _ejecutar_sudo(["iw", "dev", "wlan0", "set", "channel", str(canal)])
        time.sleep(3)
        # Filtro de captura BPF: solo tramas de gestión (0x00) que suelen
        # contener los EAPOL del handshake + beacons. tshark no permite -Y
        # con -w, por eso se filtra al analizar después.
        codigo, _, err = _ejecutar_sudo(
            ["timeout", str(duracion), "tshark", "-i", "wlan0", "-w", temp_archivo],
            timeout=duracion + 20)
        if codigo not in (0, 124):  # 124 = timeout (normal, terminó la captura)
            return {"exito": False, "mensaje": f"error de captura: {err[:150]}"}
        if not os.path.exists(temp_archivo):
            return {"exito": False, "mensaje": "tshark no generó el archivo de captura"}
        _ejecutar_sudo(["chown", "arturo:arturo", temp_archivo])
        _ejecutar(["cp", temp_archivo, salida])
        os.remove(temp_archivo)
        # Verificar si hay EAPOL en la captura
        codigo2, salida2, _ = _ejecutar(
            ["tshark", "-r", salida, "-Y", "eapol", "-c", "10"])
        eapol_frames = len([l for l in salida2.splitlines() if l.strip()])
        ok_tam = os.path.getsize(salida) if os.path.exists(salida) else 0
        return {
            "exito": True,
            "archivo": salida,
            "tamano_bytes": ok_tam,
            "frames_eapol": eapol_frames,
            "handshake_capturado": eapol_frames >= 2,
            "mensaje": (
                "Handshake capturado. Listo para crack."
                if eapol_frames >= 2
                else "Captura guardada, pero sin frames EAPOL aún."
            ),
        }
    finally:
        _restaurar_red()


def crack(captura, diccionario=None, tiempo_max=120):
    """Ataque offline por diccionario WPA2/WPA3-SAE contra un .cap."""
    if not os.path.isfile(captura):
        return {"exito": False, "mensaje": f"captura no encontrada: {captura}"}
    dicts = diccionarios_disponibles()
    if not diccionario:
        candidatos = [
            d["ruta"] for d in dicts
            if d["nombre"].startswith(("wpa-probable-top204k", "rockyou"))
        ]
        diccionario = candidatos[0] if candidatos else (dicts[0]["ruta"] if dicts else None)
    if not diccionario or not os.path.isfile(diccionario):
        return {"exito": False, "mensaje": "no hay diccionario disponible. Usa --diccionario."}
    codigo, salida, err = _ejecutar(
        ["timeout", str(tiempo_max), "aircrack-ng", "-w", diccionario, captura],
        timeout=tiempo_max + 20)
    salida_limpia = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", salida)
    encontrada = None
    intentadas = 0
    for linea in salida_limpia.splitlines():
        m = re.search(r"KEY\s*FOUND!\s*\[\s*([^\]]+?)\s*\]", linea)
        if m:
            encontrada = m.group(1).strip()
        m2 = re.search(r"(\d+)/\d+\s+keys\s+tested", linea, re.IGNORECASE)
        if m2:
            intentadas = int(m2.group(1))
    return {
        "exito": True,
        "captura": captura,
        "diccionario": os.path.basename(diccionario),
        "clave_encontrada": encontrada,
        "claves_probadas": intentadas,
        "tiempo_limite_s": tiempo_max,
        "mensaje": (
            f"Contraseña encontrada: {encontrada}"
            if encontrada else "No se encontró con el diccionario usado."
        ),
    }


def diccionarios_disponibles():
    """Lista los diccionarios de contraseñas disponibles."""
    lista = []
    if os.path.isdir(DICCIONARIOS):
        for nombre in sorted(os.listdir(DICCIONARIOS)):
            ruta = os.path.join(DICCIONARIOS, nombre)
            if os.path.isfile(ruta):
                try:
                    tam = os.path.getsize(ruta)
                except OSError:
                    tam = 0
                lista.append({
                    "nombre": nombre, "ruta": ruta,
                    "tamano_bytes": tam, "tamano_humano": f"{tam/1048576:.1f} MB" if tam > 1048576 else f"{tam/1024:.0f} KB",
                })
    return lista


def generar_lab(nombre="AP_LAB_ESPAÑOL", contrasena="laboratorio123", canal=6):
    """Genera la configuración de hostapd para un AP de prueba (uso legal)."""
    conf = f"""interface=wlan0
driver=nl80211
ssid={nombre}
hw_mode=g
channel={canal}
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase={contrasena}
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
"""
    ruta = os.path.join(os.path.expanduser("~"), "Documentos", "auditoria_wifi", "hostapd_lab.conf")
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(conf)
    return {
        "exito": True,
        "config": ruta,
        "ssid": nombre,
        "contrasena": contrasena,
        "canal": canal,
        "mensaje": (
            "AP de prueba configurado. NO ejecutes hostapd en wlan0 mientras "
            "uses el modo monitor en la misma interfaz (se necesitan dos "
            "adaptadores). Es solo para laboratorio propio."
        ),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Auditoría WiFi de este PC (RTL8852BE/rtw89). Salida JSON.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=ADVERTENCIA,
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    p_status = sub.add_parser("status", help="estado del adaptador")
    p_status.set_defaults(func=lambda a: estado_adaptador())

    p_mon = sub.add_parser("monitor", help="activa/desactiva el modo monitor")
    p_mon.add_argument("on_off", choices=["on", "off"])
    p_mon.add_argument("--autorizado", action="store_true",
                       help="confirmar uso autorizado de la advertencia")
    p_mon.set_defaults(func=lambda a: modo_monitor(a.on_off, a.autorizado))

    p_scan = sub.add_parser("scan", help="escaneo de APs cercanos")
    p_scan.add_argument("--duracion", type=int, default=8, help="segundos de captura por pasada")
    p_scan.add_argument("--bandas", default="abg", choices=["bg", "a", "abg"])
    p_scan.set_defaults(func=lambda a: scan(a.duracion, a.bandas))

    p_cap = sub.add_parser("capture", help="captura de handshake a .cap")
    p_cap.add_argument("--bssid", required=True, help="BSSID del AP objetivo (AA:BB:..)")
    p_cap.add_argument("--canal", type=int, required=True)
    p_cap.add_argument("--duracion", type=int, default=60, help="segundos de captura")
    p_cap.add_argument("--salida", default=None)
    p_cap.set_defaults(func=lambda a: capture(a.bssid, a.canal, a.duracion, a.salida))

    p_crack = sub.add_parser("crack", help="crack offline por diccionario")
    p_crack.add_argument("--captura", required=True)
    p_crack.add_argument("--diccionario", default=None)
    p_crack.add_argument("--tiempo-max", type=int, default=120)
    p_crack.set_defaults(func=lambda a: crack(a.captura, a.diccionario, a.tiempo_max))

    p_words = sub.add_parser("words", help="lista diccionarios disponibles")
    p_words.set_defaults(func=lambda a: {"exito": True, "diccionarios": diccionarios_disponibles()})

    p_lab = sub.add_parser("lab", help="configura un AP de prueba legal")
    p_lab.add_argument("--ssid", default="AP_LAB_ESPAÑOL")
    p_lab.add_argument("--contrasena", default="laboratorio123")
    p_lab.add_argument("--canal", type=int, default=6)
    p_lab.set_defaults(func=lambda a: generar_lab(a.ssid, a.contrasena, a.canal))

    args = parser.parse_args()
    resultado = args.func(args)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()