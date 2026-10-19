"""Who page: which road users pay the highest price, and at what time accidents happen."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import constants as C
from utils import metrics, ui, viz
from utils.filters import filtered_accidents, filtered_users

REFERENCE_TYPE = "Car"  # car occupants are the baseline for comparisons


def people(user_type: str) -> str:
    """Plural name of the people in a group, e.g. "Bicycle" -> "cyclists"."""
    return C.USER_TYPE_PEOPLE.get(user_type, user_type.lower())


def user_type_headline(by_type: pd.DataFrame) -> str | None:
    """The most exposed vulnerable group compared with car occupants."""
    table = by_type.set_index("user_type")
    vulnerable = table.loc[table.index.isin(C.VULNERABLE_USER_TYPES) & table["reliable"]]
    if vulnerable.empty or REFERENCE_TYPE not in table.index or not table.loc[REFERENCE_TYPE, "reliable"]:
        return None
    worst_type = vulnerable["killed_per_100"].idxmax()
    worst = vulnerable.loc[worst_type]
    car = table.loc[REFERENCE_TYPE]
    ratio = worst["killed_per_100"] / car["killed_per_100"]
    vulnerable_share = 100 * vulnerable["killed"].sum() / table["killed"].sum()
    return (
        f"{people(worst_type).capitalize()} are the most exposed: {ui.fmt_rate(worst['killed_per_100'])} of "
        f"every {C.LETHALITY_PER} involved in an injury accident died, {ratio:.1f} times the rate of car "
        f"occupants ({ui.fmt_rate(car['killed_per_100'])}). Pedestrians, cyclists, e-scooter, moped and "
        f"motorcycle riders together account for {vulnerable_share:.0f}% of the deaths in the selection."
    )


def hour_headline(acc: pd.DataFrame) -> str | None:
    """Busiest hour versus most lethal hour."""
    by_hour = metrics.count_table(acc.dropna(subset=["hour"]), "hour")
    reliable = by_hour[by_hour["reliable"]]
    if len(reliable) < 6:
        return None
    busiest = by_hour.loc[by_hour["accidents"].idxmax()]
    deadliest = reliable.loc[reliable["lethality"].idxmax()]
    return (
        f"Accidents are most frequent at {int(busiest['hour']):02d}h ({ui.fmt_int(busiest['accidents'])} "
        f"accidents, lethality {ui.fmt_rate(busiest['lethality'])}), but the most lethal hour is "
        f"{int(deadliest['hour']):02d}h, with {ui.fmt_rate(deadliest['lethality'])} deaths per "
        f"{C.LETHALITY_PER} accidents."
    )


def user_type_section(users: pd.DataFrame) -> None:
    """Deaths per 100 road users involved, by type of road user."""
    by_type = metrics.users_by(users, "user_type")
    all_rate = metrics.lethality(by_type["killed"].sum(), by_type["involved"].sum())
    ui.headline(user_type_headline(by_type) or "Too few road users in the selection to compare groups.")
    fig = viz.category_bar(by_type, "user_type", "killed_per_100", "Death rate by type of road user",
                           "Deaths per 100 users involved", None, reference=all_rate,
                           reference_label="All road users", horizontal=True, count_column="involved",
                           count_label="Users involved", value_format=".2f")
    ui.chart(fig, "Horizontal bar chart of deaths per 100 road users involved, by type of road user, "
                  "with the average for all users as a dashed line.", key="who_types")
    st.caption("This chart counts people, not accidents. Pedestrians are their own group; other users are "
               "grouped by the vehicle they were in. E-scooter / PMD = personal mobility devices. "
               f"Grey bars: fewer than {C.MIN_ACCIDENTS_FOR_RATE} users involved.")


def heatmap_section(acc: pd.DataFrame, indicator: str) -> None:
    """Hour × day-of-week heatmap of the indicator chosen in the sidebar."""
    sentence = hour_headline(acc)
    if sentence:
        ui.headline(sentence)
    spec = C.INDICATORS[indicator]
    matrix = metrics.hour_weekday(acc, spec["column"])
    scale = C.LETHALITY_SCALE if spec["column"] == "lethality" else C.SEQUENTIAL_SCALE
    fig = viz.hour_weekday_heatmap(matrix, f"{indicator} by hour and day of the week", spec["unit"],
                                   scale=scale, value_format=spec["format"])
    empty_note = (f" Empty cells: fewer than {C.MIN_ACCIDENTS_FOR_RATE} accidents."
                  if spec["column"] == "lethality" else "")
    ui.chart(fig, f"Heatmap of {indicator.lower()} by hour of the day (columns) and day of the week (rows); "
                  f"darker means higher.{empty_note}", key="who_heatmap")
    st.caption("Change the colour with the 'Indicator' choice in the sidebar. "
               "Hours are local time as recorded by the police.")


def render() -> None:
    filters = ui.current_filters()
    acc = filtered_accidents(filters.years, filters.regions)
    ui.require_rows(acc)
    users = filtered_users(filters.years, filters.regions)

    st.title("Who: which road users pay the highest price?")
    user_type_section(users)

    st.header("When do accidents happen?")
    heatmap_section(acc, filters.indicator)
    ui.source_note()
