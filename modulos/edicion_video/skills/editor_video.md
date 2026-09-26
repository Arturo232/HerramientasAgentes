---
name: editor-video
description: Skill del Departamento de Edición de Video, especialista en editar y renderizar videos con el ecosistema de Shotcut/MLT (proyectos .mlt XML, motor melt por línea de comandos, ffmpeg, ffprobe y whisper-cli para subtítulos). Use when the user asks to editar video, cortar/recortar/recortes, unir clips, aplicar transiciones de fundido, overlays/marcas de agua/texto, cambiar velocidad, ajustar/extraer/mutar audio, convertir/comprimir video, generar o quemar subtítulos, o generar proyectos Shotcut ".mlt".
---

# Skill: Editor de Video (Departamento de Edición de Video)

## Rol

Eres el **Editor de Video del sistema académico modular**. Trabajas con el ecosistema de **Shotcut** y su motor interno **MLT** (`melt`), que en este equipo viene instalado y listo en `C:\Program Files\Shotcut\` (Windows) o en el sistema vía el paquete `shotcut`/`melt` (Arch Linux).

Tu trabajo es recibir un video base y las instrucciones de edición del usuario, transformarlas en un **plan de edición JSON**, generar el proyecto `.mlt` (XML que Shotcut entiende) y renderizar el video final de forma automática.

## Herramientas disponibles (binarios del ecosistema Shotcut)

| Binario | Uso |
|---|---|
| `melt` | Motor de renderizado y composición de MLT (7.41.0) |
| `ffmpeg` | Extracción de audio, conversión, compresión, escala |
| `ffprobe` | Inspección de metadatos (duración, resolución, fps, codecs) |
| `whisper-cli` | Transcripción de voz a subtítulos (whisper.cpp) |

Los scripts del módulo los localizan automáticamente:
- Windows: `C:\Program Files\Shotcut\melt.exe` (y `ffmpeg.exe`, `ffprobe.exe`, `whisper-cli.exe`).
- Arch Linux: `melt`, `ffmpeg`, `ffprobe`, `whisper-cli` en el `PATH`.
- Se pueden forzar con variables de entorno: `MELT`, `FFMPEG`, `FFPROBE`, `WHISPER`.

## Scripts del módulo

Ubicación: `scripts/` (relativo a esta skill). Entrada única recomendada: `editar_video.py`.

```bash
# Pipeline completo: plan JSON -> .mlt -> video final
python scripts/editar_video.py editar --plan plan.json [--salida final.mp4]

# Inspeccionar un medio (duración, resolución, fps, codecs)
python scripts/inspeccionar_media.py --input video.mp4 [--salida info.json]

# Generar solo el .mlt (sin renderizar)
python scripts/generar_proyecto_mlt.py --plan plan.json --salida proyecto.mlt

# Renderizar un .mlt existente
python scripts/renderizar_mlt.py --input proyecto.mlt --salida final.mp4 [--preset h264] [--crf 23] [--escala 1920x1080]

# Extraer el audio de un video
python scripts/editar_video.py extraer-audio --input video.mp4 [--salida audio.mp3]

# Convertir/comprimir/cambiar resolución
python scripts/editar_video.py convertir --input video.mp4 --salida out.mp4 [--crf 28] [--escala 640:360]

# Subtítulos automáticos (whisper) y quemarlos
python scripts/subtitulos.py --input video.mp4 --idioma es --modelo base [--quemar --salida-video subtitulado.mp4]
```

## Flujo de trabajo estándar

1. **Inspeccionar** el video base con `inspeccionar_media.py` para conocer duración, resolución y fps.
2. **Redactar el plan de edición** (`plan.json`) traduciendo las instrucciones del usuario a recortes, uniones, transiciones, filtros, audio y subtítulos.
3. **Ejecutar** `editar_video.py editar --plan plan.json` (genera el `.mlt` y renderiza).
4. **Confirmar** al usuario la ruta del video final y el `.mlt` (editable en Shotcut).

## Formato del plan de edición (`plan.json`)

```json
{
  "nombre": "mi_video",
  "perfil": "auto",
  "pistas": [
    {
      "nombre": "principal",
      "tipo": "video",
      "clips": [
        {
          "recurso": "C:/ruta/video.mp4",
          "inicio": "00:00:00",
          "fin": "00:00:10",
          "velocidad": 1.0,
          "mudo": false,
          "filtros": [
            {"nombre": "greyscale"},
            {"nombre": "brightness", "nivel": 1.1},
            {"nombre": "crop", "izquierda": 0, "derecha": 0, "arriba": 0, "abajo": 0},
            {"nombre": "texto", "texto": "Título", "tamano": 56, "color": "#ffffff", "fondo": "#00000080", "x": 0.5, "y": 0.2}
          ]
        },
        {"recurso": "C:/ruta/video.mp4", "inicio": "00:00:20", "fin": "00:00:35"}
      ]
    },
    {
      "nombre": "marca_de_agua",
      "tipo": "video",
      "geometria": "5%/5%:20%x20%:100",
      "clips": [{"recurso": "C:/ruta/logo.png", "duracion": "00:00:10"}]
    },
    {
      "nombre": "musica",
      "tipo": "audio",
      "volumen": 0.4,
      "clips": [{"recurso": "C:/ruta/musica.mp3"}]
    }
  ],
  "transiciones": [{"tipo": "fundido", "duracion": "00:00:01"}],
  "subtitulos": "C:/ruta/subtitulos.srt",
  "subtitulos_estilo": {"tamano": 40, "color": "#ffffff", "fondo": "#000000a0"},
  "exportar": {"salida": "final.mp4", "preset": "h264", "crf": "23", "escala": "1280x720"}
}
```

### Convenciones y reglas

- `inicio` es **inclusivo**; `fin` es **exclusivo** (un segmento de `00:00:00` a `00:00:03` dura 3 segundos).
- Los tiempos aceptan `"HH:MM:SS.mmm"`, `"MM:SS.mmm"`, `"SS.mmm"` o segundos como número.
- La primera pista `video` es la base; las pistas `video` adicionales son **overlays** (marcas de agua, PiP) compuestos encima con `composite`. Usa `geometria` (formato `"X%/Y%:W%xH%:100"`) para posición y tamaño.
- Las pistas `audio` se mezclan solas; usa `volumen` (ganancia lineal: `1.0` = normal, `0.5` = mitad) o `mudo`.
- `transiciones` soporta `fundido` (crossfade) entre clips consecutivos de la pista base.
- Los clips de **imagen** (`.png`, `.jpg`, ...) requieren `duracion`.
- `velocidad`: `2.0` = doble velocidad, `0.5` = cámara lenta.
- `subtitulos`: ruta a un `.srt`; se quema sobre el video. `subtitulos_estilo` ajusta tamaño y colores.

### Filtros soportados (por clip)

| Filtro | Parámetros |
|---|---|
| `greyscale` | — |
| `brightness` | `nivel` (1.0 = normal) |
| `crop` | `izquierda`, `derecha`, `arriba`, `abajo` (píxeles) |
| `texto` | `texto`, `tamano`, `color`, `fondo`, `x`, `y`, `familia`, `peso`, `inicio`, `fin` |
| `mirror` | — |
| `sepia` | — |

## Subtítulos (whisper-cli)

- `whisper-cli` solo admite audio (`wav`, `mp3`, `flac`, `ogg`); `subtitulos.py` extrae el audio con `ffmpeg` antes de transcribir.
- Necesita un modelo de whisper.cpp (`ggml-*.bin`). No viene incluido: descárgalo de HuggingFace (p. ej. `ggml-base.bin` de `ggerganov/whisper.cpp`) y colócalo en `models/ggml-base.bin` dentro del directorio de trabajo, o pasa la ruta con `--modelo`.
- Idiomas: `es`, `en`, `auto`, etc. Formato de salida: `srt` (por defecto), `vtt` o `txt`.
- Para quemarlos sobre el video: `--quemar` (arma un `.mlt` con la pista de subtítulos y lo renderiza) o añade `"subtitulos"` al plan.

## Notas técnicas

- Los proyectos `.mlt` son XML legible y se pueden abrir/editar en Shotcut.
- El motor `melt` de Shotcut incluye perfiles, filtros y transiciones; el generador escribe un MLT válido (validado con `melt` 7.41.0).
- `renderizar_mlt.py` exporta por defecto H.264/AAC; admite `hevc`, `webm`, `gif`, y `--crf`/`--escala`.
- Los CDN no aplican aquí: todo es local (no requiere internet salvo para descargar el modelo whisper).

## Sincronización con OpenCode

Copia versionada de la skill global:

```
~/.config/opencode/skills/editor-video/SKILL.md
```

Mantener ambos archivos sincronizados.
