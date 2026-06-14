"""Static configuration: endpoint, request limits, and the station/parameter
catalogues of the HamburgService water quality endpoint."""

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

# Station code -> (station name, body of water). The 9 official WGMN stations.
# The form's checkbox order (cblStationen:0..8) is not encoded here; it is read
# from the live form at runtime (see _station_index_map in wgmn.py).
STATIONS: dict[str, tuple[str, str]] = {
    "BU": ("Bunthaus", "Elbe"),
    "SH": ("Seemannshöft", "Elbe"),
    "BL": ("Blankenese", "Elbe"),
    "LB": ("Lombardsbrücke", "Alster"),
    "HA": ("Haselknick", "Alster"),
    "TA": ("Rosenbrook", "Tarpenbek"),
    "BK": ("Brügkamp", "Ammersbek"),
    "FH": ("Fischerhof", "Bille"),
    "WA": ("Wandsbeker Allee", "Wandse"),
}

# WGS84 (latitude, longitude) per station code. Static reference data: the 9
# WGMN stations are fixed, so coordinates live here rather than in the DB schema.
# Order is (lat, lon) for human sanity; GeoJSON's [lon, lat] is the API's job.
# Keys must stay in sync with STATIONS (enforced by catalogue.stations()).
STATION_COORDS: dict[str, tuple[float, float]] = {
    "BU": (53.46166, 10.06434),  # Bunthaus (Elbe)
    "SH": (53.54024, 9.87984),  # Seemannshöft (Elbe)
    "BL": (53.55587, 9.80545),  # Blankenese (Elbe)
    "LB": (53.55725, 9.99797),  # Lombardsbrücke (Alster)
    "HA": (53.69548, 10.12075),  # Haselknick (Alster)
    "TA": (53.60223, 9.98624),  # Rosenbrook (Tarpenbek)
    "BK": (53.71191, 10.16285),  # Brügkamp (Ammersbek)
    "FH": (53.48927, 10.21090),  # Fischerhof (Bille)
    "WA": (53.57616, 10.06895),  # Wandsbeker Allee (Wandse)
}

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
