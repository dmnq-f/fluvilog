"""Near-real-time readings from Hamburg's water quality network (WGMN).

Polls the public HamburgService platform (Wassergüte-Auskunft) at
serviceportal.hamburg.de and, by default, stores readings continuously.

Usage:
    fluvilog                          # collect: poll and store (default subcommand)
    fluvilog collect --station BL SH  # collect only specific stations
    fluvilog collect --db water.db --interval 10m
    fluvilog once                     # one-shot fetch and print
    fluvilog once --csv values.csv    # ... and write to CSV
    fluvilog backfill --from 2025-01-01  # fetch and store a historical range
    fluvilog list                     # list known stations
    fluvilog serve-api                # serve the HTTP read API (needs [api] extra)
"""

import argparse
import datetime as dt
import logging
import sqlite3
import sys
from typing import Any

import pandas as pd
import requests

from . import config
from .constants import MAX_LIST_WINDOW_DAYS, PARAMETERS, STATIONS
from .service import backfill, collect
from .storage import IncompatibleSchemaError, SqliteStorage
from .wgmn import fetch

_COMMANDS = {"collect", "once", "list", "serve-api", "backfill"}

log = logging.getLogger(__name__)

_LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"
_LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"


def _iso_date(text: str) -> dt.date:
    """Parse an ISO 8601 date (YYYY-MM-DD); raises for argparse on bad input."""
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"not an ISO date (YYYY-MM-DD): {text!r}"
        ) from None


def resolve_codes(selectors: list[str] | None) -> list[str]:
    """Translate --station arguments (code or name, case-insensitive) to codes."""
    if not selectors:
        return list(STATIONS)
    by_name = {s.name.casefold(): s.code for s in STATIONS.values()}
    codes: list[str] = []
    for sel in selectors:
        if sel.upper() in STATIONS:
            codes.append(sel.upper())
        elif sel.casefold() in by_name:
            codes.append(by_name[sel.casefold()])
        else:
            log.warning("unknown station: %r (list shows all)", sel)
    return codes


def resolve_parameters(selectors: list[str] | None) -> list[int]:
    """Translate --parameter arguments to indices into PARAMETERS.

    Each selector is a 0-based index or a case-insensitive name; absent
    selectors mean all parameters. Unknown selectors are warned and skipped.
    """
    if not selectors:
        return list(range(len(PARAMETERS)))
    by_name = {name.casefold(): idx for idx, name in enumerate(PARAMETERS)}
    idxs: list[int] = []
    for sel in selectors:
        if sel.isdigit() and int(sel) < len(PARAMETERS):
            idxs.append(int(sel))
        elif sel.casefold() in by_name:
            idxs.append(by_name[sel.casefold()])
        else:
            log.warning("unknown parameter: %r", sel)
    return idxs


def _run_list() -> int:
    """Print the station catalogue and exit."""
    print("# Known WGMN stations:")
    for s in STATIONS.values():
        print(f"  {s.code}  {s.name} ({s.water_body})")
    return 0


def _run_once(args: argparse.Namespace) -> int:
    """Fetch the latest values once, print them, and optionally write CSV."""
    codes = resolve_codes(args.station)
    params = resolve_parameters(args.parameter)
    if not codes or not params:
        return 2

    try:
        df = fetch(codes, params)
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
    params = resolve_parameters(args.parameter)
    if not codes or not params:
        return 2

    try:
        with SqliteStorage(args.db) as store:
            return collect(
                codes,
                params,
                store,
                args.interval,
                max_catchup_days=args.max_catchup,
            )
    except IncompatibleSchemaError as e:
        log.error("%s", e)
        return 1
    except sqlite3.Error as e:
        log.error("database error: %s", e)
        return 1


def _run_backfill(args: argparse.Namespace) -> int:
    """Fetch and store a historical [--from, --to] range, chunked and idempotent."""
    codes = resolve_codes(args.station)
    params = resolve_parameters(args.parameter)
    if not codes or not params:
        return 2

    end = args.end or dt.date.today()
    if args.start > end:
        print("--from must not be after --to", file=sys.stderr)
        return 2

    try:
        with SqliteStorage(args.db) as store:
            return backfill(codes, params, store, args.start, end)
    except IncompatibleSchemaError as e:
        log.error("%s", e)
        return 1
    except sqlite3.Error as e:
        log.error("database error: %s", e)
        return 1


def _uvicorn_log_config() -> dict[str, Any]:
    """Clone uvicorn's default logging config with timestamps matching the CLI.

    Rewrites the `default` and `access` formatters to the `main`/`collect` format
    so the API's startup and access logs read consistently across both services.
    Call only after uvicorn imports successfully (the [api] extra owns it).
    """
    import copy

    from uvicorn.config import LOGGING_CONFIG

    log_config = copy.deepcopy(LOGGING_CONFIG)
    formatters = log_config["formatters"]
    formatters["default"]["fmt"] = _LOG_FORMAT
    formatters["default"]["datefmt"] = _LOG_DATEFMT
    formatters["access"]["fmt"] = _LOG_FORMAT.replace(
        "%(message)s", '%(client_addr)s - "%(request_line)s" %(status_code)s'
    )
    formatters["access"]["datefmt"] = _LOG_DATEFMT
    return log_config


def _run_serve_api(args: argparse.Namespace) -> int:
    """Serve the HTTP read API under uvicorn (requires the optional [api] extra).

    Imports the web stack lazily so the base CLI works without [api] installed.
    """
    try:
        import uvicorn

        from .api import create_app
    except ImportError:
        log.error(
            "The HTTP API needs the optional dependencies. "
            "Install them with: pip install 'fluvilog[api]'"
        )
        return 1

    app = create_app(db_path=args.db, allowed_origins=args.cors_origin)
    uvicorn.run(app, host=args.host, port=args.port, log_config=_uvicorn_log_config())
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

    # Shared across every subcommand; `main` applies it once parsing resolves
    # the level (built-in < env < flag) for all commands alike.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--log-level",
        type=config.parse_log_level,
        default=env.log_level,
        metavar="LEVEL",
        help=(
            "Log verbosity: DEBUG/INFO/WARNING/ERROR/CRITICAL "
            f"(default: {env.log_level}; env: FLUVILOG_LOG_LEVEL)"
        ),
    )

    p_collect = sub.add_parser(
        "collect",
        parents=[common],
        help="Continuously fetch and store (default)",
    )
    p_collect.add_argument(
        "--station",
        nargs="+",
        metavar="CODE/NAME",
        default=env.stations,
        help="Only these stations (env: FLUVILOG_STATION)",
    )
    p_collect.add_argument(
        "--parameter",
        nargs="+",
        metavar="NAME/INDEX",
        default=env.parameters,
        help=(
            "Only these parameters, by name or 0-based index "
            "(default: all; env: FLUVILOG_PARAMETER)"
        ),
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
    p_collect.add_argument(
        "--max-catchup",
        type=int,
        default=env.max_catchup,
        metavar="DAYS",
        help=(
            f"On resume, back-fill at most this many days in one poll "
            f"(capped at {MAX_LIST_WINDOW_DAYS}; longer gaps need `backfill`; "
            f"default: {env.max_catchup}; env: FLUVILOG_MAX_CATCHUP)"
        ),
    )

    p_backfill = sub.add_parser(
        "backfill",
        parents=[common],
        help="Fetch and store a historical date range (one-shot)",
    )
    p_backfill.add_argument(
        "--from",
        dest="start",
        required=True,
        type=_iso_date,
        metavar="DATE",
        help="Start date, inclusive (YYYY-MM-DD)",
    )
    p_backfill.add_argument(
        "--to",
        dest="end",
        type=_iso_date,
        metavar="DATE",
        help="End date, inclusive (YYYY-MM-DD; default: today)",
    )
    p_backfill.add_argument(
        "--station",
        nargs="+",
        metavar="CODE/NAME",
        default=env.stations,
        help="Only these stations (env: FLUVILOG_STATION)",
    )
    p_backfill.add_argument(
        "--parameter",
        nargs="+",
        metavar="NAME/INDEX",
        default=env.parameters,
        help=(
            "Only these parameters, by name or 0-based index "
            "(default: all; env: FLUVILOG_PARAMETER)"
        ),
    )
    p_backfill.add_argument(
        "--db",
        metavar="PATH",
        default=env.db,
        help=f"SQLite database path (default: {env.db}; env: FLUVILOG_DB)",
    )

    p_once = sub.add_parser("once", parents=[common], help="One-shot fetch and print")
    p_once.add_argument(
        "--station",
        nargs="+",
        metavar="CODE/NAME",
        default=env.stations,
        help="Only these stations (env: FLUVILOG_STATION)",
    )
    p_once.add_argument(
        "--parameter",
        nargs="+",
        metavar="NAME/INDEX",
        default=env.parameters,
        help=(
            "Only these parameters, by name or 0-based index "
            "(default: all; env: FLUVILOG_PARAMETER)"
        ),
    )
    p_once.add_argument("--csv", metavar="PATH", help="Write result to CSV")

    sub.add_parser("list", parents=[common], help="List known stations and exit")

    p_api = sub.add_parser(
        "serve-api",
        parents=[common],
        help="Serve the HTTP read API (needs the [api] extra)",
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
    argv = sys.argv[1:] if argv is None else list(argv)
    if not argv or (argv[0] not in _COMMANDS and argv[0] not in {"-h", "--help"}):
        argv = ["collect", *argv]

    env = config.load()
    args = build_parser(env).parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format=_LOG_FORMAT,
        datefmt=_LOG_DATEFMT,
        stream=sys.stderr,
    )

    if args.command == "list":
        return _run_list()
    if args.command == "once":
        return _run_once(args)
    if args.command == "backfill":
        return _run_backfill(args)
    if args.command == "serve-api":
        if args.cors_origin is None:
            args.cors_origin = env.cors_origins
        return _run_serve_api(args)
    return _run_collect(args)
