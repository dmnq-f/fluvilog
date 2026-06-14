"""Near-real-time readings from Hamburg's water quality network (WGMN).

Polls the public HamburgService platform (Wassergüte-Auskunft) at
serviceportal.hamburg.de and, by default, stores readings continuously.

Usage:
    fluvilog                          # serve: poll and store (default subcommand)
    fluvilog serve --station BL SH    # serve only specific stations
    fluvilog serve --db water.db --interval 10m
    fluvilog once                     # one-shot fetch and print
    fluvilog once --csv values.csv    # ... and write to CSV
    fluvilog list                     # list known stations
"""

import argparse
import logging
import sqlite3
import sys

import pandas as pd
import requests

from .constants import DEFAULT_DB_PATH, DEFAULT_INTERVAL, DEFAULT_PARAMETERS, STATIONS
from .service import parse_interval, serve
from .storage import IncompatibleSchemaError, SqliteStorage
from .wgmn import fetch

_COMMANDS = {"serve", "once", "list"}


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


def _run_serve(args: argparse.Namespace) -> int:
    """Run the continuous poll-and-store loop."""
    codes = resolve_codes(args.station)
    if not codes:
        return 2

    try:
        with SqliteStorage(args.db) as store:
            return serve(codes, DEFAULT_PARAMETERS, store, args.interval)
    except IncompatibleSchemaError as e:
        print(str(e), file=sys.stderr)
        return 1
    except sqlite3.Error as e:
        print(f"Database error: {e}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    """Entry point. Bare invocation (no subcommand) runs `serve`."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )
    argv = sys.argv[1:] if argv is None else list(argv)
    if not argv or (argv[0] not in _COMMANDS and argv[0] not in {"-h", "--help"}):
        argv = ["serve", *argv]

    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="command", required=True)

    p_serve = sub.add_parser("serve", help="Continuously fetch and store (default)")
    p_serve.add_argument(
        "--station", nargs="+", metavar="CODE/NAME", help="Only these stations"
    )
    p_serve.add_argument(
        "--db",
        metavar="PATH",
        default=DEFAULT_DB_PATH,
        help=f"SQLite database path (default: {DEFAULT_DB_PATH})",
    )
    p_serve.add_argument(
        "--interval",
        type=parse_interval,
        default=float(DEFAULT_INTERVAL),
        metavar="DURATION",
        help=f"Poll interval, e.g. 30s/10m/1h (default: {DEFAULT_INTERVAL}s)",
    )

    p_once = sub.add_parser("once", help="One-shot fetch and print")
    p_once.add_argument(
        "--station", nargs="+", metavar="CODE/NAME", help="Only these stations"
    )
    p_once.add_argument("--csv", metavar="PATH", help="Write result to CSV")

    sub.add_parser("list", help="List known stations and exit")

    args = ap.parse_args(argv)

    if args.command == "list":
        return _run_list()
    if args.command == "once":
        return _run_once(args)
    return _run_serve(args)
