"""Entry point: page setup, global sidebar filters and navigation.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

import constants as C
from sections import quality_conclusions, story, where, who
from utils import ui
from utils.filters import render_sidebar

st.set_page_config(
    page_title="Road danger in France",
    page_icon=":material/traffic:",
    layout="wide",
)

PAGES = [
    st.Page(story.render, title="Story & Overview", icon=":material/menu_book:", url_path="story", default=True),
    st.Page(where.render, title="Where", icon=":material/map:", url_path="where"),
    st.Page(who.render, title="Who", icon=":material/groups:", url_path="who"),
    st.Page(quality_conclusions.render, title="Data Quality & Conclusions", icon=":material/fact_check:",
            url_path="quality-conclusions"),
]

navigation = st.navigation(PAGES)

# The sidebar is drawn on every run, before the page, so all pages share one selection.
st.session_state[ui.FILTERS_KEY] = render_sidebar()
st.sidebar.divider()
st.sidebar.caption(
    f"Data: [BAAC, {C.DATASET_PRODUCER}]({C.DATASET_PAGE_URL}) · Licence Ouverte / Open Licence. "
    f"Boundaries: [Contours administratifs]({C.GEO_DATASET_PAGE_URL}) · {C.GEO_LICENCE}."
)

navigation.run()
