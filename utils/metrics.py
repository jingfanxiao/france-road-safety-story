"""Aggregations and indicators computed from the (filtered) accident table.

All numbers shown in the app come from these functions, so a figure in a
headline sentence and the same figure in a chart always agree.
"""

from __future__ import annotations

import pandas as pd

import constants as C


def lethality(killed: float, accidents: float) -> float:
    """Deaths per 100 injury accidents (NaN when there is no accident)."""
    if accidents == 0:
        return float("nan")
    return C.LETHALITY_PER * killed / accidents


def add_lethality(df: pd.DataFrame) -> pd.DataFrame:
    """Add a ``lethality`` column and a ``reliable`` flag to a table of counts.

    ``reliable`` is False when the unit has too few accidents for a stable rate.
    """
    df = df.copy()
    # Work in float: counts are stored as small integers (int16) in the parquet
    # file, and multiplying them by 100 would overflow.
    killed = df["killed"].astype("float64")
    accidents = df["accidents"].astype("float64")
    df["lethality"] = C.LETHALITY_PER * killed / accidents.where(accidents > 0)
    df["reliable"] = df["accidents"] >= C.MIN_ACCIDENTS_FOR_RATE
    return df


def count_table(acc: pd.DataFrame, by: str | list[str]) -> pd.DataFrame:
    """Accidents, deaths and hospitalised casualties per group, with lethality."""
    out = acc.groupby(by, observed=True).agg(
        accidents=("Num_Acc", "size"),
        killed=("n_killed", "sum"),
        hospitalised=("n_hosp", "sum"),
    ).reset_index()
    # Group sums of int16 columns stay int16; widen them before any arithmetic.
    count_cols = ["accidents", "killed", "hospitalised"]
    out[count_cols] = out[count_cols].astype("int64")
    return add_lethality(out)


# --- KPIs --------------------------------------------------------------------------

def kpis(acc: pd.DataFrame) -> dict[str, float]:
    """Headline figures for the current selection."""
    accidents = len(acc)
    killed = int(acc["n_killed"].sum())
    return {
        "accidents": accidents,
        "killed": killed,
        "hospitalised": int(acc["n_hosp"].sum()),
        "lethality": lethality(killed, accidents),
        "n_years": acc["year"].nunique(),
    }


def kpi_delta(acc: pd.DataFrame) -> dict[str, float | None]:
    """Change between the last year of the selection and the year before.

    Counts change in %, lethality in points (a % of a rate is hard to read).
    """
    years = sorted(acc["year"].unique())
    if len(years) < 2:
        return {"accidents": None, "killed": None, "hospitalised": None, "lethality": None,
                "last": None, "previous": None}
    last, previous = years[-1], years[-2]
    now = kpis(acc[acc["year"] == last])
    before = kpis(acc[acc["year"] == previous])

    def pct(key: str) -> float | None:
        return 100 * (now[key] - before[key]) / before[key] if before[key] else None

    return {
        "accidents": pct("accidents"),
        "killed": pct("killed"),
        "hospitalised": pct("hospitalised"),
        "lethality": now["lethality"] - before["lethality"],
        "last": int(last),
        "previous": int(previous),
    }


# --- Time ----------------------------------------------------------------------------

def yearly(acc: pd.DataFrame) -> pd.DataFrame:
    """One row per year."""
    return count_table(acc, "year")


def hour_weekday(acc: pd.DataFrame, value: str = "accidents") -> pd.DataFrame:
    """Matrix weekday (rows, Monday first) × hour (columns) of ``value``.

    For ``lethality`` cells with too few accidents are left empty.
    """
    table = count_table(acc.dropna(subset=["hour"]), ["weekday", "hour"])
    if value == "lethality":
        table.loc[~table["reliable"], "lethality"] = float("nan")
    matrix = table.pivot(index="weekday", columns="hour", values=value)
    return matrix.reindex(index=C.WEEKDAY_ORDER, columns=range(24))


# --- Places ----------------------------------------------------------------------------

def by_departement(acc: pd.DataFrame) -> pd.DataFrame:
    """One row per département with counts, lethality and accidents per year."""
    out = count_table(acc, ["dep", "dep_name", "region"])
    out["accidents_per_year"] = out["accidents"] / max(acc["year"].nunique(), 1)
    return out


def rank_correlation(x: pd.Series, y: pd.Series) -> float:
    """Spearman rank correlation (Pearson correlation of the ranks), between −1 and 1."""
    return x.rank().corr(y.rank())


def lethality_by_size_quartile(dep_table: pd.DataFrame) -> pd.DataFrame | None:
    """Group reliable départements into four equal groups by accidents per year.

    Returns one row per group with the pooled lethality, or None when there are
    too few départements to form four groups.
    """
    reliable = dep_table[dep_table["reliable"]]
    if len(reliable) < 8:
        return None
    labels = ["Fewest accidents", "Fewer", "More", "Most accidents"]
    quartile = pd.qcut(reliable["accidents_per_year"].rank(method="first"), 4, labels=labels)
    out = reliable.groupby(quartile, observed=True).agg(
        departements=("dep", "size"), accidents=("accidents", "sum"), killed=("killed", "sum"),
    ).rename_axis("group").reset_index()
    return add_lethality(out)


def avoided_deaths_per_year(dep_table: pd.DataFrame, national_rate: float, top_n: int, n_years: int) -> float:
    """What-if: deaths per year avoided if the N most lethal départements had the national rate.

    Only départements with enough accidents are ranked. For each of the top N:
        avoided_d = deaths_d − accidents_d × national_rate / 100
    The sum is divided by the number of years. A département already below the
    national rate avoids nothing (its term is set to 0, not counted as negative).
    """
    top = dep_table[dep_table["reliable"]].nlargest(top_n, "lethality")
    avoided = top["killed"] - top["accidents"] * national_rate / C.LETHALITY_PER
    return float(avoided.clip(lower=0).sum() / max(n_years, 1))


# --- Road users -------------------------------------------------------------------------

def users_by(users_agg: pd.DataFrame, by: str | list[str]) -> pd.DataFrame:
    """Road users involved and killed per group.

    ``killed_per_100`` = deaths per 100 road users of that group involved in an
    injury accident: how often being involved ends in death for that group.
    """
    table = users_agg.pivot_table(index=by, columns="severity", values="n_users",
                                  aggfunc="sum", fill_value=0, observed=True)
    out = pd.DataFrame(index=table.index)
    out["involved"] = table.sum(axis=1)
    out["killed"] = table.get("Killed", 0)
    out["killed_per_100"] = C.LETHALITY_PER * out["killed"] / out["involved"].where(out["involved"] > 0)
    out["reliable"] = out["involved"] >= C.MIN_ACCIDENTS_FOR_RATE
    return out.reset_index()
