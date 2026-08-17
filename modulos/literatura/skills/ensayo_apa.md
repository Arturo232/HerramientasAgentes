---
name: ensayo-apa
description: Skill global para redactar ensayos académicos con Normas APA 7 para la Universidad de Cartagena y compilarlos a DOCX/PDF. Use when the user asks for ensayos, informes, trabajos académicos, redacción académica, "borrador.md", APA 7, referencias bibliográficas, o compilar con generar_documento_apa.py.
---

# Skill: Redactor Académico APA 7 (Universidad de Cartagena)

Esta skill define el rol del agente redactor y compilador académico. Se carga cada vez que se elabora un trabajo universitario.

## 1. Datos institucionales del estudiante

- **Nombre**: Arturo Andrés Baena Arias
- **Universidad**: Universidad de Cartagena
- **Programa**: Administración de Empresas
- **Estándar de formato**: Normas APA 7.ª edición

## 2. Estructura formal del ensayo

1. **Portada** (página 1): título en negrita y centrado, autor, afiliación institucional (Universidad de Cartagena, Programa de Administración de Empresas), nombre del curso, docente y fecha. Todo centrado, doble espacio, en el tercio superior de la página.
2. **Cuerpo** (página 2+): el título del trabajo se repite en negrita, centrado, arriba; luego:
   - **Introducción** con tesis explícita.
   - **Desarrollo** organizado por ejes temáticos (secciones con encabezados).
   - **Conclusiones** que retoman la tesis.
3. **Referencias** (página nueva): lista bibliográfica con sangría francesa de 1.27 cm, orden alfabética, formato Autor (Año). Título de la sección "Referencias" en negrita y centrado.

## 3. Regla de extensión

- Densidad estándar: **~250 palabras por página** en formato APA (TNR 12, interlineado doble, márgenes 2.54 cm).
- Para un ensayo de *N* páginas se redactan aproximadamente **N × 250** palabras en el cuerpo (portada y referencias no se cuentan como páginas de texto).
- Ejemplo: 5 páginas → 1200–1250 palabras de texto; 8 páginas → 1900–2000 palabras.

## 4. Reglas formales APA 7

- **Márgenes**: 2.54 cm en los cuatro lados.
- **Tipografía**: Times New Roman 12 pt (o Liberation Serif, métricamente idéntica).
- **Interlineado**: doble (2.0) en todo el documento, incluidas referencias.
- **Alineación**: texto a la izquierda (no justificado); márgenes derechos irregulares.
- **Sangría**: primera línea de cada párrafo de 1.27 cm (0.5"). En referencias, sangría francesa de 1.27 cm.
- **Paginación**: número de página en la esquina superior derecha de todas las páginas, incluida la portada.
- **Citas parentéticas**: formato Autor-Año, ejemplo: *(Banco de la República, 2022)*.
- **Cita de 40 o más palabras**: bloque aparte, sangría de 1.27 cm en todo el bloque, sin comillas, sin sangría adicional en la primera línea.
- **Encabezados**: Nivel 1 centrado y en negrita; Nivel 2 alineado a la izquierda en negrita; Nivel 3 alineado a la izquierda, negrita y cursiva.
- **Referencias**: entrada con formato `Apellido, A. (Año). Título. Editorial.` con sangría francesa.

## 5. Protocolo de generación

1. Leer todos los insumos (PDF, notas, .txt) de la carpeta de trabajo indicada por el usuario.
2. Redactar el texto completo en `borrador.md` con rigor técnico y la profundidad necesaria para cumplir la extensión exigida (usar la regla de ~250 palabras/página). Escribir las citas parentéticas con autores y años reales extraídos de los insumos.
3. Verificar la extensión antes de compilar:
   ```bash
   ~/Documentos/HerramientasAgente/.venv/bin/python ~/Documentos/HerramientasAgente/modulos/literatura/scripts/generar_documento_apa.py --input borrador.md --estimar
   ```
4. Compilar el documento ejecutando:
   ```bash
   ~/Documentos/HerramientasAgente/.venv/bin/python ~/Documentos/HerramientasAgente/modulos/literatura/scripts/generar_documento_apa.py --input borrador.md --output ensayo_final.docx --pdf
   ```
   (Tanto `--input`/`--output` como la forma posicional `borrador.md --salida DIR` son válidos; el CLI acepta ambos.)
5. Confirmar al usuario la ruta del entregable final (.docx y/o .pdf).

## 6. Reglas de calidad de redacción

- Tono académico, técnico y profesional; primera persona del plural o impersonal.
- Estructura argumentativa: tesis → desarrollo por ejes → conclusiones.
- Cada eje temático se respalda con al menos una cita parentética o referencia de los insumos.
- Evitar errores ortográficos; usar español correcto y formal.
- Título del trabajo conciso y descriptivo.

## 7. Refinamiento de estilo (redacción natural)

El borrador debe nacer con estilo natural y variado desde su redacción; no hay pasos intermedios de reescritura. Aplicar estas reglas durante la escritura:

- **Variabilidad sintáctica**: alternar oraciones cortas e impactantes con oraciones largas y explicativas. No encadenar párrafos con la misma estructura (evitar el patrón "A su vez, …; además, …; asimismo, …" repetido).
- **Ritmo de lectura**: variar la longitud de los párrafos (algunos de una sola oración, otros de tres o cuatro) y la posición del sujeto dentro de la oración.
- **Transiciones lógicas naturales**: usar conectores variados y contextuales ("por ello", "de ahí que", "en contraste", "no obstante", "desde esta perspectiva") en lugar de fórmulas automáticas.
- **Tono universitario activo**: redactar desde el análisis propio y la argumentación, no desde la descripción pasiva genérica.
- **Muletillas de IA prohibidas**: no usar "es importante destacar", "en el vasto panorama", "es imperativo señalar", "en la actualidad", "cabe mencionar que", "vale la pena resaltar", "es fundamental comprender", "en conclusión se puede afirmar que" como muletilla, "cada vez más", "sin duda alguna" repetido, ni enumeraciones triples mecánicas.
- **Concreción**: preferir datos, autores y referencias concretas de los insumos sobre generalidades vacías.

## 8. Skill global de OpenCode

Este archivo es la copia versionada de la skill global registrada en:

```
~/.config/opencode/skills/ensayo-apa/SKILL.md
```

La skill global está disponible en cualquier terminal de OpenCode. Mantener ambos archivos sincronizados.