# Short report — Road danger in France, 2019–2024

## 1. Question and audience

Injury accidents are counted everywhere, but counts alone do not say where an accident is
most likely to kill. The app asks **where, when and to whom injury accidents are most
often fatal** in France between 2019 and 2024, for local road-safety decision makers
(préfectures, départements, municipalities) and informed citizens.

Sub-questions: (1) is the trend improving, and what happened in 2020; (2) do the
départements with the most accidents also have the deadliest ones; (3) which road users
are most exposed; (4) at what times are accidents most frequent and most lethal.

## 2. Data

- **BAAC files** (ONISR, Ministère de l'Intérieur, data.gouv.fr, Licence Ouverte / Open
  Licence): one record per injury accident attended by the police or gendarmerie, in four
  tables per year (characteristics, places, vehicles, road users). Years 2019–2024
  (the schema changed in 2019): 327,628 accidents.
- **Département boundaries** (*Contours administratifs*, data.gouv.fr, ODbL) as a map layer.

Details and attribution: `DATA_SOURCES.md`.

## 3. Methods

- **Download** through the data.gouv.fr API, cached locally; resource names that differ
  between years are matched with a regular expression.
- **Cleaning:** every file read as text then typed; `-1` and empty cells = missing; decimal
  comma in coordinates; the id column renamed in 2022; non-breaking spaces removed from ids;
  implausible ages and speed limits set to unknown; coordinates checked against the bounding
  box of their area. From 2023 an accident can have several place rows; the first is kept.
- **Features:** date and time fields, counts of killed / hospitalised / slightly injured
  people per accident, built-up area, grouped light and weather conditions, speed-limit band,
  region; per road user, age band and user type — stored only as aggregated counts.
- **Metric:** lethality = deaths (within 30 days) per 100 injury accidents. Units with fewer
  than 100 accidents (or users) are greyed out or hidden.
- **Analysis:** yearly trend indexed to 2019; départements compared by quarter of accident
  volume and with a Spearman rank correlation; deaths per 100 users involved by user type;
  hour × weekday grid; a what-if scenario (deaths avoided if the N most lethal départements
  had the national lethality).
- **Quality checks:** duplicates, orphan keys between tables, coordinates, dates, times,
  codes, birth years, speed limits, severities, missing values per column.

## 4. Findings

Figures for the full selection (2019–2024, all of France), as computed by the app. They are
recomputed when the filters change.

1. **Trend.** From 2019 to 2024, injury accidents fell by 7.5% but deaths only by 1.9%
   (3,498 → 3,432), so lethality rose from 5.9 to 6.3 deaths per 100 accidents. 2020 stands
   out: −18.9% accidents and −20.5% deaths compared with 2019, in the year of the COVID-19
   lockdowns.
2. **Where.** The départements with the most accidents are *not* the deadliest. In the quarter
   of départements with the fewest accidents, lethality is 12.6, against 3.8 in the busiest
   quarter (3.3 times as lethal); the rank correlation between accident volume and lethality
   is −0.75. Paris has the most accidents and one of the lowest lethality rates (0.8);
   rural départements such as Jura, Haute-Saône, Landes or Yonne exceed 16. Accidents outside
   built-up areas are about 3.6 times as lethal as those inside (11.2 vs 3.1).
3. **Who.** Pedestrians are the most exposed: 5.1 of every 100 involved in an injury
   accident died, 2.3 times the rate of car occupants (2.2). Pedestrians, cyclists,
   e-scooter, moped and motorcycle riders account for 46% of the deaths.
4. **When.** Accidents peak at 17h on weekdays (commuting hours), but the most lethal hour is
   05h, with 13.1 deaths per 100 accidents.
5. **What-if.** If the 10 most lethal départements (with at least 100 accidents) had the
   national lethality, about 154 deaths per year would be avoided — an order of magnitude,
   not a forecast.

## 5. Implications

- Monitor deaths and lethality, not only accident counts.
- Rank territories by lethality as well as by volume: they point to different places,
  mostly rural ones.
- Give road users outside a car (crossings, lighting, separated space) attention in
  proportion to their share of the deaths.

## 6. Data quality

17 of 26 checks pass and 6 flag less than 1% of rows. Three flag more: extra place rows
(8.9% of place rows, from 2023 — handled by keeping the first), missing speed limit (3.2%,
higher from 2023) and missing birth year (1.5%, from 2021, when people who fled the scene
were added). No duplicate ids, no orphan keys, and all dates, times and département codes
are valid.

## 7. Limitations

- Police-recorded injury accidents only; slight injuries are under-reported.
- "Hospitalised" is no longer certified by the official statistics since 2019.
- No exposure data (traffic, kilometres, population): lethality is the severity of
  accidents, not a risk per inhabitant or per kilometre.
- Place, road type, speed limit and user type are linked with each other; the findings are
  associations, not causes.
- Cleaning choices (missing codes, first place row, value bounds) can shift small numbers.

## 8. Ethics

Only aggregated counts and rates are shown; no row about a person is displayed, and
road-user data is stored only as counts. Sources and licences are credited in the app, the
README and `DATA_SOURCES.md`. Every number in the app is computed at runtime, and the
uncertainty of small units is shown (grey bars, hidden rates) rather than hidden.

## 9. Next steps

Add exposure data (traffic counts, population) to move from severity to risk; use the
coordinates to locate black spots; fit a multivariable model to separate the roles of place,
road type, speed and light; update yearly with the new BAAC file.
