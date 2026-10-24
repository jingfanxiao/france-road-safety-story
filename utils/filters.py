"""Cached data loading, the sidebar filters, and filtering by year range and region."""

import json
from dataclasses import dataclass

import pandas as pd
import streamlit as st

import constants as C


@st.cache_data(show_spinner="Loading accident data…")
def load_accidents():
    return pd.read_parquet(C.ACCIDENTS_FILE)


@st.cache_data(show_spinner=False)
def load_users_agg():
    return pd.read_parquet(C.USERS_AGG_FILE)


@st.cache_data(show_spinner=False)
def load_geojson():
    with open(C.GEOJSON_FILE, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(show_spinner=False)
def load_quality():
    """Quality checks, missing-value table and summary counts."""
    checks = pd.read_parquet(C.QUALITY_PARQUET_FILE)
    missing = pd.read_parquet(C.MISSINGNESS_FILE)
    with open(C.QUALITY_JSON_FILE, encoding="utf-8") as f:
        summary = json.load(f)["summary"]
    return checks, missing, summary


# The cache key is only (years, regions), so the big table is not hashed on every rerun.
@st.cache_data(show_spinner=False)
def filtered_accidents(years, regions=()):
    acc = load_accidents()
    mask = acc["year"].between(years[0], years[1])
    if regions:
        mask &= acc["region"].isin(regions)
    return acc[mask]


@st.cache_data(show_spinner=False)
def filtered_users(years, regions=()):
    users = load_users_agg()
    mask = users["year"].between(years[0], years[1])
    if regions:
        # The road-user table has no region column: map it from the département code.
        user_regions = users["dep"].astype(str).map(C.DEP_TO_REGION).fillna(C.OTHER_REGION)
        mask &= user_regions.isin(regions)
    return users[mask]


@dataclass
class Filters:
    """The sidebar selection. No region selected means all of France."""
    years: tuple = (C.FIRST_YEAR, C.LAST_YEAR)
    regions: tuple = ()
    indicator: str = "Injury accidents"

    def describe(self):
        place = ", ".join(self.regions) if self.regions else "All of France"
        return f"Years {self.years[0]}–{self.years[1]} · {place} · Indicator: {self.indicator}"


def default_widget_values():
    """Widget key -> default value, taken from the Filters defaults."""
    default = Filters()
    return {"f_years": default.years, "f_regions": list(default.regions), "f_indicator": default.indicator}


def reset_filters():
    # Write the defaults back instead of deleting the keys: only a value set through
    # st.session_state is sent to the browser, so deleting would leave the widgets showing
    # the old selection while the pages already use the defaults.
    for key, value in default_widget_values().items():
        st.session_state[key] = value


def render_sidebar():
    """Draw the global filters and return the current selection."""
    # The widgets take their start value from session state only (no value= argument),
    # so the reset above and the first run use the same source.
    for key, value in default_widget_values().items():
        st.session_state.setdefault(key, value)

    st.sidebar.header("Filters")
    years = st.sidebar.slider("Years", C.FIRST_YEAR, C.LAST_YEAR, key="f_years")
    regions = st.sidebar.multiselect(
        "Region", sorted(load_accidents()["region"].cat.categories), key="f_regions",
        help="Leave empty for all of France (including overseas).",
    )
    indicator = st.sidebar.selectbox(
        "Indicator", list(C.INDICATORS), key="f_indicator",
        help="Colours the hour × day-of-week heatmap on the 'Who' page. "
             "Lethality = deaths per 100 injury accidents.",
    )
    filters = Filters(tuple(years), tuple(regions), indicator)
    st.sidebar.button("Reset filters", on_click=reset_filters, disabled=filters == Filters(), width="stretch")
    st.sidebar.caption("**Active selection:** " + filters.describe())
    return filters
