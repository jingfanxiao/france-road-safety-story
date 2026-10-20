"""Page 1 — Story & Overview: hook, context, KPIs tied to the filters, yearly trend."""

import streamlit as st

import constants as C
from utils import metrics, ui, viz
from utils.filters import filtered_accidents, load_accidents


def describe_change(before, after):
    """"fell by 4.1%", "rose by 2.0%", or "stayed about the same" below 1%."""
    change = 100 * (after - before) / before
    if abs(change) < 1:
        return "stayed about the same"
    return f"{'rose' if change > 0 else 'fell'} by {abs(change):.1f}%"


def trend_headline(yearly):
    """Sentence comparing the first and the last year of the selection."""
    if len(yearly) == 1:
        row = yearly.iloc[0]
        return (f"In {int(row['year'])}, {ui.fmt_int(row['accidents'])} injury accidents and "
                f"{ui.fmt_int(row['killed'])} deaths were recorded in the selection "
                f"(lethality {ui.fmt_rate(row['lethality'])} per {C.LETHALITY_PER} accidents).")
    first, last = yearly.iloc[0], yearly.iloc[-1]
    before, after = ui.fmt_rate(first["lethality"]), ui.fmt_rate(last["lethality"])
    lethality_text = f"lethality stayed at {after}" if before == after else f"lethality went from {before} to {after}"
    return (
        f"Between {int(first['year'])} and {int(last['year'])}, injury accidents "
        f"{describe_change(first['accidents'], last['accidents'])} and deaths "
        f"{describe_change(first['killed'], last['killed'])} "
        f"({ui.fmt_int(first['killed'])} → {ui.fmt_int(last['killed'])}); "
        f"{lethality_text} deaths per {C.LETHALITY_PER} accidents."
    )


def hook():
    """Why it matters, on the whole dataset (not filtered)."""
    acc = load_accidents()
    k = metrics.kpis(acc)
    n_weeks = ((acc["date"].max() - acc["date"].min()).days + 1) / 7
    st.markdown(
        f"Across France, from {C.FIRST_YEAR} to {C.LAST_YEAR}, the police recorded "
        f"**{ui.fmt_int(k['accidents'])} injury road accidents** in which **{ui.fmt_int(k['killed'])} people "
        f"died** — about {k['killed'] / n_weeks:.0f} deaths every week. But an accident is not equally "
        "dangerous everywhere: this app asks **where** and **for whom** an accident is most likely to be fatal."
    )
    with st.expander("Context: audience, key metric and data", expanded=False):
        st.markdown(
            "- **Audience:** local road-safety decision makers (préfectures, départements, municipalities) "
            "and citizens.\n"
            f"- **Key metric — lethality:** deaths (within 30 days) per {C.LETHALITY_PER} injury accidents. "
            "It measures how *severe* accidents are, not how *frequent*; the accident count is always shown "
            f"with it, and rates on fewer than {C.MIN_ACCIDENTS_FOR_RATE} accidents are greyed out.\n"
            f"- **Data:** {C.DATASET_PRODUCER}, BAAC files {C.FIRST_YEAR}–{C.LAST_YEAR} "
            f"([data.gouv.fr]({C.DATASET_PAGE_URL}), Licence Ouverte / Open Licence). "
            "Earlier years use a different format and are left out.\n"
            "- **Filters** in the sidebar (years, region, indicator) apply to every page except the data "
            "quality checks. Patterns shown are associations, not causes."
        )


def kpi_row(acc, yearly):
    """Four KPIs; with two years or more, also the change vs the previous year and a sparkline."""
    k = metrics.kpis(acc)
    d = metrics.kpi_delta(acc)
    lethality_help = (f"Deaths (within 30 days) per {C.LETHALITY_PER} injury accidents recorded by the police. "
                      f"Rates based on fewer than {C.MIN_ACCIDENTS_FOR_RATE} accidents are hidden or greyed out.")
    items = [
        ("Injury accidents", ui.fmt_int(k["accidents"]), "accidents", "%",
         "Accidents with at least one casualty, recorded by the police."),
        ("People killed", ui.fmt_int(k["killed"]), "killed", "%", "Died on the spot or within 30 days."),
        ("Hospitalised", ui.fmt_int(k["hospitalised"]), "hospitalised", "%",
         "Hospitalised more than 24 h. Not a certified indicator since 2019: read with care."),
        ("Lethality (per 100 accidents)", ui.fmt_rate(k["lethality"]), "lethality", " pts", lethality_help),
    ]
    for column, (label, value, key, unit, help_text) in zip(st.columns(4), items):
        column.metric(
            label, value, border=True, help=help_text, delta_color="inverse",
            delta=ui.fmt_change(d[key], unit) if d else None,
            delta_description=d["vs"] if d else None,
            chart_data=yearly[key].round(2).tolist() if d else None,
        )
    if d:
        st.caption(f"Changes compare the last two years of the selection ({d['vs']}); "
                   "green means fewer accidents or deaths, or a lower lethality.")


def render():
    filters = ui.current_filters()
    acc = filtered_accidents(filters.years, filters.regions)
    yearly = metrics.count_table(acc, "year")

    st.title("Where, when and who: the hidden geography of road danger in France")
    hook()

    st.header("Are French roads getting safer?")
    ui.headline(trend_headline(yearly))
    kpi_row(acc, yearly)

    if len(yearly) > 1:
        fig = viz.yearly_trend_indexed(yearly, "Injury accidents and deaths per year")
        ui.chart(fig, "Line chart of injury accidents and deaths per year, both indexed to the first selected "
                      "year = 100, with 2020 (COVID-19 lockdowns) shaded.", key="story_trend")
        st.caption("2020 is shaded because the lockdowns cut traffic; the data shows the drop in accidents "
                   "that year but cannot tell what caused it.")
    ui.source_note()
