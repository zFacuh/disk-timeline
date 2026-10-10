"""Command line interface."""

import argparse
import os
import sys
from datetime import datetime

from . import __version__, analysis, config, db, drives
from .analysis import human_size


def _fmt_time(ts) -> str:
    return "-" if ts is None else datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def _resolve_drives(names) -> list[str]:
    if names:
        return [drives.normalize_drive(n) for n in names]
    return drives.list_fixed_drives()


def cmd_snapshot(args) -> int:
    from .snapshot import take_snapshot

    conn = db.connect()
    targets = _resolve_drives(args.drives)
    for drive in targets:
        label = drives.drive_root(drive)
        if args.quick:
            print(f"[{label}] registrando uso...", flush=True)
        else:
            print(f"[{label}] escaneando (puede tardar unos minutos)...", flush=True)

        def progress(count, current, label=label):
            print(f"  {count:>10,} archivos  {current[:90]}", file=sys.stderr)

        try:
            s = take_snapshot(
                conn, drive,
                full=not args.quick,
                depth=args.depth,
                min_new_size=analysis.parse_size(args.min_size),
                top_new=args.top,
                exclude=args.exclude or (),
                progress=None if args.quiet else progress,
            )
        except OSError as e:
            print(f"  error: {e}", file=sys.stderr)
            continue
        line = f"  usado {human_size(s.used)} de {human_size(s.total)}"
        if s.mode == "full":
            line += (f" | {s.files_scanned:,} archivos en {s.seconds:.0f}s"
                     f" | {s.new_files} archivos nuevos grandes | {s.errors} sin acceso")
        print(line, flush=True)
    return 0


def cmd_status(args) -> int:
    conn = db.connect()
    targets = [drives.normalize_drive(d) for d in args.drives] if args.drives else db.drives(conn)
    if not targets:
        print("Todavía no hay capturas. Ejecutá: disk-timeline snapshot")
        return 1
    for drive in targets:
        days = analysis.daily_series(conn, drive)
        if not days:
            continue
        last = days[-1]
        pct = 100 * last["used"] / last["total"] if last["total"] else 0
        print(f"\n{drives.drive_root(drive)}  usado {human_size(last['used'])} / "
              f"{human_size(last['total'])} ({pct:.1f}%)  libre {human_size(last['free'])}")
        print(f"  {'día':<12}{'usado':>14}{'cambio':>14}")
        for d in days[-args.days:]:
            print(f"  {d['day']:<12}{human_size(d['used']):>14}{human_size(d['delta'], signed=True):>14}")
        changes = [d["delta"] for d in days[-args.days:] if d["delta"] is not None]
        if changes:
            avg = sum(changes) / len(changes)
            print(f"  promedio diario: {human_size(int(avg), signed=True)}")
            if avg > 0:
                days_left = last["free"] / avg
                print(f"  a este ritmo el disco se llena en ~{days_left:,.0f} días")
    return 0


def cmd_growth(args) -> int:
    conn = db.connect()
    drive = drives.normalize_drive(args.drive)
    g = analysis.folder_growth(conn, drive, args.from_id, args.to_id, args.depth, args.limit)
    if not g["to"]:
        print(f"No hay capturas completas de {drive}:. Ejecutá: disk-timeline snapshot --drives {drive}")
        return 1
    if g["from"]:
        print(f"Cambios en {drives.drive_root(drive)} entre {_fmt_time(g['from']['taken_at'])} "
              f"y {_fmt_time(g['to']['taken_at'])}\n")
        print(f"  {'cambio':>12}  {'antes':>11}  {'ahora':>11}  carpeta")
        for f in g["folders"]:
            print(f"  {human_size(f['delta'], signed=True):>12}  {human_size(f['before']):>11}  "
                  f"{human_size(f['after']):>11}  {f['path']}")
    else:
        print(f"Sólo hay una captura completa de {drive}: ({_fmt_time(g['to']['taken_at'])}). "
              "Carpetas más grandes:\n")
        for f in g["folders"]:
            print(f"  {human_size(f['after']):>11}  {f['path']}")
    return 0


def cmd_new(args) -> int:
    conn = db.connect()
    drive = drives.normalize_drive(args.drive)
    if args.all:
        files = analysis.recent_new_files(conn, drive, args.limit)
        if not files:
            print("No se detectaron archivos nuevos todavía.")
            return 1
        print(f"  {'tamaño':>11}  {'detectado':<16}  archivo")
        for f in files:
            print(f"  {human_size(f['size']):>11}  {_fmt_time(f['detected_at']):<16}  {f['path']}")
        return 0
    res = analysis.new_files(conn, drive, args.snapshot, args.limit)
    if not res["snapshot"]:
        print(f"No hay capturas completas de {drive}:.")
        return 1
    snap = res["snapshot"]
    print(f"Archivos nuevos o modificados en {drives.drive_root(drive)} entre "
          f"{_fmt_time(snap['new_since'])} y {_fmt_time(snap['taken_at'])}\n")
    if not res["files"]:
        print("  (ninguno supera el tamaño mínimo)")
    for f in res["files"]:
        print(f"  {human_size(f['size']):>11}  {_fmt_time(max(f['created'] or 0, f['modified'] or 0))}  {f['path']}")
    return 0


def cmd_serve(args) -> int:
    from .server import serve

    serve(args.host, args.port, open_browser=not args.no_browser)
    return 0


def cmd_schedule(args) -> int:
    from . import scheduler

    if args.action == "install":
        return scheduler.install(args.time, quick=args.quick)
    if args.action == "remove":
        return scheduler.remove()
    return scheduler.show()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="disk-timeline",
        description="Historial diario del almacenamiento de tus discos.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--db", metavar="ARCHIVO", help="base de datos a usar (por defecto en %%LOCALAPPDATA%%)")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("snapshot", help="tomar una captura de los discos")
    s.add_argument("--drives", nargs="+", metavar="X", help="discos a capturar (por defecto todos los fijos)")
    s.add_argument("--quick", action="store_true", help="sólo registrar uso/libre, sin escanear")
    s.add_argument("--depth", type=int, default=config.DEFAULT_DEPTH,
                   help="profundidad de carpetas a registrar (por defecto %(default)s)")
    s.add_argument("--min-size", default="10MB", help="tamaño mínimo de archivo nuevo (por defecto %(default)s)")
    s.add_argument("--top", type=int, default=config.DEFAULT_TOP_NEW_FILES,
                   help="cantidad máxima de archivos nuevos a guardar (por defecto %(default)s)")
    s.add_argument("--exclude", nargs="+", metavar="RUTA", help="carpetas a ignorar")
    s.add_argument("--quiet", action="store_true", help="no mostrar progreso")
    s.set_defaults(func=cmd_snapshot)

    s = sub.add_parser("status", help="uso actual y crecimiento diario")
    s.add_argument("drives", nargs="*", metavar="X")
    s.add_argument("--days", type=int, default=14, help="días a mostrar (por defecto %(default)s)")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("growth", help="carpetas que más cambiaron entre dos capturas")
    s.add_argument("drive")
    s.add_argument("--from", dest="from_id", type=int, help="id de captura inicial")
    s.add_argument("--to", dest="to_id", type=int, help="id de captura final")
    s.add_argument("--depth", type=int, help="sólo carpetas de esta profundidad")
    s.add_argument("--limit", type=int, default=30)
    s.set_defaults(func=cmd_growth)

    s = sub.add_parser("new", help="archivos grandes agregados recientemente")
    s.add_argument("drive")
    s.add_argument("--snapshot", type=int, help="id de captura (por defecto la última)")
    s.add_argument("--all", action="store_true", help="historial de todas las capturas")
    s.add_argument("--limit", type=int, default=30)
    s.set_defaults(func=cmd_new)

    s = sub.add_parser("serve", help="abrir el panel web con gráficas")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=config.DEFAULT_PORT)
    s.add_argument("--no-browser", action="store_true", help="no abrir el navegador")
    s.set_defaults(func=cmd_serve)

    s = sub.add_parser("schedule", help="captura diaria automática (Programador de tareas)")
    s.add_argument("action", choices=["install", "remove", "show"])
    s.add_argument("--time", default="21:00", help="hora diaria HH:MM (por defecto %(default)s)")
    s.add_argument("--quick", action="store_true", help="programar sólo capturas rápidas")
    s.set_defaults(func=cmd_schedule)
    return p


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    args = build_parser().parse_args(argv)
    if args.db:
        os.environ["DISK_TIMELINE_DB"] = os.path.abspath(args.db)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
