"""Every number shown in the app is computed here from the (filtered) accident table."""

import pandas as pd

import constants as C


def lethality(killed, accidents):
    """Deaths per 100 injury accidents."""
    return C.LETHALITY_PER * killed / accidents


def add_lethality(df):
    """Add a lethality column, and flag rates based on too few accidents as unreliable."""
    df["lethality"] = lethality(df["killed"], df["accidents"])
    df["reliable"] = df["accidents"] >= C.MIN_ACCIDENTS_FOR_RATE
    return df


def count_table(acc, by):
    """Accidents, deaths and hospitalised people per group, with lethality."""
    out = acc.groupby(by, observed=True).agg(
        accidents=("Num_Acc", "size"),
        killed=("n_killed", "sum"),
        hospitalised=("n_hosp", "sum"),
    ).reset_index()
    # The parquet stores counts as int16 and group sums stay int16: widen them so they cannot overflow.
    count_cols = ["accidents", "killed", "hospitalised"]
    out[count_cols] = out[count_cols].astype("int64")
    return add_lethality(out)


def kpis(acc):
    """Headline figures for the current selection."""
    killed = int(acc["n_killed"].sum())
    return {
        "accidents": len(acc),
        "killed": killed,
        "hospitalised": int(acc["n_hosp"].sum()),
        "lethality": lethality(killed, len(acc)),
    }


def kpi_delta(acc):
    """Change between the last two years of the selection (None for a single year).

    Counts change in %, lethality in points (a % of a rate is hard to read).
    """
    years = sorted(acc["year"].unique())
    if len(years) < 2:
        return None
    previous, last = years[-2], years[-1]
    now = kpis(acc[acc["year"] == last])
    before = kpis(acc[acc["year"] == previous])
    delta = {key: 100 * (now[key] - before[key]) / before[key] for key in ["accidents", "killed", "hospitalised"]}
    delta["lethality"] = now["lethality"] - before["lethality"]
    delta["vs"] = f"{last} vs {previous}"
    return delta


def hour_weekday(acc, value):
    """Weekday (rows) × hour (columns) table of one indicator. Unreliable lethality cells stay empty."""
    table = count_table(acc, ["weekday", "hour"])
    if value == "lethality":
        table.loc[~table["reliable"], "lethality"] = float("nan")
    matrix = table.pivot(index="weekday", columns="hour", values=value)
    return matrix.reindex(index=C.WEEKDAY_ORDER, columns=range(24))


def by_departement(acc):
    """One row per département, with accidents per year for the map."""
    out = count_table(acc, ["dep", "dep_name", "region"])
    out["accidents_per_year"] = out["accidents"] / acc["year"].nunique()
    return out


def lethality_by_size_quartile(dep_table):
    """Pooled lethality of the four quarters of départements, from fewest to most accidents.

    Only reliable départements are used; None when there are fewer than 8 of them.
    """
    reliable = dep_table[dep_table["reliable"]]
    if len(reliable) < 8:
        return None
    quartile = pd.qcut(reliable["accidents_per_year"].rank(method="first"), 4, labels=False)
    out = reliable.groupby(quartile)[["accidents", "killed"]].sum()
    return add_lethality(out)


def avoided_deaths_per_year(dep_table, national_rate, top_n, n_years):
    """What-if: deaths per year avoided if the N most lethal départements had the national rate.

    For each of the top N reliable départements: avoided = deaths − accidents × national_rate / 100,
    counted as 0 when the département is already below the national rate.
    """
    top = dep_table[dep_table["reliable"]].nlargest(top_n, "lethality")
    avoided = top["killed"] - top["accidents"] * national_rate / C.LETHALITY_PER
    return float(avoided.clip(lower=0).sum() / n_years)


def users_by_type(users):
    """Road users involved and killed per user type, and deaths per 100 users involved."""
    table = users.pivot_table(index="user_type", columns="severity", values="n_users",
                              aggfunc="sum", fill_value=0, observed=True)
    out = pd.DataFrame({"involved": table.sum(axis=1), "killed": table["Killed"]})
    out["killed_per_100"] = C.LETHALITY_PER * out["killed"] / out["involved"]
    out["reliable"] = out["involved"] >= C.MIN_ACCIDENTS_FOR_RATE
    return out.reset_index()
