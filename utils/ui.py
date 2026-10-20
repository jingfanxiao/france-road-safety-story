"""Small helpers shared by the pages: number formats, headline box, charts with alt text."""

import streamlit as st

import constants as C


def fmt_int(value):
    """12345 -> "12,345"."""
    return f"{value:,.0f}"


def fmt_rate(value):
    """Rate with one decimal: 6.08 -> "6.1"."""
    return f"{value:.1f}"


def fmt_change(value, unit="%"):
    """Signed change: "+3.2%" or "−1.0 pts"."""
    sign = "+" if value >= 0 else "−"
    return f"{sign}{abs(value):.1f}{unit}"


def current_filters():
    """The sidebar selection, stored by app.py on every run."""
    return st.session_state["filters"]


def headline(text):
    """The one-sentence insight at the top of a section."""
    with st.container(border=True):
        st.markdown(f"**Key insight —** {text}")


def chart(fig, alt, key=None):
    """Show a Plotly chart; the alt text is also shown as a caption (accessibility)."""
    st.plotly_chart(fig, width="stretch", alt=alt, key=key,
                    config={"displaylogo": False, "modeBarButtonsToRemove": ["select2d", "lasso2d"]})
    st.caption(alt)


def source_note(extra=""):
    """Data source line at the bottom of a page."""
    st.caption(f"{C.SOURCE_NOTE}. {extra}".strip())
