# Manual de auditoría WiFi — este PC (RTL8852BE / rtw89)

## Hardware verificado

| Componente | Valor |
|---|---|
| Adaptador | Realtek RTL8852BE PCIe (802.11ax) |
| Driver | `rtw89_8852be` (kernel 6.18 LTS) |
| Modo monitor | ✅ Soportado (captura pasiva) |
| Inyección (aireplay/deauth) | ⚠️ No fiable en rtw89 |
| Ataques WPS (reaver/bully/wifite) | ⚠️ Dependen de inyección — no fiables |
| Estrategia del módulo | **Captura pasiva + crack offline por diccionario** |

## Requisitos previos

1. **Internet por otra vía**: el escaneo/captura pone `wlan0` en modo monitor
   y desconecta el WiFi. Usa tethering USB (`enp5s0f3u2`) o ethernet.
   El módulo **restaura la red automáticamente** al finalizar cada comando.
2. **sudo**: `echo 'TU_PASS' | sudo -S ...` o `SUDO_PASS=TU_PASS`.

## Comandos del módulo

```bash
cd ~/Documentos/HerramientasAgente

# Estado del adaptador
.venv/bin/python scripts/redes/auditoria_wifi.py status

# Escaneo de APs cercanos (2.4GHz y/o 5GHz)
SUDO_PASS='...' .venv/bin/python scripts/redes/auditoria_wifi.py scan --bandas abg --duracion 20

# Modo monitor manual (con reversión: monitor off)
SUDO_PASS='...' .venv/bin/python scripts/redes/auditoria_wifi.py monitor on --autorizado
SUDO_PASS='...' .venv/bin/python scripts/redes/auditoria_wifi.py monitor off

# Capturar handshake de un AP (canal fijado)
SUDO_PASS='...' .venv/bin/python scripts/redes/auditoria_wifi.py capture \
  --bssid AA:BB:CC:DD:EE:FF --canal 6 --duracion 60

# Crack offline por diccionario
.venv/bin/python scripts/redes/auditoria_wifi.py crack \
  --captura ~/Documentos/auditoria_wifi/capturas/captura_XXXX.cap

# Diccionarios disponibles
.venv/bin/python scripts/redes/auditoria_wifi.py words

# Laboratorio propio (AP de prueba legal)
.venv/bin/python scripts/redes/auditoria_wifi.py lab
```

## Flujo recomendado (end-to-end)

1. `scan` → elige tu objetivo (BSSID, canal, cifrado).
2. `capture --bssid ... --canal ...` → espera a que un dispositivo se
   conecte (o recarga el dispositivo) para capturar el 4-way handshake.
   **En rtw89 no se puede forzar con deauth**; la captura es pasiva.
3. `crack --captura ...` → prueba con `wpa-probable-top4800` (rápido),
   luego `wpa-probable-top204k`, luego `rockyou` (completo).
4. Si no se descifra en 5 minutos, la clave es robusta (WPA3-SAE o WPA2
   con clave larga no está en diccionarios) — conclusión de auditoría.

## Diccionarios

Ubicación: `~/Documentos/HerramientasAgente/diccionarios/`

| Archivo | Contraseñas | Uso |
|---|---|---|
| `wpa-probable-top4800.txt` | 4.800 | Primer intento (segundos) |
| `wpa-probable-top204k.txt` | 203.806 | Segundo intento (1-2 min) |
| `rockyou.txt` | 14.344.391 | Ataque completo (minutos-horas) |

## Herramientas instaladas (kit completo)

- **Captura/análisis**: aircrack-ng (airmon-ng, airodump-ng, aireplay-ng),
  tshark/wireshark, wavemon, kismet
- **WPS**: reaver, bully, pixiewps, wifite (⚠️ requieren inyección)
- **Crack offline**: hashcat, john, aircrack-ng
- **Red**: nmap, mdk4, bettercap, macchanger

## Aviso legal

Ver `scripts/redes/LEGAL.md`. Solo redes propias o con autorización.
El uso no autorizado es ilegal.
