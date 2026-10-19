"""Clean the raw BAAC tables, join them and build the tables used by the app.

Pipeline (see ``build_all``):
    raw CSV (text) -> per-table cleaning -> per-accident features
    -> accidents.parquet (one row per accident)
    -> users_agg.parquet (counts of road users, no row-level person data)
    -> departements.geojson (map background, metropolitan France + Corsica)
"""

from __future__ import annotations

import json
import logging

import numpy as np
import pandas as pd

import constants as C
from utils import io

logger = logging.getLogger(__name__)


# --- Loading ------------------------------------------------------------------

def load_table(table: str, years: list[int] = C.YEARS) -> pd.DataFrame:
    """Read one BAAC table for all years, with tidy text values and a ``year`` column."""
    frames = []
    for year in years:
        df = io.read_raw_csv(io.raw_path(table, year))
        # 2022 names the accident id "Accident_Id" instead of "Num_Acc".
        df = df.rename(columns={"Accident_Id": "Num_Acc"})
        # Codes such as " -1" carry stray spaces; ids use non-breaking spaces.
        for col in df.columns:
            df[col] = df[col].str.replace("\xa0", "", regex=False).str.strip()
        df["year"] = year
        frames.append(df)
    # usagers has no "id_usager" column before 2021; concat fills it with NaN.
    return pd.concat(frames, ignore_index=True)


# --- Small cleaning helpers ------------------------------------------------------

def to_int(series: pd.Series) -> pd.Series:
    """Convert a text column of codes to nullable integers; "-1" and blanks become NA."""
    cleaned = series.where(~series.isin(C.MISSING_CODES))
    return pd.to_numeric(cleaned, errors="coerce").astype("Int64")


def to_float_comma(series: pd.Series) -> pd.Series:
    """Convert text with a decimal comma (e.g. "47,56") to floats."""
    return pd.to_numeric(series.str.replace(",", ".", regex=False), errors="coerce")


def normalize_dep(series: pd.Series) -> pd.Series:
    """Zero-pad one-digit département codes ("1" -> "01"); keep "2A", "971" as they are."""
    return series.where(~series.str.fullmatch(r"\d"), "0" + series)


def to_category(series: pd.Series, order: list[str]) -> pd.Series:
    """Ordered categorical so charts and filters keep a meaningful order."""
    return pd.Categorical(series, categories=order, ordered=True)


# --- Per-table cleaning -------------------------------------------------------

def clean_caract(raw: pd.DataFrame) -> pd.DataFrame:
    """Accident characteristics: time, place, light, weather, coordinates."""
    df = pd.DataFrame({"Num_Acc": raw["Num_Acc"].astype("int64"), "year": raw["year"]})

    month = to_int(raw["mois"])
    day = to_int(raw["jour"])
    df["date"] = pd.to_datetime(
        pd.DataFrame({"year": df["year"], "month": month, "day": day}), errors="coerce"
    )
    df["month"] = df["date"].dt.month.astype("Int8")
    df["weekday"] = to_category(df["date"].dt.day_name(), C.WEEKDAY_ORDER)
    df["is_weekend"] = df["date"].dt.dayofweek >= 5

    hour = pd.to_numeric(raw["hrmn"].str.split(":").str[0], errors="coerce")
    df["hour"] = hour.where(hour.between(0, 23)).astype("Int8")

    df["dep"] = normalize_dep(raw["dep"])
    df["urban"] = to_category(to_int(raw["agg"]).map(C.AGG_LABELS), C.AREA_ORDER)
    df["light_cond"] = to_category(to_int(raw["lum"]).map(C.LUM_TO_LIGHT), C.LIGHT_ORDER)
    df["weather"] = to_category(to_int(raw["atm"]).map(C.ATM_TO_WEATHER), C.WEATHER_ORDER)

    df["lat"] = to_float_comma(raw["lat"])
    df["lon"] = to_float_comma(raw["long"])
    return df


def pick_main_place(raw: pd.DataFrame) -> pd.DataFrame:
    """Keep one "lieux" row per accident.

    Since 2023 an accident can have several rows (one per road at a junction).
    The files do not flag the main road, so the first row of each accident is
    kept, which is the order used by the producer. The number of rows is kept
    for the data quality page.
    """
    n_places = raw.groupby("Num_Acc").size().rename("n_places")
    main = raw.drop_duplicates(subset="Num_Acc", keep="first").set_index("Num_Acc")
    main = main.join(n_places)

    out = pd.DataFrame(index=main.index)
    out["road_type"] = to_category(to_int(main["catr"]).map(C.CATR_LABELS), C.ROAD_ORDER)
    vma = to_int(main["vma"])
    out["vma"] = vma.where(vma.between(C.VMA_MIN, C.VMA_MAX))
    out["speed_limit_band"] = pd.cut(
        out["vma"].astype("float"), bins=C.SPEED_BINS, labels=C.SPEED_LABELS
    )
    out["n_places"] = main["n_places"].astype("int8")
    out.index = out.index.astype("int64")
    return out


def vehicle_group(catv: pd.Series) -> pd.Series:
    """Map vehicle category codes to the groups used in the app."""
    return to_int(catv).map(C.CATV_TO_GROUP).fillna(C.OTHER_VEHICLE)


def clean_vehicles(raw: pd.DataFrame) -> pd.DataFrame:
    """One row per vehicle with its group."""
    return pd.DataFrame({
        "Num_Acc": raw["Num_Acc"].astype("int64"),
        "id_vehicule": raw["id_vehicule"],
        "vehicle_group": vehicle_group(raw["catv"]),
    })


def clean_users(raw: pd.DataFrame, vehicles: pd.DataFrame) -> pd.DataFrame:
    """One row per road user with severity, age band and user type.

    The user type is "Pedestrian" for pedestrians and otherwise the group of
    the vehicle the user was in. Pedestrians are linked to the vehicle that hit
    them, so their own type must come from ``catu``, not from the vehicle.
    """
    users = pd.DataFrame({
        "Num_Acc": raw["Num_Acc"].astype("int64"),
        "id_vehicule": raw["id_vehicule"],
        "year": raw["year"],
        "catu": to_int(raw["catu"]),
        "grav": to_int(raw["grav"]),
        "birth_year": to_int(raw["an_nais"]),
    })
    users = users.merge(vehicles, on=["Num_Acc", "id_vehicule"], how="left", validate="many_to_one")

    is_pedestrian = users["catu"] == C.CATU_PEDESTRIAN
    users["user_type"] = users["vehicle_group"].fillna(C.OTHER_VEHICLE)
    users.loc[is_pedestrian.fillna(False), "user_type"] = C.PEDESTRIAN

    age = users["year"] - users["birth_year"]
    users["age"] = age.where(age.between(0, C.AGE_MAX))
    users["age_band"] = pd.cut(users["age"].astype("float"), bins=C.AGE_BINS, labels=C.AGE_LABELS, right=False)
    return users


# --- Per-accident features --------------------------------------------------------

def user_counts(users: pd.DataFrame) -> pd.DataFrame:
    """Victim counts, worst severity and vulnerable-user flags per accident."""
    # One 0/1 column per severity, then a single grouped sum (fast on ~750k rows).
    indicators = pd.DataFrame({
        "Num_Acc": users["Num_Acc"],
        "n_users": 1,
        "n_killed": (users["grav"] == C.GRAV_KILLED).fillna(False).astype(int),
        "n_hosp": (users["grav"] == C.GRAV_HOSPITALISED).fillna(False).astype(int),
        "n_light": (users["grav"] == C.GRAV_LIGHT).fillna(False).astype(int),
    })
    counts = indicators.groupby("Num_Acc").sum()

    # Severity order killed > hospitalised > light > unharmed, as a rank 3..0.
    rank = users["grav"].map({C.GRAV_KILLED: 3, C.GRAV_HOSPITALISED: 2, C.GRAV_LIGHT: 1, C.GRAV_UNHARMED: 0})
    worst = rank.groupby(users["Num_Acc"]).max()
    rank_to_label = {3: "Killed", 2: "Hospitalised", 1: "Slightly injured", 0: "Unharmed"}
    counts["severity_max"] = to_category(worst.map(rank_to_label), C.SEVERITY_ORDER)
    return counts


def user_type_flags(users: pd.DataFrame, vehicles: pd.DataFrame) -> pd.DataFrame:
    """Flags telling whether an accident involved each vulnerable user type.

    Pedestrians come from the users table; two-wheelers and e-scooters come
    from the vehicles table, so a vehicle counts even if its rider is missing.
    """
    flags = pd.DataFrame(index=pd.Index(users["Num_Acc"].unique(), name="Num_Acc"))
    pedestrians = users.loc[users["user_type"] == C.PEDESTRIAN, "Num_Acc"].unique()
    flags["has_pedestrian"] = flags.index.isin(pedestrians)

    vehicle_flags = {
        "has_cyclist": "Bicycle",
        "has_escooter": "E-scooter / PMD",
        "has_moped": "Moped (<50 cc)",
        "has_motorcycle": "Motorcycle",
    }
    for column, group in vehicle_flags.items():
        ids = vehicles.loc[vehicles["vehicle_group"] == group, "Num_Acc"].unique()
        flags[column] = flags.index.isin(ids)
    return flags


def coordinates_in_bounds(dep: pd.Series, lat: pd.Series, lon: pd.Series) -> pd.Series:
    """True when the coordinates fall inside the box of the declared territory."""
    boxes = [C.BOUNDS_OVERSEAS.get(code, C.BOUNDS_METRO) for code in dep]
    box = pd.DataFrame(boxes, columns=["lat_min", "lat_max", "lon_min", "lon_max"], index=dep.index)
    return (lat.between(box["lat_min"], box["lat_max"])
            & lon.between(box["lon_min"], box["lon_max"]))


def is_overseas_code(dep: pd.Series) -> pd.Series:
    """Overseas codes have three digits (971…988); metropolitan ones have two characters."""
    return dep.str.len() == 3


def load_dep_names(geojson_path=C.GEOJSON_RAW_FILE) -> dict[str, str]:
    """Département code -> name, read from the boundaries file."""
    with open(geojson_path, encoding="utf-8") as handle:
        features = json.load(handle)["features"]
    return {f["properties"]["code"]: f["properties"]["nom"] for f in features}


def build_accidents(caract: pd.DataFrame, places: pd.DataFrame,
                    users: pd.DataFrame, vehicles: pd.DataFrame) -> pd.DataFrame:
    """Join everything into one row per accident."""
    acc = caract.set_index("Num_Acc")
    acc = acc.join(places, how="left")
    acc = acc.join(user_counts(users), how="left")
    acc = acc.join(user_type_flags(users, vehicles), how="left")
    acc = acc.join(vehicles.groupby("Num_Acc").size().rename("n_vehicles"), how="left")

    count_cols = ["n_users", "n_killed", "n_hosp", "n_light", "n_vehicles"]
    acc[count_cols] = acc[count_cols].fillna(0).astype("int16")
    flag_cols = [c for c in acc.columns if c.startswith("has_")]
    acc[flag_cols] = acc[flag_cols].fillna(False).astype(bool)
    acc["is_fatal"] = acc["n_killed"] > 0

    # Geography
    dep_names = load_dep_names()
    acc["dep_name"] = acc["dep"].map(dep_names).fillna(acc["dep"])
    acc["region"] = acc["dep"].map(C.DEP_TO_REGION).fillna(C.OTHER_REGION)
    acc["is_overseas"] = is_overseas_code(acc["dep"])
    in_bounds = coordinates_in_bounds(acc["dep"], acc["lat"], acc["lon"])
    acc["coord_out_of_bounds"] = acc["lat"].notna() & ~in_bounds
    acc.loc[~in_bounds, ["lat", "lon"]] = np.nan

    acc = acc.reset_index()
    return slim_accidents(acc)


def slim_accidents(acc: pd.DataFrame) -> pd.DataFrame:
    """Small dtypes and a fixed column order for the parquet file."""
    acc["year"] = acc["year"].astype("int16")
    for col in ["dep", "dep_name", "region"]:
        acc[col] = acc[col].astype("category")
    acc["lat"] = acc["lat"].astype("float32")
    acc["lon"] = acc["lon"].astype("float32")
    acc["vma"] = acc["vma"].astype("Int16")
    columns = [
        "Num_Acc", "date", "year", "month", "weekday", "is_weekend", "hour",
        "dep", "dep_name", "region", "is_overseas", "urban", "road_type",
        "light_cond", "weather", "vma", "speed_limit_band",
        "n_vehicles", "n_users", "n_killed", "n_hosp", "n_light", "severity_max", "is_fatal",
        "has_pedestrian", "has_cyclist", "has_escooter", "has_moped", "has_motorcycle",
        "lat", "lon", "coord_out_of_bounds", "n_places",
    ]
    return acc[columns]


# --- Aggregated users table -------------------------------------------------------

def build_users_agg(users: pd.DataFrame, accidents: pd.DataFrame) -> pd.DataFrame:
    """Count road users by year × département × area × user type × age band × severity.

    Only counts are stored, so no individual can be singled out from this table.
    """
    context = accidents[["Num_Acc", "dep", "urban"]]
    df = users.merge(context, on="Num_Acc", how="inner", validate="many_to_one")
    df["severity"] = df["grav"].map(C.GRAV_LABELS).fillna(C.UNKNOWN)
    df["age_band"] = df["age_band"].cat.add_categories(C.UNKNOWN).fillna(C.UNKNOWN)

    keys = ["year", "dep", "urban", "user_type", "age_band", "severity"]
    agg = df.groupby(keys, observed=True, dropna=False).size().rename("n_users").reset_index()

    agg["year"] = agg["year"].astype("int16")
    agg["dep"] = agg["dep"].astype("category")
    agg["user_type"] = to_category(agg["user_type"], C.USER_TYPE_ORDER)
    agg["severity"] = to_category(agg["severity"], C.SEVERITY_ORDER + [C.UNKNOWN])
    agg["n_users"] = agg["n_users"].astype("int32")
    return agg


# --- Map background -----------------------------------------------------------------

def build_metro_geojson(decimals: int = 4) -> dict:
    """Keep metropolitan France + Corsica and round coordinates to shrink the file."""
    with open(C.GEOJSON_RAW_FILE, encoding="utf-8") as handle:
        geo = json.load(handle)

    def round_coords(coords):
        if isinstance(coords[0], (int, float)):
            return [round(value, decimals) for value in coords]
        return [round_coords(part) for part in coords]

    features = []
    for feature in geo["features"]:
        code = feature["properties"]["code"]
        if len(code) == 3:  # overseas: 971…989
            continue
        features.append({
            "type": "Feature",
            "id": code,
            "properties": {"code": code, "nom": feature["properties"]["nom"]},
            "geometry": {
                "type": feature["geometry"]["type"],
                "coordinates": round_coords(feature["geometry"]["coordinates"]),
            },
        })
    return {"type": "FeatureCollection", "features": features}


# --- Orchestration ------------------------------------------------------------------

def build_all() -> dict[str, pd.DataFrame]:
    """Run the whole preparation and write the processed files."""
    logger.info("reading raw tables…")
    raw = {table: load_table(table) for table in C.TABLES}

    caract = clean_caract(raw["caract"])
    places = pick_main_place(raw["lieux"])
    vehicles = clean_vehicles(raw["vehicules"])
    users = clean_users(raw["usagers"], vehicles)

    accidents = build_accidents(caract, places, users, vehicles)
    users_agg = build_users_agg(users, accidents)
    geojson = build_metro_geojson()

    C.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    accidents.to_parquet(C.ACCIDENTS_FILE, index=False, compression="zstd")
    users_agg.to_parquet(C.USERS_AGG_FILE, index=False, compression="zstd")
    with open(C.GEOJSON_FILE, "w", encoding="utf-8") as handle:
        json.dump(geojson, handle, separators=(",", ":"), ensure_ascii=False)

    return {"raw": raw, "accidents": accidents, "users": users,
            "vehicles": vehicles, "users_agg": users_agg}
