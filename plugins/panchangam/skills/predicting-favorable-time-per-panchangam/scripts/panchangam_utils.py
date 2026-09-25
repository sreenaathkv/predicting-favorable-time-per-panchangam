"""Utilities for working with the 27 Hindu Nakshatras (lunar mansions)."""

import argparse
import calendar
import functools
import json
import re
import sys
import time
import warnings
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import geonamescache
import requests
from bs4 import BeautifulSoup

# The 27 nakshatras in their canonical order, starting from Ashwini.
# "Sanskrit" holds the Devanagiri name, "English" the romanized name,
# and "Tamil" the Tamil name, per https://www.drikpanchang.com/tutorials/nakshatra/nakshatra.html
NAKSHATRAS = [
    {"Tamil": "Aswini", "Sanskrit": "अश्विनी", "English": "Ashwini"},
    {"Tamil": "Bharani", "Sanskrit": "भरणी", "English": "Bharani"},
    {"Tamil": "Karthigai", "Sanskrit": "कृत्तिका", "English": "Krittika"},
    {"Tamil": "Rohini", "Sanskrit": "रोहिणी", "English": "Rohini"},
    {"Tamil": "Mrigasheersham", "Sanskrit": "मृगशिरा", "English": "Mrigashira"},
    {"Tamil": "Thiruvaathirai", "Sanskrit": "आर्द्रा", "English": "Ardra"},
    {"Tamil": "Punarpoosam", "Sanskrit": "पुनर्वसु", "English": "Punarvasu"},
    {"Tamil": "Poosam", "Sanskrit": "पुष्य", "English": "Pushya"},
    {"Tamil": "Aayilyam", "Sanskrit": "आश्लेषा", "English": "Ashlesha"},
    {"Tamil": "Makam", "Sanskrit": "मघा", "English": "Magha"},
    {"Tamil": "Pooram", "Sanskrit": "पूर्वाफाल्गुनी", "English": "Purva Phalguni"},
    {"Tamil": "Uthiram", "Sanskrit": "उत्तराफाल्गुनी", "English": "Uttara Phalguni"},
    {"Tamil": "Hastham", "Sanskrit": "हस्त", "English": "Hasta"},
    {"Tamil": "Chithirai", "Sanskrit": "चित्रा", "English": "Chitra"},
    {"Tamil": "Swaathi", "Sanskrit": "स्वाती", "English": "Swati"},
    {"Tamil": "Visaakam", "Sanskrit": "विशाखा", "English": "Vishakha"},
    {"Tamil": "Anusham", "Sanskrit": "अनुराधा", "English": "Anuradha"},
    {"Tamil": "Kettai", "Sanskrit": "ज्येष्ठा", "English": "Jyeshtha"},
    {"Tamil": "Moolam", "Sanskrit": "मूल", "English": "Mula"},
    {"Tamil": "Pooraadam", "Sanskrit": "पूर्वाषाढा", "English": "Purva Ashadha"},
    {"Tamil": "Uthiradam", "Sanskrit": "उत्तराषाढा", "English": "Uttara Ashadha"},
    {"Tamil": "Thiruvonam", "Sanskrit": "श्रवण", "English": "Shravana"},
    {"Tamil": "Avittam", "Sanskrit": "धनिष्ठा", "English": "Dhanishta"},
    {"Tamil": "Sadayam", "Sanskrit": "शतभिषा", "English": "Shatabhisha"},
    {"Tamil": "Poorattathi", "Sanskrit": "पूर्वाभाद्रपदा", "English": "Purva Bhadrapada"},
    {"Tamil": "Uthirattathi", "Sanskrit": "उत्तराभाद्रपदा", "English": "Uttara Bhadrapada"},
    {"Tamil": "Ravathi", "Sanskrit": "रेवती", "English": "Revati"},
]

NUM_NAKSHATRAS = len(NAKSHATRAS)

# Common alternate spellings that should resolve to a canonical name above.
_ALIASES = {
    "uthiraadam": "uthiradam",
}


def _build_lookup():
    lookup = {}
    for index, nakshatra in enumerate(NAKSHATRAS):
        for value in nakshatra.values():
            lookup[value.strip().lower()] = index
    return lookup


_LOOKUP = _build_lookup()


def resolve_nakshatra_index(nakshatra):
    """Resolve a Tamil/Sanskrit/English nakshatra name to its 0-based index in NAKSHATRAS."""
    if not isinstance(nakshatra, str) or not nakshatra.strip():
        raise ValueError("nakshatra must be a non-empty string")

    key = nakshatra.strip().lower()
    key = _ALIASES.get(key, key)

    if key not in _LOOKUP:
        raise ValueError(f"Unknown nakshatra: {nakshatra!r}")

    return _LOOKUP[key]


def next_27_nakshatras(nakshatra):
    """Return all 27 nakshatras ordered starting from `nakshatra`.

    `nakshatra` may be given as its Tamil, Sanskrit, or English name
    (case-insensitive) and is treated as the 0th (current) nakshatra.
    The remaining nakshatras wrap around using modulo arithmetic.
    """
    start_index = resolve_nakshatra_index(nakshatra)
    return [
        NAKSHATRAS[(start_index + offset) % NUM_NAKSHATRAS]
        for offset in range(NUM_NAKSHATRAS)
    ]


# 1-based positions (relative to the argument nakshatra as position 1) that
# are considered favorable. This is the classical 9-tara (Tarabala) cycle
# repeated three times across all 27 nakshatras; positions not listed here
# (including the argument nakshatra itself, position 1) are not_favorable.
_FAVORABLE_POSITIONS = {2, 4, 6, 8, 9, 11, 13, 15, 17, 18, 20, 22, 24, 26, 27}


def favorable_nakshatrams(nakshatram):
    """Split the 27 nakshatras (starting at `nakshatram`) into favorable/not.

    Returns {"favorable": [...], "not_favorable": [...]}, where each list
    holds Tamil nakshatra names in nakshatra order, per the fixed set of
    favorable positions relative to `nakshatram` (treated as position 1).
    """
    ordered = next_27_nakshatras(nakshatram)

    favorable = []
    not_favorable = []
    for position, entry in enumerate(ordered, start=1):
        if position in _FAVORABLE_POSITIONS:
            favorable.append(entry["Tamil"])
        else:
            not_favorable.append(entry["Tamil"])

    return {"favorable": favorable, "not_favorable": not_favorable}


def favorable_nakshatram_indices(nakshatram):
    """Return the 0-based NAKSHATRAS indices considered favorable relative to `nakshatram`."""
    start_index = resolve_nakshatra_index(nakshatram)
    return {
        (start_index + offset) % NUM_NAKSHATRAS
        for offset in range(NUM_NAKSHATRAS)
        if (offset + 1) in _FAVORABLE_POSITIONS
    }


# ---------------------------------------------------------------------------
# fetch_favorable_month_days: forward-looking favorable-day lookup via
# drikpanchang.com panchangam data for a given city and nakshatram.
# ---------------------------------------------------------------------------

_GEONAMES_CACHE = geonamescache.GeonamesCache()


class AmbiguousCityError(ValueError):
    """Raised when a city name matches more than one distinct place and can't be auto-resolved.

    `candidates` holds the raw geonamescache city dicts, most populous first,
    so calling code can present them to a user or otherwise pick one.
    """

    def __init__(self, city_name, candidates):
        self.city_name = city_name
        self.candidates = candidates
        lines = [f"City name {city_name!r} matches multiple places:"]
        lines += [f"  {i}. {_describe_city_candidate(c)}" for i, c in enumerate(candidates, 1)]
        lines.append(
            'Specify which one by including its state/country, e.g. '
            f'"{city_name.split(",")[0].strip()}, {candidates[0]["admin1code"]}" '
            f'or "{city_name.split(",")[0].strip()}, {candidates[0]["countrycode"]}".'
        )
        super().__init__("\n".join(lines))


def _describe_city_candidate(candidate):
    return (
        f"{candidate['name']}, {candidate['admin1code']}, {candidate['countrycode']} "
        f"(population {candidate['population']:,})"
    )


@functools.lru_cache(maxsize=1)
def _us_state_name_to_code():
    return {info["name"].lower(): code for code, info in _GEONAMES_CACHE.get_us_states().items()}


@functools.lru_cache(maxsize=1)
def _country_name_to_code():
    codes = {}
    for iso, info in _GEONAMES_CACHE.get_countries().items():
        codes[info["name"].lower()] = iso
        codes[info["iso3"].lower()] = iso
    return codes


def _qualifier_token_matches(candidate, token):
    token = token.strip().lower()
    if not token:
        return True
    if candidate["admin1code"].lower() == token:
        return True
    if candidate["countrycode"].lower() == token:
        return True
    if _us_state_name_to_code().get(token) == candidate["admin1code"]:
        return True
    if _country_name_to_code().get(token) == candidate["countrycode"]:
        return True
    return False


def _dedupe_by_geonameid(candidates):
    seen = {}
    for candidate in candidates:
        seen[candidate["geonameid"]] = candidate
    return list(seen.values())


def _stdin_is_interactive():
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except Exception:
        return False


def _prompt_for_city_choice(city_name, candidates):
    print(f"City name {city_name!r} matches multiple places:")
    for i, candidate in enumerate(candidates, 1):
        print(f"  {i}. {_describe_city_candidate(candidate)}")
    while True:
        choice = input(f"Which one did you mean? [1-{len(candidates)}]: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(candidates):
            return candidates[int(choice) - 1]
        print(f"Please enter a number from 1 to {len(candidates)}.")


def resolve_geoname_id(city_name, chooser=None, interactive=True):
    """Resolve a city name to its GeoNames.org geonameid, offline, via geonamescache.

    Tries an exact name match first, then a substring name match, then the
    same against alternate names, so spellings like "Chennai" or "Madras"
    both resolve.

    When a name matches more than one distinct place (e.g. "Springfield"
    exists in 8+ US states), this does NOT silently guess by population.
    Instead:
      - `city_name` may include a ", state" and/or ", country" qualifier
        (state/country given by name or code, e.g. "Springfield, IL" or
        "Springfield, Illinois, USA") to disambiguate up front.
      - If still ambiguous and `chooser` is given, it's called with the list
        of candidate city dicts and must return the chosen one -- for
        programmatic/scripted disambiguation (and for tests, without
        needing a real terminal).
      - Otherwise, if `interactive` (default) and stdin is a real terminal,
        the candidates are printed and the user is prompted to pick one.
      - Otherwise, raises AmbiguousCityError with the full candidate list.

    Note: geonamescache only bundles cities above a population threshold, so
    very small towns sharing a name with a larger city elsewhere may not
    appear as a candidate at all.
    """
    if not isinstance(city_name, str) or not city_name.strip():
        raise ValueError("city_name must be a non-empty string")

    parts = [part.strip() for part in city_name.split(",")]
    name_query, qualifier_tokens = parts[0], parts[1:]
    if not name_query:
        raise ValueError("city_name must be a non-empty string")

    candidates = None
    for attribute, contains_search in (
        ("name", False),
        ("name", True),
        ("alternatenames", False),
        ("alternatenames", True),
    ):
        matches = _GEONAMES_CACHE.search_cities(
            name_query, attribute=attribute, case_sensitive=False, contains_search=contains_search
        )
        if matches:
            candidates = _dedupe_by_geonameid(matches)
            break

    if not candidates:
        raise ValueError(f"Could not resolve a geoname id for city: {city_name!r}")

    if qualifier_tokens:
        qualified = [
            c for c in candidates if all(_qualifier_token_matches(c, token) for token in qualifier_tokens)
        ]
        if qualified:
            candidates = qualified
        elif len(candidates) == 1:
            # The qualifier didn't match, but there was only ever one
            # candidate for the base name -- most likely the place the
            # qualifier names isn't in geonamescache's offline dataset at
            # all (e.g. a small town below its population threshold), not
            # that the caller made a typo. Don't silently substitute a
            # different place without saying so.
            warnings.warn(
                f"No match for \"{', '.join(qualifier_tokens)}\" on city {name_query!r}; "
                f"using the only available match: {_describe_city_candidate(candidates[0])}. "
                "This can happen when the intended place isn't in geonamescache's offline "
                "dataset (e.g. a small town below its population threshold).",
                stacklevel=2,
            )
        # else: the qualifier matched none of several candidates -- leave
        # `candidates` as the full original list so it's still reported as
        # ambiguous below, rather than silently discarding the qualifier.

    candidates.sort(key=lambda c: c.get("population", 0), reverse=True)
    if len(candidates) == 1:
        return candidates[0]["geonameid"]

    if chooser is not None:
        return chooser(candidates)["geonameid"]
    if interactive and _stdin_is_interactive():
        return _prompt_for_city_choice(city_name, candidates)["geonameid"]
    raise AmbiguousCityError(city_name, candidates)


_MONTH_YEAR_FORMATS = ("%B %Y", "%b %Y", "%m/%Y", "%Y-%m", "%m-%Y")


def _parse_month_year(month_year_str):
    if not isinstance(month_year_str, str) or not month_year_str.strip():
        raise ValueError("starting_month_year must be a non-empty string")
    text = month_year_str.strip()
    for fmt in _MONTH_YEAR_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.year, parsed.month
        except ValueError:
            continue
    raise ValueError(
        f"Could not parse starting_month_year: {month_year_str!r}. "
        "Expected a format like 'September 2026', 'Sep 2026', '09/2026', or '2026-09'."
    )


_WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _normalize_weekday_name(weekday_name):
    if not isinstance(weekday_name, str) or not weekday_name.strip():
        raise ValueError("Each entry in fav_days_of_week must be a non-empty string")
    normalized = weekday_name.strip().capitalize()
    if normalized not in _WEEKDAY_NAMES:
        raise ValueError(f"Unknown weekday: {weekday_name!r}. Expected one of {_WEEKDAY_NAMES}")
    return normalized


def _dates_in_month_for_weekdays(year, month, weekday_names):
    weekday_indices = {_WEEKDAY_NAMES.index(name) for name in weekday_names}
    _, days_in_month = calendar.monthrange(year, month)
    return [
        date(year, month, day)
        for day in range(1, days_in_month + 1)
        if date(year, month, day).weekday() in weekday_indices
    ]


def _forward_looking_months(start_year, start_month, count):
    months = []
    for offset in range(count):
        total = (start_month - 1) + offset
        months.append((start_year + total // 12, total % 12 + 1))
    return months


_DRIKPANCHANG_URL = "https://www.drikpanchang.com/tamil/tamil-month-panchangam.html"
_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}
_DEFAULT_REQUEST_DELAY_SECONDS = 2.0
_DEFAULT_CACHE_DIR = Path(__file__).resolve().parent / "panchang_cache"


class DrikPanchangBlockedError(RuntimeError):
    """Raised when drikpanchang.com serves a reCAPTCHA/rate-limit page instead of panchang data."""


def _is_blocked_response(html):
    return "g-recaptcha" in html or "Recaptcha challenge" in html


def _cache_path(geoname_id, day_date, cache_dir):
    base = Path(cache_dir) if cache_dir else _DEFAULT_CACHE_DIR
    return base / f"{geoname_id}_{day_date.strftime('%Y%m%d')}.html"


def _fetch_day_panchang_html(
    geoname_id,
    day_date,
    use_cache=True,
    cache_dir=None,
    request_delay_seconds=_DEFAULT_REQUEST_DELAY_SECONDS,
    session=None,
):
    """Fetch (or read from disk cache) the drikpanchang page HTML for one day.

    Panchangam data for a published date never changes, so the cache has no
    TTL. `session` accepts any object with a `.get(...)` method compatible
    with `requests`, letting tests inject a fake transport. A reCAPTCHA/
    rate-limit response is deliberately never written to the cache, so a
    later retry (after backing off) can succeed instead of replaying the block.
    """
    path = _cache_path(geoname_id, day_date, cache_dir)
    if use_cache and path.exists():
        return path.read_text(encoding="utf-8")

    getter = session.get if session is not None else requests.get
    response = getter(
        _DRIKPANCHANG_URL,
        params={"geoname-id": geoname_id, "date": day_date.strftime("%d/%m/%Y")},
        headers=_REQUEST_HEADERS,
        timeout=20,
    )
    response.raise_for_status()
    html = response.text

    if _is_blocked_response(html):
        raise DrikPanchangBlockedError(
            f"drikpanchang.com served a reCAPTCHA/rate-limit page instead of panchang data for "
            f"{day_date}. Fetching too many dates too quickly triggers this; increase "
            "request_delay_seconds, fetch fewer months at a time, or wait before retrying."
        )

    if use_cache:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
    if request_delay_seconds:
        time.sleep(request_delay_seconds)
    return html


def _find_elements_by_key(wrapper, key_text):
    matches = []
    for element in wrapper.select("p.dpElement"):
        key_span = element.select_one(".dpElementKey")
        if key_span and key_span.get_text(strip=True) == key_text:
            matches.append(element)
    return matches


_TIME_RE = re.compile(r"(\d{1,2}):(\d{2})\s*(AM|PM)", re.IGNORECASE)
_NEXT_INDEX_RE = re.compile(r"\((\d{1,2})\)\s*$")
_MONTH_ABBR_TO_NUM = {calendar.month_abbr[m]: m for m in range(1, 13)}


def _extract_cutoff_time(value_span):
    match = _TIME_RE.search(value_span.get_text(" ", strip=True))
    if not match:
        return None
    hour, minute, meridiem = match.groups()
    return f"{int(hour):02d}:{minute} {meridiem.upper()}"


def _crosses_into_next_calendar_day(value_span, query_date):
    """True if the value's trailing date marker (e.g. "Sep 20") differs from query_date.

    drikpanchang appends this marker when a nakshatra/yogam's "upto" cutoff
    falls after midnight; that means, for the *queried* calendar day, the
    primary value is in effect the entire day (see class docstring on
    fetch_favorable_month_days for why this matters).
    """
    inline = value_span.select_one(".dpInlineBlock")
    if inline is None:
        return False
    parts = inline.get_text(strip=True).split()
    if len(parts) != 2 or parts[0] not in _MONTH_ABBR_TO_NUM:
        return False
    month_num = _MONTH_ABBR_TO_NUM[parts[0]]
    try:
        day_num = int(parts[1])
    except ValueError:
        return False
    return (month_num, day_num) != (query_date.month, query_date.day)


def _extract_next_index(anchor_tag):
    """From <a title="next Pooradam (20)">Moolam</a>, return 20 (1-based), or None."""
    if anchor_tag is None:
        return None
    match = _NEXT_INDEX_RE.search(anchor_tag.get("title", ""))
    return int(match.group(1)) if match else None


def _parse_nakshathram_segments(elements, query_date):
    """Turn the "Nakshathram" <p class="dpElement"> entries into same-day (index, cutoff) segments.

    Unlike Tamil Yogam, drikpanchang almost never renders a second <p> for
    the nakshatra that follows a same-day "upto" cutoff -- the *only* place
    that next nakshatra's name is available is the current entry's own
    `title="next X (N)"` attribute. So whenever the last (or only) element
    has a genuine same-day cutoff, we must derive the following segment from
    that same title (current = N-1, next = N, both 1-based) rather than
    treating the cutoff as if the day were open-ended. A second explicit
    "Nakshathram" <p> only shows up when there are two same-day transitions
    (three nakshatras touch the calendar day); when present, it is itself
    subject to the same rule for whatever (rarer still) comes after it.

    Returns (segments, next_day_continuation): the latter is the cutoff time
    (on the following calendar day) that the day's *last* segment is actually
    known to hold until, when that's known (i.e. the last element's own
    "upto" crossed into tomorrow) -- e.g. "12:19 AM" for a nakshatra shown as
    "upto 12:19 AM, Oct 18" when querying Oct 17. None when no such fact is
    available (either no cutoff was given at all, or the last segment was
    derived rather than read from an explicit crossing).
    """
    segments = []
    for index, element in enumerate(elements):
        value_span = element.select_one(".dpElementValue")
        next_index_1based = _extract_next_index(value_span.find("a"))
        if next_index_1based is None:
            raise ValueError(f"Could not determine next-nakshatra index for {query_date}")
        # drikpanchang's "next Nakshatra (N)" title gives the *next* nakshatra's
        # 1-based standard index; the current one is always N-1, since nakshatras
        # always progress consecutively. This sidesteps the fact that
        # drikpanchang's own transliterations (e.g. "Mirugasirisham", "Magam",
        # "Sathayam") differ from our canonical Tamil spellings in NAKSHATRAS.
        current_index = (next_index_1based - 2) % NUM_NAKSHATRAS
        cutoff = _extract_cutoff_time(value_span)

        if cutoff is not None and _crosses_into_next_calendar_day(value_span, query_date):
            segments.append((current_index, None))
            return segments, cutoff
        if cutoff is None:
            segments.append((current_index, None))
            return segments, None

        segments.append((current_index, cutoff))
        if index == len(elements) - 1:
            next_index_0based = (next_index_1based - 1) % NUM_NAKSHATRAS
            segments.append((next_index_0based, None))
    return segments, None


def _parse_tamil_yoga_segments(elements, query_date):
    """Turn the "Tamil Yoga" <p class="dpElement"> entries into same-day (name, cutoff) segments.

    Unlike Nakshathram, drikpanchang always renders an explicit, open-ended
    (no "upto" clause) trailing <p> for whatever Tamil Yogam applies after
    the last same-day cutoff, so no derivation is needed here -- just read
    each element in document order. Real data has shown up to 3 same-day
    Tamil Yogam segments in one day.

    BUT: same as Nakshathram, a segment's own "upto" cutoff can fall after
    midnight (marked by a trailing date, e.g. "upto 12:19 AM, Oct 18" when
    queried for Oct 17) -- when that happens, this Tamil Yogam value is in
    effect for the *entire* queried day, and any further <p> elements
    describe tomorrow, not the rest of today, and must be ignored.

    Returns (segments, next_day_continuation) -- see _parse_nakshathram_segments.
    """
    segments = []
    for element in elements:
        value_span = element.select_one(".dpElementValue")
        text = value_span.get_text(" ", strip=True)
        name = re.split(r"\bupto\b", text, flags=re.IGNORECASE)[0].strip()
        cutoff = _extract_cutoff_time(value_span)
        if cutoff is not None and _crosses_into_next_calendar_day(value_span, query_date):
            segments.append((name, None))
            return segments, cutoff
        if cutoff is None:
            segments.append((name, None))
            return segments, None
        segments.append((name, cutoff))
    return segments, None


def _parse_day_panchang(html, query_date):
    """Parse one drikpanchang day page into nakshatram/Tamil-Yogam segments for the day.

    Nakshatram and Tamil Yogam are parsed independently and may have
    different (or no) same-day cutoff times, and a different number of
    same-day transitions: real drikpanchang data shows cases where a
    nakshatra spans the entire calendar day while its Tamil Yogam still
    changes partway through, and vice versa. So, contrary to what one might
    expect from casual inspection of a handful of days, a present
    secondary_tam_yogam does NOT guarantee a present secondary_nakshatram
    (see _favorable_windows, which reconciles the two independently).
    """
    if _is_blocked_response(html):
        raise DrikPanchangBlockedError(
            f"drikpanchang.com served a reCAPTCHA/rate-limit page instead of panchang data for {query_date}."
        )

    soup = BeautifulSoup(html, "lxml")
    wrapper = soup.select_one(".dpDayPanchangWrapper")
    if wrapper is None:
        raise ValueError(f"Could not find panchang wrapper in page for {query_date}")

    nak_elements = _find_elements_by_key(wrapper, "Nakshathram")
    if not nak_elements:
        raise ValueError(f"Could not find 'Nakshathram' panchang element for {query_date}")
    yogam_elements = _find_elements_by_key(wrapper, "Tamil Yoga")
    if not yogam_elements:
        raise ValueError(f"Could not find 'Tamil Yoga' panchang element for {query_date}")

    nak_segments, nak_next_day_continuation = _parse_nakshathram_segments(nak_elements, query_date)
    yogam_segments, yogam_next_day_continuation = _parse_tamil_yoga_segments(yogam_elements, query_date)

    sunrise_minutes = _parse_drik_sunrise_minutes(wrapper, query_date)
    nakshatram_timeline = _finalize_timeline(_parse_drik_nakshatram_timeline(nak_elements, query_date), sunrise_minutes)

    return {
        "date": query_date,
        "_sunrise_minutes": sunrise_minutes,
        "_nakshatram_timeline": nakshatram_timeline,
        "primary_nakshatram_for_the_day": NAKSHATRAS[nak_segments[0][0]]["Tamil"],
        "secondary_nakshatram_of_the_day": (
            NAKSHATRAS[nak_segments[1][0]]["Tamil"] if len(nak_segments) > 1 else None
        ),
        "primary_tam_yogam_for_the_day": yogam_segments[0][0],
        "secondary_tam_yogam_of_the_day": yogam_segments[1][0] if len(yogam_segments) > 1 else None,
        "_nakshatram_segments": nak_segments,
        "_tam_yogam_segments": yogam_segments,
        "_nakshatram_next_day_continuation": nak_next_day_continuation,
        "_tam_yogam_next_day_continuation": yogam_next_day_continuation,
    }


_FAVORABLE_TAMIL_YOGAMS = {"siddha", "amrutha"}
_MINUTES_PER_DAY = 24 * 60


def _is_favorable_yogam(yogam_name):
    return yogam_name is not None and yogam_name.strip().lower() in _FAVORABLE_TAMIL_YOGAMS


def _format_day_label(query_date):
    return f"{calendar.month_name[query_date.month]} {query_date.day}, {query_date.year}"


def _cutoff_to_minutes(cutoff_str):
    hour_str, rest = cutoff_str.split(":")
    minute_str, meridiem = rest.split()
    hour = int(hour_str) % 12
    if meridiem.upper() == "PM":
        hour += 12
    return hour * 60 + int(minute_str)


def _minutes_to_cutoff(minutes):
    hour24, minute = divmod(minutes, 60)
    meridiem = "AM" if hour24 < 12 else "PM"
    hour12 = hour24 % 12 or 12
    return f"{hour12:02d}:{minute:02d} {meridiem}"


def _value_at(segments, minute):
    for value, cutoff in segments:
        if cutoff is None or minute < _cutoff_to_minutes(cutoff):
            return value
    return segments[-1][0]


# ---------------------------------------------------------------------------
# Tamil Yogam: computed from the traditional weekday x nakshatram chart.
# ---------------------------------------------------------------------------

# The Amirtha / Siddha / Marana yogam chart printed on the first page of the
# Vakya (Pambu) Panchangam, transcribed from
# https://www.mahastro.com/how-to-use-vakya-panchangam-or-pambu-panchangam/
# ("Yogam - Column 1"; அ = Amirtha, சி = Siddha, ம = Marana). One row per
# weekday, one letter per nakshatram in NAKSHATRAS order (Aswini .. Ravathi):
# S = Siddha, A = Amrutha (Amirtha), M = Marana. The article's worked example
# (Thursday: Pooram -> Siddha, Uthiram -> Marana, Hastham -> Siddha) and
# "Thiruvonam on Sunday is Amirtha" both hold, and mypanchang.com's published
# Tamil Yoga matches this chart on 176 of 182 days checked (see
# TestTamilYogamChart); drikpanchang.com and prokerala.com publish values from
# different tables, so their Tamil Yogam is kept only as a reference.
TAMIL_YOGAM_CHART = {
    "Sunday":    "SSSSSSSSSMSAASSMMMASAAMSSAA",
    "Monday":    "SSMAASASSMSSSSAMSSSSMASSMSS",
    "Tuesday":   "SSSASMSSSSSASSSMSSASSSSMMAS",
    "Wednesday": "MSASSSSSSSAAMSSSSSMAASMSAMS",
    "Thursday":  "ASMMMMAASASMSSASSSSSSSSMSSS",
    "Friday":    "ASSMSSSMMMSSASSSSMASSMSSSSA",
    "Saturday":  "SSAASSSSMAMMMMASSSSSSSSAMSM",
}
_TAMIL_YOGAM_CODES = {"S": "Siddha", "A": "Amrutha", "M": "Marana"}
TAMIL_YOGAM_METHOD = "Pambu (Vakya) Panchangam weekday x nakshatram chart"
DAY_MODEL = "Vedic day: sunrise to the next sunrise"


def tamil_yogam_for(weekday, nakshatram):
    """Tamil Yogam ("Siddha" / "Amrutha" / "Marana") for a Vedic weekday and nakshatram.

    `weekday` is a weekday name (any case) or a Python weekday number
    (Monday=0); `nakshatram` is any name resolve_nakshatra_index accepts, or a
    0-based index into NAKSHATRAS. The weekday must be the *Vedic* weekday,
    which runs sunrise to sunrise (so 3 AM on a Thursday is still Wednesday).
    """
    if isinstance(weekday, int):
        weekday_name = _WEEKDAY_NAMES[weekday]
    else:
        weekday_name = _normalize_weekday_name(weekday)
    index = nakshatram if isinstance(nakshatram, int) else resolve_nakshatra_index(nakshatram)
    return _TAMIL_YOGAM_CODES[TAMIL_YOGAM_CHART[weekday_name][index]]


def _vedic_day_bounds(day_result):
    """(sunrise, next sunrise) of the Vedic day starting on day_result's date, in minutes past its local midnight."""
    sunrise = day_result["_sunrise_minutes"]
    next_sunrise = day_result.get("_next_sunrise_minutes", sunrise)
    return sunrise, _MINUTES_PER_DAY + next_sunrise


def _favorable_windows(day_result, favorable_indices):
    """Favorable (start, end) windows of the Vedic day that starts at sunrise on day_result's date.

    Minutes are counted from that date's local midnight, so the day spans
    [sunrise, 1440 + next sunrise) and a window can run past midnight (> 1440)
    up to the next sunrise. A stretch is favorable when its nakshatram is in
    `favorable_indices` AND the Tamil Yogam for (this Vedic weekday, that
    nakshatram) -- from TAMIL_YOGAM_CHART, not the site's published value --
    is Siddha or Amrutha. The Tamil Yogam can only change when the nakshatram
    does (or at sunrise, when the weekday does), so walking the nakshatram
    timeline is enough. Adjacent favorable stretches are merged.
    """
    day_start, day_end = _vedic_day_bounds(day_result)
    weekday = day_result["date"].weekday()
    windows = []
    start = day_start
    for index, end in day_result["_nakshatram_timeline"]:
        segment_end = day_end if end is None else min(end, day_end)
        if segment_end <= start:
            continue
        if index in favorable_indices and _is_favorable_yogam(tamil_yogam_for(weekday, index)):
            if windows and windows[-1][1] == start:
                windows[-1] = (windows[-1][0], segment_end)
            else:
                windows.append((start, segment_end))
        start = segment_end
        if start >= day_end:
            break
    return windows


def _format_minute_of_day(day_date, minutes):
    """Minutes past `day_date`'s midnight -> "07:23 AM", or "September 17, 2026 07:23 AM" once past midnight."""
    if minutes < _MINUTES_PER_DAY:
        return _minutes_to_cutoff(minutes)
    return f"{_format_day_label(day_date + timedelta(days=1))} {_minutes_to_cutoff(minutes - _MINUTES_PER_DAY)}"


def _build_favorable_entry(day_result, favorable_indices):
    """Describe a Vedic day's favorable windows as one display string, or None if there are none.

    The day runs from sunrise to the next sunrise, so:
      "Entire day"                         sunrise -> next sunrise
      "Entire day (favorable until D T)"   sunrise -> T on the next date D (after midnight)
      "until T"                            sunrise -> T the same date
      "from T onwards"                     T -> next sunrise
      "from T onwards (favorable until D T2)"  T -> T2 on the next date D
      "from T to T2"                       both on the same date
    Several windows are joined by "; ".
    """
    windows = _favorable_windows(day_result, favorable_indices)
    if not windows:
        return None
    day_date = day_result["date"]
    day_start, day_end = _vedic_day_bounds(day_result)

    parts = []
    for start, end in windows:
        ends_next_date = end > _MINUTES_PER_DAY and end < day_end
        continuation = f" (favorable until {_format_minute_of_day(day_date, end)})" if ends_next_date else ""
        if start == day_start and end == day_end:
            parts.append("Entire day")
        elif start == day_start:
            parts.append(f"Entire day{continuation}" if ends_next_date else f"until {_minutes_to_cutoff(end)}")
        elif end == day_end:
            parts.append(f"from {_format_minute_of_day(day_date, start)} onwards")
        elif start < _MINUTES_PER_DAY and ends_next_date:
            parts.append(f"from {_minutes_to_cutoff(start)} onwards{continuation}")
        else:
            parts.append(f"from {_format_minute_of_day(day_date, start)} to {_format_minute_of_day(day_date, end)}")
    return f"{_format_day_label(day_date)} - " + "; ".join(parts)


def _finalize_timeline(raw, sunrise_minutes):
    """Normalize a raw [(nakshatram index, end minute or None)] list for the Vedic day starting at sunrise.

    Drops entries that ended at/before sunrise, stops at the first open-ended
    entry, and -- when every listed nakshatram has a known end -- appends the
    one that follows (nakshatrams always progress consecutively), open-ended.
    """
    timeline = []
    for index, end in raw:
        if end is not None and end <= sunrise_minutes:
            continue
        timeline.append((index, end))
        if end is None:
            return timeline
    if not timeline:
        raise ValueError("empty nakshatram timeline")
    timeline.append(((timeline[-1][0] + 1) % NUM_NAKSHATRAS, None))
    return timeline


def _parse_drik_nakshatram_timeline(elements, query_date):
    """Every "Nakshathram" <p> as (index, end minute past query_date's midnight), for the Vedic day.

    drikpanchang lists each nakshatram that ends within the Vedic day (sunrise
    to next sunrise) with its "upto" time -- a trailing date marker means the
    next calendar day (+1440) -- and leaves the one still running at the next
    sunrise implicit (derived from the last entry's "next X (N)" title).
    """
    raw = []
    for element in elements:
        value_span = element.select_one(".dpElementValue")
        next_index_1based = _extract_next_index(value_span.find("a"))
        if next_index_1based is None:
            raise ValueError(f"Could not determine next-nakshatra index for {query_date}")
        index = (next_index_1based - 2) % NUM_NAKSHATRAS
        cutoff = _extract_cutoff_time(value_span)
        if cutoff is None:
            raw.append((index, None))
            break
        end = _cutoff_to_minutes(cutoff)
        if _crosses_into_next_calendar_day(value_span, query_date):
            end += _MINUTES_PER_DAY
        raw.append((index, end))
    return raw


def _parse_drik_sunrise_minutes(wrapper, query_date):
    for element in _find_elements_by_key(wrapper, "Sunrise"):
        cutoff = _extract_cutoff_time(element.select_one(".dpElementValue"))
        if cutoff is not None:
            return _cutoff_to_minutes(cutoff)
    raise ValueError(f"Could not find sunrise time for {query_date}")


# ---------------------------------------------------------------------------
# prokerala.com: alternate source for the same per-day Nakshatram/Tamil Yogam
# data, parsed into the exact day_result shape _parse_day_panchang returns.
# ---------------------------------------------------------------------------

_PROKERALA_URL_TEMPLATE = "https://www.prokerala.com/astrology/tamil-panchangam/{year}-{month}-{day:02d}.html"

# prokerala links each nakshatram to /astrology/nakshatra/{slug}-nakshatra.htm;
# the slug set is fixed and, unlike the displayed Tamil spellings (e.g.
# "Sadhayam", "Tiruvonam", "Mrigashirsham"), independent of transliteration.
# Listed in the canonical NAKSHATRAS order.
_PROKERALA_NAKSHATRA_SLUGS = [
    "ashwini", "bharani", "krittika", "rohini", "mrigashirsha", "ardra", "punarvasu",
    "pushya", "ashlesha", "magha", "purva-phalguni", "uttara-phalguni", "hasta", "chitra",
    "swati", "vishaka", "anuradha", "jyeshta", "moola", "purva-ashada", "uttara-ashada",
    "shravana", "dhanishta", "satabhisha", "purva-bhadrapada", "uttara-bhadrapada", "revati",
]
_PROKERALA_SLUG_TO_INDEX = {slug: index for index, slug in enumerate(_PROKERALA_NAKSHATRA_SLUGS)}
_PROKERALA_SLUG_RE = re.compile(r"/nakshatra/([a-z-]+)-nakshatra\.htm")
_PROKERALA_RANGE_RE = re.compile(
    r"([A-Z][a-z]{2})\s+(\d{1,2})\s+(\d{1,2}:\d{2}\s*[AP]M)\s*[–-]\s*([A-Z][a-z]{2})\s+(\d{1,2})\s+(\d{1,2}:\d{2}\s*[AP]M)",
    re.IGNORECASE,
)


class PanchangSourceBlockedError(DrikPanchangBlockedError):
    """A panchang source served a block/CAPTCHA/error page instead of data.

    Subclasses DrikPanchangBlockedError so existing `except DrikPanchangBlockedError`
    handlers (including the CLI's) keep catching every "source unavailable" case.
    """


def _is_prokerala_blocked_response(html):
    """True for a CAPTCHA/challenge page: no panchang data block, but a challenge marker."""
    lowered = html.lower()
    if "panchang-data-nakshatra" in lowered:
        return False
    return any(marker in lowered for marker in ("captcha", "cf-challenge", "challenge-platform", "access denied"))


def _prokerala_url(day_date):
    return _PROKERALA_URL_TEMPLATE.format(
        year=day_date.year, month=calendar.month_name[day_date.month].lower(), day=day_date.day
    )


def _prokerala_datetime(month_abbr, day_str, time_str, query_date):
    """Build a naive local datetime from prokerala's year-less "Sep 23 10:05 PM", picking the year nearest query_date."""
    month = _MONTH_ABBR_TO_NUM[month_abbr.title()]
    minutes = _cutoff_to_minutes(_normalize_clock(time_str))
    candidates = []
    for year in (query_date.year - 1, query_date.year, query_date.year + 1):
        try:
            candidates.append(datetime(year, month, int(day_str)) + timedelta(minutes=minutes))
        except ValueError:
            continue
    anchor = datetime.combine(query_date, datetime.min.time())
    return min(candidates, key=lambda dt: abs(dt - anchor))


def _normalize_clock(time_str):
    """ "7:01 AM" / "07:01 am" -> "07:01 AM" (the form the drikpanchang parser produces)."""
    match = _TIME_RE.search(time_str)
    if not match:
        raise ValueError(f"Not a clock time: {time_str!r}")
    hour, minute, meridiem = match.groups()
    return f"{int(hour):02d}:{minute} {meridiem.upper()}"


def _prokerala_sunrise_minutes(soup, query_date):
    for label in soup.find_all(string=lambda text: text and text.strip() == "Sunrise"):
        value = label.parent.find_next_sibling("span")
        if value is not None and _TIME_RE.search(value.get_text()):
            return _cutoff_to_minutes(_normalize_clock(value.get_text()))
    raise ValueError(f"Could not find sunrise time in prokerala page for {query_date}")


def _normalize_tamil_yogam_name(text):
    """ "Amrutha Yogam" -> "Amrutha" (drikpanchang's form), tolerating spelling variants."""
    name = re.sub(r"\s*yog(?:am|a)\s*$", "", text.strip(), flags=re.IGNORECASE).strip()
    return {"amritha": "Amrutha", "amirtha": "Amrutha", "sidha": "Siddha"}.get(name.lower(), name)


def _parse_prokerala_nakshatram_segments(block, query_date):
    """Clip prokerala's dated "start – end" nakshatram ranges to query_date's (index, cutoff) segments.

    Mirrors _parse_nakshathram_segments: the first listed nakshatram is taken to
    hold from the start of the day (prokerala, like drikpanchang, lists the day
    from sunrise), each same-day end becomes a cutoff, and the first one that
    ends after midnight closes the day -- its end time becomes the next-day
    continuation when it falls on the very next calendar day.
    """
    day_end = datetime.combine(query_date + timedelta(days=1), datetime.min.time())
    day_start = day_end - timedelta(days=1)
    segments = []
    for item in block.select("li"):
        link = item.find("a", href=_PROKERALA_SLUG_RE)
        match = _PROKERALA_RANGE_RE.search(item.get_text(" ", strip=True))
        if link is None or match is None:
            continue
        slug = _PROKERALA_SLUG_RE.search(link["href"]).group(1)
        if slug not in _PROKERALA_SLUG_TO_INDEX:
            raise ValueError(f"Unknown prokerala nakshatra slug {slug!r} for {query_date}")
        index = _PROKERALA_SLUG_TO_INDEX[slug]
        end = _prokerala_datetime(match.group(4), match.group(5), match.group(6), query_date)
        if end <= day_start:
            continue
        if end >= day_end:
            segments.append((index, None))
            continuation = _normalize_clock(match.group(6)) if end < day_end + timedelta(days=1) else None
            return segments, continuation
        segments.append((index, _normalize_clock(match.group(6))))
    if not segments:
        raise ValueError(f"Could not find nakshatram data in prokerala page for {query_date}")
    # Every listed nakshatram ended the same day: whatever follows holds for the rest of it.
    segments.append(((segments[-1][0] + 1) % NUM_NAKSHATRAS, None))
    return segments, None


def _parse_prokerala_nakshatram_timeline(block, query_date):
    """Every listed nakshatram as (index, end minute past query_date's midnight); ends may exceed 1440."""
    day_start = datetime.combine(query_date, datetime.min.time())
    raw = []
    for item in block.select("li"):
        link = item.find("a", href=_PROKERALA_SLUG_RE)
        match = _PROKERALA_RANGE_RE.search(item.get_text(" ", strip=True))
        if link is None or match is None:
            continue
        slug = _PROKERALA_SLUG_RE.search(link["href"]).group(1)
        if slug not in _PROKERALA_SLUG_TO_INDEX:
            raise ValueError(f"Unknown prokerala nakshatra slug {slug!r} for {query_date}")
        end = _prokerala_datetime(match.group(4), match.group(5), match.group(6), query_date)
        raw.append((_PROKERALA_SLUG_TO_INDEX[slug], int((end - day_start).total_seconds() // 60)))
    return raw


def _parse_prokerala_tamil_yoga_segments(block, query_date, sunrise_minutes):
    """Turn prokerala's "Tamil Yogam" list into (name, cutoff) segments for query_date.

    prokerala's "Upto - HH:MM" carries no date. Its panchang day runs sunrise to
    sunrise, so a cutoff earlier than that day's sunrise is on the next calendar
    day -- which, like drikpanchang's "upto X, <next date>", means the value
    holds for the rest of query_date and becomes the next-day continuation.

    This is the Tamil Yogam block (Siddha / Amrutha / Marana ...), NOT the
    separate "Yogam" block (Dhrithi, Soola, ... -- the 27 nithya yogams).
    """
    segments = []
    for item in block.select("li"):
        name_tag = item.find("strong")
        if name_tag is None:
            continue
        name = _normalize_tamil_yogam_name(name_tag.get_text(" ", strip=True))
        upto = re.search(r"upto\s*-?\s*(\d{1,2}:\d{2}\s*[AP]M)", item.get_text(" ", strip=True), re.IGNORECASE)
        if upto is None:
            segments.append((name, None))
            return segments, None
        cutoff = _normalize_clock(upto.group(1))
        if _cutoff_to_minutes(cutoff) < sunrise_minutes:
            segments.append((name, None))
            return segments, cutoff
        segments.append((name, cutoff))
    if not segments:
        raise ValueError(f"Could not find Tamil Yogam data in prokerala page for {query_date}")
    return segments, None


def _parse_prokerala_day_panchang(html, query_date):
    """Parse one prokerala.com Tamil panchangam page into the same dict _parse_day_panchang returns."""
    if _is_prokerala_blocked_response(html):
        raise PanchangSourceBlockedError(f"prokerala.com served a CAPTCHA/block page for {query_date}.")
    soup = BeautifulSoup(html, "lxml")
    nak_block = soup.select_one(".panchang-data-nakshatra")
    yogam_block = soup.select_one(".panchang-data-tamil-yoga")
    if nak_block is None or yogam_block is None:
        raise ValueError(f"Could not find Nakshatram/Tamil Yogam blocks in prokerala page for {query_date}")

    nak_segments, nak_next_day_continuation = _parse_prokerala_nakshatram_segments(nak_block, query_date)
    sunrise_minutes = _prokerala_sunrise_minutes(soup, query_date)
    yogam_segments, yogam_next_day_continuation = _parse_prokerala_tamil_yoga_segments(
        yogam_block, query_date, sunrise_minutes
    )
    return {
        "date": query_date,
        "_sunrise_minutes": sunrise_minutes,
        "_nakshatram_timeline": _finalize_timeline(
            _parse_prokerala_nakshatram_timeline(nak_block, query_date), sunrise_minutes
        ),
        "primary_nakshatram_for_the_day": NAKSHATRAS[nak_segments[0][0]]["Tamil"],
        "secondary_nakshatram_of_the_day": (
            NAKSHATRAS[nak_segments[1][0]]["Tamil"] if len(nak_segments) > 1 else None
        ),
        "primary_tam_yogam_for_the_day": yogam_segments[0][0],
        "secondary_tam_yogam_of_the_day": yogam_segments[1][0] if len(yogam_segments) > 1 else None,
        "_nakshatram_segments": nak_segments,
        "_tam_yogam_segments": yogam_segments,
        "_nakshatram_next_day_continuation": nak_next_day_continuation,
        "_tam_yogam_next_day_continuation": yogam_next_day_continuation,
    }


# ---------------------------------------------------------------------------
# Top-level, source-agnostic day lookup: drikpanchang.com first, prokerala.com
# as a fallback whenever a source is blocked/unreachable.
# ---------------------------------------------------------------------------

DRIKPANCHANG = "drikpanchang.com"
PROKERALA = "prokerala.com"
DEFAULT_PANCHANG_SOURCES = (DRIKPANCHANG, PROKERALA)


def _source_cache_path(source, geoname_id, day_date, cache_dir):
    if source == DRIKPANCHANG:
        return _cache_path(geoname_id, day_date, cache_dir)  # unchanged, pre-existing layout
    base = Path(cache_dir) if cache_dir else _DEFAULT_CACHE_DIR
    return base / f"{geoname_id}_{day_date.strftime('%Y%m%d')}.prokerala.html"


def _fetch_prokerala_html(
    geoname_id,
    day_date,
    use_cache=True,
    cache_dir=None,
    request_delay_seconds=_DEFAULT_REQUEST_DELAY_SECONDS,
    session=None,
):
    """Fetch (or read from disk cache) the prokerala.com Tamil panchangam page for one day.

    Same contract as _fetch_day_panchang_html: no TTL, and a block/CAPTCHA
    page is never cached (raises PanchangSourceBlockedError instead).
    """
    path = _source_cache_path(PROKERALA, geoname_id, day_date, cache_dir)
    if use_cache and path.exists():
        return path.read_text(encoding="utf-8")

    getter = session.get if session is not None else requests.get
    response = getter(_prokerala_url(day_date), params={"loc": geoname_id}, headers=_REQUEST_HEADERS, timeout=20)
    if getattr(response, "status_code", 200) in (403, 429, 503):
        raise PanchangSourceBlockedError(
            f"prokerala.com refused the request for {day_date} (HTTP {response.status_code})."
        )
    response.raise_for_status()
    html = response.text
    if _is_prokerala_blocked_response(html):
        raise PanchangSourceBlockedError(f"prokerala.com served a CAPTCHA/block page for {day_date}.")

    if use_cache:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
    if request_delay_seconds:
        time.sleep(request_delay_seconds)
    return html


_SOURCE_FETCHERS = {
    DRIKPANCHANG: (_fetch_day_panchang_html, _parse_day_panchang),
    PROKERALA: (_fetch_prokerala_html, _parse_prokerala_day_panchang),
}


def _utc_offset_change_minutes(geoname_id, day_date):
    """How far local clocks move between day_date and the next day (e.g. -60 when DST ends).

    The next sunrise is taken to be at the same wall-clock time as this one,
    adjusted by this; sunrise itself drifts only a minute or two a day.
    """
    try:
        tz = _city_timezone(geoname_id)
    except ValueError:
        return 0
    noon = datetime.combine(day_date, datetime.min.time()) + timedelta(hours=12)
    before = noon.replace(tzinfo=tz).utcoffset()
    after = (noon + timedelta(days=1)).replace(tzinfo=tz).utcoffset()
    return int((after - before).total_seconds() // 60)


def fetch_day_panchang(
    geoname_id,
    day_date,
    *,
    sources=DEFAULT_PANCHANG_SOURCES,
    use_cache=True,
    cache_dir=None,
    request_delay_seconds=_DEFAULT_REQUEST_DELAY_SECONDS,
    session=None,
    unavailable_sources=None,
):
    """Return one day's primary/secondary Tamil Nakshatram and Tamil Yogam for a city, from any source.

    Tries each of `sources` in order (default: drikpanchang.com, then
    prokerala.com) -- cached page first, then a live request -- and returns
    the first successfully parsed day_result (the dict _parse_day_panchang
    documents), with an added "source" key naming where it came from. A
    source that is blocked (CAPTCHA/rate-limit/HTTP 403/429/503) or
    unreachable is skipped in favor of the next one.

    `unavailable_sources`, if given, is a set shared across calls within one
    run: a source that gets blocked is added to it and not retried live for
    the rest of that run (its cached pages are still used), so a blocked site
    isn't hammered once per remaining day.

    Note the two sites agree on nakshatram timings but *not always* on the
    Tamil Yogam for a given weekday+nakshatram (see TestSourceAgreement), so
    drikpanchang.com -- this skill's reference source -- is always preferred.

    Raises PanchangSourceBlockedError (a DrikPanchangBlockedError) if no
    source could provide the day.
    """
    if unavailable_sources is None:
        unavailable_sources = set()
    failures = []
    for source in sources:
        fetch, parse = _SOURCE_FETCHERS[source]
        cached = use_cache and _source_cache_path(source, geoname_id, day_date, cache_dir).exists()
        if source in unavailable_sources and not cached:
            failures.append(f"{source}: skipped (blocked earlier in this run)")
            continue
        try:
            html = fetch(
                geoname_id,
                day_date,
                use_cache=use_cache,
                cache_dir=cache_dir,
                request_delay_seconds=request_delay_seconds,
                session=session,
            )
            day_result = parse(html, day_date)
        except (DrikPanchangBlockedError, requests.RequestException) as exc:
            unavailable_sources.add(source)
            failures.append(f"{source}: {exc}")
            continue
        day_result["source"] = source
        day_result["_next_sunrise_minutes"] = day_result["_sunrise_minutes"] + _utc_offset_change_minutes(
            geoname_id, day_date
        )
        return day_result
    raise PanchangSourceBlockedError(
        f"No panchang source could provide {day_date} for geoname-id {geoname_id}. " + " | ".join(failures)
    )


def _slugify_for_filename(text, label="value"):
    """Turn arbitrary text into a filesystem-safe path component.

    Strips anything that isn't alphanumeric/underscore/hyphen (which also
    rules out path separators and ".." segments), so a crafted value can't
    write outside the intended output directory.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"{label} must be a non-empty string")
    slug = re.sub(r"\s+", "_", text.strip())
    slug = re.sub(r"[^A-Za-z0-9_-]", "", slug)
    if not slug:
        raise ValueError(f"{label} {text!r} could not be turned into a valid filename component")
    return slug


def _slugify_person_name(person):
    """Turn a person's name into a filesystem-safe folder name. See _slugify_for_filename."""
    return _slugify_for_filename(person, label="person")


def _slugify_city_name(input_city_name):
    """Turn a city name (with any ", state"/", country" qualifier) into a safe folder name.

    E.g. "Sunnyvale" -> "Sunnyvale", "Springfield, IL" -> "Springfield_IL".
    See _slugify_for_filename.
    """
    return _slugify_for_filename(input_city_name, label="input_city_name")


def _person_city_output_dir(output_dir, person, input_city_name):
    """Return (creating it if needed) `{output_dir}/{slugified person}/{slugified city}`.

    Results are split per city so running the same person against a second
    city doesn't overwrite the first city's .txt/.json files (their file
    names carry the person and month but not the city).
    """
    city_dir = Path(output_dir) / _slugify_person_name(person) / _slugify_city_name(input_city_name)
    city_dir.mkdir(parents=True, exist_ok=True)
    return city_dir


def _format_month_file_contents(person, input_nakshatram, input_city_name, month_entry):
    header = [
        f"Favorable days for {person}",
        f"Nakshatram: {input_nakshatram}",
        f"City: {input_city_name}",
        f"Month: {month_entry['month']} {month_entry['year']}",
        f"Days run from sunrise to the next sunrise; Tamil Yogam per the {TAMIL_YOGAM_METHOD}.",
        "-" * 60,
    ]
    body = month_entry["fav_days_with_ts"] or ["No favorable days found."]
    return "\n".join(header + body) + "\n"


def _write_month_file(person, input_nakshatram, input_city_name, output_dir, month_entry):
    city_dir = _person_city_output_dir(output_dir, person, input_city_name)
    file_path = city_dir / f"{month_entry['month']}_{month_entry['year']}.txt"
    file_path.write_text(
        _format_month_file_contents(person, input_nakshatram, input_city_name, month_entry),
        encoding="utf-8",
    )
    return file_path


def _split_favorable_entry_into_row(entry):
    """Split a "{date} - {prediction}" display string into {"date": ..., "prediction": ...}.

    Every string _build_favorable_entry produces follows this "{date} - ..."
    shape (see its docstring), so this is a plain, lossless split -- turning
    the flat display strings into a uniform-columns row suitable for a table.
    """
    date_part, _, prediction_part = entry.partition(" - ")
    return {"date": date_part, "prediction": prediction_part}


def _with_sunrise(row, sunrise_by_date):
    """Add the day's sunrise (start of its Vedic day) to a {date, prediction} row, when known."""
    if row["date"] in sunrise_by_date:
        row["sunrise"] = sunrise_by_date[row["date"]]
    return row


def collate_and_save_predictions(
    person,
    input_nakshatram,
    input_city_name,
    starting_month_year,
    forward_looking_months,
    output_dir,
    favorable_days_with_ts,
    data_sources=None,
):
    """Collate every forward-looking month's favorable days into one consolidated JSON file.

    Reshapes `favorable_days_with_ts` (the list fetch_favorable_month_days
    builds up, one dict per month) into a single JSON document with a
    tabular "favorable_days" row list (columns: date, prediction) per month,
    and writes it to
    `{output_dir}/{slugified person}/{slugified city}/{slugified person}_{slugified starting_month_year}_{forward_looking_months}.json`
    (the same per-person, per-city subfolder each month's .txt file already lives in).

    Returns the path the consolidated file was written to.
    """
    months_table = [
        {
            "month": month_entry["month"],
            "year": month_entry["year"],
            "favorable_days": [
                _with_sunrise(_split_favorable_entry_into_row(entry), month_entry.get("sunrise_by_date", {}))
                for entry in month_entry["fav_days_with_ts"]
            ],
        }
        for month_entry in favorable_days_with_ts
    ]

    consolidated = {
        "person": person,
        "input_nakshatram": input_nakshatram,
        "input_city_name": input_city_name,
        "starting_month_year": starting_month_year,
        "forward_looking_months": forward_looking_months,
        "tamil_yogam_method": TAMIL_YOGAM_METHOD,
        "day_model": DAY_MODEL,
        "months": months_table,
    }
    if data_sources is not None:
        # Which site each day's data came from; "fallback_dates" lists days that
        # had to come from prokerala.com because drikpanchang.com was blocked.
        consolidated["data_sources"] = data_sources

    city_dir = _person_city_output_dir(output_dir, person, input_city_name)
    file_name = (
        f"{_slugify_person_name(person)}_"
        f"{_slugify_for_filename(starting_month_year, label='starting_month_year')}_"
        f"{forward_looking_months}.json"
    )
    file_path = city_dir / file_name
    file_path.write_text(json.dumps(consolidated, indent=2, ensure_ascii=False), encoding="utf-8")
    return file_path


def fetch_favorable_month_days(
    fav_days_of_week,
    input_nakshatram,
    input_city_name,
    starting_month_year,
    forward_looking_months=12,
    *,
    person,
    output_dir=None,
    use_cache=True,
    cache_dir=None,
    request_delay_seconds=_DEFAULT_REQUEST_DELAY_SECONDS,
    session=None,
    city_chooser=None,
    interactive=True,
    sources=DEFAULT_PANCHANG_SOURCES,
):
    """Find favorable days, on given weekdays, over a forward-looking window of months.

    `person` is mandatory. It, and every other parameter after
    `forward_looking_months`, is keyword-only (pass them as e.g.
    `person="..."`, not positionally) -- call with
    `fetch_favorable_month_days(days, nakshatram, city, month_year, N, person="...")`.
    (`person` can't be a plain positional parameter placed right after
    `forward_looking_months`, since `forward_looking_months` has a default
    value and Python doesn't allow a required parameter to follow a
    defaulted one in the same positional group -- keyword-only sidesteps
    that while still making `person` mandatory and keeping it right after
    `forward_looking_months` in the signature.)

    For each of `forward_looking_months` months starting at `starting_month_year`,
    checks every date falling on one of `fav_days_of_week` (e.g. ["Monday", "Wednesday"])
    against that date's drikpanchang.com panchangam for `input_city_name`. A date
    qualifies when its nakshatram is favorable relative to `input_nakshatram` (per
    favorable_nakshatram_indices) AND its Tamil Yogam is Siddha or Amrutha (not Marana),
    checked separately for the portion of the day before/after any mid-day nakshatra
    change, and combined into one entry ("Entire day" / "until TIME" / "from TIME onwards").

    `input_city_name` may include a ", state" and/or ", country" qualifier (e.g.
    "Springfield, IL" or "Springfield, Illinois, USA") to disambiguate a name that
    exists in more than one place. If it's still ambiguous: `city_chooser`, if given,
    is called with the list of candidate city dicts and must return the chosen one
    (for scripted/programmatic use); otherwise, if `interactive` (default) and stdin
    is a real terminal, the candidates are printed and the user is prompted to pick
    one; otherwise AmbiguousCityError is raised with the full candidate list. See
    resolve_geoname_id for details.

    Results are always additionally persisted to disk, as one text file per
    forward-looking month, under `{output_dir}/{person}/{city}/{Month}_{Year}.txt`
    (`person` and `input_city_name` are each sanitized into a safe folder name
    for those subfolders, e.g. "Springfield, IL" -> "Springfield_IL"). If
    `output_dir` isn't given, it defaults to `f"{person}_output_dir"` (a path
    relative to the current working directory). Each returned month dict
    gets an "output_file" key holding that path (a string).

    Once every month has been fetched and saved, all of them are also
    collated into one consolidated tabular JSON file (see
    collate_and_save_predictions) at
    `{output_dir}/{person}/{city}/{person}_{starting_month_year}_{forward_looking_months}.json`;
    every returned month dict gets a "consolidated_output_file" key holding
    that same path (a string).

    Returns a list with one entry per forward-looking month:
        [{"month": "September", "year": 2026, "fav_days_with_ts": [...],
          "output_file": "...", "consolidated_output_file": "..."}, ...]

    Note: fetches drikpanchang.com over the network (unless already cached on disk in
    `cache_dir`), roughly one request per matching weekday per month.
    """
    if not fav_days_of_week:
        raise ValueError("fav_days_of_week must be a non-empty list of weekday names")
    weekday_names = [_normalize_weekday_name(day) for day in fav_days_of_week]

    if not isinstance(person, str) or not person.strip():
        raise ValueError("person must be a non-empty string")
    if output_dir is None:
        output_dir = f"{person}_output_dir"
    _slugify_city_name(input_city_name)  # fail fast, before any network requests

    favorable_indices = favorable_nakshatram_indices(input_nakshatram)
    geoname_id = resolve_geoname_id(input_city_name, chooser=city_chooser, interactive=interactive)
    start_year, start_month = _parse_month_year(starting_month_year)

    unavailable_sources = set()
    source_counts = {}
    fallback_dates = []
    favorable_days_with_ts = []
    for year, month in _forward_looking_months(start_year, start_month, forward_looking_months):
        month_entries = []
        sunrise_by_date = {}
        for day_date in _dates_in_month_for_weekdays(year, month, weekday_names):
            day_result = fetch_day_panchang(
                geoname_id,
                day_date,
                sources=sources,
                use_cache=use_cache,
                cache_dir=cache_dir,
                request_delay_seconds=request_delay_seconds,
                session=session,
                unavailable_sources=unavailable_sources,
            )
            source_counts[day_result["source"]] = source_counts.get(day_result["source"], 0) + 1
            if day_result["source"] != DRIKPANCHANG:
                fallback_dates.append(day_date.isoformat())
            entry = _build_favorable_entry(day_result, favorable_indices)
            if entry is not None:
                month_entries.append(entry)
                sunrise_by_date[_format_day_label(day_date)] = _minutes_to_cutoff(day_result["_sunrise_minutes"])

        month_result = {
            "month": calendar.month_name[month],
            "year": year,
            "fav_days_with_ts": month_entries,
            "sunrise_by_date": sunrise_by_date,
        }
        file_path = _write_month_file(person, input_nakshatram, input_city_name, output_dir, month_result)
        month_result["output_file"] = str(file_path)

        favorable_days_with_ts.append(month_result)

    consolidated_file_path = collate_and_save_predictions(
        person,
        input_nakshatram,
        input_city_name,
        starting_month_year,
        forward_looking_months,
        output_dir,
        favorable_days_with_ts,
        data_sources={"days_by_source": source_counts, "fallback_dates": fallback_dates},
    )
    for month_result in favorable_days_with_ts:
        month_result["consolidated_output_file"] = str(consolidated_file_path)
        month_result["data_sources"] = {"days_by_source": source_counts, "fallback_dates": fallback_dates}

    return favorable_days_with_ts


# ---------------------------------------------------------------------------
# Joint favorable times for a group of people (e.g. a couple), possibly in
# different cities/time zones.
# ---------------------------------------------------------------------------


def _favorable_intervals(day_result, favorable_indices):
    """Favorable windows as (start, end) minutes past the date's local midnight (see _favorable_windows)."""
    return _favorable_windows(day_result, favorable_indices)


def _city_timezone(geoname_id):
    """Return the ZoneInfo for a resolved geoname-id (drikpanchang times are local wall-clock times there)."""
    city = _GEONAMES_CACHE.get_cities().get(str(geoname_id))
    tz_name = city.get("timezone") if city else None
    if not tz_name:
        raise ValueError(f"No time zone known for geoname-id {geoname_id}")
    return ZoneInfo(tz_name)


def _local_minutes_to_utc(day_date, minutes, tz):
    """Convert "`minutes` past local midnight of `day_date`" (may exceed 1440) in `tz` to an aware UTC datetime."""
    local_wall_clock = datetime.combine(day_date, datetime.min.time()) + timedelta(minutes=minutes)
    return local_wall_clock.replace(tzinfo=tz).astimezone(timezone.utc)


# Consecutive favorable Vedic days meet at a sunrise that's estimated from the
# previous one (same clock time), so they can be a minute or two apart.
_SUNRISE_SEAM_TOLERANCE = timedelta(minutes=2)


def _merge_intervals(intervals, tolerance=None):
    """Sort and merge overlapping/touching (start, end) intervals.

    With `tolerance` (same type as end - start, e.g. a timedelta), gaps up to
    that size are closed too -- used to join consecutive Vedic days, whose
    boundary (the next sunrise) is estimated to within a minute or two.
    """
    merged = []
    for start, end in sorted(intervals):
        if merged and (start <= merged[-1][1] or (tolerance is not None and start - merged[-1][1] <= tolerance)):
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _intersect_intervals(a, b):
    """Intersect two sorted, merged lists of (start, end) intervals."""
    result = []
    i = j = 0
    while i < len(a) and j < len(b):
        start = max(a[i][0], b[j][0])
        end = min(a[i][1], b[j][1])
        if start < end:
            result.append((start, end))
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return result


def _dates_between_for_weekdays(first_date, last_date, weekday_names):
    wanted = {_WEEKDAY_NAMES.index(name) for name in weekday_names}
    day_date = first_date
    while day_date <= last_date:
        if day_date.weekday() in wanted:
            yield day_date
        day_date += timedelta(days=1)


def _format_local_datetime(dt):
    return f"{calendar.day_name[dt.weekday()]}, {_format_day_label(dt.date())} {_minutes_to_cutoff(dt.hour * 60 + dt.minute)}"


def _normalize_group_member(member):
    required = ("person", "input_nakshatram", "input_city_name", "fav_days_of_week")
    missing = [key for key in required if not member.get(key)]
    if missing:
        raise ValueError(f"group member {member!r} is missing: {', '.join(missing)}")
    if not isinstance(member["person"], str) or not member["person"].strip():
        raise ValueError("each group member's person must be a non-empty string")
    return {
        "person": member["person"].strip(),
        "input_nakshatram": member["input_nakshatram"],
        "input_city_name": member["input_city_name"],
        "fav_days_of_week": [_normalize_weekday_name(day) for day in member["fav_days_of_week"]],
    }


def _format_group_file_contents(consolidated):
    lines = [f"Common favorable times for {consolidated['group']}"]
    for member in consolidated["participants"]:
        lines.append(
            f"  {member['person']}: {member['input_nakshatram']} nakshatram, {member['input_city_name']} "
            f"({member['timezone']}), favorable weekdays {', '.join(member['fav_days_of_week'])}"
        )
    lines.append(
        f"Window: {consolidated['forward_looking_months']} month(s) from {consolidated['starting_month_year']}"
    )
    lines.append("=" * 60)
    for month in consolidated["months"]:
        lines.append(f"{month['month']} {month['year']}:")
        if not month["common_windows"]:
            lines.append("  No common favorable time found.")
        for window in month["common_windows"]:
            lines.append(f"  {window['duration_minutes'] // 60}h {window['duration_minutes'] % 60:02d}m together:")
            for local in window["local_times"]:
                lines.append(f"    {local['person']} ({local['input_city_name']}): {local['start']} -> {local['end']}")
    return "\n".join(lines) + "\n"


def find_common_favorable_times(
    people,
    starting_month_year,
    forward_looking_months=3,
    *,
    group_name=None,
    output_dir=None,
    use_cache=True,
    cache_dir=None,
    request_delay_seconds=_DEFAULT_REQUEST_DELAY_SECONDS,
    session=None,
    city_chooser=None,
    interactive=True,
    sources=DEFAULT_PANCHANG_SOURCES,
):
    """Find time windows that are favorable for every person in `people` at the same moment.

    `people` is a list of 2+ dicts, each with "person", "input_nakshatram",
    "input_city_name" and "fav_days_of_week" -- the same inputs
    fetch_favorable_month_days takes for one person. People may live in
    different cities and time zones.

    Each person is evaluated independently in their *own* city, exactly as
    fetch_favorable_month_days would: only on their own favorable weekdays
    (by their local date), with the nakshatram favorable relative to *their*
    birth nakshatram and a Siddha/Amrutha Tamil Yogam as published for
    *their* city. Every person's favorable windows are then placed on one
    absolute (UTC) timeline and intersected. Because a nakshatram transition
    happens at the same instant everywhere, any moment inside every person's
    window is automatically in a nakshatram favorable to all of them; the
    weekday and yogam are each person's local ones. So e.g. a favorable
    Wednesday night in Chennai can overlap a favorable Wednesday morning in
    Sunnyvale.

    Each person's dates are scanned one day beyond each end of the window,
    so an overlap straddling a month/window boundary across time zones isn't
    lost; an overlap is kept if it starts inside the window on at least one
    person's local calendar, and is filed under the month of its start on
    the first person's local calendar.

    Writes `{output_dir}/{group slug}/{group slug}_{starting_month_year}_{N}.json`
    and a matching `.txt`, where `group slug` joins the slugified person
    names with "_" and `output_dir` defaults to `f"{group slug}_output_dir"`.
    Returns the consolidated dict (also what's written to the JSON), with an
    added "output_file" key.
    """
    if not isinstance(people, (list, tuple)) or len(people) < 2:
        raise ValueError("people must list at least two group members")
    members = [_normalize_group_member(member) for member in people]
    group_slug = "_".join(_slugify_person_name(member["person"]) for member in members)
    if group_name is None:
        group_name = " & ".join(member["person"] for member in members)
    if output_dir is None:
        output_dir = f"{group_slug}_output_dir"
    for member in members:
        _slugify_city_name(member["input_city_name"])  # fail fast, before any network requests

    start_year, start_month = _parse_month_year(starting_month_year)
    months = list(_forward_looking_months(start_year, start_month, forward_looking_months))
    window_first = date(months[0][0], months[0][1], 1)
    last_year, last_month = months[-1]
    window_last = date(last_year, last_month, calendar.monthrange(last_year, last_month)[1])

    unavailable_sources = set()
    fallback_dates = []
    common = None
    for member in members:
        favorable_indices = favorable_nakshatram_indices(member["input_nakshatram"])
        geoname_id = resolve_geoname_id(member["input_city_name"], chooser=city_chooser, interactive=interactive)
        tz = _city_timezone(geoname_id)
        member["_tz"] = tz
        member["timezone"] = tz.key

        intervals = []
        for day_date in _dates_between_for_weekdays(
            window_first - timedelta(days=1), window_last + timedelta(days=1), member["fav_days_of_week"]
        ):
            day_result = fetch_day_panchang(
                geoname_id,
                day_date,
                sources=sources,
                use_cache=use_cache,
                cache_dir=cache_dir,
                request_delay_seconds=request_delay_seconds,
                session=session,
                unavailable_sources=unavailable_sources,
            )
            if day_result["source"] != DRIKPANCHANG:
                fallback_dates.append(f"{member['person']}: {day_date.isoformat()}")
            for start, end in _favorable_intervals(day_result, favorable_indices):
                intervals.append((_local_minutes_to_utc(day_date, start, tz), _local_minutes_to_utc(day_date, end, tz)))
        intervals = _merge_intervals(intervals, tolerance=_SUNRISE_SEAM_TOLERANCE)
        common = intervals if common is None else _intersect_intervals(common, intervals)

    common_indices = set.intersection(*(set(favorable_nakshatram_indices(m["input_nakshatram"])) for m in members))
    month_buckets = {(year, month): [] for year, month in months}
    for start_utc, end_utc in common:
        local_starts = [start_utc.astimezone(member["_tz"]) for member in members]
        if not any(window_first <= local.date() <= window_last for local in local_starts):
            continue
        anchor = local_starts[0]
        bucket_key = (anchor.year, anchor.month)
        if bucket_key not in month_buckets:
            # Starts inside the window only on another member's calendar: file it
            # under the nearest in-window month on the first member's calendar.
            bucket_key = months[0] if anchor.date() < window_first else months[-1]
        month_buckets[bucket_key].append(
            {
                "start_utc": start_utc.isoformat(),
                "end_utc": end_utc.isoformat(),
                "duration_minutes": int((end_utc - start_utc).total_seconds() // 60),
                "local_times": [
                    {
                        "person": member["person"],
                        "input_city_name": member["input_city_name"],
                        "timezone": member["timezone"],
                        "start": _format_local_datetime(start_utc.astimezone(member["_tz"])),
                        "end": _format_local_datetime(end_utc.astimezone(member["_tz"])),
                    }
                    for member in members
                ],
            }
        )

    consolidated = {
        "group": group_name,
        "starting_month_year": starting_month_year,
        "forward_looking_months": forward_looking_months,
        "participants": [
            {key: member[key] for key in ("person", "input_nakshatram", "input_city_name", "timezone", "fav_days_of_week")}
            for member in members
        ],
        "common_favorable_nakshatrams": [NAKSHATRAS[i]["Tamil"] for i in sorted(common_indices)],
        "tamil_yogam_method": TAMIL_YOGAM_METHOD,
        "day_model": DAY_MODEL,
        "data_sources": {"fallback_dates": fallback_dates},
        "months": [
            {"month": calendar.month_name[month], "year": year, "common_windows": month_buckets[(year, month)]}
            for year, month in months
        ],
    }

    group_dir = Path(output_dir) / group_slug
    group_dir.mkdir(parents=True, exist_ok=True)
    stem = (
        f"{group_slug}_"
        f"{_slugify_for_filename(starting_month_year, label='starting_month_year')}_"
        f"{forward_looking_months}"
    )
    json_path = group_dir / f"{stem}.json"
    json_path.write_text(json.dumps(consolidated, indent=2, ensure_ascii=False), encoding="utf-8")
    (group_dir / f"{stem}.txt").write_text(_format_group_file_contents(consolidated), encoding="utf-8")

    consolidated["output_file"] = str(json_path)
    return consolidated


# ---------------------------------------------------------------------------
# Command-line interface: `python3 panchangam_utils.py ...`
# ---------------------------------------------------------------------------


def _build_arg_parser():
    parser = argparse.ArgumentParser(
        prog="panchangam_utils.py",
        description=(
            "Find favorable days (by nakshatram + Tamil Yogam) on given weekdays, over a "
            "forward-looking window of months, for a person's nakshatram and city."
        ),
    )
    parser.add_argument(
        "fav_days_of_week",
        nargs="+",
        metavar="WEEKDAY",
        help='Favorable weekday name(s), space-separated, e.g. Monday Wednesday Friday.',
    )
    parser.add_argument("input_nakshatram", help='Nakshatram name, e.g. "Uthiradam".')
    parser.add_argument(
        "input_city_name",
        help='City name, e.g. "Sunnyvale" or "Springfield, IL" to disambiguate.',
    )
    parser.add_argument("starting_month_year", help='Starting month and year, e.g. "September 2026".')
    parser.add_argument("person", help="Name of the individual these results are for.")
    parser.add_argument(
        "--forward-looking-months",
        type=int,
        default=12,
        help="Number of months to look ahead, starting at starting_month_year (default: 12).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help='Directory to write results to (default: "{person}_output_dir", relative to the '
        "current directory).",
    )
    parser.add_argument(
        "--cache-dir",
        default=None,
        help="Directory to cache fetched drikpanchang pages in (default: panchang_cache/ next "
        "to this file).",
    )
    parser.add_argument(
        "--no-cache",
        dest="use_cache",
        action="store_false",
        default=True,
        help="Disable the on-disk drikpanchang page cache.",
    )
    parser.add_argument(
        "--request-delay-seconds",
        type=float,
        default=_DEFAULT_REQUEST_DELAY_SECONDS,
        help=f"Delay between live drikpanchang requests, in seconds (default: {_DEFAULT_REQUEST_DELAY_SECONDS}).",
    )
    parser.add_argument(
        "--no-fallback",
        dest="sources",
        action="store_const",
        const=(DRIKPANCHANG,),
        default=DEFAULT_PANCHANG_SOURCES,
        help="Only use drikpanchang.com; don't fall back to prokerala.com when it's blocked.",
    )
    parser.add_argument(
        "--non-interactive",
        dest="interactive",
        action="store_false",
        default=True,
        help="Don't prompt to disambiguate an ambiguous city name; raise an error instead.",
    )
    return parser


def _print_fallback_note(fallback_dates):
    if fallback_dates:
        print(
            f"Note: {len(fallback_dates)} day(s) came from prokerala.com because drikpanchang.com was "
            f"blocked: {', '.join(fallback_dates)}. The two sites occasionally disagree on Tamil Yogam."
        )


def _parse_group_member_spec(spec):
    """Parse a --person value "NAME;NAKSHATRAM;CITY;WEEKDAY,WEEKDAY,..." into a group-member dict.

    ";" separates the fields because city names themselves contain commas
    (e.g. "Sunnyvale, CA"); weekdays may be separated by commas and/or spaces.
    """
    parts = [part.strip() for part in spec.split(";")]
    if len(parts) != 4 or not all(parts):
        raise argparse.ArgumentTypeError(
            f"expected 'NAME;NAKSHATRAM;CITY;WEEKDAY,WEEKDAY,...', got {spec!r}"
        )
    person, nakshatram, city, weekdays = parts
    return {
        "person": person,
        "input_nakshatram": nakshatram,
        "input_city_name": city,
        "fav_days_of_week": [day for day in re.split(r"[,\s]+", weekdays) if day],
    }


def _build_group_arg_parser():
    parser = argparse.ArgumentParser(
        prog="panchangam_utils.py group",
        description=(
            "Find time windows favorable for every person at once (e.g. a couple), each evaluated "
            "in their own city and time zone, then intersected on a common timeline."
        ),
    )
    parser.add_argument(
        "--person",
        dest="people",
        action="append",
        required=True,
        type=_parse_group_member_spec,
        metavar="'NAME;NAKSHATRAM;CITY;WEEKDAY,...'",
        help="One group member; repeat for each (at least two). "
        "E.g. --person 'Jai;Uthiradam;Chennai;Monday,Wednesday'.",
    )
    parser.add_argument("starting_month_year", help='Starting month and year, e.g. "September 2026".')
    parser.add_argument(
        "--forward-looking-months",
        type=int,
        default=3,
        help="Number of months to look ahead, starting at starting_month_year (default: 3).",
    )
    parser.add_argument("--group-name", default=None, help='Display name (default: "A & B").')
    parser.add_argument(
        "--output-dir",
        default=None,
        help='Directory to write results to (default: "{A}_{B}_output_dir", relative to the current directory).',
    )
    parser.add_argument("--cache-dir", default=None, help="Directory to cache fetched drikpanchang pages in.")
    parser.add_argument("--no-cache", dest="use_cache", action="store_false", default=True)
    parser.add_argument("--request-delay-seconds", type=float, default=_DEFAULT_REQUEST_DELAY_SECONDS)
    parser.add_argument(
        "--no-fallback",
        dest="sources",
        action="store_const",
        const=(DRIKPANCHANG,),
        default=DEFAULT_PANCHANG_SOURCES,
        help="Only use drikpanchang.com; don't fall back to prokerala.com when it's blocked.",
    )
    parser.add_argument("--non-interactive", dest="interactive", action="store_false", default=True)
    return parser


def _group_main(argv):
    args = _build_group_arg_parser().parse_args(argv)
    try:
        result = find_common_favorable_times(
            args.people,
            args.starting_month_year,
            args.forward_looking_months,
            group_name=args.group_name,
            output_dir=args.output_dir,
            use_cache=args.use_cache,
            cache_dir=args.cache_dir,
            request_delay_seconds=args.request_delay_seconds,
            interactive=args.interactive,
            sources=args.sources,
        )
    except (ValueError, DrikPanchangBlockedError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Common favorable nakshatrams: {', '.join(result['common_favorable_nakshatrams']) or 'none'}")
    for month in result["months"]:
        print(f"{month['month']} {month['year']}:")
        if not month["common_windows"]:
            print("  No common favorable time found.")
        for window in month["common_windows"]:
            print(f"  {window['duration_minutes'] // 60}h {window['duration_minutes'] % 60:02d}m together:")
            for local in window["local_times"]:
                print(f"    {local['person']} ({local['input_city_name']}): {local['start']} -> {local['end']}")
    print(f"Consolidated summary saved to {result['output_file']}")
    _print_fallback_note(result["data_sources"]["fallback_dates"])
    return 0


def main(argv=None):
    """CLI entry point: `python3 panchangam_utils.py WEEKDAY [WEEKDAY ...] NAKSHATRAM CITY MONTH_YEAR PERSON [options]`.

    `python3 panchangam_utils.py group --person ... --person ... MONTH_YEAR [options]`
    instead runs find_common_favorable_times for a group (see _build_group_arg_parser).

    Wires argparse straight onto fetch_favorable_month_days's parameters,
    prints a per-month summary of favorable days to stdout, and reports
    which file each month's results were also saved to. Returns a process
    exit code (0 on success, 1 on a recognized error) rather than raising,
    so `sys.exit(main())` at the bottom of this file gives a clean CLI
    error message instead of a raw traceback for expected failure modes
    (bad input, an unresolvable/ambiguous city, or drikpanchang rate-limiting).
    """
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "group":
        return _group_main(argv[1:])

    args = _build_arg_parser().parse_args(argv)

    try:
        results = fetch_favorable_month_days(
            args.fav_days_of_week,
            args.input_nakshatram,
            args.input_city_name,
            args.starting_month_year,
            args.forward_looking_months,
            person=args.person,
            output_dir=args.output_dir,
            use_cache=args.use_cache,
            cache_dir=args.cache_dir,
            request_delay_seconds=args.request_delay_seconds,
            interactive=args.interactive,
            sources=args.sources,
        )
    except (ValueError, DrikPanchangBlockedError) as exc:
        # ValueError also covers AmbiguousCityError, a subclass.
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"(Days run from sunrise to the next sunrise; Tamil Yogam per the {TAMIL_YOGAM_METHOD}.)")
    for month_result in results:
        print(f"{month_result['month']} {month_result['year']}:")
        if month_result["fav_days_with_ts"]:
            for entry in month_result["fav_days_with_ts"]:
                print(f"  {entry}")
        else:
            print("  No favorable days found.")
        print(f"  (saved to {month_result['output_file']})")

    print(f"Consolidated summary saved to {results[0]['consolidated_output_file']}")
    _print_fallback_note(results[0]["data_sources"]["fallback_dates"])

    return 0


if __name__ == "__main__":
    sys.exit(main())

