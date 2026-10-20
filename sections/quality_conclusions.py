"""Page 4 — Data Quality & Conclusions: checks, missing values, findings, limitations, next steps."""

import streamlit as st

import constants as C
from sections import story, where, who
from utils import metrics, ui, viz
from utils.filters import filtered_accidents, filtered_users, load_quality
from utils.quality import STRUCTURAL_MISSING

STATUS_ICONS = {"pass": " pass", "minor": " minor", "warning": " warning"}
STATUS_COLORS = {
    "pass": "#4D4D4D",     
    "minor": "#A15C00",    
    "warning": "#B42318"   
}


def quality_headline(overall, summary):
    """Number of checks per status, and the checks with a warning."""
    warnings = overall[overall["status"] == "warning"].sort_values("pct_flagged", ascending=False)
    worst = "; ".join(f"{row.check.lower()} ({row.pct_flagged:.1f}% of {row.table} rows)"
                      for row in warnings.itertuples())
    text = (f"{summary['n_pass']} of {summary['n_checks']} checks pass, {summary['n_minor']} flag less than "
            f"{C.QUALITY_WARN_PCT:.0f}% of rows and {summary['n_warning']} flag more")
    return text + (f": {worst}." if worst else ".")

def status_style(status):

    clean_status = str(status).strip()
    
    color = STATUS_COLORS.get(clean_status, "black") 
    
    weight = "bold" if clean_status == "warning" else "normal"
    
    return f"color: {color}; font-weight: {weight}"


def checks_table(overall):
    """Duplicates, orphan keys, coordinates and value checks, all years together."""
    
    view = overall.copy() 
    
    styled_view = view[["status", "check", "table", "n_flagged", "n_rows", "pct_flagged", "description"]]\
        .style.map(status_style, subset=["status"])
    
    st.dataframe(
        styled_view,
        hide_index=True, 
        width="stretch",
        column_config={
            "status": "Status", 
            "check": "Check", 
            "table": "Table",
            "n_flagged": st.column_config.NumberColumn("Rows flagged", format="localized"),
            "n_rows": st.column_config.NumberColumn("Rows checked", format="localized"),
            "pct_flagged": st.column_config.NumberColumn("% flagged", format="%.2f"),
            "description": st.column_config.TextColumn("What is checked", width="large"),
        },
    )
    
    st.caption(
        f"Status: pass = nothing flagged; minor = less than {C.QUALITY_WARN_PCT:.0f}% of rows; "
        f"warning = {C.QUALITY_WARN_PCT:.0f}% or more. Per-year results are in "
        "data/processed/quality_report.json."
    )

def missingness_chart(missing):
    """Columns with the most missing values, all years together, free-text fields left out."""
    data = missing[~missing["is_text_field"]]
    totals = data.groupby(["table", "column"], as_index=False)[["n_missing", "n_rows"]].sum()
    totals["pct_missing"] = 100 * totals["n_missing"] / totals["n_rows"]
    fig = viz.missingness_bar(totals[totals["n_missing"] > 0], "Columns with the most missing values",
                              STRUCTURAL_MISSING)
    ui.chart(fig, "Horizontal bar chart of the share of missing values per column, highest first. Grey bars are "
                  "columns that are empty by design for most rows.", key="quality_missing")
    st.caption('"Missing" counts the code -1 and empty cells (free-text fields such as the address are left '
               "out). Grey: second/third safety device and pedestrian-only fields, which do not apply to most "
               "road users.")


def conclusions(filters):
    """The three page headlines, recomputed for the selection, each with what it implies."""
    acc = filtered_accidents(filters.years, filters.regions)
    users = filtered_users(filters.years, filters.regions)
    findings = [
        ("Trend", story.trend_headline(metrics.count_table(acc, "year")),
         "Look at deaths and lethality, not only at accident counts: fewer accidents do not automatically "
         "mean fewer deaths."),
        ("Where", where.size_vs_lethality_headline(metrics.by_departement(acc)),
         "Ranking territories by lethality points to different places than ranking them by accident counts; "
         "both views are needed to set local priorities."),
        ("Who", who.user_type_headline(metrics.users_by_type(users)),
         "Road users outside a car deserve specific attention (crossings, lighting, separated space), "
         "in proportion to their share of the deaths."),
    ]
    for number, (label, finding, implication) in enumerate(findings, start=1):
        if finding:  # a headline is None when the selection is too small
            st.markdown(f"**{number}. {label}.** {finding}  \n*Implication:* {implication}")


def render():
    filters = ui.current_filters()
    checks, missing, summary = load_quality()
    # One row per check for all years together ("Rows per year" is information, not a check).
    overall = checks[(checks["year"] == "all") & (checks["check"] != "Rows per year")]

    st.title("Data quality & conclusions")

    st.header("Can we trust these numbers?")
    ui.headline(quality_headline(overall, summary))
    st.caption("Checks run on the raw files as published, before cleaning, for all years and places "
               "(they do not follow the sidebar filters).")
    checks_table(overall)
    missingness_chart(missing)

    st.header("Conclusions")
    st.caption("Recomputed for the current selection: " + filters.describe())
    conclusions(filters)

    st.header("Limitations")
    st.markdown(
        "- **Collection:** every record comes from a police or gendarmerie report (BAAC form) of an injury "
        "accident on a public road — a census of recorded accidents, not a sample. Accidents without police "
        "attendance are missing, so slight injuries are under-reported.\n"
        "- **Measures:** deaths (within 30 days) are the most reliable outcome; 'hospitalised' is not "
        "certified by the official statistics authority since 2019. From 2021, people who fled the scene are "
        "added with little information (age, sex).\n"
        "- **No exposure data** (traffic, kilometres, population): lethality is the severity of accidents, "
        "not a risk per inhabitant or per kilometre.\n"
        "- **No causal claims:** these are associations; place, road type, speed and road-user type are "
        "linked with each other. The what-if scenario is arithmetic, not a forecast.\n"
        f"- **Cleaning choices:** '-1' and empty cells are missing; ages outside 0–{C.AGE_MAX} and speed limits "
        f"outside {C.VMA_MIN}–{C.VMA_MAX} km/h are unknown; from 2023 the first road of each accident is kept.\n"
        "- **Privacy and licence:** only aggregated counts and rates are shown. Data: "
        f"{C.DATASET_PRODUCER}, [data.gouv.fr]({C.DATASET_PAGE_URL}), Licence Ouverte / Open Licence; "
        f"boundaries: [Contours administratifs]({C.GEO_DATASET_PAGE_URL}), {C.GEO_LICENCE}."
    )

    st.header("Next steps")
    st.markdown(
        "- Add **exposure data** (traffic counts, population) to move from severity to risk.\n"
        "- Use the accident **coordinates** to find local black spots on road sections.\n"
        "- Fit a **multivariable model** to separate the roles of place, road type, speed and light.\n"
        "- **Update** each year with the new BAAC file: "
        "`python scripts/build_data.py --download --prepare --quality`."
    )
    ui.source_note()
