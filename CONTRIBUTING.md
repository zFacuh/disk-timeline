# Contribuir a disk-timeline

¡Gracias por tu interés! Cualquier aporte suma: reportar un error, proponer una idea, mejorar
la documentación o enviar código.

## Reportar errores o proponer ideas

Abrí un [issue](https://github.com/zFacuh/disk-timeline/issues/new/choose) usando la plantilla
correspondiente. Para errores, incluí:

- el comando que ejecutaste y la salida completa (o el contenido de `scheduled.log`);
- tu versión de Windows y de Python (`python --version`);
- la versión de disk-timeline (`disk-timeline --version`).

> No pegues tu `history.db` ni listas completas de archivos si contienen información privada.

## Preparar el entorno

```powershell
git clone https://github.com/zFacuh/disk-timeline.git
cd disk-timeline
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

No hay dependencias de desarrollo: las pruebas usan `unittest` de la biblioteca estándar.

```powershell
python -m unittest discover -s tests -v
```

Para trabajar en el panel web sin esperar días de capturas, generá datos de demostración:

```powershell
python scripts/make_demo_db.py demo.db
python -m disk_timeline --db demo.db serve
```

Los archivos del panel (`disk_timeline/web/`) se sirven tal cual: alcanza con recargar el
navegador después de editarlos.

## Pautas

- **Sin dependencias externas.** Es una de las ideas centrales del proyecto. Si una mejora
  necesita una librería, abrí antes un issue para discutirlo.
- **Python 3.10+.** El CI corre en Windows y Linux con Python 3.10 y 3.13.
- **Rendimiento del escaneo.** `scanner.py` procesa millones de archivos: evitá llamadas al
  sistema extra por archivo (`os.stat`, `entry.inode()`, etc.) salvo que sea imprescindible.
- **Textos en español.** La interfaz y la documentación están en español; los nombres en el
  código y los mensajes de commit, en inglés.
- **Pruebas.** Agregá o actualizá pruebas en `tests/` para cualquier cambio de comportamiento.
- **Compatibilidad de la base de datos.** Si cambiás el esquema en `db.py`, la base existente de
  los usuarios tiene que seguir funcionando (agregá columnas con valores por defecto en lugar de
  modificar las existentes).

## Enviar cambios

1. Hacé un fork y creá una rama: `git checkout -b mejora-descriptiva`.
2. Hacé tus cambios con commits pequeños y descriptivos.
3. Verificá que las pruebas pasen.
4. Abrí un *pull request* explicando qué cambia y por qué. Si toca el panel, agregá una captura
   de pantalla.

Ideas para empezar: mirá los issues con la etiqueta
[`good first issue`](https://github.com/zFacuh/disk-timeline/labels/good%20first%20issue) o la
sección de ideas en el [CHANGELOG](CHANGELOG.md#ideas-a-futuro).
