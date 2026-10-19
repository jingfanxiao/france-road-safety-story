"""Download and read the raw files.

Downloads are cached on disk: a file that already exists in ``data/raw`` is
not fetched again unless ``force=True``.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd
import requests

import constants as C

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 120
CHUNK_SIZE = 1 << 20  # 1 MiB

# Resource file names are not consistent across years on data.gouv.fr
# (e.g. "Caract_2024.csv", "carcteristiques-2022.csv", "caracteristiques-2019.csv").
# This pattern accepts all known spellings and maps them to one table name.
# It deliberately rejects "vehicules-immatricules-baac-YYYY.csv", a different file.
RESOURCE_PATTERN = re.compile(
    r"^(?P<table>caract|carcteristiques|caracteristiques|lieux|vehicules|usagers)"
    r"[-_](?P<year>\d{4})\.csv$",
    flags=re.IGNORECASE,
)
TABLE_ALIASES = {
    "caract": "caract",
    "carcteristiques": "caract",
    "caracteristiques": "caract",
    "lieux": "lieux",
    "vehicules": "vehicules",
    "usagers": "usagers",
}


# --- Locating resources -------------------------------------------------------

def fetch_dataset_metadata(api_url: str = C.DATASET_API_URL) -> dict:
    """Return the dataset metadata (including its resource list) from the data.gouv API."""
    response = requests.get(api_url, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def parse_resource_name(name: str) -> tuple[str, int] | None:
    """Return (table, year) if a file name is one of the four BAAC tables, else None."""
    match = RESOURCE_PATTERN.match(name.strip())
    if match is None:
        return None
    table = TABLE_ALIASES[match.group("table").lower()]
    return table, int(match.group("year"))


def match_baac_resources(resources: list[dict], years: list[int]) -> dict[tuple[str, int], str]:
    """Map (table, year) -> download URL for the requested years.

    Both the resource title and the last part of its URL are tried, because
    either one may carry the clean file name depending on the year.
    """
    found: dict[tuple[str, int], str] = {}
    for resource in resources:
        url = resource["url"]
        candidates = [resource.get("title", ""), url.rsplit("/", 1)[-1]]
        for name in candidates:
            parsed = parse_resource_name(name)
            if parsed and parsed[1] in years:
                found.setdefault(parsed, url)
                break
    return found


def find_resource_url(resources: list[dict], title: str) -> str | None:
    """Return the URL of the first resource whose title equals ``title``."""
    for resource in resources:
        if resource.get("title", "").strip().lower() == title.lower():
            return resource["url"]
    return None


def raw_path(table: str, year: int) -> Path:
    """Local path of a raw BAAC file, with one naming scheme for every year."""
    return C.RAW_DIR / f"{table}-{year}.csv"


# --- Downloading --------------------------------------------------------------

def download_file(url: str, dest: Path, force: bool = False) -> Path:
    """Download ``url`` to ``dest`` unless it is already there.

    The file is written to a temporary name first, so an interrupted download
    never leaves a truncated file that would later be mistaken for a cached one.
    """
    if dest.exists() and dest.stat().st_size > 0 and not force:
        logger.info("cached   %-45s %8.1f MB", dest.name, dest.stat().st_size / 1e6)
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with requests.get(url, stream=True, timeout=TIMEOUT_SECONDS) as response:
        response.raise_for_status()
        with open(tmp, "wb") as handle:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                handle.write(chunk)
    tmp.replace(dest)
    logger.info("download %-45s %8.1f MB", dest.name, dest.stat().st_size / 1e6)
    return dest


def download_baac(years: list[int] = C.YEARS, force: bool = False) -> list[Path]:
    """Download the four BAAC tables for each year, plus the variable description PDF."""
    metadata = fetch_dataset_metadata()
    resources = metadata["resources"]

    urls = match_baac_resources(resources, years)
    expected = {(table, year) for table in C.TABLES for year in years}
    missing = sorted(expected - set(urls))
    if missing:
        raise RuntimeError(f"No resource found on data.gouv.fr for: {missing}")

    paths = []
    for table, year in sorted(expected, key=lambda key: (key[1], C.TABLES.index(key[0]))):
        paths.append(download_file(urls[(table, year)], raw_path(table, year), force))

    pdf_url = find_resource_url(resources, C.DESCRIPTION_PDF_TITLE)
    if pdf_url:
        download_file(pdf_url, C.DESCRIPTION_PDF_FILE, force)
    else:
        logger.warning("Variable description PDF not found on the dataset page.")
    return paths


def download_geojson(force: bool = False) -> Path:
    """Download the département boundaries used as the map background."""
    return download_file(C.GEOJSON_URL, C.GEOJSON_RAW_FILE, force)


# --- Reading ------------------------------------------------------------------

ENCODINGS = ("utf-8", "latin-1")


def detect_separator(path: Path, encoding: str) -> str:
    """Guess the field separator from the header line (``;`` or ``,``)."""
    with open(path, encoding=encoding) as handle:
        header = handle.readline()
    return ";" if header.count(";") >= header.count(",") else ","


def read_raw_csv(path: Path, nrows: int | None = None) -> pd.DataFrame:
    """Read one raw BAAC file with every column as text.

    Everything is kept as text at this stage: codes such as "2A" or "01" must
    not be turned into numbers, and decimal commas are converted later.
    The encoding varies between years, so UTF-8 is tried before Latin-1.
    """
    last_error: Exception | None = None
    for encoding in ENCODINGS:
        try:
            sep = detect_separator(path, encoding)
            return pd.read_csv(
                path,
                sep=sep,
                encoding=encoding,
                dtype=str,
                keep_default_na=False,
                nrows=nrows,
                low_memory=False,
            )
        except UnicodeDecodeError as error:
            last_error = error
    raise ValueError(f"Could not decode {path.name} with {ENCODINGS}") from last_error
