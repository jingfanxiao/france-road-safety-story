"""Data quality checks on the raw BAAC tables.

The checks run on the raw files (after trimming spaces and renaming the id
column) so that the report describes the data as published, before any
cleaning choice is applied.

Outputs:
    quality_report.parquet  one row per check (table, year, rows, flagged, status)
    missingness.parquet     missing cells per table × column × year
    quality_report.json     the same checks as JSON, plus a short summary
"""

from __future__ import annotations

import json

import pandas as pd

import constants as C
from utils import prep

# Columns that are empty by design for most rows: a second/third safety device
# rarely exists, and pedestrian fields only apply to pedestrians.
STRUCTURAL_MISSING = {"usagers.secu2", "usagers.secu3", "usagers.locp", "usagers.actp", "usagers.etatp"}

# Free-text or optional columns where blanks are expected and not a defect.
TEXT_COLUMNS = {"adr", "voie", "v1", "v2", "pr", "pr1", "lartpc", "larrout", "occutc", "id_usager"}


# --- Helpers ----------------------------------------------------------------------

def status_for(pct: float) -> str:
    """Traffic-light status from the share of affected rows."""
    if pct == 0:
        return "pass"
    return "warning" if pct >= C.QUALITY_WARN_PCT else "minor"


def check_row(check: str, table: str, year: int | str, n_rows: int, n_flagged: int, description: str) -> dict:
    """One line of the report."""
    pct = 100 * n_flagged / n_rows if n_rows else 0.0
    return {
        "check": check,
        "table": table,
        "year": str(year),
        "n_rows": int(n_rows),
        "n_flagged": int(n_flagged),
        "pct_flagged": round(pct, 3),
        "status": status_for(pct),
        "description": description,
    }


def per_year(df: pd.DataFrame, mask: pd.Series, check: str, table: str, description: str) -> list[dict]:
    """Apply one boolean check year by year and for all years together."""
    rows = []
    for year, part in df.groupby("year"):
        rows.append(check_row(check, table, year, len(part), mask.loc[part.index].sum(), description))
    rows.append(check_row(check, table, "all", len(df), mask.sum(), description))
    return rows


# --- Missingness --------------------------------------------------------------------

def missingness(raw: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Count "-1" and empty cells per table, column and year.

    Code 0 is not counted: for many variables it is a valid answer ("none").
    """
    frames = []
    for table, df in raw.items():
        columns = [c for c in df.columns if c != "year"]
        is_missing = df[columns].isin(C.MISSING_CODES) | df[columns].isna()
        counts = is_missing.groupby(df["year"]).sum()
        totals = df.groupby("year").size()
        long = counts.reset_index().melt(id_vars="year", var_name="column", value_name="n_missing")
        long["n_rows"] = long["year"].map(totals)
        long["table"] = table
        frames.append(long)
    out = pd.concat(frames, ignore_index=True)
    out["pct_missing"] = (100 * out["n_missing"] / out["n_rows"]).round(3)
    out["is_text_field"] = out["column"].isin(TEXT_COLUMNS)
    return out[["table", "column", "year", "n_rows", "n_missing", "pct_missing", "is_text_field"]]


# --- Individual checks -------------------------------------------------------------

def check_rows_per_year(raw: dict[str, pd.DataFrame]) -> list[dict]:
    """Rows per table and year (information only, nothing is flagged)."""
    rows = []
    for table, df in raw.items():
        for year, n in df.groupby("year").size().items():
            rows.append(check_row("Rows per year", table, year, n, 0, "Number of records in the raw file."))
    return rows


def check_duplicates(raw: dict[str, pd.DataFrame]) -> list[dict]:
    """Fully identical rows, and repeated keys where a key must be unique."""
    rows = []
    for table, df in raw.items():
        description = "Rows identical to an earlier row in all columns."
        if table == "usagers":
            # Before 2021 there is no user id, so two passengers with the same
            # seat code, sex, birth year… look identical while being two people.
            description += " Before 2021 (no user id) these can be distinct people."
        rows += per_year(df, df.duplicated(keep="first"), "Duplicate rows", table, description)

    caract = raw["caract"]
    rows += per_year(caract, caract.duplicated("Num_Acc"), "Duplicate accident id", "caract",
                     "Num_Acc must identify one accident.")
    vehicles = raw["vehicules"]
    rows += per_year(vehicles, vehicles.duplicated(["Num_Acc", "id_vehicule"]), "Duplicate vehicle id",
                     "vehicules", "id_vehicule must be unique within an accident.")
    users = raw["usagers"]
    has_id = users["id_usager"].notna()
    rows += per_year(users, has_id & users.duplicated("id_usager"), "Duplicate user id", "usagers",
                     "id_usager must be unique (column exists from 2021).")
    return rows


def check_orphans(raw: dict[str, pd.DataFrame]) -> list[dict]:
    """Records that cannot be joined to the table they depend on."""
    accident_ids = set(raw["caract"]["Num_Acc"])
    rows = []
    for table in ["lieux", "vehicules", "usagers"]:
        df = raw[table]
        rows += per_year(df, ~df["Num_Acc"].isin(accident_ids), "Orphan accident id", table,
                         "Num_Acc not found in the characteristics table.")

    caract = raw["caract"]
    for table in ["lieux", "vehicules", "usagers"]:
        ids = set(raw[table]["Num_Acc"])
        rows += per_year(caract, ~caract["Num_Acc"].isin(ids), f"Accident without {table}", "caract",
                         f"Accident with no record in the {table} table.")

    vehicles = raw["vehicules"]
    users = raw["usagers"]
    vehicle_keys = pd.MultiIndex.from_frame(vehicles[["Num_Acc", "id_vehicule"]])
    user_keys = pd.MultiIndex.from_frame(users[["Num_Acc", "id_vehicule"]])
    rows += per_year(users, pd.Series(~user_keys.isin(vehicle_keys), index=users.index),
                     "User without vehicle", "usagers", "id_vehicule not found in the vehicles table.")
    rows += per_year(vehicles, pd.Series(~vehicle_keys.isin(user_keys), index=vehicles.index),
                     "Vehicle without user", "vehicules",
                     "No user recorded for this vehicle (mostly drivers who fled, per ONISR).")
    return rows


def check_coordinates(raw: dict[str, pd.DataFrame]) -> list[dict]:
    """Coordinates that are missing or outside the box of the declared territory."""
    caract = raw["caract"]
    lat = prep.to_float_comma(caract["lat"])
    lon = prep.to_float_comma(caract["long"])
    dep = prep.normalize_dep(caract["dep"])
    missing = lat.isna() | lon.isna()
    out_of_bounds = ~missing & ~prep.coordinates_in_bounds(dep, lat, lon)
    rows = per_year(caract, missing, "Missing coordinates", "caract", "lat/long empty or not numeric.")
    rows += per_year(caract, out_of_bounds, "Coordinates out of bounds", "caract",
                     "lat/long outside the bounding box of the accident's département or territory.")
    return rows


def check_values(raw: dict[str, pd.DataFrame]) -> list[dict]:
    """Field-level validity rules."""
    caract = raw["caract"]
    users = raw["usagers"]
    places = raw["lieux"]
    rows = []

    hour = pd.to_numeric(caract["hrmn"].str.split(":").str[0], errors="coerce")
    rows += per_year(caract, ~hour.between(0, 23), "Invalid time", "caract", "hrmn is not a valid HH:MM time.")

    date = pd.to_datetime(
        pd.DataFrame({"year": caract["year"], "month": prep.to_int(caract["mois"]), "day": prep.to_int(caract["jour"])}),
        errors="coerce",
    )
    rows += per_year(caract, date.isna(), "Invalid date", "caract", "jour/mois/an do not form a valid date.")

    dep = prep.normalize_dep(caract["dep"])
    known = set(C.DEP_TO_REGION) | set(C.BOUNDS_OVERSEAS)
    rows += per_year(caract, ~dep.isin(known), "Unknown département code", "caract",
                     "dep is not a known département or overseas code.")

    birth = prep.to_int(users["an_nais"])
    age = users["year"] - birth
    rows += per_year(users, birth.isna(), "Missing birth year", "usagers", "an_nais is empty.")
    rows += per_year(users, birth.notna() & ~age.between(0, C.AGE_MAX), "Invalid birth year", "usagers",
                     f"Age outside 0–{C.AGE_MAX} years (birth year after the accident or implausibly old).")

    grav = prep.to_int(users["grav"])
    rows += per_year(users, ~grav.isin(list(C.GRAV_LABELS)).fillna(False), "Missing severity", "usagers",
                     "grav is not filled in (mostly users who fled, from 2021).")

    vma = prep.to_int(places["vma"])
    rows += per_year(places, vma.isna(), "Missing speed limit", "lieux", "vma is not filled in.")
    rows += per_year(places, vma.notna() & ~vma.between(C.VMA_MIN, C.VMA_MAX), "Implausible speed limit", "lieux",
                     f"vma outside {C.VMA_MIN}–{C.VMA_MAX} km/h.")
    rows += per_year(places, places.duplicated("Num_Acc"), "Extra place rows", "lieux",
                     "Additional road rows for the same accident (from 2023); the first one is kept.")
    return rows


# --- Report --------------------------------------------------------------------------

def build_report(raw: dict[str, pd.DataFrame] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run every check and return (checks table, missingness table)."""
    if raw is None:
        raw = {table: prep.load_table(table) for table in C.TABLES}

    rows = (check_rows_per_year(raw) + check_duplicates(raw) + check_orphans(raw)
            + check_coordinates(raw) + check_values(raw))
    checks = pd.DataFrame(rows)
    return checks, missingness(raw)


def summarize(checks: pd.DataFrame) -> dict:
    """Headline figures for the JSON file and the app."""
    overall = checks[(checks["year"] == "all")]
    return {
        "n_checks": int(len(overall)),
        "n_pass": int((overall["status"] == "pass").sum()),
        "n_minor": int((overall["status"] == "minor").sum()),
        "n_warning": int((overall["status"] == "warning").sum()),
        "warnings": overall.loc[overall["status"] == "warning", "check"].tolist(),
    }


def write_report(checks: pd.DataFrame, missing: pd.DataFrame) -> None:
    """Save the report next to the other processed files."""
    C.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    checks.to_parquet(C.QUALITY_PARQUET_FILE, index=False)
    missing.to_parquet(C.MISSINGNESS_FILE, index=False)
    payload = {"summary": summarize(checks), "checks": checks.to_dict(orient="records")}
    with open(C.QUALITY_JSON_FILE, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1, ensure_ascii=False)
