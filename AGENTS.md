# AGENTS.md — 19_Radio_Tecno

## Sobre el proyecto

Podcast diario de unos 30 minutos de noticias de tecnología (IA, Google, Microsoft, NVIDIA, programación, Python, Linux, repos de GitHub) leídas con voz de mujer (edge-tts): primero todas en español y después todas en inglés, porque Javier está aprendiendo inglés. Cada episodio tiene transcripción con el tiempo de cada palabra y `escuchar.html` la marca mientras suena (único JavaScript del proyecto, porque corre en el navegador). Python 3.12, solo librería estándar más `edge-tts`; sin IA ni claves. La configuración está en `feeds.toml`. Se ejecuta con `python -m radio [--dry-run]` y se prueba con `python -m unittest discover tests`. GitHub Actions (`.github/workflows/episodio.yml`) lo arma todos los días a las 06:00 de Argentina y lo publica en la rama `gh-pages` (GitHub Pages, repo público `the-heimdallr/radio-tecno`); esa rama se reescribe en cada corrida y guarda solo los últimos 7 episodios. Pedido de Javier del 21/11/2026, desde mi-segundo-cerebro.

## Entorno compartido

Antes de proponer herramientas, dependencias o servicios, leé `../_plantilla/ENTORNO.md` (reglas, servicios y sus límites) y `../_plantilla/EQUIPO.md` (hardware y versiones instaladas). Antes de construir algo, buscá en `../_plantilla/RECETAS.md` si ya está resuelto en otro proyecto, y si resolvés algo reutilizable, sumalo ahí. Si no están en esa ruta, avisale a Javier.

Reglas que valen siempre: Python primero; el equipo tiene 4 GB de RAM; solo servicios gratuitos ya listados en `ENTORNO.md`; ningún valor de clave en archivos versionados.

## Protocolo de gestión de tareas

Estas reglas valen para cualquier asistente de IA que trabaje en este proyecto.

1. **Al empezar:** leé `TASKS.md` antes de proponer o modificar algo.
2. **Al terminar cualquier cambio** (función nueva, bug resuelto, bloqueo descubierto): actualizá `TASKS.md` y sumalo al mismo commit que el código. El repositorio tiene un hook que rechaza commits que no incluyen `TASKS.md`.
3. **Formato:** `TASKS.md` es una tabla Markdown que lee un script externo. No cambies las columnas ni su orden. No uses el carácter `|` ni saltos de línea dentro de una celda.
4. **ID:** correlativo (`T-001`, `T-002`...). Nunca se reutiliza ni se renumera.
5. **Responsable:**
   - `IA`: tarea técnica que un asistente puede resolver sin intervención humana.
   - `Javier`: decisiones de arquitectura, credenciales, accesos, compras, pagos o cualquier cosa que requiera acción humana. En Detalle escribí los pasos concretos que tiene que hacer.
6. **Estado:** `pendiente`, `en curso` o `bloqueado`. Si está bloqueado, decí en Detalle qué lo bloquea (con el ID si es otra tarea).
7. **Prioridad:** `alta`, `media` o `baja`.
8. **Fecha:** solo Javier pone fechas. Si no te dio una, dejá `-`. No inventes plazos.
9. **Al completar una tarea:** mové la fila a la tabla "Hechas" con la fecha real de cierre. Dejá solo las últimas 20.
10. **No inventes tareas.** Solo registrá lo que surge del código, de un TODO, de un error real o de un pedido de Javier. Si algo es dudoso, cargalo con responsable `Javier` y detalle "confirmar si corresponde".
11. **Al cerrar la sesión:** resumí en tres líneas qué se hizo, qué queda pendiente y qué depende de Javier.
