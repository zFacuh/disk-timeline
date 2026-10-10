<div align="center">

# disk-timeline

**El historial de tus discos: cuánto espacio se ocupa cada día y qué fue lo que lo ocupó.**

[![tests](https://github.com/zFacuh/disk-timeline/actions/workflows/tests.yml/badge.svg)](https://github.com/zFacuh/disk-timeline/actions/workflows/tests.yml)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![Windows](https://img.shields.io/badge/plataforma-Windows-0078D6)
![Sin dependencias](https://img.shields.io/badge/dependencias-ninguna-brightgreen)
[![Licencia MIT](https://img.shields.io/badge/licencia-MIT-green)](LICENSE)

[English version](README.en.md)

</div>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/dashboard-oscuro.jpg">
  <img alt="Panel de disk-timeline con la gráfica de espacio usado, el cambio diario, las carpetas que crecieron y los últimos archivos agregados (datos de demostración)" src="docs/dashboard-claro.jpg">
</picture>

---

## ¿Para qué sirve?

¿Alguna vez el disco `C:` amaneció con 20 GB menos y no tenías idea de por qué?
**disk-timeline** toma una "foto" de tus discos todos los días y te responde:

- 📈 **¿Cómo viene evolucionando el espacio usado?** Gráfica en el tiempo de cada disco.
- 📊 **¿Cuánto creció hoy respecto a ayer?** Cambio diario en MB/GB (positivo o negativo).
- 🗂️ **¿Qué carpetas crecieron?** Compará dos fechas cualesquiera y mirá dónde está la diferencia.
- 🆕 **¿Qué fue lo último que se agregó?** Lista de los archivos grandes nuevos, con su fecha.
- ⏳ **¿Cuándo se va a llenar?** Estimación según el ritmo promedio de crecimiento.

Todo corre en tu PC: no envía nada a internet, no necesita cuenta, ni permisos de administrador,
ni instalar dependencias. Sólo Python.

## Índice

- [Inicio rápido](#inicio-rápido)
- [Instalación](#instalación)
- [Uso](#uso)
  - [Tomar capturas](#tomar-capturas)
  - [Ver el estado en la consola](#ver-el-estado-en-la-consola)
  - [El panel web](#el-panel-web)
  - [Captura automática diaria](#captura-automática-diaria)
- [Referencia de comandos](#referencia-de-comandos)
- [Cómo funciona](#cómo-funciona)
- [Dónde se guardan los datos](#dónde-se-guardan-los-datos)
- [Preguntas frecuentes](#preguntas-frecuentes)
- [Desinstalar](#desinstalar)
- [Contribuir](#contribuir)

## Inicio rápido

```powershell
pip install git+https://github.com/zFacuh/disk-timeline.git
disk-timeline snapshot                    # primera captura (1-2 minutos)
disk-timeline schedule install            # una captura automática por día a las 21:00
disk-timeline serve                       # abre el panel en el navegador
```

Desde el segundo día ya vas a ver el crecimiento diario y qué carpetas cambiaron.

## Instalación

**Requisitos:** Windows 10/11 y [Python 3.10 o superior](https://www.python.org/downloads/)
(marcá *"Add python.exe to PATH"* al instalarlo). Funciona también en Linux/macOS con
algunas limitaciones (ver [preguntas frecuentes](#preguntas-frecuentes)).

**Opción A: instalar con pip** (recomendada)

```powershell
pip install git+https://github.com/zFacuh/disk-timeline.git
```

**Opción B: clonar el repositorio** (para modificar el código)

```powershell
git clone https://github.com/zFacuh/disk-timeline.git
cd disk-timeline
pip install -e .
```

Comprobá que quedó instalado:

```powershell
disk-timeline --version
```

> [!TIP]
> Si Windows dice que `disk-timeline` no se reconoce como comando, la carpeta `Scripts` de
> Python no está en el PATH. Podés usar siempre `python -m disk_timeline` en su lugar:
> `python -m disk_timeline snapshot`, `python -m disk_timeline serve`, etc.

## Uso

### Tomar capturas

Una **captura completa** registra el uso de cada disco, escanea todas las carpetas y detecta
los archivos grandes nuevos:

```text
> disk-timeline snapshot
[C:\] escaneando (puede tardar unos minutos)...
  usado 381.97 GB de 446.14 GB | 1,156,837 archivos en 58s | 200 archivos nuevos grandes | 424 sin acceso
[D:\] escaneando (puede tardar unos minutos)...
  usado 343.41 GB de 1.82 TB | 146,819 archivos en 33s | 0 archivos nuevos grandes | 5 sin acceso
```

Como referencia: un disco con ~1,1 millones de archivos tarda alrededor de 1 minuto la primera
vez y unos 20 segundos las siguientes (Windows mantiene en caché la información de los archivos).

Una **captura rápida** sólo anota el espacio usado y libre. Es instantánea y alcanza para la
gráfica, pero no dice *qué* cambió:

```powershell
disk-timeline snapshot --quick
```

Otras variantes útiles:

```powershell
disk-timeline snapshot --drives C            # sólo el disco C:
disk-timeline snapshot --depth 4             # registrar carpetas hasta 4 niveles (C:\Users\vos\AppData\Local)
disk-timeline snapshot --min-size 100MB      # listar como "nuevos" sólo archivos de 100 MB o más
disk-timeline snapshot --exclude D:\VMs      # no escanear una carpeta
```

### Ver el estado en la consola

**Uso actual y cambio diario:**

```text
> disk-timeline status C

C:\  usado 388.28 GB / 476.00 GB (81.6%)  libre 87.72 GB
  día                  usado        cambio
  2026-10-06       387.26 GB    +388.71 MB
  2026-10-07       387.88 GB    +640.23 MB
  2026-10-08       386.69 GB      -1.19 GB
  2026-10-09       386.82 GB    +136.70 MB
  2026-10-10       388.28 GB      +1.46 GB
  promedio diario: +287.24 MB
  a este ritmo el disco se llena en ~313 días
```

**Qué carpetas cambiaron** (por defecto, entre las dos últimas capturas completas):

```text
> disk-timeline growth C --depth 3

Cambios en C:\ entre 2026-10-09 12:23 y 2026-10-10 12:23

        cambio        antes        ahora  carpeta
    -481.77 MB     18.28 GB     17.81 GB  C:\Users\usuario\Videos
    +343.63 MB     22.39 GB     22.73 GB  C:\Users\usuario\AppData
    -242.09 MB     19.89 GB     19.65 GB  C:\Users\usuario\Downloads
```

Para comparar dos fechas concretas, buscá los números de captura con `disk-timeline list C`
y pasalos así: `disk-timeline growth C --from 12 --to 40`. En el panel web se eligen directamente
por fecha.

**Qué archivos grandes se agregaron:**

```text
> disk-timeline new C

Archivos nuevos o modificados en C:\ entre 2026-10-09 12:23 y 2026-10-10 12:23

      4.70 GB  2026-10-10 09:03  C:\Users\usuario\Downloads\dataset.zip
      3.76 GB  2026-10-09 23:04  C:\Users\usuario\Videos\clip-vacaciones.mov
      3.10 GB  2026-10-09 16:46  C:\Users\usuario\AppData\Local\Temp\installer.msi
```

Con `disk-timeline new C --all` ves el historial de archivos nuevos de todas las capturas.

### El panel web

```powershell
disk-timeline serve
```

Abre `http://127.0.0.1:8765` en tu navegador. El panel muestra:

| Sección | Qué muestra |
|---|---|
| **Indicadores** | Espacio usado y libre, cambio del último día, promedio diario y en cuántos días se llenaría el disco. |
| **Espacio usado** | Gráfica en el tiempo, con rango de 30 días, 90 días, 1 año o todo. Pasá el mouse para ver el detalle de cada día. |
| **Cambio diario** | Barras rojas cuando el disco creció y azules cuando se liberó espacio. También se puede ver como tabla. |
| **¿Qué creció?** | Carpetas que más cambiaron entre dos capturas que elijas, filtrando por nivel de profundidad. |
| **Lo último que se agregó** | Archivos grandes nuevos de la última captura o de todo el historial. El botón **Abrir** lo muestra en el Explorador. |

Desde el panel también podés tomar una **captura rápida** (todos los discos) o un
**escaneo completo** (del disco seleccionado). Se adapta al tema claro/oscuro de Windows
y funciona sin conexión a internet.

El panel sólo es accesible desde tu propia PC. Para usar otro puerto: `disk-timeline serve --port 9000`.

### Captura automática diaria

El historial sirve si hay capturas todos los días, así que lo ideal es programarlas:

```powershell
disk-timeline schedule install                 # todos los días a las 21:00
disk-timeline schedule install --time 13:30    # a otra hora
disk-timeline schedule install --quick         # sólo capturas rápidas (sin escaneo)
disk-timeline schedule show                    # ver la tarea programada
disk-timeline schedule remove                  # quitarla
```

Esto crea una tarea llamada `disk-timeline` en el **Programador de tareas de Windows** que:

- corre en segundo plano, sin abrir ventanas y con prioridad baja;
- **si la PC estaba apagada a esa hora, se ejecuta apenas la encendés**;
- funciona también con la notebook a batería;
- deja un registro en `%LOCALAPPDATA%\disk-timeline\scheduled.log`.

## Referencia de comandos

| Comando | Descripción |
|---|---|
| `disk-timeline snapshot` | Captura completa de todos los discos fijos. |
| `disk-timeline status [X ...]` | Uso actual y cambio diario de los últimos días (`--days N`, por defecto 14). |
| `disk-timeline growth X` | Carpetas que más cambiaron. Opciones: `--from ID`, `--to ID`, `--depth N`, `--limit N`. |
| `disk-timeline list X` | Capturas completas de un disco, con su id, fecha y duración. |
| `disk-timeline new X` | Archivos grandes nuevos de la última captura. Opciones: `--snapshot ID`, `--all`, `--limit N`. |
| `disk-timeline serve` | Panel web. Opciones: `--port N`, `--host H`, `--no-browser`. |
| `disk-timeline schedule install\|remove\|show` | Captura diaria automática. Opciones: `--time HH:MM`, `--quick`. |

Opciones de `snapshot`:

| Opción | Por defecto | Descripción |
|---|---|---|
| `--drives X [X ...]` | todos los discos fijos | Discos a capturar (`C`, `D`, ...). Los USB y de red se omiten salvo que los indiques. |
| `--quick` | no | Sólo registrar uso/libre, sin escanear. |
| `--depth N` | `3` | Hasta qué nivel de carpetas guardar tamaños. `C:\Users` es nivel 1, `C:\Users\vos` nivel 2... |
| `--min-size TAMAÑO` | `10MB` | Tamaño mínimo para que un archivo nuevo aparezca en la lista. Acepta `500KB`, `50MB`, `1.5GB`... |
| `--top N` | `200` | Cuántos archivos nuevos (los más grandes) guardar por captura. |
| `--exclude RUTA [...]` | — | Carpetas que no se escanean. |
| `--quiet` | no | No mostrar el progreso. |

Opción global: `--db ARCHIVO` usa otra base de datos (va **antes** del comando:
`disk-timeline --db prueba.db status`).

## Cómo funciona

Cada captura completa recorre el disco **una sola vez** y guarda en una base SQLite local:

1. **El uso del disco** (total, usado, libre), igual al que muestra el Explorador de Windows.
2. **El tamaño de cada carpeta** hasta el nivel indicado con `--depth`. Comparando estos
   tamaños entre dos capturas se ve qué carpetas crecieron o se achicaron.
3. **Los archivos grandes nuevos**: los que se crearon o modificaron desde la captura anterior.
   En Windows, copiar o descomprimir un archivo le pone fecha de creación nueva, así que
   también se detectan aunque conserven una fecha de modificación vieja.

En la primera captura no hay "anterior", así que se listan los archivos de los últimos 7 días.

Más detalles técnicos (estructura de la base de datos, API del panel, decisiones de diseño)
en [docs/como-funciona.md](docs/como-funciona.md).

## Dónde se guardan los datos

| Qué | Dónde |
|---|---|
| Base de datos | `%LOCALAPPDATA%\disk-timeline\history.db` |
| Registro de la tarea programada | `%LOCALAPPDATA%\disk-timeline\scheduled.log` |
| Script que ejecuta la tarea | `%LOCALAPPDATA%\disk-timeline\run_snapshot.pyw` |

La base ocupa poco: una captura completa de un disco usa menos de 1 MB (casi todo es el tamaño
de las carpetas). Un año de capturas diarias de dos discos ronda los 300 MB; con `--depth 2`,
bastante menos.

Para cambiar la ubicación, definí la variable de entorno `DISK_TIMELINE_HOME` (carpeta) o
`DISK_TIMELINE_DB` (archivo de base de datos).

**Privacidad:** todo queda en tu PC. disk-timeline no se conecta a internet y el panel web
sólo escucha en `127.0.0.1`. La base contiene nombres de carpetas y de archivos, así que no la
compartas si eso te preocupa.

## Preguntas frecuentes

<details>
<summary><b>¿Por qué la suma de las carpetas no coincide con el espacio usado del disco?</b></summary>

Es normal. El espacio usado incluye cosas que no son archivos visibles: la tabla de archivos
del sistema (MFT), los puntos de restauración, la papelera de otros usuarios, carpetas a las
que no hay permiso de acceso, etc. Además, disk-timeline cuenta el tamaño real de cada archivo,
que puede diferir del "tamaño en disco" en archivos comprimidos o muy chicos.
</details>

<details>
<summary><b>¿Qué significa "N sin acceso"?</b></summary>

Son carpetas o archivos que Windows no deja leer sin permisos de administrador (por ejemplo
`C:\System Volume Information`). No hace falta ejecutar como administrador; si lo hacés, ese
número baja y las carpetas del sistema se miden con más precisión.
</details>

<details>
<summary><b>¿Escanear el disco todos los días lo desgasta o pone lenta la PC?</b></summary>

No. Sólo se lee la información de los archivos (nombre, tamaño, fechas), no su contenido.
Es parecido a abrir las propiedades de una carpeta. La tarea programada corre con prioridad
baja y suele tardar menos de un minuto.
</details>

<details>
<summary><b>Un mismo archivo aparece con dos rutas distintas, ¿es un error?</b></summary>

disk-timeline detecta los archivos de 16 MB o más que son el mismo archivo físico (enlaces
duros o rutas que Windows redirige, como el `AppData` de las apps de la Microsoft Store) y los
cuenta una sola vez. En archivos más chicos puede pasar, pero su impacto es mínimo.
</details>

<details>
<summary><b>¿Se escanean los discos USB o de red?</b></summary>

Por defecto no: sólo los discos fijos internos. Podés incluir uno a mano con
`disk-timeline snapshot --drives E`.
</details>

<details>
<summary><b>¿Qué pasa con las carpetas enlazadas (junctions o symlinks)?</b></summary>

No se siguen, para no contar dos veces lo mismo ni entrar en bucles. Se mide el contenido en su
ubicación real.
</details>

<details>
<summary><b>¿Funciona en Linux o macOS?</b></summary>

En parte. Las capturas, la consola y el panel funcionan, escaneando `/` como único disco
(podés indicar otros puntos de montaje con `--drives /home`). La programación automática y el
botón "Abrir" del panel son sólo para Windows; en Linux/macOS podés programar con cron:

```cron
0 21 * * * disk-timeline snapshot --quiet
```
</details>

<details>
<summary><b>¿Puedo probar el panel sin esperar varios días de capturas?</b></summary>

Sí, hay un generador de datos de demostración con 60 días simulados:

```powershell
python scripts/make_demo_db.py demo.db
disk-timeline --db demo.db serve
```
</details>

Más problemas y soluciones en [docs/preguntas-frecuentes.md](docs/preguntas-frecuentes.md).

## Desinstalar

```powershell
disk-timeline schedule remove      # quitar la tarea programada
pip uninstall disk-timeline
```

Si además querés borrar el historial, eliminá la carpeta `%LOCALAPPDATA%\disk-timeline`.

## Contribuir

¡Las sugerencias y mejoras son bienvenidas! Abrí un
[issue](https://github.com/zFacuh/disk-timeline/issues) para reportar un error o proponer una
idea, o mirá [CONTRIBUTING.md](CONTRIBUTING.md) para preparar el entorno y enviar cambios.

## Licencia

[MIT](LICENSE): podés usarlo, modificarlo y distribuirlo libremente.
