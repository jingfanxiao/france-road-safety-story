# Where, when and who: the hidden geography of road danger in France (2019–2024)

A Streamlit data-storytelling app built on the French road-accident files (BAAC, ONISR,
data.gouv.fr). It follows one question from problem to implications: **where, when and to
whom are injury accidents most often deadly?**

- **Live app:** _to be added after deployment_ (Streamlit Community Cloud)
- **Repository:** _to be added_
- **Dataset:** https://www.data.gouv.fr/datasets/bases-de-donnees-annuelles-des-accidents-corporels-de-la-circulation-routiere-annees-de-2005-a-2024

---

## The story

**Hook.** Every week, French roads still take dozens of lives. Accident counts alone do not
tell where the danger is greatest: a place can have few accidents and still be among the
deadliest.

**Audience.** Local road-safety decision makers (préfectures, départements, municipalities)
and informed citizens.

**Key metric — lethality.** Deaths per 100 injury accidents. It can be computed from the
BAAC files alone (no population or traffic data needed). It is always shown next to the
number of accidents, and units with fewer than 100 accidents in the selection are greyed
out or hidden because their rate is too noisy.

**Questions.**
1. *Trend* — Are French roads getting safer between 2019 and 2024? What happened in 2020?
2. *Where* — Do the départements with the most accidents also have the deadliest ones?
3. *Who* — Which road users (pedestrians, cyclists, e-scooter, moped and motorcycle riders)
   are most exposed?
4. *When* — At what hours and on which days are accidents most frequent, and most lethal?

Every headline sentence and number in the app is computed from the data at runtime and
follows the sidebar filters, so the story stays correct for any selection.

## Pages

| Page | What it shows |
|---|---|
| **Story & Overview** | Hook and context, KPI row tied to the filters (accidents, deaths, hospitalised, lethality, change vs previous year, sparklines), yearly trend of accidents and deaths indexed to the first year = 100, with 2020 shaded |
| **Where** | Choropleth of départements (switch between accidents per year and lethality), top 10 départements by lethality, and a *what-if* slider: deaths avoided per year if the N most lethal départements had the national lethality |
| **Who** | Deaths per 100 road users involved, by type of road user; hour × day-of-week heatmap coloured by the indicator chosen in the sidebar |
| **Data Quality & Conclusions** | Validation checks (duplicates, orphan keys, coordinates, values), missing values per column, three conclusions with implications, limitations and next steps |

**Sidebar (shared by all pages):** year range, region, indicator, *Reset filters* button and
a summary of the active selection.

## How to run

Requires **Python 3.11**. The processed data is included in `data/processed/`, so the app
runs without downloading anything.

**With `make`** (macOS / Linux, or Windows with GNU make):

```bash
make setup   # create .venv and install the pinned requirements
make run     # open the app at http://localhost:8501
```

**Without `make` — Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run app.py
```

**Without `make` — macOS / Linux:**

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

**Rebuild the data from the source** (about 180 MB of raw files, downloaded once and cached
in `data/raw/`):

```bash
make data
# or: python scripts/build_data.py --download --prepare --quality
```

`--download` skips files that already exist (add `--force` to download again), `--prepare`
writes the cleaned files to `data/processed/`, `--quality` writes the data quality report.

**Smoke test** (builds every chart outside Streamlit): `make check` or
`python scripts/check_charts.py`.

## Project structure

```
.
├─ app.py                  entry point: page setup, sidebar, navigation
├─ constants.py            paths, URLs, years, thresholds, code → label mappings, colours, seed
├─ sections/               one file per page, each with a render() function
│  ├─ story.py             Story & Overview
│  ├─ where.py             Where (map, top 10, what-if)
│  ├─ who.py               Who (road-user types, hour × weekday heatmap)
│  └─ quality_conclusions.py
├─ utils/
│  ├─ io.py                find and download the source files (cached)
│  ├─ prep.py              cleaning, joins, feature engineering, processed outputs
│  ├─ quality.py           data quality checks and report
│  ├─ filters.py           cached loaders, sidebar, filter application
│  ├─ metrics.py           KPIs, lethality, aggregations, what-if calculation
│  ├─ viz.py               one Plotly chart per function, shared style
│  └─ ui.py                formatting and page helpers (headline box, chart + alt text)
├─ scripts/
│  ├─ build_data.py        --download / --prepare / --quality
│  └─ check_charts.py      smoke test for all charts
├─ data/
│  ├─ raw/                 downloaded source files (not committed)
│  └─ processed/           small cleaned files used by the app (committed)
├─ docs/                   storyboard, video script, report
├─ .streamlit/config.toml  theme
├─ requirements.txt        pinned versions
├─ Makefile
├─ DATA_SOURCES.md         sources, licences, attribution
└─ README.md
```

## Methods

- **Scope.** Years 2019–2024 only: the BAAC schema changed in 2019, so earlier years are not
  comparable. All départements are included (metropolitan France, Corsica and overseas).
- **Reading.** All files are read as text, then typed: `;` separator, UTF-8 with a Latin-1
  fallback, decimal comma in coordinates. The accident id is called `Accident_Id` in the
  2022 characteristics file and is renamed to `Num_Acc`. Non-breaking spaces inside ids are
  removed so the tables join correctly.
- **Missing values.** The code `-1` and empty cells are treated as missing. Ages outside
  0–110 and speed limits outside 5–130 km/h are set to unknown. Coordinates outside the
  bounding box of their area are set to missing and flagged.
- **Joins.** Characteristics, places, vehicles and users are joined on `Num_Acc` (and
  `id_vehicule` for users ↔ vehicles). From 2023 an accident can have several place rows;
  the first one is kept and the number of rows is stored.
- **Features.** Per accident: date, hour, weekday, number of people killed / hospitalised /
  slightly injured, worst severity, built-up area, grouped light and weather conditions,
  speed-limit band, region, flags for pedestrians, cyclists, e-scooters and motorcycles.
  Per road user (aggregated only): age band and user type (pedestrian, or the group of the
  user's vehicle).
- **Lethality.** Deaths (within 30 days) per 100 injury accidents. Rates based on fewer than
  100 accidents (or 100 road users) are marked as unreliable.
- **Where vs. size.** Départements are compared by quarter of accident volume, and with a
  Spearman rank correlation between accidents per year and lethality.
- **What-if.** For each of the N most lethal départements (reliable ones only):
  `avoided = deaths − accidents × national lethality / 100` (0 if already below the national
  rate), summed and divided by the number of years. The national rate is France as a whole
  for the selected years. It is simple arithmetic to give a sense of scale, **not a
  prediction**.
- **Performance.** Raw data is cleaned once into small parquet files; the app reads them
  with `st.cache_data` and caches the filtered tables by year range and region.
- **Accessibility.** Colour-blind-safe palette (Okabe-Ito), every chart has a title,
  labelled axes with units, hover details and a one-sentence text description under it.

## Data quality

`scripts/build_data.py --quality` checks the raw files for: rows per year; duplicate
accident, vehicle and user ids and duplicate rows; orphan keys between the four tables
(accidents without places, vehicles or users, vehicles without users and the reverse);
extra place rows; missing or out-of-bounds coordinates; invalid dates, times and
département codes; missing or invalid birth years and speed limits; missing severities; and
missing values per column. The results are shown on the *Data Quality & Conclusions* page and saved
to `data/processed/quality_report.json`.

## Limitations and ethics

- Only **police-recorded injury accidents**: accidents without police attendance are
  missing and slight injuries are under-reported.
- **Deaths** (within 30 days) are the most reliable outcome; "hospitalised" is no longer
  certified by the official statistics since 2019. From 2021, people who fled the scene are
  recorded with little information.
- **No exposure data** (traffic, kilometres driven, population): lethality measures how
  severe accidents are, not the risk per inhabitant or per kilometre.
- **No causal claims.** The app shows associations; place, road type, speed limit and type
  of road user are linked with each other.
- **Privacy.** The app only shows aggregated counts and rates, never a row about a person.
- **Cleaning choices** (missing codes, first place row from 2023, value bounds) are listed
  above and on the quality page.

## Data and licences

- Road accidents (BAAC): ONISR / Ministère de l'Intérieur, data.gouv.fr — **Licence Ouverte /
  Open Licence**.
- Département boundaries: *Contours administratifs*, data.gouv.fr (from IGN Admin Express) —
  **ODbL**. Used as a map layer only.

Full details, attribution and the changes made to each source are in
[DATA_SOURCES.md](DATA_SOURCES.md).
