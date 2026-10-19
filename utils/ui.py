"""Small Streamlit building blocks shared by all pages (headlines, charts, notes)."""

from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import constants as C
from utils.filters import Filters

FILTERS_KEY = "filters"


# --- Number formatting ---------------------------------------------------------------

def fmt_int(value: float) -> str:
    """12345 -> "12,345"."""
    return f"{value:,.0f}"


def fmt_rate(value: float) -> str:
    """Lethality with one decimal, or an en dash when not available."""
    return "–" if value is None or math.isnan(value) else f"{value:.1f}"


def fmt_change(value: float | None, unit: str = "%") -> str:
    """Signed change such as "+3.2%" or "−1.0 pts"."""
    if value is None or math.isnan(value):
        return "n/a"
    sign = "+" if value >= 0 else "−"
    return f"{sign}{abs(value):.1f}{unit}"


CLEAR_RATIO = 1.2  # below this ratio two rates are described as "about the same"


def compare_rates(a: float, b: float) -> str:
    """How rate ``a`` compares with rate ``b``, in words that never overstate small gaps.

    Returns e.g. "2.7 times as lethal as", "about as lethal as" or "less lethal than".
    """
    if b == 0 or math.isnan(a) or math.isnan(b):
        return "not comparable with"
    ratio = a / b
    if ratio >= CLEAR_RATIO:
        return f"{ratio:.1f} times as lethal as"
    if ratio <= 1 / CLEAR_RATIO:
        return "less lethal than"
    return "about as lethal as"


# --- Page parts ---------------------------------------------------------------------------

def current_filters() -> Filters:
    """The selection made in the sidebar (set by app.py on every run)."""
    return st.session_state.get(FILTERS_KEY, Filters())


def headline(text: str) -> None:
    """The one-sentence insight that opens a page or a section."""
    with st.container(border=True):
        st.markdown(f"**Key insight —** {text}")


def chart(fig: go.Figure, alt: str, key: str | None = None) -> None:
    """Show a Plotly chart with an accessible description shown as a caption too."""
    st.plotly_chart(fig, width="stretch", alt=alt, key=key,
                    config={"displaylogo": False, "modeBarButtonsToRemove": ["select2d", "lasso2d"]})
    st.caption(alt)


def source_note(extra: str = "") -> None:
    """Data source line placed under a group of charts."""
    st.caption(f"{C.SOURCE_NOTE}. {extra}".strip())


def require_rows(df: pd.DataFrame) -> None:
    """Stop the page politely when the filters leave no data."""
    if df.empty:
        st.warning("No accident matches the current filters. Widen the selection in the sidebar.")
        st.stop()


def lethality_help() -> str:
    """Definition shown in tooltips."""
    return (f"Deaths (within 30 days) per {C.LETHALITY_PER} injury accidents recorded by the police. "
            f"Rates based on fewer than {C.MIN_ACCIDENTS_FOR_RATE} accidents are hidden or greyed out.")
