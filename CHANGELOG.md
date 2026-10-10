# Cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). El proyecto usa
[versionado semántico](https://semver.org/lang/es/).

## [Sin publicar]

### Agregado
- Comando `list` para ver las capturas completas de un disco con su id.
- Documentación ampliada: guía de uso, funcionamiento interno, preguntas frecuentes, versión en inglés.
- Plantillas de issues y pull requests.

### Corregido
- `serve` muestra un mensaje claro si el puerto está ocupado en lugar de un error de Python.

## [0.1.0] - 2026-10-10

Primera versión.

### Agregado
- Capturas completas (uso + tamaño de carpetas + archivos nuevos grandes) y rápidas (sólo uso).
- Comandos de consola `snapshot`, `status`, `growth`, `new`, `serve` y `schedule`.
- Panel web local con gráficas de espacio usado y cambio diario, carpetas que crecieron y
  archivos agregados, con tema claro y oscuro.
- Captura diaria automática con el Programador de tareas de Windows, que se ejecuta al encender
  la PC si estaba apagada a la hora programada.
- Archivos grandes alcanzables por varias rutas (enlaces duros, carpetas redirigidas) se cuentan
  una sola vez.
- Generador de datos de demostración (`scripts/make_demo_db.py`).

## Ideas a futuro

Ideas que podrían sumarse (¡se aceptan contribuciones!):

- Exportar el historial a CSV desde la consola y el panel.
- Limpieza automática de capturas antiguas (por ejemplo, conservar una por semana después de 3 meses).
- Alertas cuando un disco crece más de cierto umbral en un día o queda poco espacio libre.
- Gráfica de evolución de una carpeta concreta.
- Programación automática en Linux/macOS (cron / launchd).

[Sin publicar]: https://github.com/zFacuh/disk-timeline/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/zFacuh/disk-timeline/releases/tag/v0.1.0
