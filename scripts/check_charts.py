"""Smoke test: build every chart from the processed data, without opening the app.

Run from the project root:  python scripts/check_charts.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # so "import constants" works

import constants as C  # noqa: E402
from utils import metrics, viz  # noqa: E402
from utils.filters import filtered_accidents, filtered_users, load_geojson, load_quality  # noqa: E402
from utils.quality import STRUCTURAL_MISSING  # noqa: E402

# Filters: the full range keeps everything; a narrower one must shrink both tables.
acc = filtered_accidents((C.FIRST_YEAR, C.LAST_YEAR))
users = filtered_users((C.FIRST_YEAR, C.LAST_YEAR))
narrow = filtered_accidents((2022, 2024), ("Bretagne",))
users_narrow = filtered_users((2022, 2024), ("Bretagne",))
assert 0 < len(narrow) < len(acc) and narrow["year"].min() >= 2022
assert set(narrow["region"].astype(str)) == {"Bretagne"}
assert set(users_narrow["dep"].astype(str)) == {"22", "29", "35", "56"}
print(f"filters ok: {len(acc):,} accidents -> {len(narrow):,} (2022–2024, Bretagne)")

k = metrics.kpis(acc)
dep = metrics.by_departement(acc)
avoided = metrics.avoided_deaths_per_year(dep, k["lethality"], top_n=10, n_years=acc["year"].nunique())
assert avoided > 0
print(f"what-if ok: {avoided:.0f} deaths per year avoided for N = 10")

geojson = load_geojson()
checks, missing, summary = load_quality()
totals = missing.groupby(["table", "column"], as_index=False)[["n_missing", "n_rows"]].sum()
totals["pct_missing"] = 100 * totals["n_missing"] / totals["n_rows"]

figures = {
    "yearly_trend_indexed": viz.yearly_trend_indexed(metrics.count_table(acc, "year"), "Accidents and deaths"),
    "map_count": viz.dep_choropleth(dep, geojson, "accidents_per_year", "Accidents per year", "Accidents / year"),
    "map_lethality": viz.dep_choropleth(dep, geojson, "lethality", "Lethality", "Deaths / 100",
                                        scale=C.LETHALITY_SCALE, value_format=".1f", hide_unreliable=True),
    "top10_bar": viz.category_bar(dep.nlargest(10, "lethality"), "dep_name", "lethality", "Top 10",
                                  "Deaths per 100 accidents", k["lethality"], "Average"),
    "user_type_bar": viz.category_bar(metrics.users_by_type(users), "user_type", "killed_per_100",
                                      "Deaths per 100 users", "Deaths per 100 users involved", 2.0, "Average",
                                      count_column="involved", count_label="Users"),
}
for name, spec in C.INDICATORS.items():
    figures[f"heatmap {name}"] = viz.hour_weekday_heatmap(
        metrics.hour_weekday(acc, spec["column"]), name, spec["unit"], value_format=spec["format"])
figures["missingness_bar"] = viz.missingness_bar(totals[totals["n_missing"] > 0], "Missing values",
                                                 STRUCTURAL_MISSING)

for name, fig in figures.items():
    fig.to_json()  # full validation, as Streamlit does
    assert fig.layout.title.text, f"{name}: missing title"
    # Number of points: x values for line/bar/heatmap traces, locations for maps.
    n_points = sum(len(trace.x if getattr(trace, "x", None) is not None else trace.locations) for trace in fig.data)
    print(f"  ok  {name:<26} traces={len(fig.data):<3} points={n_points:<5}")
print(f"{len(figures)} charts built without error.")
