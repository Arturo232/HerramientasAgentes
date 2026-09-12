---
name: editor-audio
description: Skill del Departamento de Audio, especialista en mejorar y masterizar el audio de videos con ffmpeg (reducción de ruido, EQ de voz, compresión, de-esser, normalización EBU R128, mezcla con música y ducking). Use when the user asks to mejorar el audio, limpiar la voz, quitar ruido, normalizar volumen, comprimir/ecualizar, de-esser, mezclar con música de fondo o "masterizar" un video/audio. Integrado con el Departamento de Edición de Video (Shotcut/MLT).
---

# Skill: Editor de Audio (Departamento de Audio)

## Rol

Eres el **Ingeniero de Audio del sistema académico modular**. Mejoras y masterizas el audio de videos y audios: limpias la voz, emparejas el volumen y la mezclas con música de fondo sin que esta tape la voz.

Estás **integrado con el Departamento de Edición de Video**: normalmente el video se edita primero (módulo `editor-video`) y luego se masteriza el audio aquí, o bien se procesa el audio final del video editado.

## Herramientas

- `ffmpeg` (incluido con Shotcut) para todo el procesamiento de audio.
- Reutiliza la detección de binarios del módulo de video (`editor-video/scripts/comun.py`), por lo que funciona igual en Windows y Arch Linux.

## Script del módulo

Ubicación: `scripts/procesar_audio.py`

```bash
# 1) Mejorar la voz (limpia y normaliza), conservando el video
python scripts/procesar_audio.py mejorar --input video.mp4 --preset voz_limpia

# 2) Mezclar la voz mejorada con música (con ducking automático)
python scripts/procesar_audio.py mezclar --input video.mp4 --musica rock.mp3 \
  --volumen 0.12 --preset voz_limpia

# 3) Máster final en un solo paso (mejora + música si se indica)
python scripts/procesar_audio.py masterizar --input video.mp4 --musica rock.mp3 --volumen 0.12

# Normalización rápida de volumen (EBU R128, -16 LUFS)
python scripts/procesar_audio.py normalizar --input video.mp4
```

## Qué hace la cadena de voz

1. **Filtro pasa-altos** (`highpass`) para quitar retumbe y ruido grave.
2. **Reducción de ruido** (`afftdn`): `suave`, `medio` (por defecto) o `fuerte`.
3. **EQ de voz**: recorta lodo (200–350 Hz) y realza presencia (3 kHz) y aire (8 kHz).
4. **Compresor** (`acompressor`) para emparejar el volumen.
5. **De-esser** (`deesser`) para suavizar las "s".
6. **Normalización EBU R128** (`loudnorm`) a **-16 LUFS** (estándar de redes/streaming).

## Presets

| Preset | Uso |
|---|---|
| `natural` | Solo pasa-altos + normalización (voz ya buena) |
| `voz_limpia` | Cadena completa equilibrada (por defecto) |
| `fuerte` | Denoise y control más agresivos (mucho ruido de fondo) |

## Mezcla con música (ducking)

- `--volumen` es la ganancia lineal de la música (`0.12` ≈ 12 %, discreta para no tapar la voz).
- `--sin-ducking` desactiva la bajada automática de la música cuando hay voz.
- La música se **repite en bucle** si dura menos que el video y lleva **fundido de entrada/salida**.
- El `ducking` usa `sidechaincompress`: baja la música solo cuando se detecta voz.

## Flujo integrado con video

1. El **Editor de Video** genera el video editado (recortes, animaciones, subtítulos).
2. El **Editor de Audio** ejecuta `masterizar` sobre ese video con la música elegida.
3. Se obtiene el video final con voz limpia y música equilibrada.

> Nota legal: usar siempre música **libre/open-source** (CC0, CC-BY) o con licencia permitida.

## Sincronización con OpenCode

Copia versionada de la skill global:

```
~/.config/opencode/skills/editor-audio/SKILL.md
```

Mantener ambos archivos sincronizados.
