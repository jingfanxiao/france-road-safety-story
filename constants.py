"""Project-wide constants: paths, scope, thresholds and shared reference tables.

Everything that should stay consistent between the data pipeline and the app
lives here, so a single edit changes the behaviour everywhere.
"""

from pathlib import Path

# --- Reproducibility --------------------------------------------------------
# The pipeline and the app are fully deterministic (no sampling). This seed is
# the single place to fix randomness if a sample or a model is added later.
RANDOM_SEED = 42

# --- Paths ------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

ACCIDENTS_FILE = PROCESSED_DIR / "accidents.parquet"
USERS_AGG_FILE = PROCESSED_DIR / "users_agg.parquet"
QUALITY_PARQUET_FILE = PROCESSED_DIR / "quality_report.parquet"
QUALITY_JSON_FILE = PROCESSED_DIR / "quality_report.json"
MISSINGNESS_FILE = PROCESSED_DIR / "missingness.parquet"
GEOJSON_FILE = PROCESSED_DIR / "departements.geojson"

# A quality check is "warning" above this share of affected rows (in %),
# "minor" below it and "pass" when nothing is flagged.
QUALITY_WARN_PCT = 1.0

# --- Data source --------------------------------------------------------------
DATASET_ID = "53698f4ca3a729239d2036df"
DATASET_API_URL = f"https://www.data.gouv.fr/api/1/datasets/{DATASET_ID}/"
DATASET_PAGE_URL = (
    "https://www.data.gouv.fr/datasets/"
    "bases-de-donnees-annuelles-des-accidents-corporels-de-la-circulation-routiere-"
    "annees-de-2005-a-2024"
)
DATASET_PRODUCER = "ONISR (Observatoire national interministériel de la sécurité routière)"
# Official variable description (codes and definitions), kept next to the raw files.
DESCRIPTION_PDF_TITLE = "description-des-bases-de-donnees-annuelles.pdf"
DESCRIPTION_PDF_FILE = RAW_DIR / "description-des-bases-de-donnees-annuelles.pdf"

# Département boundaries, used only as a map background layer.
# "Contours administratifs" (data.gouv.fr), 2024 vintage, simplified at 1000 m.
GEO_DATASET_PAGE_URL = "https://www.data.gouv.fr/datasets/contours-administratifs"
GEO_LICENCE = "ODbL (Open Database License)"
GEOJSON_URL = (
    "https://object.data.gouv.fr/contours-administratifs/2024/geojson/"
    "departements-1000m.geojson"
)
GEOJSON_RAW_FILE = RAW_DIR / "departements-1000m.geojson"

# The BAAC schema changed in 2019, so earlier years are not comparable.
FIRST_YEAR = 2019
LAST_YEAR = 2024
YEARS = list(range(FIRST_YEAR, LAST_YEAR + 1))

# The four annual tables, joined on the accident id.
TABLES = ["caract", "lieux", "vehicules", "usagers"]

# --- Analysis thresholds ----------------------------------------------------
# Lethality = deaths per 100 injury accidents. Units with fewer accidents than
# this over the selected period give noisy rates, so they are flagged/hidden.
MIN_ACCIDENTS_FOR_RATE = 100
LETHALITY_PER = 100

# --- Geography --------------------------------------------------------------
# Rough bounding boxes (lat_min, lat_max, lon_min, lon_max) used to flag
# coordinates that cannot belong to the declared territory.
BOUNDS_METRO = (41.0, 51.5, -5.5, 10.0)

# Département code -> region name (2016 regions). Codes are zero-padded strings.
DEP_TO_REGION: dict[str, str] = {
    **{d: "Auvergne-Rhône-Alpes" for d in
       ["01", "03", "07", "15", "26", "38", "42", "43", "63", "69", "73", "74"]},
    **{d: "Bourgogne-Franche-Comté" for d in
       ["21", "25", "39", "58", "70", "71", "89", "90"]},
    **{d: "Bretagne" for d in ["22", "29", "35", "56"]},
    **{d: "Centre-Val de Loire" for d in ["18", "28", "36", "37", "41", "45"]},
    **{d: "Corse" for d in ["2A", "2B"]},
    **{d: "Grand Est" for d in
       ["08", "10", "51", "52", "54", "55", "57", "67", "68", "88"]},
    **{d: "Hauts-de-France" for d in ["02", "59", "60", "62", "80"]},
    **{d: "Île-de-France" for d in
       ["75", "77", "78", "91", "92", "93", "94", "95"]},
    **{d: "Normandie" for d in ["14", "27", "50", "61", "76"]},
    **{d: "Nouvelle-Aquitaine" for d in
       ["16", "17", "19", "23", "24", "33", "40", "47", "64", "79", "86", "87"]},
    **{d: "Occitanie" for d in
       ["09", "11", "12", "30", "31", "32", "34", "46", "48", "65", "66", "81", "82"]},
    **{d: "Pays de la Loire" for d in ["44", "49", "53", "72", "85"]},
    **{d: "Provence-Alpes-Côte d'Azur" for d in
       ["04", "05", "06", "13", "83", "84"]},
    "971": "Guadeloupe",
    "972": "Martinique",
    "973": "Guyane",
    "974": "La Réunion",
    "976": "Mayotte",
}
# Other codes found in the data (e.g. overseas collectivities) are grouped
# under this label once verified in the raw files.
OTHER_REGION = "Other overseas territories"


# Boxes for overseas territories, keyed by département / collectivity code.
BOUNDS_OVERSEAS: dict[str, tuple[float, float, float, float]] = {
    "971": (15.8, 16.6, -61.9, -60.9),     # Guadeloupe
    "972": (14.3, 14.9, -61.3, -60.8),     # Martinique
    "973": (2.0, 5.9, -54.7, -51.5),       # Guyane
    "974": (-21.5, -20.8, 55.2, 55.9),     # La Réunion
    "975": (46.7, 47.2, -56.5, -56.1),     # Saint-Pierre-et-Miquelon
    "976": (-13.1, -12.6, 44.9, 45.4),     # Mayotte
    "977": (17.8, 18.0, -63.0, -62.7),     # Saint-Barthélemy
    "978": (18.0, 18.2, -63.2, -62.9),     # Saint-Martin
    "986": (-14.4, -13.1, -178.3, -176.0),  # Wallis-et-Futuna
    "987": (-28.0, -7.0, -155.0, -134.0),  # Polynésie française
    "988": (-23.0, -19.5, 163.5, 168.5),   # Nouvelle-Calédonie
}

# --- BAAC codes -> labels ------------------------------------------------------
# Checked against "Description des bases de données annuelles" (ONISR, 2025-10-21).
# In the raw files "-1" (and empty cells) means "not filled in".
MISSING_CODES = {"-1", ""}

# grav: injury severity of each road user.
GRAV_UNHARMED, GRAV_KILLED, GRAV_HOSPITALISED, GRAV_LIGHT = 1, 2, 3, 4
GRAV_LABELS = {
    GRAV_KILLED: "Killed",
    GRAV_HOSPITALISED: "Hospitalised",
    GRAV_LIGHT: "Slightly injured",
    GRAV_UNHARMED: "Unharmed",
}
SEVERITY_ORDER = ["Killed", "Hospitalised", "Slightly injured", "Unharmed"]

# catu: road user category.
CATU_PEDESTRIAN = 3

# agg: 1 = outside built-up area, 2 = inside built-up area.
AGG_LABELS = {1: "Rural", 2: "Urban"}
AREA_ORDER = ["Urban", "Rural"]

# lum: lighting conditions, grouped into four classes.
# 4 = "night, street lighting not switched on" counts as unlit.
LUM_TO_LIGHT = {1: "Daylight", 2: "Dusk or dawn", 3: "Night, unlit", 4: "Night, unlit", 5: "Night, lit"}
LIGHT_ORDER = ["Daylight", "Dusk or dawn", "Night, lit", "Night, unlit"]

# atm: weather, grouped so that rare classes do not give noisy rates.
ATM_TO_WEATHER = {
    1: "Normal",
    8: "Overcast",
    2: "Rain",
    3: "Rain",
    4: "Snow or hail",
    5: "Fog or smoke",
    6: "Other (wind, glare…)",
    7: "Other (wind, glare…)",
    9: "Other (wind, glare…)",
}
WEATHER_ORDER = ["Normal", "Overcast", "Rain", "Snow or hail", "Fog or smoke", "Other (wind, glare…)"]

# catr: road category.
CATR_LABELS = {
    1: "Motorway",
    2: "National road",
    3: "Departmental road",
    4: "Municipal road",
    5: "Other",
    6: "Other",
    7: "Municipal road",  # "routes de métropole urbaine"
    9: "Other",
}
ROAD_ORDER = ["Motorway", "National road", "Departmental road", "Municipal road", "Other"]

# catv: vehicle category -> vehicle group (codes are stored without leading zero).
CATV_TO_GROUP: dict[int, str] = {
    1: "Bicycle", 80: "Bicycle",                     # 80 = e-bike (VAE)
    50: "E-scooter / PMD", 60: "E-scooter / PMD",    # personal mobility devices
    2: "Moped (<50 cc)", 30: "Moped (<50 cc)",
    31: "Motorcycle", 32: "Motorcycle", 33: "Motorcycle", 34: "Motorcycle",
    41: "Motorcycle", 42: "Motorcycle", 43: "Motorcycle",
    7: "Car",
    10: "Van",
    13: "Truck", 14: "Truck", 15: "Truck", 16: "Truck", 17: "Truck",
    37: "Bus, coach, tram", 38: "Bus, coach, tram", 39: "Bus, coach, tram", 40: "Bus, coach, tram",
}
OTHER_VEHICLE = "Other vehicle"
PEDESTRIAN = "Pedestrian"
# User types shown in the app; the first five are the "vulnerable" road users.
USER_TYPE_ORDER = [
    PEDESTRIAN, "Bicycle", "E-scooter / PMD", "Moped (<50 cc)", "Motorcycle",
    "Car", "Van", "Truck", "Bus, coach, tram", OTHER_VEHICLE,
]
VULNERABLE_USER_TYPES = USER_TYPE_ORDER[:5]

# How to name the people in each group in sentences.
USER_TYPE_PEOPLE = {
    PEDESTRIAN: "pedestrians",
    "Bicycle": "cyclists",
    "E-scooter / PMD": "e-scooter and PMD users",
    "Moped (<50 cc)": "moped riders",
    "Motorcycle": "motorcyclists",
    "Car": "car occupants",
    "Van": "van occupants",
    "Truck": "truck occupants",
    "Bus, coach, tram": "bus, coach and tram occupants",
    OTHER_VEHICLE: "users of other vehicles",
}

# vma: speed limit in km/h. Values outside this range are treated as invalid.
VMA_MIN, VMA_MAX = 5, 130
SPEED_BINS = [0, 30, 50, 70, 80, 90, 110, 130]
SPEED_LABELS = ["≤30 km/h", "40–50 km/h", "60–70 km/h", "80 km/h", "90 km/h", "100–110 km/h", "130 km/h"]

# Age of road users (accident year − birth year).
AGE_MAX = 110
AGE_BINS = [0, 18, 25, 35, 50, 65, 75, AGE_MAX + 1]
AGE_LABELS = ["0–17", "18–24", "25–34", "35–49", "50–64", "65–74", "75+"]
UNKNOWN = "Unknown"

WEEKDAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# --- Labels shared by charts --------------------------------------------------

# Okabe-Ito palette (first six hues), checked for colour-blind separation of
# neighbouring colours. Lighter hues have low contrast on white, so charts
# always pair colour with labels, hover text or a table.
PALETTE = [
    "#0072B2",  # blue
    "#E69F00",  # orange
    "#009E73",  # green
    "#D55E00",  # vermillion
    "#CC79A7",  # pink
    "#56B4E9",  # sky blue
]
MAIN_COLOR = PALETTE[0]
HIGHLIGHT_COLOR = PALETTE[3]
NEUTRAL_COLOR = "#8C8C8C"      # reference lines, "not enough data"
TEXT_COLOR = "#1A1A1A"
GRID_COLOR = "#E5E5E5"
SEQUENTIAL_SCALE = "Blues"     # counts
LETHALITY_SCALE = "OrRd"       # lethality rates

# 2020 is marked on the yearly trend: COVID-19 lockdowns cut traffic that year.
LOCKDOWN_YEAR = 2020

# Sidebar "indicator" choice -> column in the count tables, and how to show it.
INDICATORS = {
    "Injury accidents": {"column": "accidents", "unit": "Accidents (count)", "format": ",.0f"},
    "Deaths": {"column": "killed", "unit": "Deaths (persons)", "format": ",.0f"},
    "Lethality": {"column": "lethality", "unit": "Deaths per 100 accidents", "format": ".1f"},
}

SOURCE_NOTE = f"Source: {DATASET_PRODUCER}, BAAC {FIRST_YEAR}–{LAST_YEAR}, data.gouv.fr"
