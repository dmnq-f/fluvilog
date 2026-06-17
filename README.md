# fluvilog

[![CI](https://github.com/dmnq-f/fluvilog/actions/workflows/ci.yml/badge.svg)](https://github.com/dmnq-f/fluvilog/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/fluvilog)](https://pypi.org/project/fluvilog/)

Near-real-time readings from Hamburg's water-quality network ([WGMN](https://www.hamburg.de/politik-und-verwaltung/behoerden/bukea/hu/umweltuntersuchungen/wasseruntersuchungen/wasserguetemessnetz)), via the
public [Service Portal](https://serviceportal.hamburg.de/HamburgGateway/Service/Entry/WGMN) service.

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
uv run fluvilog         # Continuously fetch and store (all parameters, all stations)
uv run fluvilog backfill --from 2025-01-01   # fetch and store a historical range
```

Bare `fluvilog` (no subcommand) runs `collect`. A single fetch cycle takes ~30–50 s — this is due to the way the data is provided, not an issue with your network or the code.

Configuration arguments are provided to select specific stations, metrics, configure fetch intervals and more. `fluvilog --help` to your rescue.

## Configuration

Every relevant flag has a `FLUVILOG_*` environment-variable equivalent. A flag
overrides the environment, which overrides the built-in default.

| Variable               | Flag            | Default                                                   |
| ---------------------- | --------------- | --------------------------------------------------------- |
| `FLUVILOG_DB`          | `--db`          | `fluvilog.db`                                             |
| `FLUVILOG_INTERVAL`    | `--interval`    | `600` (seconds; accepts `s`/`m`/`h` suffix)               |
| `FLUVILOG_MAX_CATCHUP` | `--max-catchup` | `7` (days back-filled per poll on resume)                 |
| `FLUVILOG_STATION`     | `--station`     | all stations (comma-separated codes or names)             |
| `FLUVILOG_PARAMETER`   | `--parameter`   | all parameters (comma-separated names or 0-based indices) |
| `FLUVILOG_API_HOST`    | `--host`        | `127.0.0.1`                                               |
| `FLUVILOG_API_PORT`    | `--port`        | `8000`                                                    |
| `FLUVILOG_CORS_ORIGIN` | `--cors-origin` | none (comma-separated origins)                            |
| `FLUVILOG_LOG_LEVEL`   | `--log-level`   | `INFO` (DEBUG/INFO/WARNING/ERROR/CRITICAL)                |

### Gaps after downtime

`collect` resumes from the latest stored reading, so an outage (crash, restart,
deploy) shorter than `--max-catchup` days back-fills automatically on the next
poll — writes are idempotent, so the re-fetched overlap is harmless. A single
query can only cover ~10 days at full 10-minute resolution, which is why the
per-poll catch-up is capped.

For longer gaps (or to seed history), run a one-shot backfill over an explicit
range — it splits the range into source-sized windows and stores each
idempotently, so it is safe to re-run and resumes cleanly after an interruption:

```sh
uv run fluvilog backfill --from 2025-01-01 --to 2025-03-31 --db water.db
```

`--to` defaults to today. Data goes back to each station's start. For windows before a selected station began recording,
backfill omits that station from the request (and warns), so it never polls for
data that cannot exist yet.

## HTTP API (optional)

Install the `[api]` extra, then:

```sh
uv run fluvilog serve-api --db water.db --cors-origin http://localhost:5173
```

The API opens the database read-only per request, so it can run concurrently with
`collect` (the single writer) under SQLite WAL. Endpoints:

- `GET /api/health` — service liveness probe (`{"status": "ok"}`)
- `GET /api/ready` — readiness probe; 200 when the database is reachable, 503 otherwise (`{"service": "ok", "db": "ok"}`)
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

Released images are published to GHCR:

```sh
docker run -v "$PWD/data:/data" ghcr.io/dmnq-f/fluvilog   # collect into /data/fluvilog.db
```

Or build locally:

```sh
docker build -t fluvilog .
docker run -v "$PWD/data:/data" fluvilog
```

To run `collect` and the HTTP API together against a shared database, see
[`examples/compose.yaml`](examples/compose.yaml):

```sh
docker compose -f examples/compose.yaml up -d   # collect (writer) + serve-api on http://localhost:8000
```
