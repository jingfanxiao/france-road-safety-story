"""Page 2 — Where: do the départements with the most accidents also have the deadliest ones?"""

import streamlit as st

import constants as C
from utils import metrics, ui, viz
from utils.filters import filtered_accidents, load_geojson

# The two views of the map: column shown, colour bar title, colour scale, number format, grey small ones.
MAP_VIEWS = {
    "Accidents per year": ("accidents_per_year", "Accidents / year", C.SEQUENTIAL_SCALE, ",.0f", False),
    "Lethality": ("lethality", "Deaths / 100 acc.", C.LETHALITY_SCALE, ".1f", True),
}


def size_vs_lethality_headline(dep):
    """Compare the quarter of départements with the fewest accidents with the quarter with the most."""
    quartiles = metrics.lethality_by_size_quartile(dep)
    if quartiles is None:
        return None
    reliable = dep[dep["reliable"]]
    rho = reliable["accidents_per_year"].rank().corr(reliable["lethality"].rank())  # Spearman
    fewest, most = quartiles.iloc[0], quartiles.iloc[-1]

    # Describe the gap in words that never overstate it: below 1.2 times, the rates are "about" equal.
    ratio = fewest["lethality"] / most["lethality"]
    if ratio >= 1.2:
        relation = f"{ratio:.1f} times as lethal as"
    elif ratio <= 1 / 1.2:
        relation = "less lethal than"
    else:
        relation = "about as lethal as"

    # A firm answer needs both a clear gap between the groups and a clear overall trend (|rho| >= 0.3).
    if ratio >= 1.2 and rho <= -0.3:
        verdict = "No — it is the opposite"
    elif ratio <= 1 / 1.2 and rho >= 0.3:
        verdict = "Yes"
    else:
        verdict = "Not clearly"
    return (
        f"{verdict}: in the quarter of départements with the fewest accidents, an accident is {relation} "
        f"in the quarter with the most accidents ({ui.fmt_rate(fewest['lethality'])} vs "
        f"{ui.fmt_rate(most['lethality'])} deaths per {C.LETHALITY_PER} accidents; rank correlation between "
        f"accident volume and lethality: {rho:+.2f} over {len(reliable)} départements)."
    )


def map_section(dep):
    """One map, switched between accident volume and lethality."""
    geojson = load_geojson()
    map_codes = {feature["id"] for feature in geojson["features"]}
    if not dep["dep"].astype(str).isin(map_codes).any():
        st.info("The current selection only contains overseas territories, which are not drawn on the map. "
                "See the ranking below.")
        return
    view_name = st.radio("Map shows", list(MAP_VIEWS), horizontal=True, key="where_map_view")
    value, colorbar, scale, value_format, hide_unreliable = MAP_VIEWS[view_name]
    fig = viz.dep_choropleth(dep, geojson, value, f"{view_name} by département", colorbar,
                             scale=scale, value_format=value_format, hide_unreliable=hide_unreliable)
    alt = (f"Map of metropolitan départements coloured by {view_name.lower()}; darker means higher."
           + (" Grey: too few accidents for a rate." if hide_unreliable else ""))
    ui.chart(fig, alt, key="where_map")
    st.caption("Switch between the two views: the darkest areas are not the same. Overseas départements and "
               "territories are not drawn but are included in the KPIs and the ranking.")


def ranking(dep, average):
    """The 10 départements with the highest lethality; small ones in grey."""
    top = dep.nlargest(10, "lethality")
    top["label"] = top["dep"].astype(str) + " – " + top["dep_name"].astype(str)
    fig = viz.category_bar(top, "label", "lethality", f"Top {len(top)} départements by lethality",
                           "Deaths per 100 accidents", average, "Selection average")
    ui.chart(fig, f"Horizontal bar chart of the {len(top)} départements with the highest lethality, with the "
                  "selection average as a dashed line; grey bars rest on too few accidents.", key="where_top")
    unreliable = top.loc[~top["reliable"], "dep_name"].astype(str).tolist()
    note = f"Grey bars: fewer than {C.MIN_ACCIDENTS_FOR_RATE} accidents, so the rate is not reliable"
    st.caption(note + (f" ({', '.join(unreliable)})." if unreliable else "; none in this ranking."))


def whatif_section(dep, years):
    """Simple scenario: the N most lethal départements at the national rate."""
    with st.expander("What if the deadliest départements matched the national average?"):
        # The national rate is all of France for the selected years, whatever regions are selected.
        national = metrics.kpis(filtered_accidents(years))["lethality"]
        top_n = st.slider("N most lethal départements", 1, 20, 10, key="whatif_n")
        avoided = metrics.avoided_deaths_per_year(dep, national, top_n, years[1] - years[0] + 1)
        st.metric("Deaths per year that would be avoided (estimate)", f"{avoided:.0f}", border=True,
                  help=f"National lethality used: {ui.fmt_rate(national)} deaths per {C.LETHALITY_PER} accidents.")
        st.caption(
            f"For each of the N most lethal départements (with at least {C.MIN_ACCIDENTS_FOR_RATE} accidents), "
            "avoided deaths = deaths − accidents × national rate; the total is divided by the number of years. "
            "This is an illustrative scenario, not a prediction: it keeps the number of accidents unchanged and "
            "says nothing about how the gap could be closed."
        )


def render():
    filters = ui.current_filters()
    acc = filtered_accidents(filters.years, filters.regions)
    dep = metrics.by_departement(acc)

    st.title("Where: do the départements with the most accidents have the deadliest ones?")
    ui.headline(size_vs_lethality_headline(dep) or "Select more regions (at least 8 départements with enough "
                                                   "accidents) to compare busy and quiet départements.")
    map_section(dep)
    ranking(dep, metrics.kpis(acc)["lethality"])
    st.caption("Lethality describes how severe accidents are, not how many people are at risk: without traffic "
               "or population data, a low lethality does not mean a low risk per inhabitant. Dense and rural "
               "areas differ in road type, speed and many other ways, so this is an association, not a cause.")
    whatif_section(dep, filters.years)
    ui.source_note(f"Boundaries: Contours administratifs, data.gouv.fr · {C.GEO_LICENCE}.")
