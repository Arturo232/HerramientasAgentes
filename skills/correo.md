---
name: correo
description: Envía correos o responde en un hilo con Gmail usando el agente de correo 24/7. Use when the user asks to enviar un correo, mandar un email, responder a un mensaje, adjuntar un archivo a un correo, o consultar el estado del agente de correo.
---

# Correo (Gmail)

Usa el módulo `agente_correo` del repositorio `~/Documentos/HerramientasAgente`.
La cuenta del agente es `caballerotaitus7@gmail.com`; la única dirección
autorizada a dar órdenes es `arturomxo@gmail.com`.

## Enviar desde el agente

Prefiere la herramienta MCP `correo` (servidor `herramientas`) o el CLI:

```bash
cd ~/Documentos/HerramientasAgente
.venv/bin/python -m agente_correo.enviar \
  --para arturomxo@gmail.com \
  --asunto "Asunto" \
  --cuerpo "Mensaje"
```

- `--dry-run`: escribe el `.eml` en `out/envios-dry-run/` y **no envía**.
- `--adjunto RUTA`: se puede repetir; la ruta debe estar dentro de `entrada/`
  o `out/` salvo `--permitir-rutas-externas`.
- `--responder-a ID`: conserva el hilo usando `In-Reply-To` y `References`.
- Destinatarios permitidos: `DESTINATARIOS_PERMITIDOS` (por defecto
  `AUTORIZADO_FROM`). `--confirmar` abre la lista solo para esa ejecución.

## Reglas de seguridad

1. No envíes correos a terceros sin que el usuario lo pida explícitamente.
2. Si el usuario no confirmó el envío, usa `--dry-run` y muestra el resultado.
3. No leas ni muestres `.env`, `secrets/` ni `token.json`.
4. No ejecutes `listener --once` si el servicio `agente-correo.service` está
   activo: competirían por la misma bandeja y la misma SQLite.
5. Para el estado del servicio usa `systemctl --user status agente-correo`.

## Servicio

```bash
systemctl --user status agente-correo.service
journalctl --user -u agente-correo.service -n 30 --no-pager
```

El listener solo obedece a `arturomxo@gmail.com`; los demás remitentes se
archivan como denegados (no se borran) y no reciben respuesta.
