"""Clean the raw BAAC tables, join them and write the files used by the app.

raw CSV (text) -> clean each table -> one row per accident -> data/processed/accidents.parquet
                                   -> road-user counts (no person-level rows) -> users_agg.parquet
boundaries -> metropolitan France + Corsica only -> departements.geojson
"""

import json

import numpy as np
import pandas as pd

import constants as C
from utils import io


def load_table(table):
    """Read one BAAC table for all years, as text, with a year column."""
    frames = []
    for year in C.YEARS:
        df = io.read_raw_csv(io.raw_path(table, year))
        df = df.rename(columns={"Accident_Id": "Num_Acc"})  # the 2022 file uses another name
        for col in df.columns:
            # Codes such as " -1" have stray spaces, and ids contain non-breaking spaces.
            df[col] = df[col].str.replace("\xa0", "", regex=False).str.strip()
        df["year"] = year
        frames.append(df)
    return pd.concat(frames, ignore_index=True)  # "id_usager" only exists from 2021: NaN before


# --- Small helpers, also used by quality.py --------------------------------------

def to_int(series):
    """Text codes -> integers; "-1" and empty cells become missing (NA)."""
    return pd.to_numeric(series.where(~series.isin(C.MISSING_CODES)), errors="coerce").astype("Int64")


def to_float_comma(series):
    """Text with a decimal comma ("47,56") -> float."""
    return pd.to_numeric(series.str.replace(",", ".", regex=False), errors="coerce")


def normalize_dep(series):
    """Zero-pad one-digit département codes ("1" -> "01"); "2A" and "971" stay as they are."""
    return series.where(~series.str.fullmatch(r"\d"), "0" + series)


def to_category(series, order):
    """Ordered categories, so charts keep a meaningful order."""
    return pd.Categorical(series, categories=order, ordered=True)


def coordinates_in_bounds(dep, lat, lon):
    """True when (lat, lon) is inside the box of the accident's territory."""
    boxes = [C.BOUNDS_OVERSEAS.get(code, C.BOUNDS_METRO) for code in dep]
    box = pd.DataFrame(boxes, columns=["lat_min", "lat_max", "lon_min", "lon_max"], index=dep.index)
    return lat.between(box["lat_min"], box["lat_max"]) & lon.between(box["lon_min"], box["lon_max"])


# --- One function per raw table ----------------------------------------------------

def clean_caract(raw):
    """Accident characteristics: date and time, place, light, weather, coordinates."""
    df = pd.DataFrame({"Num_Acc": raw["Num_Acc"].astype("int64"), "year": raw["year"]})
    df["date"] = pd.to_datetime(
        pd.DataFrame({"year": df["year"], "month": to_int(raw["mois"]), "day": to_int(raw["jour"])}),
        errors="coerce",
    )
    df["month"] = df["date"].dt.month.astype("Int8")
    df["weekday"] = to_category(df["date"].dt.day_name(), C.WEEKDAY_ORDER)
    df["is_weekend"] = df["date"].dt.dayofweek >= 5
    hour = pd.to_numeric(raw["hrmn"].str.split(":").str[0], errors="coerce")  # "HH:MM" -> HH
    df["hour"] = hour.where(hour.between(0, 23)).astype("Int8")

    df["dep"] = normalize_dep(raw["dep"])
    df["urban"] = to_category(to_int(raw["agg"]).map(C.AGG_LABELS), C.AREA_ORDER)
    df["light_cond"] = to_category(to_int(raw["lum"]).map(C.LUM_TO_LIGHT), C.LIGHT_ORDER)
    df["weather"] = to_category(to_int(raw["atm"]).map(C.ATM_TO_WEATHER), C.WEATHER_ORDER)
    df["lat"] = to_float_comma(raw["lat"])
    df["lon"] = to_float_comma(raw["long"])
    return df


def clean_places(raw):
    """One "lieux" row per accident: road type and speed limit.

    From 2023 an accident can have several rows (one per road at a junction) and the
    main road is not flagged, so the first row is kept. The number of rows is stored.
    """
    n_places = raw.groupby("Num_Acc").size().rename("n_places")
    main = raw.drop_duplicates(subset="Num_Acc", keep="first").set_index("Num_Acc").join(n_places)

    out = pd.DataFrame(index=main.index)
    out["road_type"] = to_category(to_int(main["catr"]).map(C.CATR_LABELS), C.ROAD_ORDER)
    vma = to_int(main["vma"])
    out["vma"] = vma.where(vma.between(C.VMA_MIN, C.VMA_MAX))
    out["speed_limit_band"] = pd.cut(out["vma"].astype("float"), bins=C.SPEED_BINS, labels=C.SPEED_LABELS)
    out["n_places"] = main["n_places"].astype("int8")
    out.index = out.index.astype("int64")
    return out


def clean_vehicles(raw):
    """One row per vehicle with its group (bicycle, car...)."""
    return pd.DataFrame({
        "Num_Acc": raw["Num_Acc"].astype("int64"),
        "id_vehicule": raw["id_vehicule"],
        "vehicle_group": to_int(raw["catv"]).map(C.CATV_TO_GROUP).fillna(C.OTHER_VEHICLE),
    })


def clean_users(raw, vehicles):
    """One row per road user with severity, age band and user type.

    Pedestrians are linked to the vehicle that hit them, so their type comes from catu,
    not from the vehicle; everyone else gets the group of their own vehicle.
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
    users["user_type"] = users["vehicle_group"].fillna(C.OTHER_VEHICLE)
    users.loc[(users["catu"] == C.CATU_PEDESTRIAN).fillna(False), "user_type"] = C.PEDESTRIAN

    age = users["year"] - users["birth_year"]
    users["age"] = age.where(age.between(0, C.AGE_MAX))
    users["age_band"] = pd.cut(users["age"].astype("float"), bins=C.AGE_BINS, labels=C.AGE_LABELS, right=False)
    return users


# --- One row per accident ---------------------------------------------------------

def user_counts(users):
    """Per accident: number of users, killed, hospitalised and slightly injured, and the worst severity."""
    indicators = pd.DataFrame({
        "Num_Acc": users["Num_Acc"],
        "n_users": 1,
        "n_killed": (users["grav"] == C.GRAV_KILLED).fillna(False).astype(int),
        "n_hosp": (users["grav"] == C.GRAV_HOSPITALISED).fillna(False).astype(int),
        "n_light": (users["grav"] == C.GRAV_LIGHT).fillna(False).astype(int),
    })
    counts = indicators.groupby("Num_Acc").sum()
    # Worst severity: rank killed 3 > hospitalised 2 > slightly injured 1 > unharmed 0, then take the max.
    rank = users["grav"].map({C.GRAV_KILLED: 3, C.GRAV_HOSPITALISED: 2, C.GRAV_LIGHT: 1, C.GRAV_UNHARMED: 0})
    worst = rank.groupby(users["Num_Acc"]).max()
    rank_to_label = {3: "Killed", 2: "Hospitalised", 1: "Slightly injured", 0: "Unharmed"}
    counts["severity_max"] = to_category(worst.map(rank_to_label), C.SEVERITY_ORDER)
    return counts


def user_type_flags(users, vehicles):
    """Did the accident involve a pedestrian, a cyclist, an e-scooter, a moped, a motorcycle?

    Pedestrians come from the users table; the others from the vehicles table,
    so a vehicle counts even when its rider is not recorded.
    """
    flags = pd.DataFrame(index=pd.Index(users["Num_Acc"].unique(), name="Num_Acc"))
    flags["has_pedestrian"] = flags.index.isin(users.loc[users["user_type"] == C.PEDESTRIAN, "Num_Acc"])
    for column, group in [("has_cyclist", "Bicycle"), ("has_escooter", "E-scooter / PMD"),
                          ("has_moped", "Moped (<50 cc)"), ("has_motorcycle", "Motorcycle")]:
        flags[column] = flags.index.isin(vehicles.loc[vehicles["vehicle_group"] == group, "Num_Acc"])
    return flags


def build_accidents(caract, places, users, vehicles):
    """Join everything into one row per accident, with small dtypes for the parquet file."""
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

    # Geography: département name (from the boundaries file), region, overseas flag, coordinate check.
    with open(C.GEOJSON_RAW_FILE, encoding="utf-8") as f:
        dep_names = {feat["properties"]["code"]: feat["properties"]["nom"] for feat in json.load(f)["features"]}
    acc["dep_name"] = acc["dep"].map(dep_names).fillna(acc["dep"])
    acc["region"] = acc["dep"].map(C.DEP_TO_REGION).fillna(C.OTHER_REGION)
    acc["is_overseas"] = acc["dep"].str.len() == 3  # overseas codes have 3 digits (971...)
    in_bounds = coordinates_in_bounds(acc["dep"], acc["lat"], acc["lon"])
    acc["coord_out_of_bounds"] = acc["lat"].notna() & ~in_bounds
    acc.loc[~in_bounds, ["lat", "lon"]] = np.nan

    acc = acc.reset_index()
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


def build_users_agg(users, accidents):
    """Count road users by year × département × area × user type × age band × severity.

    Only counts are stored, so no person can be singled out from this table.
    """
    df = users.merge(accidents[["Num_Acc", "dep", "urban"]], on="Num_Acc", how="inner", validate="many_to_one")
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


def build_metro_geojson():
    """Keep metropolitan France + Corsica, and round coordinates to 4 decimals to make the file small."""
    with open(C.GEOJSON_RAW_FILE, encoding="utf-8") as f:
        geo = json.load(f)

    def round_coords(coords):  # coordinates are nested lists of [lon, lat] pairs
        if isinstance(coords[0], (int, float)):
            return [round(value, 4) for value in coords]
        return [round_coords(part) for part in coords]

    features = [
        {"type": "Feature", "id": feat["properties"]["code"],
         "properties": {"code": feat["properties"]["code"], "nom": feat["properties"]["nom"]},
         "geometry": {"type": feat["geometry"]["type"], "coordinates": round_coords(feat["geometry"]["coordinates"])}}
        for feat in geo["features"]
        if len(feat["properties"]["code"]) == 2  # overseas codes have 3 digits
    ]
    return {"type": "FeatureCollection", "features": features}


def build_all():
    """Run the whole preparation, write the processed files and return the raw tables."""
    print("reading raw tables…")
    raw = {table: load_table(table) for table in C.TABLES}
    vehicles = clean_vehicles(raw["vehicules"])
    users = clean_users(raw["usagers"], vehicles)
    accidents = build_accidents(clean_caract(raw["caract"]), clean_places(raw["lieux"]), users, vehicles)

    accidents.to_parquet(C.ACCIDENTS_FILE, index=False, compression="zstd")
    build_users_agg(users, accidents).to_parquet(C.USERS_AGG_FILE, index=False, compression="zstd")
    with open(C.GEOJSON_FILE, "w", encoding="utf-8") as f:
        json.dump(build_metro_geojson(), f, separators=(",", ":"), ensure_ascii=False)
    return raw
