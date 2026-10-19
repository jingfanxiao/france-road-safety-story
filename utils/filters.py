"""Cached data loading, sidebar filters and filter application.

The sidebar values live in ``st.session_state`` so every page sees the same
selection. Filtering is cached on the filter values only (plain tuples), so
the large accident table is never hashed on each rerun.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import pandas as pd
import streamlit as st

import constants as C

# Session-state keys of the sidebar widgets.
KEY_YEARS = "f_years"
KEY_REGIONS = "f_regions"
KEY_INDICATOR = "f_indicator"
DEFAULT_INDICATOR = "Injury accidents"


# --- Cached loaders ------------------------------------------------------------------

@st.cache_data(show_spinner="Loading accident data…")
def load_accidents() -> pd.DataFrame:
    """One row per accident (see utils/prep.py)."""
    return pd.read_parquet(C.ACCIDENTS_FILE)


@st.cache_data(show_spinner=False)
def load_users_agg() -> pd.DataFrame:
    """Road-user counts by year × département × area × user type × age band × severity."""
    return pd.read_parquet(C.USERS_AGG_FILE)


@st.cache_data(show_spinner=False)
def load_geojson() -> dict:
    """Département boundaries for metropolitan France and Corsica."""
    with open(C.GEOJSON_FILE, encoding="utf-8") as handle:
        return json.load(handle)


@st.cache_data(show_spinner=False)
def load_quality() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Quality checks, missingness table and summary."""
    checks = pd.read_parquet(C.QUALITY_PARQUET_FILE)
    missing = pd.read_parquet(C.MISSINGNESS_FILE)
    with open(C.QUALITY_JSON_FILE, encoding="utf-8") as handle:
        summary = json.load(handle)["summary"]
    return checks, missing, summary


@st.cache_data(show_spinner=False)
def region_options() -> list[str]:
    """Regions present in the data, sorted by name (for the sidebar)."""
    return sorted(load_accidents()["region"].astype(str).unique())


# --- Filter state --------------------------------------------------------------------

@dataclass(frozen=True)
class Filters:
    """The current sidebar selection. An empty ``regions`` tuple means all of France."""

    years: tuple[int, int] = (C.FIRST_YEAR, C.LAST_YEAR)
    regions: tuple[str, ...] = ()
    indicator: str = DEFAULT_INDICATOR

    def is_default(self) -> bool:
        return self == Filters()

    def describe(self) -> str:
        """Human-readable summary of the active filters."""
        place = ", ".join(self.regions) if self.regions else "All of France"
        return f"Years {self.years[0]}–{self.years[1]} · {place} · Indicator: {self.indicator}"


def apply_to_accidents(acc: pd.DataFrame, years: tuple[int, int], regions: tuple[str, ...]) -> pd.DataFrame:
    """Keep the accidents in the year range and regions (pure pandas, no Streamlit)."""
    mask = acc["year"].between(years[0], years[1])
    if regions:
        mask &= acc["region"].isin(regions)
    return acc[mask]


def apply_to_users(users: pd.DataFrame, years: tuple[int, int], regions: tuple[str, ...]) -> pd.DataFrame:
    """Keep the road-user counts in the year range and regions.

    The road-user table has no region column, so regions are found from the
    département code with the same mapping as the accident table.
    """
    mask = users["year"].between(years[0], years[1])
    if regions:
        user_regions = users["dep"].astype(str).map(C.DEP_TO_REGION).fillna(C.OTHER_REGION)
        mask &= user_regions.isin(regions)
    return users[mask]


@st.cache_data(show_spinner=False)
def filtered_accidents(years: tuple[int, int], regions: tuple[str, ...] = ()) -> pd.DataFrame:
    """Cached filtered accident table."""
    return apply_to_accidents(load_accidents(), years, regions)


@st.cache_data(show_spinner=False)
def filtered_users(years: tuple[int, int], regions: tuple[str, ...] = ()) -> pd.DataFrame:
    """Cached filtered road-user counts."""
    return apply_to_users(load_users_agg(), years, regions)


# --- Sidebar --------------------------------------------------------------------------

def reset_filters() -> None:
    """Callback of the "Reset filters" button."""
    for key in [KEY_YEARS, KEY_REGIONS, KEY_INDICATOR]:
        st.session_state.pop(key, None)


def render_sidebar() -> Filters:
    """Draw the global filters and return the current selection."""
    sidebar = st.sidebar
    sidebar.header("Filters")

    years = sidebar.slider("Years", C.FIRST_YEAR, C.LAST_YEAR, (C.FIRST_YEAR, C.LAST_YEAR), key=KEY_YEARS)
    regions = sidebar.multiselect(
        "Region", region_options(), key=KEY_REGIONS,
        help="Leave empty for all of France (including overseas).",
    )
    indicator = sidebar.selectbox(
        "Indicator", list(C.INDICATORS), key=KEY_INDICATOR,
        help="Colours the hour × day-of-week heatmap on the 'Who' page. "
             "Lethality = deaths per 100 injury accidents.",
    )

    filters = Filters(years=tuple(years), regions=tuple(regions), indicator=indicator)
    sidebar.button("Reset filters", on_click=reset_filters, disabled=filters.is_default(), width="stretch")
    sidebar.caption("**Active selection:** " + filters.describe())
    return filters
