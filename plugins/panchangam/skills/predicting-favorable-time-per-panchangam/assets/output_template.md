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

# Group (couple) template

Use this for `panchangam_utils.py group` results (`{A}_{B}_{starting_month_year}_{N}.json`). Add one local-time column per person, in the same order as `participants`, and repeat the per-month section for every month. When a month has no `common_windows`, produce a single "NIL" row.

```markdown
# Common Favorable Times for {group}

| Person | Birth Nakshatram | City (time zone) | Favorable weekdays |
| --- | --- | --- | --- |
| Jai | Uthiradam | Sunnyvale, CA (America/Los_Angeles) | Mon, Wed, Fri, Sat |
| Sai | Poosam | Chennai, India (Asia/Kolkata) | Tue, Wed, Thu, Sat |

**Common favorable nakshatrams:** {common_favorable_nakshatrams}
**Forecast window:** {forward_looking_months} months from {starting_month_year}

---
## October 2026: 2 common windows

| # | Jai (Sunnyvale) | Sai (Chennai) | Together for |
| --- | --- | --- | --- |
| 1 | Wed, Oct 21, 07:17 AM – 11:00 AM | Wed, Oct 21, 07:47 PM – 11:30 PM | 3h 43m |
| 2 | Sat, Oct 24, 08:02 AM – 12:00 PM | Sat, Oct 24, 08:32 PM – Oct 25, 12:30 AM | 3h 58m |

## November 2026: 0 common windows

| # | Jai (Sunnyvale) | Sai (Chennai) | Together for |
| --- | --- | --- | --- |
| NIL | NIL | NIL | NIL |
```
(The rows above are illustrative placeholders; always use the values from the JSON.)

