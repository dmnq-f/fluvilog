"""Near-real-time readings from Hamburg's water quality network (WGMN).

Polls the public HamburgService platform (Wassergüte-Auskunft) at
serviceportal.hamburg.de and, by default, stores readings continuously.

Usage:
    fluvilog                          # collect: poll and store (default subcommand)
    fluvilog collect --station BL SH  # collect only specific stations
    fluvilog collect --db water.db --interval 10m
    fluvilog once                     # one-shot fetch and print
    fluvilog once --csv values.csv    # ... and write to CSV
    fluvilog list                     # list known stations
    fluvilog serve-api                # serve the HTTP read API (needs [api] extra)
"""

import argparse
import logging
import sqlite3
import sys

import pandas as pd
import requests

from . import config
from .constants import DEFAULT_PARAMETERS, STATIONS
from .service import collect
from .storage import IncompatibleSchemaError, SqliteStorage
from .wgmn import fetch

_COMMANDS = {"collect", "once", "list", "serve-api"}


def resolve_codes(selectors: list[str] | None) -> list[str]:
    """Translate --station arguments (code or name, case-insensitive) to codes."""
    if not selectors:
        return list(STATIONS)
    by_name = {name.casefold(): code for code, (name, _) in STATIONS.items()}
    codes: list[str] = []
    for sel in selectors:
        if sel.upper() in STATIONS:
            codes.append(sel.upper())
        elif sel.casefold() in by_name:
            codes.append(by_name[sel.casefold()])
        else:
            print(f"  ! unknown station: {sel!r} (list shows all)", file=sys.stderr)
    return codes


def _run_list() -> int:
    """Print the station catalogue and exit."""
    print("# Known WGMN stations:")
    for code, (name, water_body) in STATIONS.items():
        print(f"  {code}  {name} ({water_body})")
    return 0


def _run_once(args: argparse.Namespace) -> int:
    """Fetch the latest values once, print them, and optionally write CSV."""
    codes = resolve_codes(args.station)
    if not codes:
        return 2

    try:
        df = fetch(codes, DEFAULT_PARAMETERS)
    except requests.RequestException as e:
        print(f"Network/HTTP error: {e}", file=sys.stderr)
        return 1

    if df.empty:
        print("No measurements available.", file=sys.stderr)
        return 1

    pd.set_option("display.max_rows", None)
    pd.set_option("display.width", 200)
    print(df.to_string(index=False))
    latest = df["timestamp"].max()
    print(
        f"\n{len(df)} measurement(s) from {df['station'].nunique()} station(s), "
        f"latest: {latest:%d.%m.%Y %H:%M}."
    )

    if args.csv:
        df.to_csv(args.csv, index=False)
        print(f"Saved: {args.csv}")
    return 0


def _run_collect(args: argparse.Namespace) -> int:
    """Run the continuous poll-and-store loop."""
    codes = resolve_codes(args.station)
    if not codes:
        return 2

    try:
        with SqliteStorage(args.db) as store:
            return collect(codes, DEFAULT_PARAMETERS, store, args.interval)
    except IncompatibleSchemaError as e:
        print(str(e), file=sys.stderr)
        return 1
    except sqlite3.Error as e:
        print(f"Database error: {e}", file=sys.stderr)
        return 1


def _run_serve_api(args: argparse.Namespace) -> int:
    """Serve the HTTP read API under uvicorn (requires the optional [api] extra).

    Imports the web stack lazily so the base CLI works without [api] installed.
    """
    try:
        import uvicorn

        from .api import create_app
    except ImportError:
        print(
            "The HTTP API needs the optional dependencies. "
            "Install them with: pip install 'fluvilog[api]'",
            file=sys.stderr,
        )
        return 1

    app = create_app(db_path=args.db, allowed_origins=args.cors_origin)
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


def build_parser(env: config.EnvConfig) -> argparse.ArgumentParser:
    """Build the argument parser, seeding each default from the environment.

    Defaults layer built-in (`constants`) < environment (`env`) < command line:
    every argument's default is the environment-resolved value, and argparse
    prefers an explicitly parsed argument over its default. `--cors-origin`
    defaults to None (not `env.cors_origins`) because its `append` action would
    otherwise extend the environment value rather than replace it; `main`
    substitutes the environment fallback when no flag is given.
    """
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="command", required=True)

    p_collect = sub.add_parser("collect", help="Continuously fetch and store (default)")
    p_collect.add_argument(
        "--station",
        nargs="+",
        metavar="CODE/NAME",
        default=env.stations,
        help="Only these stations (env: FLUVILOG_STATION)",
    )
    p_collect.add_argument(
        "--db",
        metavar="PATH",
        default=env.db,
        help=f"SQLite database path (default: {env.db}; env: FLUVILOG_DB)",
    )
    p_collect.add_argument(
        "--interval",
        type=config.parse_interval,
        default=env.interval,
        metavar="DURATION",
        help=(
            f"Poll interval, e.g. 30s/10m/1h "
            f"(default: {env.interval}; env: FLUVILOG_INTERVAL)"
        ),
    )

    p_once = sub.add_parser("once", help="One-shot fetch and print")
    p_once.add_argument(
        "--station",
        nargs="+",
        metavar="CODE/NAME",
        default=env.stations,
        help="Only these stations (env: FLUVILOG_STATION)",
    )
    p_once.add_argument("--csv", metavar="PATH", help="Write result to CSV")

    sub.add_parser("list", help="List known stations and exit")

    p_api = sub.add_parser(
        "serve-api", help="Serve the HTTP read API (needs the [api] extra)"
    )
    p_api.add_argument(
        "--db",
        metavar="PATH",
        default=env.db,
        help=f"SQLite database path (default: {env.db}; env: FLUVILOG_DB)",
    )
    p_api.add_argument(
        "--host",
        metavar="HOST",
        default=env.api_host,
        help=f"Bind host (default: {env.api_host}; env: FLUVILOG_API_HOST)",
    )
    p_api.add_argument(
        "--port",
        type=int,
        metavar="PORT",
        default=env.api_port,
        help=f"Bind port (default: {env.api_port}; env: FLUVILOG_API_PORT)",
    )
    p_api.add_argument(
        "--cors-origin",
        action="append",
        default=None,
        metavar="ORIGIN",
        help="Allowed CORS origin; repeatable (env: FLUVILOG_CORS_ORIGIN)",
    )
    return ap


def main(argv: list[str] | None = None) -> int:
    """Entry point. Bare invocation (no subcommand) runs `collect`.

    FLUVILOG_* environment variables set defaults; command-line flags override
    them. See `config` for the variable names.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )
    argv = sys.argv[1:] if argv is None else list(argv)
    if not argv or (argv[0] not in _COMMANDS and argv[0] not in {"-h", "--help"}):
        argv = ["collect", *argv]

    env = config.load()
    args = build_parser(env).parse_args(argv)

    if args.command == "list":
        return _run_list()
    if args.command == "once":
        return _run_once(args)
    if args.command == "serve-api":
        if args.cors_origin is None:
            args.cors_origin = env.cors_origins
        return _run_serve_api(args)
    return _run_collect(args)
