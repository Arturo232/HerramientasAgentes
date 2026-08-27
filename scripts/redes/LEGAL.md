# Aviso legal — Auditoría WiFi

## Uso permitido

El módulo `scripts/redes/auditoria_wifi.py` (incluido el subcomando `clon`,
que crea una red gemela/evil twin con portal cautivo) y las herramientas
instaladas (aircrack-ng, reaver, bully, pixiewps, wifite, hashcat, john,
tshark, wireshark, nmap, mdk4, kismet, bettercap, macchanger, hostapd,
dnsmasq) son instrumentos de **auditoría de seguridad profesional**.

Su uso está permitido ÚNICAMENTE en:

1. **Redes de tu propiedad** (tu router, tu laboratorio).
2. **Redes sobre las que tienes autorización escrita/explícita** del
   propietario (contratos de pentesting, auditorías contratadas).

El **clon de red / portal cautivo** es una técnica de ingeniería social
dirigida a usuarios. Solo es legal en ejercicios de auditoría autorizados
(donde los participantes han dado su consentimiento), **nunca** contra
usuarios reales sin autorización.

## Prohibiciones

- Acceder, capturar, descifrar o interferir redes de terceros **sin permiso**
  es ilegal en la mayoría de jurisdicciones (acceso no autorizado a sistemas
  informáticos, interceptación de comunicaciones).
- Las penas incluyen multas y prisión. En Colombia: Ley 1273 de 2009
  (protección de datos e información), entre otras.

## Responsabilidad

El propietario del equipo es el único responsable del uso que dé a estas
herramientas. Este repositorio se proporciona con fines **educativos y de
seguridad defensiva** (validar la fortaleza de tus propias claves y redes).

## Uso responsable recomendado

- Probar el flujo completo en un **laboratorio propio**: crea un AP de
  prueba con `hostapd` (`auditoria_wifi.py lab`) y rompe SU clave para
  validar la robustez de tus contraseñas.
- Si una clave se descifra en tu propia red: es la señal para cambiarla
  por una más larga y con entropía real.
