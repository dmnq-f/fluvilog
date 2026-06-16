"""Static configuration: endpoint, request limits, and the station/parameter
catalogues of the HamburgService water quality endpoint."""

from datetime import date

from .models import Station

# Service endpoint (ASP.NET WebForms "Wassergüte-Auskunft").
BASE = "https://serviceportal.hamburg.de/HamburgGateway"
START = f"{BASE}/Service/StartService/WGMN?linkId=0&ars=020000000000"
PFX = "GatewayMaster:ContentSection:wucStationenAuswahlListe1:"
ENCODING = "windows-1252"
TIMEOUT = 60
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Safari/605.1.15"
)

# Service limit per request.
MAX_STATIONS = 5
MAX_PARAMETERS = 5

# The 9 official WGMN stations and their static reference data: name +
# water_body, WGS84 position as (lat, lon) decimal degrees, and recording_since
# (first reporting day — the earliest a backfill can reach). The form's checkbox
# order (cblStationen:0..8) is dictated upstream and read from the live form at
# runtime (see _station_index_map in wgmn.py), not encoded here.
_STATIONS: tuple[Station, ...] = (
    Station("BU", "Bunthaus", "Elbe", 53.46166, 10.06434, date(1988, 5, 1)),
    Station("SH", "Seemannshöft", "Elbe", 53.54024, 9.87984, date(1988, 5, 1)),
    Station("BL", "Blankenese", "Elbe", 53.55587, 9.80545, date(1988, 5, 1)),
    Station("LB", "Lombardsbrücke", "Alster", 53.55725, 9.99797, date(1993, 12, 3)),
    Station("HA", "Haselknick", "Alster", 53.69548, 10.12075, date(1995, 11, 1)),
    Station("TA", "Rosenbrook", "Tarpenbek", 53.60223, 9.98624, date(1991, 12, 19)),
    Station("BK", "Brügkamp", "Ammersbek", 53.71191, 10.16285, date(1992, 1, 1)),
    Station("FH", "Fischerhof", "Bille", 53.48927, 10.21090, date(1996, 8, 1)),
    Station("WA", "Wandsbeker Allee", "Wandse", 53.57616, 10.06895, date(1992, 1, 29)),
)
# Keyed by code; the order above is preserved.
STATIONS: dict[str, Station] = {s.code: s for s in _STATIONS}

# Order of the parameter checkboxes (clbMesswerte:0..13) in the form.
PARAMETERS = [
    "Lufttemperatur",
    "Wassertemperatur",
    "Sauerstoffkonzentration",
    "Sauerstoffsättigung",
    "pH-Wert",
    "Leitfähigkeit Kappa 25",
    "Trübung",
    "Gesamtchlorophyll",
    "Chlorophyll Blaualgen",
    "Chlorophyll Grünalgen",
    "Chlorophyll Kieselalgen",
    "Chlorophyll Cryptophyceen",
    "UV-Absorption",
    "AlarmIndex",
]
# Core parameters (water temp, O2 conc., O2 sat., pH, conductivity, turbidity).
DEFAULT_PARAMETERS = [1, 2, 3, 4, 5, 6]

# Collect-mode defaults.
DEFAULT_INTERVAL = 600  # seconds between polls (source updates ~every 10 min)
MIN_INTERVAL = 30  # floor enforced by --interval parsing
DEFAULT_DB_PATH = "fluvilog.db"  # SQLite file, relative to cwd

# Logging defaults.
DEFAULT_LOG_LEVEL = "INFO"  # root level until --log-level / FLUVILOG_LOG_LEVEL

# Window limits. The source's export only returns 10-min values for windows up
# to 10 days; a longer window degrades to daily means
MAX_LIST_WINDOW_DAYS = 10  # hard ceiling for one query's date span
BACKFILL_CHUNK_DAYS = 7  # span per backfill request (conservative, <= ceiling)
DEFAULT_MAX_CATCHUP_DAYS = 7  # collect's per-poll auto-resume cap on resume

# Timezone of stored reading timestamps; also the offset all read APIs emit.
BERLIN_TZ = "Europe/Berlin"

# HTTP API tier (optional [api] extra; see fluvilog.api).
MAX_WINDOW_DAYS = 30  # largest /api/readings window before a 422
DEFAULT_API_HOST = "127.0.0.1"
DEFAULT_API_PORT = 8000

# Schema object names (DDL itself lives in storage.py).
TABLE_READINGS = "readings"  # fact table
TABLE_STATIONS = "stations"  # station dimension
TABLE_PARAMETERS = "parameters"  # parameter dimension
VIEW_READINGS_FULL = "readings_full"  # denormalized join of the three
