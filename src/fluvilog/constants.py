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

# Serve-mode defaults.
DEFAULT_INTERVAL = 600  # seconds between polls (source updates ~every 10 min)
MIN_INTERVAL = 30  # floor enforced by --interval parsing
DEFAULT_DB_PATH = "fluvilog.db"  # SQLite file, relative to cwd

# Schema object names (DDL itself lives in storage.py).
TABLE_READINGS = "readings"  # fact table
TABLE_STATIONS = "stations"  # station dimension
TABLE_PARAMETERS = "parameters"  # parameter dimension
VIEW_READINGS_FULL = "readings_full"  # denormalized join of the three
