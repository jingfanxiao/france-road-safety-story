"""Data quality checks, run on the raw tables (before any cleaning choice).

Outputs in data/processed: quality_report.parquet (one row per check and year),
missingness.parquet (missing cells per table, column and year) and quality_report.json.
"""

import json

import pandas as pd

import constants as C
from utils import prep

# Columns empty by design for most rows: a second/third safety device is rare,
# and the pedestrian fields only apply to pedestrians.
STRUCTURAL_MISSING = {"usagers.secu2", "usagers.secu3", "usagers.locp", "usagers.actp", "usagers.etatp"}

# Free-text or optional columns, where blanks are expected.
TEXT_COLUMNS = {"adr", "voie", "v1", "v2", "pr", "pr1", "lartpc", "larrout", "occutc", "id_usager"}


def check_row(check, table, year, n_rows, n_flagged, description):
    """One line of the report, with a status: pass (0 rows), minor (< 1%) or warning."""
    pct = 100 * n_flagged / n_rows
    status = "pass" if pct == 0 else ("warning" if pct >= C.QUALITY_WARN_PCT else "minor")
    return {"check": check, "table": table, "year": str(year), "n_rows": int(n_rows), "n_flagged": int(n_flagged),
            "pct_flagged": round(pct, 3), "status": status, "description": description}


def per_year(df, mask, check, table, description):
    """Apply one True/False check year by year, then for all years together."""
    rows = [check_row(check, table, year, len(part), mask.loc[part.index].sum(), description)
            for year, part in df.groupby("year")]
    rows.append(check_row(check, table, "all", len(df), mask.sum(), description))
    return rows


def missingness(raw):
    """Count "-1" and empty cells per table, column and year (0 is a valid code, so it is not counted)."""
    frames = []
    for table, df in raw.items():
        columns = [c for c in df.columns if c != "year"]
        is_missing = df[columns].isin(C.MISSING_CODES) | df[columns].isna()
        long = is_missing.groupby(df["year"]).sum().reset_index().melt(
            id_vars="year", var_name="column", value_name="n_missing")
        long["n_rows"] = long["year"].map(df.groupby("year").size())
        long["table"] = table
        frames.append(long)
    out = pd.concat(frames, ignore_index=True)
    out["pct_missing"] = (100 * out["n_missing"] / out["n_rows"]).round(3)
    out["is_text_field"] = out["column"].isin(TEXT_COLUMNS)
    return out[["table", "column", "year", "n_rows", "n_missing", "pct_missing", "is_text_field"]]


def check_duplicates(raw):
    """Fully identical rows, and repeated ids where an id must be unique."""
    rows = []
    for table, df in raw.items():
        description = "Rows identical to an earlier row in all columns."
        if table == "usagers":
            # Before 2021 there is no user id: two passengers with the same seat, sex, birth year...
            # look identical while being two people.
            description += " Before 2021 (no user id) these can be distinct people."
        rows += per_year(df, df.duplicated(keep="first"), "Duplicate rows", table, description)

    caract, vehicles, users = raw["caract"], raw["vehicules"], raw["usagers"]
    rows += per_year(caract, caract.duplicated("Num_Acc"), "Duplicate accident id", "caract",
                     "Num_Acc must identify one accident.")
    rows += per_year(vehicles, vehicles.duplicated(["Num_Acc", "id_vehicule"]), "Duplicate vehicle id",
                     "vehicules", "id_vehicule must be unique within an accident.")
    # id_usager is empty before 2021, and empty values must not count as duplicates.
    rows += per_year(users, users["id_usager"].notna() & users.duplicated("id_usager"), "Duplicate user id",
                     "usagers", "id_usager must be unique (column exists from 2021).")
    return rows


def check_orphans(raw):
    """Records that cannot be joined to the table they belong to."""
    caract, vehicles, users = raw["caract"], raw["vehicules"], raw["usagers"]
    accident_ids = set(caract["Num_Acc"])
    rows = []
    for table in ["lieux", "vehicules", "usagers"]:
        df = raw[table]
        rows += per_year(df, ~df["Num_Acc"].isin(accident_ids), "Orphan accident id", table,
                         "Num_Acc not found in the characteristics table.")
    for table in ["lieux", "vehicules", "usagers"]:
        rows += per_year(caract, ~caract["Num_Acc"].isin(set(raw[table]["Num_Acc"])), f"Accident without {table}",
                         "caract", f"Accident with no record in the {table} table.")

    # Users and vehicles are linked on the pair (accident id, vehicle id).
    vehicle_keys = pd.MultiIndex.from_frame(vehicles[["Num_Acc", "id_vehicule"]])
    user_keys = pd.MultiIndex.from_frame(users[["Num_Acc", "id_vehicule"]])
    rows += per_year(users, pd.Series(~user_keys.isin(vehicle_keys), index=users.index),
                     "User without vehicle", "usagers", "id_vehicule not found in the vehicles table.")
    rows += per_year(vehicles, pd.Series(~vehicle_keys.isin(user_keys), index=vehicles.index),
                     "Vehicle without user", "vehicules",
                     "No user recorded for this vehicle (mostly drivers who fled, per ONISR).")
    return rows


def check_coordinates(raw):
    """Coordinates that are missing, or outside the box of the accident's territory."""
    caract = raw["caract"]
    lat = prep.to_float_comma(caract["lat"])
    lon = prep.to_float_comma(caract["long"])
    missing = lat.isna() | lon.isna()
    out_of_bounds = ~missing & ~prep.coordinates_in_bounds(prep.normalize_dep(caract["dep"]), lat, lon)
    rows = per_year(caract, missing, "Missing coordinates", "caract", "lat/long empty or not numeric.")
    rows += per_year(caract, out_of_bounds, "Coordinates out of bounds", "caract",
                     "lat/long outside the bounding box of the accident's département or territory.")
    return rows


def check_values(raw):
    """Validity rules on single fields."""
    caract, users, places = raw["caract"], raw["usagers"], raw["lieux"]
    rows = []

    hour = pd.to_numeric(caract["hrmn"].str.split(":").str[0], errors="coerce")
    rows += per_year(caract, ~hour.between(0, 23), "Invalid time", "caract", "hrmn is not a valid HH:MM time.")
    date = pd.to_datetime(
        pd.DataFrame({"year": caract["year"], "month": prep.to_int(caract["mois"]), "day": prep.to_int(caract["jour"])}),
        errors="coerce",
    )
    rows += per_year(caract, date.isna(), "Invalid date", "caract", "jour/mois/an do not form a valid date.")
    known_deps = set(C.DEP_TO_REGION) | set(C.BOUNDS_OVERSEAS)
    rows += per_year(caract, ~prep.normalize_dep(caract["dep"]).isin(known_deps), "Unknown département code",
                     "caract", "dep is not a known département or overseas code.")

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


def build_report(raw):
    """Run every check. Returns (checks table, missingness table)."""
    rows = []
    for table, df in raw.items():  # rows per table and year: information only, nothing flagged
        for year, n in df.groupby("year").size().items():
            rows.append(check_row("Rows per year", table, year, n, 0, "Number of records in the raw file."))
    rows += check_duplicates(raw) + check_orphans(raw) + check_coordinates(raw) + check_values(raw)
    return pd.DataFrame(rows), missingness(raw)


def write_report(checks, missing):
    """Save the report files, with a summary (counts per status) in the JSON."""
    checks.to_parquet(C.QUALITY_PARQUET_FILE, index=False)
    missing.to_parquet(C.MISSINGNESS_FILE, index=False)
    overall = checks[checks["year"] == "all"]
    summary = {
        "n_checks": int(len(overall)),
        "n_pass": int((overall["status"] == "pass").sum()),
        "n_minor": int((overall["status"] == "minor").sum()),
        "n_warning": int((overall["status"] == "warning").sum()),
        "warnings": overall.loc[overall["status"] == "warning", "check"].tolist(),
    }
    with open(C.QUALITY_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "checks": checks.to_dict(orient="records")}, f, indent=1, ensure_ascii=False)
    return summary
