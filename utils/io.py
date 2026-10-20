"""Find the BAAC files on data.gouv.fr, download them (once) and read them as text."""

import re

import pandas as pd
import requests

import constants as C

# The file names on data.gouv.fr change between years ("caracteristiques-2019.csv",
# "carcteristiques-2022.csv", "Caract_2024.csv"...). This pattern accepts every spelling.
# The ^...$ anchors reject "vehicules-immatricules-baac-YYYY.csv", which is another file.
RESOURCE_PATTERN = re.compile(
    r"^(?P<table>caract|carcteristiques|caracteristiques|lieux|vehicules|usagers)[-_](?P<year>\d{4})\.csv$",
    flags=re.IGNORECASE,
)
# Spelling found in the file name -> our table name.
TABLE_NAMES = {"caract": "caract", "carcteristiques": "caract", "caracteristiques": "caract",
               "lieux": "lieux", "vehicules": "vehicules", "usagers": "usagers"}


def raw_path(table, year):
    """Local file name, the same for every year: data/raw/caract-2022.csv."""
    return C.RAW_DIR / f"{table}-{year}.csv"


def download_file(url, dest, force=False):
    """Download url to dest, unless the file is already there (cache)."""
    if dest.exists() and not force:
        print(f"cached   {dest.name}")
        return dest
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(response.content)  # written only once the download is complete
    print(f"download {dest.name} ({len(response.content) / 1e6:.1f} MB)")
    return dest


def download_baac(force=False):
    """Download the 4 tables for every year in C.YEARS, plus the PDF describing the variables."""
    response = requests.get(C.DATASET_API_URL, timeout=120)
    response.raise_for_status()
    resources = response.json()["resources"]

    urls = {}
    pdf_url = None
    for resource in resources:
        if pdf_url is None and resource["title"].strip().lower() == C.DESCRIPTION_PDF_TITLE:
            pdf_url = resource["url"]
        # The clean file name is in the title for some years and at the end of the URL for others.
        for name in [resource["title"], resource["url"].rsplit("/", 1)[-1]]:
            match = RESOURCE_PATTERN.match(name.strip())
            if match and int(match["year"]) in C.YEARS:
                urls.setdefault((TABLE_NAMES[match["table"].lower()], int(match["year"])), resource["url"])
                break

    missing = [(table, year) for year in C.YEARS for table in C.TABLES if (table, year) not in urls]
    if missing:
        raise RuntimeError(f"No file found on data.gouv.fr for: {missing}")

    paths = [download_file(urls[(table, year)], raw_path(table, year), force)
             for year in C.YEARS for table in C.TABLES]
    if pdf_url:
        download_file(pdf_url, C.DESCRIPTION_PDF_FILE, force)
    return paths


def download_geojson(force=False):
    """Download the département boundaries used for the map."""
    return download_file(C.GEOJSON_URL, C.GEOJSON_RAW_FILE, force)


def read_raw_csv(path):
    """Read one raw BAAC file with every column as text.

    Text keeps codes such as "01" and "2A" intact; numbers and the decimal comma
    are converted later in prep.py. The files use ";" as separator. Their encoding
    is not documented: 2019–2024 are UTF-8, Latin-1 is a fallback for other years.
    """
    try:
        return pd.read_csv(path, sep=";", encoding="utf-8", dtype=str, keep_default_na=False)
    except UnicodeDecodeError:
        return pd.read_csv(path, sep=";", encoding="latin-1", dtype=str, keep_default_na=False)
