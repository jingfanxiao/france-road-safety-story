"""Plotly charts, one function per chart, all with the same style.

Each chart has a title, axis titles with units and a hover text. The functions
only build figures (no Streamlit), so scripts/check_charts.py can test them.
"""

import numpy as np
import plotly.graph_objects as go

import constants as C


def style(fig, title, x_title=None, y_title=None, height=380):
    """Common layout: white background, light grid, readable fonts."""
    fig.update_layout(
        title={"text": title, "x": 0, "xanchor": "left", "font": {"size": 17}},
        template="plotly_white",
        font={"family": "Source Sans Pro, Arial, sans-serif", "size": 13, "color": C.TEXT_COLOR},
        height=height,
        margin={"l": 10, "r": 10, "t": 60, "b": 10},
        hoverlabel={"bgcolor": "white", "font_size": 13},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.0, "xanchor": "left", "x": 0},
        colorway=C.PALETTE,
    )
    fig.update_xaxes(title_text=x_title, gridcolor=C.GRID_COLOR, zeroline=False)
    fig.update_yaxes(title_text=y_title, gridcolor=C.GRID_COLOR, zeroline=False, rangemode="tozero")
    return fig


REFERENCE_LINE = {"dash": "dash", "color": C.NEUTRAL_COLOR, "width": 1.5}


def yearly_trend_indexed(yearly, title):
    """Accidents and deaths per year, both indexed to the first year = 100.

    The two counts differ by a factor ~20, and two y-axes mislead; an index puts
    both trends on one scale, while the hover text gives the real counts.
    """
    base_year = int(yearly["year"].iloc[0])
    fig = go.Figure()
    for column, label, color, dash in [("accidents", "Injury accidents", C.MAIN_COLOR, "solid"),
                                       ("killed", "Deaths", C.HIGHLIGHT_COLOR, "dash")]:
        index = 100 * yearly[column] / yearly[column].iloc[0]
        fig.add_trace(go.Scatter(
            x=yearly["year"], y=index, name=label, mode="lines+markers",
            line={"color": color, "width": 2.5, "dash": dash}, marker={"size": 8, "color": color},
            customdata=yearly[column],
            hovertemplate=(f"<b>{label}</b>, %{{x}}<br>Index: %{{y:.1f}} ({base_year} = 100)"
                           "<br>Count: %{customdata:,}<extra></extra>"),
        ))
        # Label at the end of each line, so the series are not told apart by colour alone.
        fig.add_annotation(x=yearly["year"].iloc[-1], y=index.iloc[-1], text=f" {label}", showarrow=False,
                           xanchor="left", font={"color": C.TEXT_COLOR, "size": 12})
    if C.LOCKDOWN_YEAR in set(yearly["year"]):
        fig.add_vrect(x0=C.LOCKDOWN_YEAR - 0.5, x1=C.LOCKDOWN_YEAR + 0.5, fillcolor=C.NEUTRAL_COLOR,
                      opacity=0.15, line_width=0, annotation_text="2020: COVID-19 lockdowns",
                      annotation_position="top left", annotation_font={"size": 11, "color": C.TEXT_COLOR})
    fig.add_hline(y=100, line=REFERENCE_LINE, annotation_text=f"{base_year} level",
                  annotation_position="top left", annotation_font_color=C.TEXT_COLOR)
    style(fig, title, "Year", f"Index ({base_year} = 100)")
    fig.update_xaxes(dtick=1, range=[yearly["year"].min() - 0.3, yearly["year"].max() + 0.9])
    fig.update_yaxes(rangemode="normal")
    return fig


def hour_weekday_heatmap(matrix, title, colorbar_title, scale=C.SEQUENTIAL_SCALE, value_format=",.0f"):
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


def category_bar(table, category, value, title, x_title, reference, reference_label,
                 value_format=".1f", count_column="accidents", count_label="Accidents"):
    """Horizontal bars with a value label and a dashed reference line.

    Grey bars rest on too few cases for a stable rate; the hover shows the sample size.
    """
    fig = go.Figure(go.Bar(
        x=table[value], y=table[category].astype(str), orientation="h",
        marker={"color": np.where(table["reliable"], C.MAIN_COLOR, C.NEUTRAL_COLOR)},
        text=[f"{v:{value_format}}" for v in table[value]], textposition="outside", cliponaxis=False,
        customdata=table[count_column],
        hovertemplate=(f"<b>%{{y}}</b><br>{x_title}: %{{x:{value_format}}}<br>"
                       f"{count_label}: %{{customdata:,}}<extra></extra>"),
    ))
    style(fig, title, x_title, None)
    fig.update_yaxes(autorange="reversed", rangemode="normal")
    fig.update_xaxes(range=[0, table[value].max() * 1.18])
    fig.add_vline(x=reference, line=REFERENCE_LINE, annotation_text=reference_label,
                  annotation_position="top right", annotation_font_color=C.TEXT_COLOR)
    return fig


def dep_choropleth(dep_table, geojson, value, title, colorbar_title, scale=C.SEQUENTIAL_SCALE,
                   value_format=",.0f", hide_unreliable=False):
    """Map of metropolitan départements (overseas ones are not in the GeoJSON).

    With hide_unreliable, départements below the accident threshold are drawn in grey.
    """
    map_codes = {feature["id"] for feature in geojson["features"]}
    data = dep_table.assign(dep=dep_table["dep"].astype(str))
    data = data[data["dep"].isin(map_codes)]
    shown = data[data["reliable"]] if hide_unreliable else data
    greyed = data[~data["reliable"]]

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
    if hide_unreliable and len(greyed):
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


def missingness_bar(missing, title, structural):
    """The 15 columns with the most missing values; grey = empty by design (e.g. pedestrian-only fields)."""
    table = missing.sort_values("pct_missing", ascending=False).head(15)
    labels = table["table"] + "." + table["column"]
    fig = go.Figure(go.Bar(
        x=table["pct_missing"], y=labels, orientation="h",
        marker={"color": np.where(labels.isin(structural), C.NEUTRAL_COLOR, C.MAIN_COLOR)},
        text=[f"{v:.1f}%" for v in table["pct_missing"]], textposition="outside", cliponaxis=False,
        customdata=table[["n_missing", "n_rows"]],
        hovertemplate=("<b>%{y}</b><br>Missing: %{x:.2f}%<br>"
                       "%{customdata[0]:,} of %{customdata[1]:,} rows<extra></extra>"),
    ))
    style(fig, title, "Missing values (% of rows)", None, height=28 * len(table) + 120)
    fig.update_yaxes(autorange="reversed", rangemode="normal")
    fig.update_xaxes(range=[0, min(100, table["pct_missing"].max() * 1.2 + 1)])
    return fig
