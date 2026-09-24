# Predicting Favorable Time per Panchangam

A [Claude Code](https://claude.com/claude-code) skill that finds favorable days and
time windows for a person, based on their birth **Nakshatram** (star), their
favorable **weekdays**, and a **city**, over any number of months ahead.

For each candidate day it scrapes that day's Panchangam from
[drikpanchang.com](https://www.drikpanchang.com) and reports the time windows where
all three of these hold at once:

1. the day is one of the person's favorable weekdays,
2. the running Nakshatram is favorable relative to the birth Nakshatram, and
3. the Tamil Yogam is Siddha or Amrutha (not Marana).

## Install

### As a Claude Code plugin (recommended)

In Claude Code:

```
/plugin marketplace add sreenaathkv/predicting-favorable-time-per-panchangam
/plugin install panchangam@panchangam-skills
```

To pick up new versions later, run `/plugin marketplace update panchangam-skills`.

### Manually

Copy the skill folder into your personal (or a project's) skills directory:

```bash
git clone https://github.com/sreenaathkv/predicting-favorable-time-per-panchangam.git
cp -r predicting-favorable-time-per-panchangam/plugins/panchangam/skills/predicting-favorable-time-per-panchangam \
      ~/.claude/skills/
```

**Requirements:** `python3` on your `PATH`. The skill creates its own virtualenv
under `~/.cache/predicting-favorable-time-per-panchangam/` the first time it runs, and
installs `requests`, `beautifulsoup4`, `lxml` and `geonamescache` into it.

## Usage

Ask Claude something like:

> Find favorable timings for Jai, nakshatram Uthiradam, favorable days Monday and
> Wednesday, living in Chennai, starting September 2026, 3 months ahead.

The skill asks for any missing input. It needs:

| Input | Example |
| --- | --- |
| Person name | `Jai` |
| Birth Nakshatram (one of the 27 Tamil names) | `Uthiradam` |
| Favorable weekdays | `Monday Wednesday` |
| City (add state/country if the name is ambiguous) | `Chennai` or `Springfield, IL` |
| Starting month and year | `September 2026` |
| Months to look ahead | `3` |

Results go to `{person}_output_dir/{person}/{city}/` in your current directory: one
`.txt` file per month, plus a consolidated JSON. Claude then shows the results as a
table for each month.

## Notes and limitations

- Timings come from drikpanchang.com and are shown in the city's local time.
- drikpanchang.com rate-limits heavy scraping and may show a CAPTCHA. The script waits
  between requests and caches every fetched day under
  `~/.cache/predicting-favorable-time-per-panchangam/panchang_cache/`, so repeat runs
  are fast. Very long forecast windows can still hit the limit. If that happens, wait
  a while and re-run.
- This is a calculation aid based on traditional rules. It is not astrological advice.

## Development

```bash
cd plugins/panchangam/skills/predicting-favorable-time-per-panchangam/scripts
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
python3 -m unittest test_panchangam_utils.py -v
```

See [`CLAUDE.md`](CLAUDE.md) and
[`scripts/CLAUDE.md`](plugins/panchangam/skills/predicting-favorable-time-per-panchangam/scripts/CLAUDE.md)
for the architecture, and `scripts/prompt.md` for the design history.
