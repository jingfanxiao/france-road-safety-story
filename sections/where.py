"""Where page: do the départements with the most accidents also have the deadliest ones?"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import constants as C
from utils import metrics, ui, viz
from utils.filters import Filters, filtered_accidents, load_geojson

MIN_CLEAR_CORRELATION = 0.3  # |rank correlation| needed before stating a clear pattern
TOP_N = 10
WHATIF_MAX_N = 20
WHATIF_DEFAULT_N = 10

MAP_VIEWS = {
    "Accidents per year": {"value": "accidents_per_year", "colorbar": "Accidents / year",
                           "scale": C.SEQUENTIAL_SCALE, "format": ",.0f", "hide_unreliable": False},
    "Lethality": {"value": "lethality", "colorbar": "Deaths / 100 acc.",
                  "scale": C.LETHALITY_SCALE, "format": ".1f", "hide_unreliable": True},
}


def size_vs_lethality_headline(dep: pd.DataFrame) -> str | None:
    """Compare the busiest and the quietest quarter of départements."""
    quartiles = metrics.lethality_by_size_quartile(dep)
    if quartiles is None:
        return None
    reliable = dep[dep["reliable"]]
    rho = metrics.rank_correlation(reliable["accidents_per_year"], reliable["lethality"])
    most, fewest = quartiles.iloc[-1], quartiles.iloc[0]
    relation = ui.compare_rates(fewest["lethality"], most["lethality"])
    # A firm answer needs both a clear gap between the groups and a clear overall trend.
    if "times" in relation and rho <= -MIN_CLEAR_CORRELATION:
        verdict = "No — it is the opposite"
    elif relation.startswith("less") and rho >= MIN_CLEAR_CORRELATION:
        verdict = "Yes"
    else:
        verdict = "Not clearly"
    return (
        f"{verdict}: in the quarter of départements with the fewest accidents, an accident is {relation} "
        f"in the quarter with the most accidents ({ui.fmt_rate(fewest['lethality'])} vs "
        f"{ui.fmt_rate(most['lethality'])} deaths per {C.LETHALITY_PER} accidents; rank correlation between "
        f"accident volume and lethality: {rho:+.2f} over {len(reliable)} départements)."
    )


def map_section(dep: pd.DataFrame) -> None:
    """One choropleth, switched between accident volume and lethality."""
    geojson = load_geojson()
    map_codes = {feature["id"] for feature in geojson["features"]}
    if not dep["dep"].astype(str).isin(map_codes).any():
        st.info("The current selection only contains overseas territories, which are not drawn on the map. "
                "See the ranking below.")
        return
    view_name = st.radio("Map shows", list(MAP_VIEWS), horizontal=True, key="where_map_view")
    view = MAP_VIEWS[view_name]
    fig = viz.dep_choropleth(dep, geojson, view["value"], f"{view_name} by département",
                             view["colorbar"], scale=view["scale"], value_format=view["format"],
                             hide_unreliable=view["hide_unreliable"])
    alt = (f"Map of metropolitan départements coloured by {view_name.lower()}; darker means higher."
           + (" Grey: too few accidents for a rate." if view["hide_unreliable"] else ""))
    ui.chart(fig, alt, key="where_map")
    st.caption("Switch between the two views: the darkest areas are not the same. Overseas départements and "
               "territories are not drawn but are included in the KPIs and the ranking.")


def ranking(dep: pd.DataFrame, average: float) -> None:
    """The 10 départements with the highest lethality, small ones greyed out."""
    top = dep.nlargest(TOP_N, "lethality")
    top = top.assign(label=top["dep"].astype(str) + " – " + top["dep_name"].astype(str))
    fig = viz.category_bar(top, "label", "lethality", f"Top {len(top)} départements by lethality",
                           "Deaths per 100 accidents", None, reference=average,
                           reference_label="Selection average", horizontal=True)
    ui.chart(fig, f"Horizontal bar chart of the {len(top)} départements with the highest lethality, with the "
                  "selection average as a dashed line; grey bars rest on too few accidents.", key="where_top")
    unreliable = top.loc[~top["reliable"], "dep_name"].astype(str).tolist()
    note = f"Grey bars: fewer than {C.MIN_ACCIDENTS_FOR_RATE} accidents, so the rate is not reliable"
    st.caption(note + (f" ({', '.join(unreliable)})." if unreliable else "; none in this ranking."))


def whatif_section(dep: pd.DataFrame, filters: Filters) -> None:
    """Simple scenario: the N most lethal départements at the national rate."""
    with st.expander("What if the deadliest départements matched the national average?"):
        # The national rate covers all of France for the selected years, whatever regions are selected.
        national = metrics.kpis(filtered_accidents(filters.years))["lethality"]
        n_years = filters.years[1] - filters.years[0] + 1
        top_n = st.slider("N most lethal départements", 1, WHATIF_MAX_N, WHATIF_DEFAULT_N, key="whatif_n")
        avoided = metrics.avoided_deaths_per_year(dep, national, top_n, n_years)
        st.metric("Deaths per year that would be avoided (estimate)", f"{avoided:.0f}", border=True,
                  help=f"National lethality used: {ui.fmt_rate(national)} deaths per {C.LETHALITY_PER} accidents.")
        st.caption(
            f"For each of the N most lethal départements (with at least {C.MIN_ACCIDENTS_FOR_RATE} accidents), "
            "avoided deaths = deaths − accidents × national rate; the total is divided by the number of years. "
            "This is an illustrative scenario, not a prediction: it keeps the number of accidents unchanged and "
            "says nothing about how the gap could be closed."
        )


def render() -> None:
    filters = ui.current_filters()
    acc = filtered_accidents(filters.years, filters.regions)
    ui.require_rows(acc)
    average = metrics.kpis(acc)["lethality"]
    dep = metrics.by_departement(acc)

    st.title("Where: do the départements with the most accidents have the deadliest ones?")
    ui.headline(size_vs_lethality_headline(dep) or "Select more regions (at least 8 départements with enough "
                                                   "accidents) to compare busy and quiet départements.")
    map_section(dep)
    ranking(dep, average)
    st.caption("Lethality describes how severe accidents are, not how many people are at risk: without traffic "
               "or population data, a low lethality does not mean a low risk per inhabitant. Dense and rural "
               "areas differ in road type, speed and many other ways, so this is an association, not a cause.")
    whatif_section(dep, filters)
    ui.source_note(f"Boundaries: Contours administratifs, data.gouv.fr · {C.GEO_LICENCE}.")
