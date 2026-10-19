# Data sources

The app uses one dataset (the BAAC road-accident files) plus one reference map layer
(département boundaries). Nothing else is used.

Raw files are **not** committed: `scripts/build_data.py --download` fetches them into
`data/raw/` and skips files that are already there. The small processed files in
`data/processed/` are committed so the app starts without downloading anything.

---

## 1. Road accidents — BAAC files

| | |
|---|---|
| Title | *Bases de données annuelles des accidents corporels de la circulation routière — Années de 2005 à 2024* |
| Producer | ONISR (Observatoire national interministériel de la sécurité routière) |
| Publisher on data.gouv.fr | Ministère de l'Intérieur |
| Page | https://www.data.gouv.fr/datasets/bases-de-donnees-annuelles-des-accidents-corporels-de-la-circulation-routiere-annees-de-2005-a-2024 |
| Dataset id | `53698f4ca3a729239d2036df` |
| API used to find the download URLs | https://www.data.gouv.fr/api/1/datasets/53698f4ca3a729239d2036df/ |
| Last update of the dataset (from the API, checked 2026-10-19) | 2025-12-29 |
| Licence | **Licence Ouverte / Open Licence** (data.gouv.fr licence id `fr-lo`) — https://www.etalab.gouv.fr/wp-content/uploads/2014/05/Licence_Ouverte.pdf |

**Files used.** Years 2019–2024, four tables per year (24 CSV files), plus the official
variable description:

| Table | File in `data/raw/` | Content |
|---|---|---|
| Characteristics | `caract-YYYY.csv` | date, time, light, weather, built-up area, département, coordinates |
| Places | `lieux-YYYY.csv` | road category, speed limit, surface… |
| Vehicles | `vehicules-YYYY.csv` | vehicle category, obstacles, manoeuvre… |
| Road users | `usagers-YYYY.csv` | user category, injury severity, birth year… |
| Codebook | `description-des-bases-de-donnees-annuelles.pdf` | meaning of every code |

The resource names on data.gouv.fr are not consistent across years (for example
`caracteristiques-2019`, `carcteristiques-2022`, `Caract_2024`), so `utils/io.py` matches
them with a regular expression and saves them under the uniform names above.

**Why 2019–2024 only.** The BAAC schema changed in 2019 (new variables and codes), so
earlier years cannot be compared directly with later ones.

**Collection method.** Each record comes from the accident report (BAAC form) filled in by
the police or gendarmerie unit that attended an injury accident on a public road. It is a
census of recorded injury accidents, not a sample. Accidents without police attendance,
and accidents with material damage only, are not included.

**Licence terms (summary of the Licence Ouverte / Open Licence).** The data may be freely
reused — copied, published, transmitted, adapted, modified, extracted, transformed and
used commercially — provided the source and the date of its last update are credited.
Attribution used in this project:

> Source: Ministère de l'Intérieur — ONISR, *Bases de données annuelles des accidents
> corporels de la circulation routière*, data.gouv.fr, last updated 2025-12-29.

---

## 2. Département boundaries (map layer only)

| | |
|---|---|
| Title | *Contours administratifs* |
| Publisher | data.gouv.fr |
| Page | https://www.data.gouv.fr/datasets/contours-administratifs |
| File | `departements-1000m.geojson`, 2024 vintage, generalised at 1000 m |
| Download URL | https://object.data.gouv.fr/contours-administratifs/2024/geojson/departements-1000m.geojson |
| Built from | IGN Admin Express (according to the dataset page) |
| Licence | **ODbL — Open Data Commons Open Database License** (data.gouv.fr licence id `odc-odbl`) — https://opendatacommons.org/licenses/odbl/ |

**How it is used.** Only to draw the choropleth map. All counts and rates come from the
BAAC files; the map joins on the département code (`dep`), which both sources share.

**Changes made** (`utils/prep.build_metro_geojson`): the overseas départements are dropped
(only metropolitan France and Corsica are drawn) and coordinates are rounded to 4 decimals
to keep the file small. Overseas départements are still counted in all KPIs, rankings and
tables; the map page says so.

**Licence obligations.** ODbL requires attribution and that a redistributed adapted
database stays under the ODbL. The file `data/processed/departements.geojson` is such an
adapted database and is therefore shared under the ODbL, with this attribution:

> Contains département boundaries from *Contours administratifs*, data.gouv.fr (from IGN
> Admin Express), ODbL.

---

## 3. Processed files (`data/processed/`, committed)

Built by `python scripts/build_data.py --prepare --quality` from the raw files above.

| File | Content |
|---|---|
| `accidents.parquet` | one row per accident with cleaned and derived columns (no person-level data) |
| `users_agg.parquet` | counts of road users by year × département × area × user type × age band × severity |
| `departements.geojson` | simplified boundaries, metropolitan France and Corsica |
| `quality_report.parquet` / `.json` | results of the data quality checks |
| `missingness.parquet` | missing values per table, column and year |

No row-level information about people is stored or shown: road users only appear as
aggregated counts.
