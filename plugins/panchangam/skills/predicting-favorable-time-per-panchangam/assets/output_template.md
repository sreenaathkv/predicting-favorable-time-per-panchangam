# Markdown Template for good day/time predictor

Use this template when generating collated prediction output across months in Markdown format.
The input value for the placeholder marked with {} is same as the input passed to the scripts/panchangam_utils.py script. So use that arguments passed on to the script, to fill in for values in the below markdown template. The consolidated JSON to read from lives at `{output_dir}/{person}/{city}/{person}_{starting_month_year}_{forward_looking_months}.json` (`output_dir` defaults to `{person}_output_dir`; `{city}` is the city name as passed to the script, sanitized, e.g. `Springfield_IL` for "Springfield, IL"). The below markdown has an example where it lists the day/times for three months (September 2026, October 2026 and November, 2026). Repeat similar (per-month section template) for as many forward looking forecast months as needed. When a month does not have any favorable day/time, produce a single row with "NIL" as the cell value. See November, 2026 as example reference for that.

```markdown
# Favorable Days & Times for {person}

| | |
| --- | --- |
| **Birth Nakshatram** | {input_nakshatram} |
| **City** | {input_city_name} |
| **Favorable weekdays** | {fav_days_of_week} |
| **Forecast window** | {forward_looking_months} months from {starting_month_year} |

---
## September 2026 — 9 favorable days

| Date | Day | Favorable window | Notes |
| --- | --- | --- | --- |
| September 4, 2026 | Friday | until 11:04 PM | |
| September 7, 2026 | Monday | from 06:14 PM onwards | |
| September 9, 2026 | Wednesday | from 03:14 PM onwards | |

## October 2026 — 13 favorable days

| Date | Day | Favorable window | Notes |
| --- | --- | --- | --- |
| October 7, 2026 | Wednesday | Entire day | |
| October 14, 2026 | Wednesday | Entire day | continues until Oct 15, 04:03 AM |

## November 2026 — 0 favorable days

| Date | Day | Favorable window | Notes |
| --- | --- | --- | --- |
| NIL | NIL | NIL | NIL |

```
## Formatting Guidelines
-- Use `---` horizontal rules to separate major sections
- Include blank lines between sections for readability



