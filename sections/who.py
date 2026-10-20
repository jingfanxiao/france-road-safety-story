"""Page 3 — Who: which road users pay the highest price, and when do accidents happen?"""

import streamlit as st

import constants as C
from utils import metrics, ui, viz
from utils.filters import filtered_accidents, filtered_users


def user_type_headline(by_type):
    """The most exposed vulnerable group, compared with car occupants."""
    table = by_type.set_index("user_type")
    vulnerable = table.loc[table.index.isin(C.VULNERABLE_USER_TYPES) & table["reliable"]]
    # Small selections may not have enough users for a fair comparison.
    if vulnerable.empty or "Car" not in table.index or not table.loc["Car", "reliable"]:
        return None
    worst_type = vulnerable["killed_per_100"].idxmax()
    worst = vulnerable.loc[worst_type]
    car = table.loc["Car"]
    ratio = worst["killed_per_100"] / car["killed_per_100"]
    vulnerable_share = 100 * vulnerable["killed"].sum() / table["killed"].sum()
    return (
        f"{C.USER_TYPE_PEOPLE[worst_type].capitalize()} are the most exposed: {ui.fmt_rate(worst['killed_per_100'])} of "
        f"every {C.LETHALITY_PER} involved in an injury accident died, {ratio:.1f} times the rate of car "
        f"occupants ({ui.fmt_rate(car['killed_per_100'])}). Pedestrians, cyclists, e-scooter, moped and "
        f"motorcycle riders together account for {vulnerable_share:.0f}% of the deaths in the selection."
    )


def hour_headline(acc):
    """Busiest hour versus most lethal hour (None if fewer than 6 hours have enough accidents)."""
    by_hour = metrics.count_table(acc, "hour")
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


def render():
    filters = ui.current_filters()
    acc = filtered_accidents(filters.years, filters.regions)
    users = filtered_users(filters.years, filters.regions)

    st.title("Who: which road users pay the highest price?")
    by_type = metrics.users_by_type(users)
    all_rate = metrics.lethality(by_type["killed"].sum(), by_type["involved"].sum())
    ui.headline(user_type_headline(by_type) or "Too few road users in the selection to compare groups.")
    fig = viz.category_bar(by_type, "user_type", "killed_per_100", "Death rate by type of road user",
                           "Deaths per 100 users involved", all_rate, "All road users",
                           value_format=".2f", count_column="involved", count_label="Users involved")
    ui.chart(fig, "Horizontal bar chart of deaths per 100 road users involved, by type of road user, "
                  "with the average for all users as a dashed line.", key="who_types")
    st.caption("This chart counts people, not accidents. Pedestrians are their own group; other users are "
               "grouped by the vehicle they were in. E-scooter / PMD = personal mobility devices. "
               f"Grey bars: fewer than {C.MIN_ACCIDENTS_FOR_RATE} users involved.")

    st.header("When do accidents happen?")
    sentence = hour_headline(acc)
    if sentence:
        ui.headline(sentence)
    # The sidebar "Indicator" chooses what colours the heatmap.
    spec = C.INDICATORS[filters.indicator]
    is_lethality = spec["column"] == "lethality"
    fig = viz.hour_weekday_heatmap(metrics.hour_weekday(acc, spec["column"]),
                                   f"{filters.indicator} by hour and day of the week", spec["unit"],
                                   scale=C.LETHALITY_SCALE if is_lethality else C.SEQUENTIAL_SCALE,
                                   value_format=spec["format"])
    empty_note = f" Empty cells: fewer than {C.MIN_ACCIDENTS_FOR_RATE} accidents." if is_lethality else ""
    ui.chart(fig, f"Heatmap of {filters.indicator.lower()} by hour of the day (columns) and day of the week (rows); "
                  f"darker means higher.{empty_note}", key="who_heatmap")
    st.caption("Change the colour with the 'Indicator' choice in the sidebar. "
               "Hours are local time as recorded by the police.")
    ui.source_note()
