# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository status

This git repo (https://github.com/sreenaathkv/predicting-favorable-time-per-panchangam)
is a **Claude Code plugin marketplace**: `.claude-plugin/marketplace.json`
lists one plugin, `panchangam` (`plugins/panchangam/`, manifest in
`plugins/panchangam/.claude-plugin/plugin.json`), which ships a single
Skill, `predicting-favorable-time-per-panchangam`, under
`plugins/panchangam/skills/`. Keep the skill directory name, the SKILL.md
`name:` field and the plugin/marketplace manifests in sync, and bump
`version` in `plugin.json` when shipping changes so installed copies
update. Personal results (`*_output_dir/`), `panchang_cache/`, `.venv/` and
`__pycache__/` are gitignored — never commit them. The
implementation is done and complete:
`plugins/panchangam/skills/predicting-favorable-time-per-panchangam/scripts/panchangam_utils.py`
(1000+ lines) satisfies the 1800+-line test suite in
`scripts/test_panchangam_utils.py` (195 tests, all passing), the
`scripts/tests_fixtures/` HTML fixtures it loads exist, and
`scripts/requirements.txt` pins dependencies. `scripts/prompt.md` is a
running log of every prompt that drove the implementation and its bug
fixes — read it before touching parsing/merge or collation logic, since it
records *why* several non-obvious design decisions exist (see also the
detailed `plugins/panchangam/skills/predicting-favorable-time-per-panchangam/scripts/CLAUDE.md`, which
documents the module's internals in depth and should be your primary
reference once inside `scripts/`).

The JSON collation SKILL.md step 3b calls for is no longer a manual/ad hoc
step: `fetch_favorable_month_days` calls `collate_and_save_predictions`
automatically right after writing the per-month `.txt` files, producing
`{output_dir}/{slugified person}/{slugified city}/{slugified person}_{slugified
starting_month_year}_{forward_looking_months}.json` on every run (CLI or
direct import) — see `TestCollateAndSavePredictions` and
`TestFetchFavorableMonthDaysCollation` in the test suite.

`plugins/panchangam/skills/predicting-favorable-time-per-panchangam/evals/evals.json` holds
skill-creator-format eval prompts for this skill (see "Evaluating this
skill" below).

`viewer/` is a separate, build-free static page (React UMD + htm, one
`index.html`) that renders the consolidated JSON in the browser; it's published
to GitHub Pages by `.github/workflows/pages.yml` and is intentionally *not*
inside `plugins/` so it isn't shipped with the skill. It parses the
`prediction` strings built by `_build_favorable_entry` ("Entire day" / "until
T" / "from T onwards" / "from T to T", joined by "; ", optional "(favorable
until …)" suffix) — keep `parsePrediction()`/`validate()` there in sync with
any change to that format or to `collate_and_save_predictions`' JSON shape.

## What the skill does

Given a person's birth Nakshatram (star), their favorable weekdays, and a
location, it scrapes drikpanchang.com's daily Panchangam pages and computes
which future dates/time-windows are astrologically favorable, over N forward
months. See `plugins/panchangam/skills/predicting-favorable-time-per-panchangam/SKILL.md` for the full
input contract and the 3-step workflow (sanitize inputs → run
`fetch_favorable_month_days()`, which writes both the per-month `.txt`
files and the consolidated JSON itself → present the JSON as a table).

## Commands

All commands below are run from
`plugins/panchangam/skills/predicting-favorable-time-per-panchangam/scripts/`.

Set up the environment:
```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

Run the full test suite:
```bash
python3 -m unittest test_panchangam_utils.py -v
```

Run a single test class or test:
```bash
python3 -m unittest test_panchangam_utils.TestFavorableNakshatrams -v
python3 -m unittest test_panchangam_utils.TestFavorableNakshatrams.test_sample_input_uthiradam -v
```

Invoke the CLI directly (positional args: weekday(s), birth nakshatram,
city, "Month Year", person name):
```bash
python3 panchangam_utils.py Monday Wednesday Uthiradam Chennai "September 2026" Jai --forward-looking-months 6
```

There is no build step or linter; tests use stdlib `unittest` (no `pytest`).
`.venv/` and `panchang_cache/` are local working state, not source.

`TestFetchFavorableMonthDaysLiveSmoke` tests make genuine live requests to
drikpanchang.com and self-skip on network errors or a CAPTCHA/rate-limit
page — don't treat a skip there as a failure.

## Architecture

`panchangam_utils.py` has two layers:

1. **Nakshatra model** — `NAKSHATRAS` (the 27 Hindu lunar mansions, each
   with Tamil/Sanskrit/English names), `resolve_nakshatra_index`,
   `next_27_nakshatras`, and `favorable_nakshatrams`/
   `favorable_nakshatram_indices`, which derive the 15 favorable / 12
   not-favorable nakshatras from a fixed 1-indexed position pattern
   relative to the birth nakshatram (positions
   {2,4,6,8,9,11,13,15,17,18,20,22,24,26,27} are favorable; the birth
   nakshatram itself, position 1, never is).

2. **`fetch_favorable_month_days`: favorable-day lookup via
   drikpanchang.com** — resolves a city to a geoname-id offline
   (`resolve_geoname_id`, via `geonamescache`, disambiguating same-name
   cities across states/countries instead of guessing), then for each
   requested weekday across the forward-looking window fetches (or reads
   from an on-disk `panchang_cache/`) that day's drikpanchang HTML and
   determines favorability.

   **Tamil Yogam is computed, not scraped**: `TAMIL_YOGAM_CHART` (the Pambu
   / Vakya Panchangam weekday x nakshatram chart) decides Siddha/Amrutha/Marana,
   and each favorable weekday is a *Vedic* day (sunrise to next sunrise); the
   sites only supply nakshatram timings and sunrise (see `scripts/CLAUDE.md`,
   last section, and `references/domain_knowledge.md`).

   **The core subtlety of this whole skill**: a day's favorability requires
   intersecting three independently-timed signals — the day-of-week match,
   the Nakshatram segment(s) (a day can have multiple segments, each with
   its own cutoff, sometimes crossing into the next calendar day), and the
   Tamil Yogam segment(s) (Siddha/Amrutha = favorable, Marana = not; up to 3
   segments, with cutoffs **entirely independent** of the nakshatram
   segment cutoffs). The favorable output is the union of sub-windows where
   *both* signals are favorable at once — never the day treated as one
   all-day value from whichever signal happens to have only one HTML
   paragraph. Several regression tests exist specifically because this was
   gotten wrong before (see `scripts/CLAUDE.md` for the full history and
   `scripts/prompt.md` Prompts 4–6 for the original bug reports).

   Results are always written to
   `{output_dir}/{slugified person}/{slugified city}/{Month}_{Year}.txt` (one file per
   forward-looking month; `output_dir` defaults to `{person}_output_dir`,
   relative to CWD), and then immediately collated by
   `collate_and_save_predictions` into one consolidated
   `{...}_{starting_month_year}_{forward_looking_months}.json` in that same
   per-person, per-city subfolder — the JSON `fetch_favorable_month_days` and the CLI
   both hand back to the caller/print at the end. `person` is a mandatory,
   keyword-only parameter (and everything after `forward_looking_months` in
   the signature is keyword-only) — this was a deliberate fix for a real
   bug where positional `person`/`output_dir` arguments silently bound to
   `use_cache`/`cache_dir` instead.

## Evaluating this skill

`plugins/panchangam/skills/predicting-favorable-time-per-panchangam/evals/evals.json` holds
skill-creator-style eval prompts (`{skill_name, evals: [{id, prompt,
expected_output, assertions, files}]}`) for running this skill's
quantitative/qualitative eval loop via the `skill-creator` Skill — spawn
with-skill (and baseline) subagent runs per eval, grade the assertions, and
use `skill-creator`'s `eval-viewer/generate_review.py` +
`scripts.aggregate_benchmark` to review results before iterating on
`SKILL.md`. Prefer eval prompts that exercise the CLI end-to-end against a
`panchang_cache/` you've pre-warmed (i.e. `use_cache=True`, the default —
don't pass `--no-cache`), or the offline fixture-driven unit tests for
parsing/collation-only checks, rather than uncached live runs against
several forward-looking months, since
drikpanchang.com rate-limits/CAPTCHAs aggressive scraping (see
`scripts/CLAUDE.md`) — `panchang_cache/` is local working state, not
something checked in, so don't assume it's warm for a given city/month
without checking first.

For exhaustive detail on every function, parsing edge case, and the bugs
each design decision fixes, read
`plugins/panchangam/skills/predicting-favorable-time-per-panchangam/scripts/CLAUDE.md` — it is kept
up to date and is more authoritative than a summary here for anything
below the module's two top-level layers.
