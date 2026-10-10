# Cómo funciona disk-timeline

Este documento explica el funcionamiento interno: para quien quiera entender los números que
muestra la herramienta, adaptarla o contribuir.

- [Visión general](#visión-general)
- [Estructura del código](#estructura-del-código)
- [La captura paso a paso](#la-captura-paso-a-paso)
- [Base de datos](#base-de-datos)
- [Cómo se calculan los indicadores](#cómo-se-calculan-los-indicadores)
- [API del panel web](#api-del-panel-web)
- [Tarea programada](#tarea-programada)
- [Decisiones de diseño](#decisiones-de-diseño)

## Visión general

```text
        ┌──────────────────────┐
        │ disk-timeline snapshot│  (a mano, desde el panel o por la tarea programada)
        └──────────┬───────────┘
                   │ 1 recorrido del disco
                   ▼
   uso del disco + tamaño de carpetas + archivos nuevos grandes
                   │
                   ▼
          ┌─────────────────┐
          │ history.db      │  SQLite, una fila por captura y disco
          └───┬─────────┬───┘
              │         │
     consola  ▼         ▼  panel web (http://127.0.0.1:8765)
  status / growth /   servidor HTTP propio → API JSON → gráficas SVG
  new / list
```

No hay dependencias externas: todo usa la biblioteca estándar de Python (`os.scandir`,
`sqlite3`, `http.server`, `argparse`, `ctypes`). El panel es HTML/CSS/JS sin frameworks ni CDNs.

## Estructura del código

| Archivo | Responsabilidad |
|---|---|
| `disk_timeline/cli.py` | Comandos de consola (`argparse`) y formato de salida. |
| `disk_timeline/drives.py` | Detecta los discos fijos (API de Windows `GetLogicalDrives`/`GetDriveTypeW`) y lee su uso (`shutil.disk_usage`). |
| `disk_timeline/scanner.py` | Recorre un disco una vez: suma tamaños por carpeta y junta los archivos nuevos más grandes. |
| `disk_timeline/snapshot.py` | Orquesta una captura: uso + escaneo + guardado. |
| `disk_timeline/db.py` | Esquema SQLite e inserciones. |
| `disk_timeline/analysis.py` | Consultas sobre el historial: series diarias, crecimiento de carpetas, archivos nuevos. |
| `disk_timeline/server.py` | Servidor web local y API JSON. |
| `disk_timeline/scheduler.py` | Alta/baja de la tarea en el Programador de tareas de Windows. |
| `disk_timeline/config.py` | Rutas de datos y valores por defecto. |
| `disk_timeline/web/` | El panel: `index.html`, `style.css`, `app.js`. |
| `scripts/make_demo_db.py` | Genera una base con 60 días simulados para probar el panel. |
| `tests/` | Pruebas unitarias (`unittest`). |

## La captura paso a paso

1. **Uso del disco.** `shutil.disk_usage("C:\\")` devuelve total, usado y libre: los mismos
   números que el Explorador de Windows.
2. **Punto de corte para "archivos nuevos".** Se busca la captura completa anterior del mismo
   disco y se toma su fecha. Si no hay ninguna, se usan los últimos 7 días.
3. **Recorrido.** `scanner.scan()` recorre el disco con una pila (sin recursión) usando
   `os.scandir`. En Windows, `scandir` ya trae tamaño y fechas de cada archivo, así que no hace
   falta una llamada extra por archivo; por eso se pueden recorrer ~1 millón de archivos en
   20-60 segundos.
   - **Tamaño de carpetas:** cada carpeta hasta `--depth` niveles tiene un acumulador. Cada
     archivo suma su tamaño a todas sus carpetas "ancestro" registradas (como mucho `depth + 1`
     sumas por archivo). Por ejemplo, con `depth=3`, un archivo en
     `C:\Users\ana\Downloads\juegos\setup.exe` suma a `C:\`, `C:\Users`, `C:\Users\ana` y
     `C:\Users\ana\Downloads`.
   - **Archivos nuevos:** si un archivo pesa al menos `--min-size` y su fecha de creación **o**
     de modificación es posterior al punto de corte, es candidato. Se mantiene un *heap* con los
     `--top` más grandes, así la memoria no crece aunque haya miles de candidatos.
   - **Enlaces:** las carpetas que son *junctions* o *symlinks* (atributo
     `FILE_ATTRIBUTE_REPARSE_POINT`) no se siguen, para evitar bucles y dobles conteos.
   - **Archivos repetidos:** los archivos de 16 MB o más se identifican por su *inode* (índice
     de archivo de NTFS). Si el mismo archivo físico aparece por otra ruta (enlace duro, o
     carpetas que Windows redirige como el `AppData` de las apps de la Microsoft Store), se
     cuenta una sola vez. No se hace con los archivos chicos porque obtener el *inode* cuesta
     una llamada extra al sistema.
   - **Errores:** carpetas sin permiso de lectura se saltean y se cuentan como "sin acceso".
4. **Guardado.** Se insertan la fila de la captura, los tamaños de carpeta (sólo las de 1 MB o
   más, para que la base no crezca de más) y la lista de archivos nuevos, todo en una transacción.

Una captura **rápida** (`--quick`) sólo hace el paso 1.

## Base de datos

SQLite, en `%LOCALAPPDATA%\disk-timeline\history.db`. Se puede abrir con cualquier cliente
SQLite (por ejemplo [DB Browser for SQLite](https://sqlitebrowser.org/)).

```sql
CREATE TABLE snapshots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    taken_at      REAL    NOT NULL,   -- fecha como timestamp unix
    drive         TEXT    NOT NULL,   -- "C", "D"...
    total         INTEGER NOT NULL,   -- bytes
    used          INTEGER NOT NULL,
    free          INTEGER NOT NULL,
    mode          TEXT    NOT NULL,   -- 'quick' | 'full'
    depth         INTEGER,            -- profundidad usada (sólo full)
    new_since     REAL,               -- punto de corte de los archivos nuevos
    files_scanned INTEGER,
    errors        INTEGER,            -- elementos sin acceso
    scan_seconds  REAL
);

CREATE TABLE folder_sizes (
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    path        TEXT    NOT NULL,     -- "C:\Users\ana\Downloads"
    depth       INTEGER NOT NULL,     -- 0 = raíz del disco
    size        INTEGER NOT NULL,     -- bytes, incluye subcarpetas
    file_count  INTEGER NOT NULL,
    PRIMARY KEY (snapshot_id, path)
);

CREATE TABLE new_files (
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    path        TEXT    NOT NULL,
    size        INTEGER NOT NULL,
    created     REAL,                 -- timestamp unix
    modified    REAL
);
```

Ejemplos de consultas útiles:

```sql
-- Espacio usado de C: al final de cada día
SELECT date(taken_at, 'unixepoch', 'localtime') AS dia, MAX(taken_at), used / 1e9 AS gb
FROM snapshots WHERE drive = 'C' GROUP BY dia;

-- Evolución de una carpeta concreta
SELECT datetime(s.taken_at, 'unixepoch', 'localtime'), f.size / 1e9 AS gb
FROM folder_sizes f JOIN snapshots s ON s.id = f.snapshot_id
WHERE f.path = 'C:\Users\ana\Downloads' ORDER BY s.taken_at;

-- Borrar capturas de más de un año (los detalles se borran en cascada)
PRAGMA foreign_keys = ON;
DELETE FROM snapshots WHERE taken_at < strftime('%s', 'now', '-1 year');
VACUUM;
```

## Cómo se calculan los indicadores

| Indicador | Cálculo |
|---|---|
| **Serie diaria** | De cada día (hora local) se toma la **última** captura, rápida o completa. |
| **Cambio diario** | `usado(día) − usado(día anterior con datos)`. Si faltan días en el medio, el cambio acumula todo ese período. |
| **Promedio diario** | Promedio de los cambios diarios de los últimos 15 días con datos (en el panel) o del rango de `--days` (en la consola). |
| **Se llena en** | `libre ÷ promedio diario`, sólo si el promedio es positivo. |
| **Crecimiento de carpetas** | `tamaño(captura B) − tamaño(captura A)` por ruta. Una carpeta que no existe en A figura como "nueva"; una que no existe en B, como "borrada". Por defecto se comparan las dos últimas capturas completas. |

> El crecimiento de carpetas sólo se puede calcular entre capturas **completas** que hayan usado
> una profundidad igual o mayor al nivel que se consulta.

## API del panel web

El servidor (`disk-timeline serve`) escucha en `127.0.0.1:8765` y expone:

| Método y ruta | Devuelve |
|---|---|
| `GET /api/drives` | Discos con historial y su último estado. |
| `GET /api/daily?drive=C` | Serie diaria (una entrada por día). |
| `GET /api/series?drive=C` | Todas las capturas, sin agrupar por día. |
| `GET /api/snapshots?drive=C` | Capturas completas (id, fecha, archivos escaneados...). |
| `GET /api/growth?drive=C&from=ID&to=ID&depth=N&limit=N` | Carpetas que más cambiaron. |
| `GET /api/new?drive=C&snapshot=ID&limit=N` | Archivos nuevos de una captura (por defecto la última). |
| `GET /api/recent-new?drive=C&limit=N` | Archivos nuevos de todas las capturas. |
| `GET /api/job` | Estado de la captura en curso iniciada desde el panel. |
| `POST /api/snapshot` `{"full": true, "drives": ["C"]}` | Inicia una captura en segundo plano. |
| `POST /api/reveal` `{"path": "C:\\..."}` | Muestra el archivo en el Explorador. |

Todas las respuestas son JSON con tamaños en bytes y fechas como timestamp unix.

Las peticiones `POST` exigen la cabecera `X-Disk-Timeline: 1`. Un sitio web cualquiera no puede
enviarla a `localhost` sin un permiso CORS que el servidor nunca concede, así que otras páginas
abiertas en tu navegador no pueden iniciar capturas ni abrir el Explorador.

## Tarea programada

`disk-timeline schedule install` hace dos cosas:

1. Escribe `%LOCALAPPDATA%\disk-timeline\run_snapshot.pyw`, un script mínimo que ejecuta
   `disk-timeline snapshot --quiet` y guarda la salida en `scheduled.log`. La extensión `.pyw`
   y `pythonw.exe` hacen que no se abra ninguna ventana.
2. Registra la tarea `disk-timeline` con `schtasks /Create /XML`. Se usa XML (y no las opciones
   simples de `schtasks`) para poder activar:
   - `StartWhenAvailable`: si la PC estaba apagada a la hora programada, corre al encenderla;
   - `DisallowStartIfOnBatteries = false`: corre también a batería;
   - `Priority = 7`: prioridad baja;
   - `ExecutionTimeLimit = 2 h` y `MultipleInstancesPolicy = IgnoreNew`.

La tarea corre con tu usuario y sin privilegios elevados.

## Decisiones de diseño

- **Sin dependencias.** Instalar y mantener es trivial, y no hay riesgo de que una actualización
  de terceros rompa la herramienta.
- **Un solo recorrido por captura.** Tamaños de carpetas y archivos nuevos salen del mismo
  recorrido, en lugar de escanear dos veces.
- **Profundidad limitada.** Guardar el tamaño de *todas* las carpetas haría crecer la base muy
  rápido. Con 3 niveles se llega a carpetas como `C:\Users\ana\Downloads`, que suele ser
  suficiente para saber dónde buscar; se puede subir con `--depth`.
- **Tamaño lógico, no "tamaño en disco".** Se usa el tamaño del archivo (`st_size`). Obtener el
  tamaño en disco requiere una llamada extra por archivo y haría el escaneo mucho más lento.
- **Gráficas propias en SVG.** Así el panel funciona sin internet y respeta el tema
  claro/oscuro del sistema.
