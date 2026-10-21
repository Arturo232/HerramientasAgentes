# Agente de correo 24/7

Convierte la estación Arch Linux en un nodo autónomo controlado por correo:
Arturo envía un mensaje desde **una única dirección autorizada**, el agente lo
procesa en local con el selector determinista de `HerramientasAgente`, ejecuta
una herramienta de la lista blanca y responde **en el mismo hilo** con el
resultado, adjuntos pequeños o enlaces de Google Drive.

```
Gmail (cuenta del agente)
   │  polling Gmail API cada 50 s (NAT, sin endpoint público)
   ▼
listener.py ──► parser.py ──► lista blanca exacta + dedupe SQLite
   │                              │
   │                              ├─ PAUSA / STOP / REANUDAR
   │                              └─ orquestador.py
   │                                     │  subprocess argv (sin shell)
   │                                     ▼
   │                         selector_herramientas.py  (JSON)
   │                                     │
   │                                     ▼
   │                         script registrado + args filtrados
   ▼
dispatcher.py ──► Gmail send (threadId + In-Reply-To/References)
                └─► Drive (si el total > MAX_ADJUNTOS_MB)
```

## Decisiones de diseño

| Tema | Decisión |
|---|---|
| Transporte | Gmail API + OAuth 2.0 installed-app con loopback, **polling cada 45-60 s** (`POLL_SEGUNDOS=50`). No hay endpoint público ni Pub/Sub. |
| Scopes | `gmail.modify`, `gmail.send`, `drive.file`. Nada de `mail.google.com` ni `drive` completo. |
| Respuesta | Mismo hilo: `threadId` + `In-Reply-To` + `References`. |
| Adjuntos | Total ≤ `MAX_ADJUNTOS_MB` (20 MB): adjuntos en el correo. Si supera, o si el MIME codificado pasa de 24 MB, se sube a Drive y se envía el `webViewLink`. |
| Drive | Se comparte **solo con `AUTORIZADO_FROM` como lector**; nunca `anyone with link`. |
| Lista blanca | Comparación exacta y case-insensitive de la dirección parseada de `From` contra `AUTORIZADO_FROM`. Default: denegar. |
| Ejecución | Solo el selector y solo herramientas de `HERRAMIENTAS_PERMITIDAS`. Sin bash, sin eval, sin código del correo. |
| Idempotencia | SQLite con `message_id` (o id de Gmail) como clave primaria; se marca leído y etiqueta al terminar. |
| Límites | `MAX_TAREAS_HORA` (6 por defecto) + `PAUSA`/`STOP` hasta `REANUDAR`. |
| Servicio | Unidad **systemd de usuario**, `Restart=always`, `EnvironmentFile=.env` (600), journald y endurecimiento. |
| Energía | Scripts de máscara de suspensión y tapa; por defecto **solo muestran el plan**, aplican con `--aplicar`. |

### Por qué polling y no Pub/Sub

La estación está detrás de NAT y no tiene endpoint público. Pub/Sub push
necesitaría un túnel HTTPS permanente y verificación de dominio. El polling
cada 50 s entra dentro de la cuota gratuita de Gmail API para una sola cuenta y
es suficiente para órdenes humanas.

### Fallback documentado: IMAP IDLE + SMTP (no implementado)

Si en el futuro se quiere evitar OAuth o la verificación de Google:

- `imaplib.IMAP4_SSL("imap.gmail.com", 993)` con contraseña de aplicación
  (requiere 2FA) o `XOAUTH2` con el mismo token.
- `IDLE` no existe de forma nativa en `imaplib`; usar `imaplib2` o polling
  `SEARCH UNSEEN` cada 50 s. El listener, el parser, la lista blanca, SQLite y
  el dispatcher se reutilizan tal cual.
- Envío con `smtplib.SMTP("smtp.gmail.com", 587)` + STARTTLS y el mismo
  `Message-ID`/`In-Reply-To`/`References` para conservar el hilo.
- Motivo para no usarlo como primario: las contraseñas de aplicación son un
  secreto de larga vida (peor que un refresh token revocable), Gmail las está
  retirando para algunas cuentas y no ofrecen `threadId` ni etiquetas nativas.

## 1. Google Cloud Console (una vez)

1. Entra en <https://console.cloud.google.com/> con la cuenta del agente
   (`caballerotaitus7@gmail.com`).
2. **Crear proyecto** (por ejemplo `agente-correo-arturo`).
3. **APIs y servicios → Biblioteca**:
   - Habilitar **Gmail API**.
   - Habilitar **Google Drive API**.
4. **APIs y servicios → Pantalla de consentimiento OAuth**:
   - Tipo de usuario: **External**.
   - Nombre de la app, correo de asistencia y correo del desarrollador.
   - En **Usuarios de prueba**, agrega la dirección personal que será
     `AUTORIZADO_FROM`.
   - En **Permisos/Scopes**, agrega:
     - `https://www.googleapis.com/auth/gmail.modify`
     - `https://www.googleapis.com/auth/gmail.send`
     - `https://www.googleapis.com/auth/drive.file`
5. **Publicar la app en producción** (botón *Publish app*).
   - En estado **Testing**, Google caduca los refresh tokens a los **7 días**.
   - En **Production** el refresh token no caduca por esa regla.
   - `gmail.modify` y `gmail.send` son scopes restringidos: si Google exige
     verificación, una app personal con pocos usuarios puede seguir usando
     usuarios de prueba, pero volverá la caducidad de 7 días. Alternativas:
     cuenta de Google Workspace con app **Internal**, o reautorizar cada
     semana. Para uso personal, publicar y completar la verificación si Google
     la solicita es el camino recomendado.
6. **APIs y servicios → Credenciales → Crear credenciales → ID de cliente
   OAuth**:
   - Tipo: **Aplicación de escritorio** (Desktop app).
   - Descargar el JSON.
   - Guardarlo como
     `~/Documentos/HerramientasAgente/agente_correo/secrets/client_secret.json`
     con `chmod 600`.
7. La primera autorización abrirá `http://localhost:8765`. El cliente Desktop
   admite loopback en cualquier puerto; no hace falta registrar la URI.

> El `client_secret.json` y el `token.json` **no se versionan**. El
> `.gitignore` del módulo excluye `secrets/`, `.env`, `*.db` y `out/`.

## 2. Instalación

```bash
cd ~/Documentos/HerramientasAgente/agente_correo
cp .env.example .env
chmod 600 .env
$EDITOR .env          # AUTORIZADO_FROM, GMAIL_USER, DRIVE_FOLDER_ID
./bin/instalar.sh     # venv del repo + deps + directorios + tests + unidad
```

`instalar.sh` usa el `.venv` existente del repositorio (el mismo que usan los
scripts del selector). Si no existe, lo crea e instala `requirements.txt` del
repo. No arranca el servicio salvo `--arrancar`.

### Autorizar OAuth

Desde la raíz del repositorio, para que el paquete `agente_correo` sea
importable:

```bash
cd ~/Documentos/HerramientasAgente
.venv/bin/python -m agente_correo.oauth_login
.venv/bin/python -m agente_correo.oauth_login --check
```

El flujo abre el navegador, pide consentimiento y guarda
`agente_correo/secrets/token.json` con permisos `600`. El listener refresca el
access token solo; si el refresh token se revoca o caduca, hay que repetir
`oauth_login`.

### Prueba sin credenciales reales (obligatoria antes de arrancar)

```bash
cd ~/Documentos/HerramientasAgente
AUTORIZADO_FROM=arturo@example.com \
GMAIL_USER=caballerotaitus7@gmail.com \
.venv/bin/python -m agente_correo.listener --once --dry-run \
  --fixture agente_correo/tests/fixtures
```

Esto **no lee Gmail, no ejecuta herramientas y no envía correo**. Escribe los
`.eml` simulados en `agente_correo/out/dry-run/` y muestra en el log qué
herramienta se habría ejecutado. Los fixtures incluyen un correo autorizado,
uno denegado, una auto-respuesta y un `PAUSA`.

También se puede usar `--dry-run` con credenciales reales para leer los no
leídos y simular; en ese caso no marca leído ni etiqueta.

### Procesar una vez de verdad

```bash
cd ~/Documentos/HerramientasAgente
.venv/bin/python -m agente_correo.listener --once
```

No ejecutes `--once` mientras `agente-correo.service` está activo: dos
listeners sobre la misma bandeja y la misma SQLite pueden competir. Para una
prueba real, detén el servicio primero (`systemctl --user stop ...`).

### Servicio 24/7

```bash
systemctl --user enable --now agente-correo.service
systemctl --user status agente-correo.service
journalctl --user -u agente-correo.service -f
sudo loginctl enable-linger arturo   # sobrevive al cierre de sesión
```

La unidad está en `service/agente-correo.service` y se instala en
`~/.config/systemd/user/`. `WorkingDirectory` es la raíz del repo para que
`python -m agente_correo.listener` encuentre el paquete.

Endurecimiento incluido: `NoNewPrivileges=yes`, `PrivateTmp=yes`,
`ProtectSystem=strict`, `ProtectHome=read-only`, `ReadWritePaths` solo para
`data/` y `out/`, `ProtectKernelTunables`, `ProtectControlGroups`,
`ProtectKernelModules`, `RestrictSUIDSGID`, `RestrictRealtime`,
`LockPersonality` y `UMask=0077`.

`secrets/` queda de solo lectura para el servicio: el access token refrescado
se mantiene en memoria. Si Google rotara el refresh token, se ejecuta
`oauth_login` de nuevo. Esto evita que un compromiso del proceso pueda
reescribir el token.

> Si cambias `REPO_DIR`, `PYTHON_BIN`, `DIR_DATOS` o `DIR_SALIDA` en `.env`,
> actualiza también `WorkingDirectory`, `ExecStart` y `ReadWritePaths` de la
> unidad; el sandbox de systemd no lee esas rutas desde `.env`.

## 3. Protocolo de correo

El cuerpo es la intención en lenguaje natural. Si el cuerpo está vacío se usa
el asunto. Se ignoran citas (`>`), firmas (`--`) y el texto de respuestas
anteriores.

Ejemplos:

| Correo (cuerpo) | Herramienta | Argumentos efectivos |
|---|---|---|
| `estado del sistema` | `sistema` | `--info` |
| `diagnóstico de red` | `redes` | `--sin-reconexion` (por defecto) |
| `genera un excel de prueba` | `datos` | `--test --salida out/reporte-*.xlsx` |
| `PAUSA` o `STOP` | — | pausa el procesamiento |
| `REANUDAR` | — | reactiva el procesamiento |

- **PAUSA/STOP/REANUDAR** deben ser una palabra sola en las primeras líneas
  útiles. `no pares el servidor` no activa nada.
- Mientras está pausado, los correos normales **no se reservan ni se marcan**:
  quedan no leídos para procesarse después de `REANUDAR`.
- Los correos de direcciones no autorizadas se registran en el log, se
  etiquetan `AgenteCorreo/Denegado`, se archivan y **no reciben respuesta**
  (evita backscatter).
- Las auto-respuestas (`Auto-Submitted`, `X-Autoreply`, `Precedence: bulk`) y
  los mensajes enviados por la propia cuenta del agente se descartan.
- El asunto de la respuesta es `Re: <original>`; se conserva el hilo.
- Los adjuntos **entrantes no se procesan**: el correo es una orden, no un
  canal para subir archivos. Los adjuntos son siempre de salida. Para `libro`,
  el PDF debe colocarse manualmente en `entrada/`.

### Enviar correo o responder en un hilo (CLI)

`enviar.py` es el puente que usa el agente/chat para redactar y enviar correos
sin pasar por el listener. Reutiliza el mismo cliente de Gmail y el mismo
generador MIME:

```bash
cd ~/Documentos/HerramientasAgente

# Simulación: escribe out/envios-dry-run/*.eml y no envía
.venv/bin/python -m agente_correo.enviar \
  --para arturo@example.com --asunto "Hola" --cuerpo "Mensaje" --dry-run

# Envío real con adjunto
.venv/bin/python -m agente_correo.enviar \
  --para arturo@example.com --asunto "Informe" \
  --cuerpo-archivo out/cuerpo.txt --adjunto out/informe.pdf

# Respuesta en el mismo hilo
.venv/bin/python -m agente_correo.enviar \
  --para arturo@example.com --responder-a 18f0c2... --cuerpo "Recibido"
```

La salida estándar es un único JSON con `ok`, `mensaje_id`, `hilo`,
`destinatarios`, `adjuntos` y `dry_run` (más `ruta_eml` en dry-run y `error`
si falla). Los mensajes legibles van a `stderr`.

Decisiones de seguridad:

- Destinatarios permitidos: `DESTINATARIOS_PERMITIDOS` (coma o punto y coma);
  si falta, se usa `AUTORIZADO_FROM`. `--confirmar` abre la lista solo para esa
  ejecución.
- `--adjunto` y `--cuerpo-archivo` deben estar dentro de `entrada/` u `out/`.
  `--permitir-rutas-externas` autoriza una ruta concreta fuera de ellos; se
  resuelven symlinks antes de comprobar.
- Se aplican `MAX_ADJUNTOS_MB`, `MAX_ARTEFACTO_MB` y el límite de 24 MB de
  Gmail. Este puente **no sube a Drive**: si algo supera el límite, falla.
- `--dry-run` no construye el servicio de Gmail salvo que `--responder-a`
  necesite leer el original.

### Lista blanca por defecto

`HERRAMIENTAS_PERMITIDAS=sistema,redes,datos`.

- `sistema`: solo `--info`. `--limpiar` se rechaza por correo.
- `redes`: solo diagnóstico. La reconexión se fuerza a `--sin-reconexion`
  salvo `PERMITIR_RECONEXION=1`.
- `datos`: solo el reporte de prueba `--test`; la ruta de salida la impone el
  agente dentro de `out/`, nunca el correo.
- `libro`: no está en la lista por defecto. Si se habilita, el PDF debe estar
  dentro de `entrada/` y la salida se fuerza a `out/`.
- `auditoria_wifi`: no está en la lista. Si se habilita, solo se permite
  `status`; escaneo/captura/crack requieren sudo y autorización legal.

Para habilitar otra herramienta hay que añadirla a `HERRAMIENTAS_PERMITIDAS`
**y** que exista en `scripts/orquestador/selector_herramientas.py` y en
`capacidades.json`. Si no existe una política de argumentos en
`orquestador.py`, se rechaza por seguridad.

## 4. Integración exacta con el selector existente

`orquestador.py` no reimplementa el enrutado. Ejecuta el selector como
subproceso, con `argv` y sin shell:

```bash
/home/arturo/Documentos/HerramientasAgente/.venv/bin/python \
  /home/arturo/Documentos/HerramientasAgente/scripts/orquestador/selector_herramientas.py \
  --intencion="estado del sistema"
```

El selector imprime JSON por `stdout`:

```json
{
  "exito": true,
  "herramienta": "sistema",
  "script": "scripts/sistema/mantenimiento_pc.py",
  "argumentos": ["--info"],
  "comando_sugerido": "python3 scripts/sistema/mantenimiento_pc.py --info"
}
```

El puente valida, en este orden:

1. `exito == true` y `herramienta` está en `HERRAMIENTAS_PERMITIDAS`.
2. `script` coincide exactamente con el catálogo del selector (`--listar`) y
   con la entrada de `capacidades.json`. Los nombres del selector se mapean a
   los ids del catálogo: `redes`→`red`, `datos`→`excel`,
   `auditoria_wifi`→`wifi`; `sistema` y `libro` coinciden.
3. La ruta resuelta no sale del repositorio y es un archivo regular.
4. Los argumentos son textos sin NUL/saltos y pasan la política de la
   herramienta.
5. Se ejecuta con el Python del venv, `cwd` fijo en la raíz del repo, un
   entorno mínimo sin tokens y `timeout=TIEMPO_TAREA`.

El resultado se lee de `stdout` (JSON de los scripts actuales); si no es JSON,
se envía la salida cruda recortada. Los artefactos solo se aceptan dentro de
`out/` y con extensiones conocidas.

## 5. Variables de `.env`

| Variable | Obligatoria | Default | Uso |
|---|---|---|---|
| `GMAIL_USER` | sí | — | Cuenta que envía/recibe. |
| `AUTORIZADO_FROM` | sí | — | Única dirección que puede ordenar. Exacta, case-insensitive. |
| `DESTINATARIOS_PERMITIDOS` | no | `AUTORIZADO_FROM` | Lista (coma) a la que `enviar.py` puede escribir. |
| `GOOGLE_CLIENT_SECRET` | sí para OAuth | `secrets/client_secret.json` | JSON de cliente Desktop. |
| `GOOGLE_TOKEN` | sí para OAuth | `secrets/token.json` | Token con permisos 600. |
| `OAUTH_PORT` | no | `8765` | Puerto loopback. |
| `DRIVE_FOLDER_ID` | no | vacío | Carpeta de Drive; si no es accesible, se usa/crea `AgenteCorreo`. |
| `REPO_DIR` | no | raíz del repo | Cwd y base del selector. |
| `PYTHON_BIN` | no | `.venv/bin/python` | Intérprete de los scripts. |
| `DIR_DATOS` | no | `data/` | SQLite. |
| `DIR_SALIDA` | no | `out/` | Artefactos y `.eml` de dry-run. |
| `DIR_ENTRADA` | no | `entrada/` | PDFs permitidos para `libro`. |
| `POLL_SEGUNDOS` | no | `50` | Intervalo de polling (15-3600). |
| `MAX_TAREAS_HORA` | no | `6` | Tope de ejecuciones por hora. |
| `MAX_ADJUNTOS_MB` | no | `20` | Umbral para adjuntar vs. Drive. |
| `MAX_SALIDA_BYTES` | no | `65536` | Tope de stdout/stderr. |
| `TIMEOUT_TAREA` | no | `120` | Timeout por herramienta. |
| `TIMEOUT_SELECTOR` | no | `15` | Timeout del selector. |
| `MAX_CUERPO_CHARS` | no | `4000` | Recorte del cuerpo. |
| `MAX_RESUMEN_CHARS` | no | `6000` | Recorte del resumen enviado. |
| `MAX_ARTEFACTOS` | no | `8` | Adjuntos máximos. |
| `MAX_ARTEFACTO_MB` | no | `200` | Tope por artefacto. |
| `HERRAMIENTAS_PERMITIDAS` | no | `sistema,redes,datos` | Lista blanca. |
| `PERMITIR_RECONEXION` | no | `0` | `1` permite que `redes` reconecte. |
| `GMAIL_ETIQUETA_BASE` | no | `AgenteCorreo` | Prefijo de etiquetas. |
| `LOG_LEVEL` | no | `INFO` | Nivel de journald. |

## 6. Seguridad

- **Contraseña quemada**: la contraseña de aplicación que se pegó en el chat
  debe revocarse en <https://myaccount.google.com/apppasswords>. Este código no
  la usa ni la guarda. El flujo es OAuth; no hay contraseñas en `.env`.
- **Scopes mínimos**: leer/marcar/etiquetar (`gmail.modify`), enviar
  (`gmail.send`) y archivos creados por la app (`drive.file`). No se pide
  acceso total a Drive.
- **Lista blanca exacta**: no se aceptan dominios, subdirecciones ni
  `+alias`. Un `From` con varias direcciones o inválido se deniega.
- **Sin ejecución arbitraria**: no hay `bash -c`, `eval`, `exec` ni
  interpretación de rutas/comandos del correo. El único ejecutable es el
  script que devuelve el selector, validado contra el catálogo.
- **Argumentos filtrados**: `sistema --limpiar`, `redes` con reconexión,
  `datos` con rutas del correo y `libro` con PDFs fuera de `entrada/` se
  rechazan.
- **Entorno hijo mínimo**: sin `GOOGLE_TOKEN`, `GOOGLE_CLIENT_SECRET`,
  `AUTORIZADO_FROM` ni el resto del entorno del servicio.
- **Idempotencia**: `INSERT OR IGNORE` por `message_id`; una tarea no se
  ejecuta dos veces ni aunque el listener se reinicie. Las reservas colgadas
  se avisan y no se reprocesan.
- **Tope y pausa**: `MAX_TAREAS_HORA` y `PAUSA`/`STOP` limitan un bucle o un
  correo malicioso.
- **Secretos**: `secrets/` y `.env` con permisos 600; `.gitignore`; logs sin
  cuerpo del correo ni tokens. Los errores que van al correo pasan por
  `redactar()`.
- **systemd**: sin privilegios nuevos, `/tmp` privado, sistema de solo
  lectura, home de solo lectura y escritura limitada a `data/` y `out/`.
- **Drive**: permiso `reader` solo para `AUTORIZADO_FROM`; no se crean enlaces
  públicos.

### Limitaciones de la lista blanca

El header `From` no es una firma criptográfica. Gmail aplica DMARC/SPF a la
mayoría de remitentes, pero un correo internamente spoofeado podría falsificar
la dirección. Para un entorno de mayor riesgo, añadir una comprobación de
`Authentication-Results`/DKIM antes de aceptar. No se implementa aquí porque
la cuenta es personal y el buzón no es público.

## 7. Google Drive con `drive.file`

`drive.file` solo da acceso a archivos **creados o abiertos por la app**. Una
carpeta creada a mano en Drive no es visible para el agente aunque se ponga su
ID en `DRIVE_FOLDER_ID`. Comportamiento implementado:

1. Si `DRIVE_FOLDER_ID` es accesible, se usa.
2. Si no, se busca/crea `AgenteCorreo` en la raíz de My Drive y se sube ahí.
3. El archivo se comparte como `reader` con `AUTORIZADO_FROM` y se devuelve
   `webViewLink`.

Si necesitas una carpeta concreta, créala desde la app (primera ejecución) y
copia su ID a `.env`, o usa Google Picker para conceder acceso puntual. No se
usa `drive` completo porque rompe la decisión de scopes mínimos.

## 8. Energía 24/7 (solo generar, no aplicar)

Los scripts **no se han ejecutado**. Ambos muestran el plan por defecto y solo
modifican el sistema con `--aplicar` y `sudo`:

```bash
cd ~/Documentos/HerramientasAgente/agente_correo

# Ver el plan (no toca nada)
./bin/potencia-24-7.sh
./bin/potencia-revertir.sh

# Aplicar (requiere sudo; decisión del usuario)
sudo ./bin/potencia-24-7.sh --aplicar

# Revertir
sudo ./bin/potencia-revertir.sh --aplicar
```

Qué hace `potencia-24-7.sh --aplicar`:

- `systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target`.
- Crea `/etc/systemd/logind.conf.d/99-agente-correo.conf` con
  `HandleLidSwitch=ignore`, `HandleLidSwitchExternalPower=ignore` y
  `HandleLidSwitchDocked=ignore`.
- `systemctl reload systemd-logind.service`.

La reversión elimina el drop-in, desenmascara los objetivos y recarga logind.
No toca `agente-correo.service`.

Advertencias: con la tapa cerrada el equipo puede calentarse; asegura
ventilación y un UPS si el servicio es crítico. `loginctl enable-linger` es
independiente de estos scripts.

## 9. Reversión y desinstalación

```bash
systemctl --user disable --now agente-correo.service
rm ~/.config/systemd/user/agente-correo.service
systemctl --user daemon-reload

# Opcional: revocar OAuth y borrar secretos/datos
rm ~/Documentos/HerramientasAgente/agente_correo/secrets/token.json
rm ~/Documentos/HerramientasAgente/agente_correo/secrets/client_secret.json
# Revocar el acceso de la app en https://myaccount.google.com/permissions
```

Los scripts de potencia se revierten con `potencia-revertir.sh --aplicar`.

## 10. Pruebas

```bash
cd ~/Documentos/HerramientasAgente
.venv/bin/python -m compileall -q agente_correo
.venv/bin/python -m pytest -q agente_correo/tests
```

Cobertura sin red:

- `test_parser.py`: multipart/base64, HTML, citas/firma, RFC 2047, control,
  auto-respuesta, `From` múltiple.
- `test_whitelist.py`: aceptación exacta case-insensitive, display name,
  lookalikes, subdominios, `+alias`, listas y vacíos.
- `test_dedupe.py`: reserva única, finalización, contador/hora, pausa.
- `test_orquestador.py`: lista blanca, política de argumentos, path traversal,
  PDF de `libro` fuera de `entrada/`, redacción de tokens.
- `test_listener.py`: denegación sin respuesta, dedupe, dry-run, pausa y
  límite por hora.
- `test_dispatcher.py`: hilo, adjuntos, umbral de Drive, `.eml` dry-run y
  redacción de errores.
- `test_gmail_client.py`: listar/modificar/etiquetar/enviar con un servicio
  falso, sin red.
- `test_enviar.py`: envío permitido, lista blanca y `--confirmar`, dry-run,
  respuesta en hilo, límites de adjuntos y CLI JSON.

## 11. Problemas frecuentes

| Síntoma | Causa / solución |
|---|---|
| `No module named agente_correo` | Ejecutar desde la raíz del repo, no desde `agente_correo/`. |
| `No hay token OAuth` | `cd repo && .venv/bin/python -m agente_correo.oauth_login`. |
| `invalid_grant` / token caducado | Revocado o 7 días en Testing. Reautorizar; publicar la app. |
| `insufficientPermissions` | Faltan scopes; borrar `token.json` y reautorizar. |
| `Gmail API has not been used...` | Habilitar Gmail API y Drive API en el proyecto. |
| `Access blocked: app not verified` | Añadir el usuario de prueba o completar verificación. |
| `DRIVE_FOLDER_ID` da 404 | `drive.file` no ve carpetas creadas a mano; usar `AgenteCorreo`. |
| El servicio no arranca tras cerrar sesión | `sudo loginctl enable-linger arturo`; `loginctl show-user arturo`. |
| `status=203/EXEC` | `PYTHON_BIN`/venv inexistente o ruta del `.env` mala. |
| Se queda en `PAUSADO` | Enviar `REANUDAR`; revisar `sqlite3 data/agente_correo.db "select * from estado"`. |
| Correo ignorado | Revisar `journalctl --user -u agente-correo.service`; etiqueta `Denegado`. |
| `puerto 8765 ocupado` | `ss -ltnp | grep 8765`; usar `--port 8766` (y actualizar `OAUTH_PORT`). |

## 12. Estructura

```
agente_correo/
├── README.md
├── .env.example
├── .gitignore
├── requirements.txt
├── __init__.py
├── config.py            # .env, validación, rutas, scopes
├── db.py                # SQLite: dedupe, pausa, contador
├── parser.py            # payload Gmail -> Mensaje; whitelist/control
├── gmail_client.py      # OAuth, list/get/modify/send (imports perezosos)
├── drive.py             # subir + permiso reader + webViewLink
├── orquestador.py       # puente al selector + políticas de args
├── dispatcher.py        # MIME, adjuntos, Drive, .eml dry-run
├── enviar.py            # CLI: enviar correo o responder en un hilo
├── listener.py          # polling, --once, --dry-run, --fixture
├── oauth_login.py       # loopback :8765, token 600
├── service/
│   └── agente-correo.service
├── bin/
│   ├── instalar.sh
│   ├── potencia-24-7.sh
│   └── potencia-revertir.sh
└── tests/
    ├── conftest.py
    ├── test_parser.py
    ├── test_whitelist.py
    ├── test_dedupe.py
    ├── test_orquestador.py
    ├── test_listener.py
    ├── test_gmail_client.py
    ├── test_dispatcher.py
    ├── test_enviar.py
    └── fixtures/
        ├── correo_autorizado.json
        ├── correo_denegado.json
        ├── correo_auto.json
        └── correo_control.json
```

## 13. Pendiente del lado del usuario

1. Revocar la contraseña de aplicación pegada en el chat.
2. Crear el proyecto de Google Cloud, habilitar Gmail API y Drive API, publicar
   la app y descargar `client_secret.json`.
3. Poner el valor exacto de `AUTORIZADO_FROM` (dirección personal) y
   `GMAIL_USER` en `.env`.
4. Ejecutar `oauth_login` y `--check`.
5. Decidir `DRIVE_FOLDER_ID` (o dejar que se cree `AgenteCorreo`).
6. Ejecutar la prueba dry-run y luego `--once` real.
7. Instalar/arrancar el servicio y `loginctl enable-linger`.
8. Decidir si aplica `potencia-24-7.sh --aplicar` (no se aplicó).
