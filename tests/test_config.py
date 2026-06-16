"""Environment configuration: resolution and command-line override precedence."""

import datetime as dt
import logging

import pytest

from fluvilog import config
from fluvilog.cli import build_parser
from fluvilog.constants import (
    DEFAULT_API_HOST,
    DEFAULT_API_PORT,
    DEFAULT_DB_PATH,
    DEFAULT_INTERVAL,
    DEFAULT_LOG_LEVEL,
    DEFAULT_MAX_CATCHUP_DAYS,
)

_VARS = [
    "FLUVILOG_DB",
    "FLUVILOG_INTERVAL",
    "FLUVILOG_MAX_CATCHUP",
    "FLUVILOG_STATION",
    "FLUVILOG_API_HOST",
    "FLUVILOG_API_PORT",
    "FLUVILOG_CORS_ORIGIN",
    "FLUVILOG_LOG_LEVEL",
]


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start each test from a clean FLUVILOG_* environment."""
    for var in _VARS:
        monkeypatch.delenv(var, raising=False)


def test_defaults_when_unset() -> None:
    env = config.load()
    assert env.db == DEFAULT_DB_PATH
    assert env.interval == str(DEFAULT_INTERVAL)
    assert env.max_catchup == str(DEFAULT_MAX_CATCHUP_DAYS)
    assert env.stations is None
    assert env.api_host == DEFAULT_API_HOST
    assert env.api_port == str(DEFAULT_API_PORT)
    assert env.cors_origins == []
    assert env.log_level == DEFAULT_LOG_LEVEL


def test_env_values_are_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLUVILOG_DB", "/data/water.db")
    monkeypatch.setenv("FLUVILOG_INTERVAL", "10m")
    monkeypatch.setenv("FLUVILOG_API_PORT", "9000")
    env = config.load()
    assert env.db == "/data/water.db"
    assert env.interval == "10m"
    assert env.api_port == "9000"


def test_blank_env_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLUVILOG_DB", "   ")
    assert config.load().db == DEFAULT_DB_PATH


def test_list_values_split_on_commas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLUVILOG_STATION", "BL, SH ,LB")
    monkeypatch.setenv("FLUVILOG_CORS_ORIGIN", "http://a.test,http://b.test")
    env = config.load()
    assert env.stations == ["BL", "SH", "LB"]
    assert env.cors_origins == ["http://a.test", "http://b.test"]


def test_cli_overrides_env_db(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLUVILOG_DB", "/data/env.db")
    parser = build_parser(config.load())
    assert parser.parse_args(["collect"]).db == "/data/env.db"
    assert parser.parse_args(["collect", "--db", "cli.db"]).db == "cli.db"


def test_interval_string_default_coerced_by_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FLUVILOG_INTERVAL", "10m")
    args = build_parser(config.load()).parse_args(["collect"])
    assert args.interval == 600.0  # parse_interval applied to the string default


def test_port_string_default_coerced_to_int() -> None:
    args = build_parser(config.load()).parse_args(["serve-api"])
    assert args.port == DEFAULT_API_PORT
    assert isinstance(args.port, int)


def test_max_catchup_env_and_int_coercion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLUVILOG_MAX_CATCHUP", "3")
    args = build_parser(config.load()).parse_args(["collect"])
    assert args.max_catchup == 3
    assert isinstance(args.max_catchup, int)


def test_backfill_parses_iso_dates() -> None:
    parser = build_parser(config.load())
    args = parser.parse_args(["backfill", "--from", "2025-06-01", "--to", "2025-06-10"])
    assert args.start == dt.date(2025, 6, 1)
    assert args.end == dt.date(2025, 6, 10)


def test_backfill_to_defaults_to_none_for_run_layer() -> None:
    args = build_parser(config.load()).parse_args(["backfill", "--from", "2025-06-01"])
    assert args.end is None  # _run_backfill substitutes today


def test_backfill_requires_from() -> None:
    with pytest.raises(SystemExit):
        build_parser(config.load()).parse_args(["backfill"])


def test_backfill_rejects_non_iso_from() -> None:
    with pytest.raises(SystemExit):
        build_parser(config.load()).parse_args(["backfill", "--from", "01.06.2025"])


def test_cors_origin_default_is_none_so_main_can_use_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FLUVILOG_CORS_ORIGIN", "http://env.test")
    parser = build_parser(config.load())
    # No flag → None, so main() substitutes the environment fallback.
    assert parser.parse_args(["serve-api"]).cors_origin is None
    # Explicit flags replace rather than extend the environment value.
    args = parser.parse_args(["serve-api", "--cors-origin", "http://cli.test"])
    assert args.cors_origin == ["http://cli.test"]


def test_parse_log_level_is_case_insensitive() -> None:
    assert config.parse_log_level("debug") == logging.DEBUG
    assert config.parse_log_level("  Warning ") == logging.WARNING


def test_parse_log_level_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        config.parse_log_level("verbose")


def test_log_level_env_is_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLUVILOG_LOG_LEVEL", "DEBUG")
    assert config.load().log_level == "DEBUG"


def test_log_level_default_coerced_to_int() -> None:
    args = build_parser(config.load()).parse_args(["collect"])
    assert args.log_level == logging.INFO  # DEFAULT_LOG_LEVEL string coerced by type=


def test_log_level_flag_overrides_default() -> None:
    args = build_parser(config.load()).parse_args(["collect", "--log-level", "debug"])
    assert args.log_level == logging.DEBUG


def test_log_level_shared_across_subcommands() -> None:
    # The parent parser wires --log-level to every subcommand, not just collect.
    args = build_parser(config.load()).parse_args(["list", "--log-level", "WARNING"])
    assert args.log_level == logging.WARNING
