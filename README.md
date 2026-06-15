# fluvilog

Near-real-time readings from Hamburg's water-quality network (WGMN), via the
public [Wassergüte-Auskunft](https://serviceportal.hamburg.de) service.

By default it runs as a continuous service that polls and stores readings into
SQLite. A one-shot mode prints the latest values as a table instead, and an
optional HTTP API serves the stored data.

## Requirements

- Python 3.13
- [uv](https://docs.astral.sh/uv/) (recommended to make use of provided configuration and dependency lockfile)

## Getting started

```sh
uv sync --extra api     # api extra is optional, needed only for `serve-api` mode
```

Without uv: `python -m venv .venv && .venv/bin/pip install -e .` (add `'.[api]'`
for the HTTP API).

Once installed:

```sh
uv run fluvilog list    # list stations (no egress here)
uv run fluvilog once    # one-shot fetch and print
uv run fluvilog         # Continuously fetch and store (default metrics, all stations)
```

Bare `fluvilog` (no subcommand) runs `collect`. A single fetch cycle takes ~30–50 s — this is due to the way the data is provided, not an issue with your network or the code.

Configuration arguments are provided to select specific stations, metrics, configure fetch intervals and more. `fluvilog --help` to your rescue.

## HTTP API (optional)

Install the `[api]` extra, then:

```sh
uv run fluvilog serve-api --db water.db --cors-origin http://localhost:5173
```

The API opens the database read-only per request, so it can run concurrently with
`collect` (the single writer) under SQLite WAL. Endpoints:

- `GET /api/stations` — station catalogue with WGS84 coordinates
- `GET /api/readings/latest?station=&parameter=` — latest reading per series
- `GET /api/readings?from=&to=&station=&parameter=` — readings in a window (≤30 days)

## Data source

The Wassergüte-Auskunft limits each request to ≤5 stations and ≤5 parameters
(otherwise it silently truncates), so fetches are batched around that. Readings
arrive at a 10-minute cadence and are stored idempotently, keyed on
`(station, parameter, timestamp)`, so the poll interval is decoupled from the
source cadence.

## Docker

```sh
docker build -t fluvilog .
docker run -v "$PWD/data:/data" fluvilog        # collect into /data/fluvilog.db
```
