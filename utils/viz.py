"""Plotly chart functions, one chart per function, sharing one visual style.

Every chart has a title, axis titles with units and a hover template.
Functions return a figure and never call Streamlit, so they can be tested
outside the app.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

import constants as C

FONT_FAMILY = "Source Sans Pro, Arial, sans-serif"
CHART_HEIGHT = 380


# --- Shared style -----------------------------------------------------------------

def style(fig: go.Figure, title: str, x_title: str | None = None, y_title: str | None = None,
          height: int = CHART_HEIGHT) -> go.Figure:
    """Apply the common layout: white background, light grid, readable fonts."""
    fig.update_layout(
        title={"text": title, "x": 0, "xanchor": "left", "font": {"size": 17}},
        template="plotly_white",
        font={"family": FONT_FAMILY, "size": 13, "color": C.TEXT_COLOR},
        height=height,
        margin={"l": 10, "r": 10, "t": 60, "b": 10},
        hoverlabel={"bgcolor": "white", "font_size": 13},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.0, "xanchor": "left", "x": 0},
        colorway=C.PALETTE,
    )
    fig.update_xaxes(title_text=x_title, gridcolor=C.GRID_COLOR, zeroline=False)
    fig.update_yaxes(title_text=y_title, gridcolor=C.GRID_COLOR, zeroline=False, rangemode="tozero")
    return fig


def add_reference_line(fig: go.Figure, value: float, label: str, axis: str = "y") -> go.Figure:
    """Dashed reference line (e.g. the average of the selection)."""
    if value is None or np.isnan(value):
        return fig
    line = {"dash": "dash", "color": C.NEUTRAL_COLOR, "width": 1.5}
    if axis == "y":
        fig.add_hline(y=value, line=line, annotation_text=label, annotation_position="top left",
                      annotation_font_color=C.TEXT_COLOR)
    else:
        fig.add_vline(x=value, line=line, annotation_text=label, annotation_position="top right",
                      annotation_font_color=C.TEXT_COLOR)
    return fig


# --- Time ---------------------------------------------------------------------------

def yearly_trend_indexed(yearly: pd.DataFrame, title: str) -> go.Figure:
    """Accidents and deaths per year, both indexed to the first year = 100.

    Accidents (~50,000 a year) and deaths (~3,000) cannot share one axis in
    absolute numbers, and two y-axes mislead; an index puts both trends on the
    same scale while the hover text gives the real counts.
    """
    base_year = int(yearly["year"].iloc[0])
    series = [("accidents", "Injury accidents", C.MAIN_COLOR, "solid"),
              ("killed", "Deaths", C.HIGHLIGHT_COLOR, "dash")]
    fig = go.Figure()
    for column, label, color, dash in series:
        index = 100 * yearly[column] / yearly[column].iloc[0]
        fig.add_trace(go.Scatter(
            x=yearly["year"], y=index, name=label, mode="lines+markers",
            line={"color": color, "width": 2.5, "dash": dash}, marker={"size": 8, "color": color},
            customdata=yearly[column],
            hovertemplate=(f"<b>{label}</b>, %{{x}}<br>Index: %{{y:.1f}} ({base_year} = 100)"
                           "<br>Count: %{customdata:,}<extra></extra>"),
        ))
        # Direct label at the end of each line, so identity does not rely on colour alone.
        fig.add_annotation(x=yearly["year"].iloc[-1], y=index.iloc[-1], text=f" {label}", showarrow=False,
                           xanchor="left", font={"color": C.TEXT_COLOR, "size": 12})
    if C.LOCKDOWN_YEAR in set(yearly["year"]):
        fig.add_vrect(x0=C.LOCKDOWN_YEAR - 0.5, x1=C.LOCKDOWN_YEAR + 0.5, fillcolor=C.NEUTRAL_COLOR,
                      opacity=0.15, line_width=0, annotation_text="2020: COVID-19 lockdowns",
                      annotation_position="top left", annotation_font={"size": 11, "color": C.TEXT_COLOR})
    add_reference_line(fig, 100, f"{base_year} level")
    style(fig, title, "Year", f"Index ({base_year} = 100)")
    fig.update_xaxes(dtick=1, range=[yearly["year"].min() - 0.3, yearly["year"].max() + 0.9])
    fig.update_yaxes(rangemode="normal")
    return fig


def hour_weekday_heatmap(matrix: pd.DataFrame, title: str, colorbar_title: str,
                         scale: str = C.SEQUENTIAL_SCALE, value_format: str = ",.0f") -> go.Figure:
    """Weekday × hour heatmap; empty cells mean too few accidents."""
    fig = go.Figure(go.Heatmap(
        z=matrix.values, x=[f"{h:02d}h" for h in matrix.columns], y=list(matrix.index),
        colorscale=scale, colorbar={"title": {"text": colorbar_title}},
        xgap=1, ygap=1, hoverongaps=False,
        hovertemplate="<b>%{y}, %{x}</b><br>" + colorbar_title + ": %{z:" + value_format + "}<extra></extra>",
    ))
    style(fig, title, "Hour of the day", "Day of the week", height=360)
    fig.update_yaxes(autorange="reversed", rangemode="normal", showgrid=False)
    fig.update_xaxes(showgrid=False)
    return fig


# --- Categories -----------------------------------------------------------------------

def category_bar(table: pd.DataFrame, category: str, value: str, title: str, x_title: str | None,
                 y_title: str | None, reference: float | None = None, reference_label: str = "",
                 horizontal: bool = False, value_format: str = ".1f",
                 count_column: str = "accidents", count_label: str = "Accidents") -> go.Figure:
    """Bar per category with a value label, a hover showing the sample size,
    and grey bars when the sample is too small for a stable rate."""
    colors = np.where(table["reliable"], C.MAIN_COLOR, C.NEUTRAL_COLOR)
    labels = [f"{v:{value_format}}" if pd.notna(v) else "" for v in table[value]]
    cats = table[category].astype(str)
    hover = ("<b>%{" + ("y" if horizontal else "x") + "}</b><br>" + (x_title if horizontal else y_title)
             + ": %{" + ("x" if horizontal else "y") + ":" + value_format + "}<br>"
             + count_label + ": %{customdata:,}<extra></extra>")
    fig = go.Figure(go.Bar(
        x=table[value] if horizontal else cats,
        y=cats if horizontal else table[value],
        orientation="h" if horizontal else "v",
        marker={"color": colors}, text=labels, textposition="outside", cliponaxis=False,
        customdata=table[count_column], hovertemplate=hover,
    ))
    style(fig, title, x_title, y_title)
    if horizontal:
        fig.update_yaxes(autorange="reversed", rangemode="normal")
        fig.update_xaxes(range=[0, table[value].max() * 1.18])
    else:
        fig.update_yaxes(range=[0, table[value].max() * 1.18])
    if reference is not None:
        add_reference_line(fig, reference, reference_label, axis="x" if horizontal else "y")
    return fig


# --- Map ----------------------------------------------------------------------------------

def dep_choropleth(dep_table: pd.DataFrame, geojson: dict, value: str, title: str,
                   colorbar_title: str, scale: str = C.SEQUENTIAL_SCALE,
                   value_format: str = ",.0f", hide_unreliable: bool = False) -> go.Figure:
    """Choropleth of metropolitan départements. Overseas units are not drawn.

    With ``hide_unreliable`` the départements below the accident threshold are
    drawn in grey instead of coloured, so noisy rates do not stand out.
    """
    map_codes = {feature["id"] for feature in geojson["features"]}
    data = dep_table[dep_table["dep"].astype(str).isin(map_codes)].copy()
    data["dep"] = data["dep"].astype(str)
    shown = data[data["reliable"]] if hide_unreliable else data
    greyed = data[~data["reliable"]] if hide_unreliable else data.iloc[0:0]

    custom = ["dep_name", "accidents", "killed", "lethality"]
    hover = ("<b>%{customdata[0]} (%{location})</b><br>"
             "Accidents: %{customdata[1]:,}<br>Deaths: %{customdata[2]:,}<br>"
             "Lethality: %{customdata[3]:.1f} deaths per 100 accidents<extra></extra>")
    fig = go.Figure(go.Choropleth(
        geojson=geojson, locations=shown["dep"], featureidkey="id", z=shown[value],
        colorscale=scale, marker_line_color="white", marker_line_width=0.5,
        colorbar={"title": {"text": colorbar_title}, "tickformat": value_format},
        customdata=shown[custom], hovertemplate=hover,
    ))
    if len(greyed):
        fig.add_trace(go.Choropleth(
            geojson=geojson, locations=greyed["dep"], featureidkey="id", z=np.zeros(len(greyed)),
            colorscale=[[0, "#DDDDDD"], [1, "#DDDDDD"]], showscale=False,
            marker_line_color="white", marker_line_width=0.5, customdata=greyed[custom],
            hovertemplate=hover.replace("<extra>", f"<br><i>Fewer than {C.MIN_ACCIDENTS_FOR_RATE} accidents: "
                                                   "rate not shown</i><extra>"),
        ))
    fig.update_geos(fitbounds="locations", visible=False)
    style(fig, title, height=560)
    fig.update_layout(margin={"l": 0, "r": 0, "t": 50, "b": 0})
    return fig


# --- Quality ------------------------------------------------------------------------------

def missingness_bar(missing: pd.DataFrame, title: str, structural: set[str] = frozenset(),
                    top_n: int = 15) -> go.Figure:
    """Columns with the highest share of missing values ("-1" or empty).

    Columns listed in ``structural`` (as "table.column") are drawn in grey: they
    are empty by design for most rows (e.g. pedestrian-only fields).
    """
    table = missing.sort_values("pct_missing", ascending=False).head(top_n)
    labels = table["table"] + "." + table["column"]
    colors = np.where(labels.isin(structural), C.NEUTRAL_COLOR, C.MAIN_COLOR)
    fig = go.Figure(go.Bar(
        x=table["pct_missing"], y=labels, orientation="h", marker={"color": colors},
        text=[f"{v:.1f}%" for v in table["pct_missing"]], textposition="outside", cliponaxis=False,
        customdata=table[["n_missing", "n_rows"]],
        hovertemplate=("<b>%{y}</b><br>Missing: %{x:.2f}%<br>"
                       "%{customdata[0]:,} of %{customdata[1]:,} rows<extra></extra>"),
    ))
    style(fig, title, "Missing values (% of rows)", None, height=28 * len(table) + 120)
    fig.update_yaxes(autorange="reversed", rangemode="normal")
    fig.update_xaxes(range=[0, min(100, table["pct_missing"].max() * 1.2 + 1)])
    return fig
