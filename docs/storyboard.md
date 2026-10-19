# Storyboard

**Title:** Where, when and who: the hidden geography of road danger in France (2019–2024)
**Audience:** local road-safety decision makers and informed citizens.
**Arc:** problem → analysis → insights → implications.

Headlines are computed by the app from the current selection. The values quoted below are
those shown for the default selection (2019–2024, all of France).

---

## Page 1 — Story & Overview (problem and context)

| | |
|---|---|
| Role in the story | **Hook + context**: why it matters, what is measured, is it getting better? |
| Hook | "Across France, from 2019 to 2024, the police recorded 327,628 injury road accidents in which 19,877 people died — about 63 deaths every week." |
| Context (expander) | audience, definition of lethality, data source and licence, how the filters work, associations not causes |
| Headline | "Between 2019 and 2024, injury accidents fell by 7.5% and deaths fell by 1.9% (3,498 → 3,432); lethality went from 5.9 to 6.3 deaths per 100 accidents." |
| KPIs (follow filters) | injury accidents · people killed · hospitalised · lethality, each with change vs previous year and a sparkline |
| Visual | yearly accidents and deaths indexed to the first year = 100, 2020 lockdowns shaded |
| Transition | Fewer accidents did not bring fewer deaths in proportion → *where* are accidents most deadly? |

## Page 2 — Where (analysis: geography)

| | |
|---|---|
| Question | Do the départements with the most accidents have the deadliest ones? |
| Headline | "No — it is the opposite: in the quarter of départements with the fewest accidents, an accident is 3.3 times as lethal as in the quarter with the most accidents (12.6 vs 3.8 deaths per 100 accidents; rank correlation −0.75 over 104 départements)." |
| Visual 1 | choropleth with a toggle *Accidents per year / Lethality*: the dark areas swap from the big cities to rural départements |
| Visual 2 | top 10 départements by lethality, average as a reference line, grey = fewer than 100 accidents |
| What-if (expander) | slider N (1–20) → deaths avoided per year if the N most lethal départements had the national lethality (154 per year for N = 10); illustrative, not a prediction |
| Transition | Where an accident happens matters; so does *who* is involved. |

## Page 3 — Who (analysis: people and time)

| | |
|---|---|
| Question | Which road users pay the highest price, and when do accidents happen? |
| Headline 1 | "Pedestrians are the most exposed: 5.1 of every 100 involved in an injury accident died, 2.3 times the rate of car occupants (2.2). Pedestrians, cyclists, e-scooter, moped and motorcycle riders together account for 46% of the deaths." |
| Visual 1 | deaths per 100 users involved, by type of road user, all-users average as a reference line |
| Headline 2 | "Accidents are most frequent at 17h (28,103 accidents, lethality 5.0), but the most lethal hour is 05h, with 13.1 deaths per 100 accidents." |
| Visual 2 | hour × day-of-week heatmap; the sidebar *Indicator* switches it between accidents, deaths and lethality |
| Transition | Before drawing conclusions: can we trust the data? |

## Page 4 — Data Quality & Conclusions (insights and implications)

| | |
|---|---|
| Headline | "17 of 26 checks pass, 6 flag less than 1% of rows and 3 flag more: extra place rows (8.9%), missing speed limit (3.2%), missing birth year (1.5%)." |
| Visuals | checks table (duplicates, orphan keys, coordinates, values); missing values per column |
| Conclusions | the three headlines above, each with an implication: look at deaths and lethality, not only counts; rank territories by lethality as well as by volume; give road users outside a car specific attention |
| Limitations | police-recorded injury accidents only, under-reporting of slight injuries, "hospitalised" not certified since 2019, no exposure data, no causality, cleaning choices, privacy, licences |
| Next steps | add exposure data, local black spots from coordinates, a multivariable model, yearly update |

---

## Sidebar (all pages)

Year range · Region · Indicator · Reset filters · summary of the active selection.
Changing a filter updates every KPI, headline and chart, so the story can be retold for one
region (for example Bretagne) or one year.
