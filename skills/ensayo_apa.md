# Skill: Ensayo Académico en Normas APA 7.ª edición

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
3. Compilar el documento ejecutando:

```bash
.venv/bin/python ~/Documentos/HerramientasAgente/scripts/generar_documento_apa.py ruta/al/borrador.md --pdf
```

4. Verificar con `--estimar` que la extensión del borrador cumpla el número de páginas solicitadas antes de compilar.
5. Confirmar al usuario la ruta del entregable final (.docx y/o .pdf).

## 6. Reglas de calidad de redacción

- Tono académico, técnico y profesional; primera persona del plural o impersonal.
- Estructura argumentativa: tesis → desarrollo por ejes → conclusiones.
- Cada eje temático se respalda con al menos una cita parentética o referencia de los insumos.
- Evitar errores ortográficos; usar español correcto y formal.
- Título del trabajo conciso y descriptivo.