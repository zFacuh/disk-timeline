# Preguntas frecuentes y solución de problemas

## Instalación

### `disk-timeline` no se reconoce como un comando

La carpeta `Scripts` de Python no está en el PATH. Opciones:

- Usar el módulo directamente: `python -m disk_timeline snapshot` (funciona igual con todos los comandos).
- O agregar la carpeta al PATH. Para saber cuál es:

  ```powershell
  python -c "import sysconfig; print(sysconfig.get_path('scripts'))"
  ```

### `python` no se reconoce como un comando

Python no está instalado o no está en el PATH. Instalalo desde
[python.org](https://www.python.org/downloads/) y marcá **"Add python.exe to PATH"** en el
instalador. También podés probar con `py` en lugar de `python`.

### `pip install git+https://...` falla con "git no se reconoce"

Instalá [Git para Windows](https://git-scm.com/download/win), o descargá el repositorio como
ZIP desde GitHub (**Code → Download ZIP**), descomprimilo y ejecutá dentro de la carpeta:

```powershell
pip install .
```

## Capturas

### El escaneo tarda mucho

La primera vez es la más lenta porque Windows tiene que leer la información de los archivos
del disco. Las siguientes suelen ser 2-3 veces más rápidas. Si igual es lento:

- Excluí carpetas enormes que no te interesan: `--exclude D:\Backups`.
- Usá capturas rápidas a diario y completas de vez en cuando: `schedule install --quick`, y
  ejecutá `disk-timeline snapshot` manualmente cuando quieras saber qué cambió.

### "N sin acceso" es un número alto

Son carpetas protegidas del sistema. Es normal y no afecta el uso total del disco (que se lee
directamente de Windows). Sólo hace que esas carpetas no aparezcan en "¿Qué creció?". Si querés
medirlas, ejecutá la consola como administrador.

### Un archivo que descargué hace días aparece como "nuevo"

Se considera nuevo todo archivo **creado o modificado** desde la captura anterior. Si un programa
lo modificó (por ejemplo, un juego que se actualizó o un archivo de base de datos que se escribe
constantemente), vuelve a aparecer. Eso es intencional: ese archivo cambió y puede haber crecido.

### En la primera captura aparecen archivos de hace una semana

Como no hay captura anterior para comparar, la primera muestra los archivos de los últimos 7 días.

### Borré archivos pero el disco no muestra el espacio liberado

Si los mandaste a la papelera, siguen ocupando espacio hasta que la vacíes. También pasa con
los puntos de restauración y las copias de Windows Update, que Windows libera por su cuenta.

## Panel web

### "No se pudo usar el puerto 8765"

Otro programa usa ese puerto, o ya tenés el panel abierto en otra ventana (en ese caso entrá
directamente a `http://127.0.0.1:8765`). Si no, usá otro puerto:

```powershell
disk-timeline serve --port 9000
```

### El panel dice "Todavía no hay capturas"

Tomá una con el botón **Escaneo completo** o con `disk-timeline snapshot`. Si ya tomaste
capturas, revisá que no estés usando otra base de datos (`--db` o las variables
`DISK_TIMELINE_DB` / `DISK_TIMELINE_HOME`).

### La gráfica de cambio diario está vacía

Hacen falta capturas de **al menos dos días distintos**. Lo mismo con "¿Qué creció?", que
necesita dos capturas completas.

## Tarea programada

### ¿Cómo sé si la tarea se está ejecutando?

- `disk-timeline schedule show` muestra la última y la próxima ejecución.
- `%LOCALAPPDATA%\disk-timeline\scheduled.log` guarda la salida de cada ejecución, incluidos
  los errores.
- `disk-timeline status` muestra si hay una captura por día.

### La tarea dejó de funcionar después de actualizar o mover Python

La tarea guarda la ruta de `pythonw.exe` y de la instalación de disk-timeline. Volvé a
registrarla:

```powershell
disk-timeline schedule install
```

### "Acceso denegado" al instalar la tarea

Algunas políticas de empresa bloquean crear tareas programadas. En ese caso podés crear la tarea
a mano desde el **Programador de tareas** apuntando a
`pythonw.exe "%LOCALAPPDATA%\disk-timeline\run_snapshot.pyw"`, o pedir permiso a tu
administrador.

## Datos

### ¿Cuánto ocupa el historial?

Una captura completa de un disco ocupa menos de 1 MB; las rápidas, casi nada. Un año de capturas
diarias de dos discos ronda los 300 MB. Para reducirlo, usá `--depth 2` o borrá capturas viejas
(ver [cómo-funciona.md](como-funciona.md#base-de-datos)).

### ¿Puedo llevar el historial a otra PC?

Sí: copiá `%LOCALAPPDATA%\disk-timeline\history.db` a la misma ubicación en la otra PC.

### ¿Puedo exportar los datos a Excel?

La base es SQLite estándar. Con [DB Browser for SQLite](https://sqlitebrowser.org/) podés
abrirla y exportar cualquier tabla a CSV. Las consultas de ejemplo están en
[como-funciona.md](como-funciona.md#base-de-datos).

---

¿No encontraste tu problema? [Abrí un issue](https://github.com/zFacuh/disk-timeline/issues/new/choose)
con la salida del comando y tu versión de Windows y Python.
