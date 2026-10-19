"""Smoke test: build every chart from the processed data, outside Streamlit.

Usage (from the project root):
    python scripts/check_charts.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

import constants as C  # noqa: E402
from utils import metrics, viz  # noqa: E402
from utils.filters import apply_to_accidents, apply_to_users  # noqa: E402
from utils.quality import STRUCTURAL_MISSING  # noqa: E402


def count_points(trace) -> int:
    """Number of data points in a trace (x values, or map locations)."""
    for attribute in ("x", "locations"):
        values = getattr(trace, attribute, None)
        if values is not None:
            return len(values)
    return 0


def main() -> None:
    acc = pd.read_parquet(C.ACCIDENTS_FILE)
    users = pd.read_parquet(C.USERS_AGG_FILE)
    missing = pd.read_parquet(C.MISSINGNESS_FILE)
    with open(C.GEOJSON_FILE, encoding="utf-8") as handle:
        geojson = json.load(handle)

    # Filters: the full range keeps everything; a narrower one must shrink both tables.
    everything = apply_to_accidents(acc, (C.FIRST_YEAR, C.LAST_YEAR), ())
    narrow = apply_to_accidents(acc, (2022, 2024), ("Bretagne",))
    users_narrow = apply_to_users(users, (2022, 2024), ("Bretagne",))
    assert len(everything) == len(acc) and 0 < len(narrow) < len(acc)
    assert narrow["year"].min() >= 2022 and set(narrow["region"].astype(str)) == {"Bretagne"}
    assert set(users_narrow["dep"].astype(str)) == {"22", "29", "35", "56"}
    print(f"filters ok: {len(everything):,} accidents -> {len(narrow):,} (2022–2024, Bretagne)")

    k = metrics.kpis(acc)
    dep = metrics.by_departement(acc)
    avoided = metrics.avoided_deaths_per_year(dep, k["lethality"], top_n=10, n_years=k["n_years"])
    assert avoided > 0
    print(f"what-if ok: {avoided:.0f} deaths per year avoided for N = 10")

    totals = missing.groupby(["table", "column"], as_index=False)[["n_missing", "n_rows"]].sum()
    totals["pct_missing"] = 100 * totals["n_missing"] / totals["n_rows"]

    figures = {
        "yearly_trend_indexed": viz.yearly_trend_indexed(metrics.yearly(acc), "Accidents and deaths"),
        "map_count": viz.dep_choropleth(dep, geojson, "accidents_per_year", "Accidents per year",
                                        "Accidents / year"),
        "map_lethality": viz.dep_choropleth(dep, geojson, "lethality", "Lethality", "Deaths / 100",
                                            scale=C.LETHALITY_SCALE, value_format=".1f", hide_unreliable=True),
        "top10_bar": viz.category_bar(dep.nlargest(10, "lethality"), "dep_name", "lethality", "Top 10",
                                      "Deaths per 100 accidents", None, horizontal=True),
        "user_type_bar": viz.category_bar(metrics.users_by(users, "user_type"), "user_type", "killed_per_100",
                                          "Deaths per 100 users", "Deaths per 100 users involved", None,
                                          horizontal=True, count_column="involved", count_label="Users"),
    }
    for name, spec in C.INDICATORS.items():
        figures[f"heatmap {name}"] = viz.hour_weekday_heatmap(
            metrics.hour_weekday(acc, spec["column"]), name, spec["unit"], value_format=spec["format"])
    figures["missingness_bar"] = viz.missingness_bar(totals[totals["n_missing"] > 0], "Missing values",
                                                     structural=STRUCTURAL_MISSING)

    for name, fig in figures.items():
        start = time.perf_counter()
        fig.to_json()  # forces full validation/serialisation, as Streamlit does
        assert fig.layout.title.text, f"{name}: missing title"
        n_points = sum(count_points(trace) for trace in fig.data)
        print(f"  ok  {name:<26} traces={len(fig.data):<3} points={n_points:<5} "
              f"{1000 * (time.perf_counter() - start):5.0f} ms")
    print(f"{len(figures)} charts built without error.")


if __name__ == "__main__":
    main()
