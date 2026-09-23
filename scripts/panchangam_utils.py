"""Utilities for working with the 27 Hindu Nakshatras (lunar mansions)."""

import argparse
import calendar
import functools
import json
import re
import sys
import time
import warnings
from datetime import date, datetime, timedelta
from pathlib import Path

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

    return {
        "date": query_date,
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


def _favorable_windows(day_result, favorable_indices):
    """Return merged (start_minute, end_minute) windows, within the day, that are favorable.

    Builds the timeline by cutting the day at every cutoff time present in
    either segment list (nakshatram's and Tamil Yogam's transitions need not
    coincide, and either can have more than one same-day transition), then
    checks favorability of the nakshatra+yogam pair active in each resulting
    slice, merging adjacent favorable slices together.
    """
    nak_segments = day_result["_nakshatram_segments"]
    yogam_segments = day_result["_tam_yogam_segments"]
    boundaries = sorted(
        {
            _cutoff_to_minutes(cutoff)
            for segments in (nak_segments, yogam_segments)
            for _, cutoff in segments
            if cutoff is not None
        }
    )
    edges = [0, *boundaries, _MINUTES_PER_DAY]

    windows = []
    for start, end in zip(edges, edges[1:]):
        nak_idx = _value_at(nak_segments, start)
        yogam = _value_at(yogam_segments, start)
        if nak_idx in favorable_indices and _is_favorable_yogam(yogam):
            windows.append((start, end))

    merged = []
    for start, end in windows:
        if merged and merged[-1][1] == start:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return merged


def _next_day_continuation_label(day_result):
    """If the day's trailing nakshatram/yogam segment is known to hold into tomorrow
    until a specific time, return "{next day's date} {time}"; else None.

    Both dimensions can each carry such a fact independently (see
    _parse_nakshathram_segments / _parse_tamil_yoga_segments); when both are
    known, the earlier of the two is reported, since that's the point at
    which today's combined favorable state is first at risk of changing.
    """
    known_cutoffs = [
        c
        for c in (
            day_result["_nakshatram_next_day_continuation"],
            day_result["_tam_yogam_next_day_continuation"],
        )
        if c is not None
    ]
    if not known_cutoffs:
        return None
    earliest_cutoff = min(known_cutoffs, key=_cutoff_to_minutes)
    next_day = day_result["date"] + timedelta(days=1)
    return f"{_format_day_label(next_day)} {earliest_cutoff}"


def _build_favorable_entry(day_result, favorable_indices):
    """Combine a day's favorable windows into one display string, or None if not favorable at all."""
    windows = _favorable_windows(day_result, favorable_indices)
    if not windows:
        return None

    label = _format_day_label(day_result["date"])
    continuation = _next_day_continuation_label(day_result)

    if windows == [(0, _MINUTES_PER_DAY)]:
        if continuation:
            return f"{label} - Entire day (favorable until {continuation})"
        return f"{label} - Entire day"

    parts = []
    for start, end in windows:
        if start == 0:
            parts.append(f"until {_minutes_to_cutoff(end)}")
        elif end == _MINUTES_PER_DAY:
            if continuation:
                parts.append(f"from {_minutes_to_cutoff(start)} onwards (favorable until {continuation})")
            else:
                parts.append(f"from {_minutes_to_cutoff(start)} onwards")
        else:
            parts.append(f"from {_minutes_to_cutoff(start)} to {_minutes_to_cutoff(end)}")
    return f"{label} - " + "; ".join(parts)


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


def _format_month_file_contents(person, input_nakshatram, input_city_name, month_entry):
    header = [
        f"Favorable days for {person}",
        f"Nakshatram: {input_nakshatram}",
        f"City: {input_city_name}",
        f"Month: {month_entry['month']} {month_entry['year']}",
        "-" * 60,
    ]
    body = month_entry["fav_days_with_ts"] or ["No favorable days found."]
    return "\n".join(header + body) + "\n"


def _write_month_file(person, input_nakshatram, input_city_name, output_dir, month_entry):
    person_dir = Path(output_dir) / _slugify_person_name(person)
    person_dir.mkdir(parents=True, exist_ok=True)
    file_path = person_dir / f"{month_entry['month']}_{month_entry['year']}.txt"
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


def collate_and_save_predictions(
    person, input_nakshatram, input_city_name, starting_month_year, forward_looking_months, output_dir, favorable_days_with_ts
):
    """Collate every forward-looking month's favorable days into one consolidated JSON file.

    Reshapes `favorable_days_with_ts` (the list fetch_favorable_month_days
    builds up, one dict per month) into a single JSON document with a
    tabular "favorable_days" row list (columns: date, prediction) per month,
    and writes it to
    `{output_dir}/{slugified person}/{slugified person}_{slugified starting_month_year}_{forward_looking_months}.json`
    (the same per-person subfolder each month's .txt file already lives in).

    Returns the path the consolidated file was written to.
    """
    months_table = [
        {
            "month": month_entry["month"],
            "year": month_entry["year"],
            "favorable_days": [
                _split_favorable_entry_into_row(entry) for entry in month_entry["fav_days_with_ts"]
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
        "months": months_table,
    }

    person_dir = Path(output_dir) / _slugify_person_name(person)
    person_dir.mkdir(parents=True, exist_ok=True)
    file_name = (
        f"{_slugify_person_name(person)}_"
        f"{_slugify_for_filename(starting_month_year, label='starting_month_year')}_"
        f"{forward_looking_months}.json"
    )
    file_path = person_dir / file_name
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
    forward-looking month, under `{output_dir}/{person}/{Month}_{Year}.txt`
    (`person` is sanitized into a safe folder name for that subfolder). If
    `output_dir` isn't given, it defaults to `f"{person}_output_dir"` (a path
    relative to the current working directory). Each returned month dict
    gets an "output_file" key holding that path (a string).

    Once every month has been fetched and saved, all of them are also
    collated into one consolidated tabular JSON file (see
    collate_and_save_predictions) at
    `{output_dir}/{person}/{person}_{starting_month_year}_{forward_looking_months}.json`;
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

    favorable_indices = favorable_nakshatram_indices(input_nakshatram)
    geoname_id = resolve_geoname_id(input_city_name, chooser=city_chooser, interactive=interactive)
    start_year, start_month = _parse_month_year(starting_month_year)

    favorable_days_with_ts = []
    for year, month in _forward_looking_months(start_year, start_month, forward_looking_months):
        month_entries = []
        for day_date in _dates_in_month_for_weekdays(year, month, weekday_names):
            html = _fetch_day_panchang_html(
                geoname_id,
                day_date,
                use_cache=use_cache,
                cache_dir=cache_dir,
                request_delay_seconds=request_delay_seconds,
                session=session,
            )
            day_result = _parse_day_panchang(html, day_date)
            entry = _build_favorable_entry(day_result, favorable_indices)
            if entry is not None:
                month_entries.append(entry)

        month_result = {
            "month": calendar.month_name[month],
            "year": year,
            "fav_days_with_ts": month_entries,
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
    )
    for month_result in favorable_days_with_ts:
        month_result["consolidated_output_file"] = str(consolidated_file_path)

    return favorable_days_with_ts


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
        "--non-interactive",
        dest="interactive",
        action="store_false",
        default=True,
        help="Don't prompt to disambiguate an ambiguous city name; raise an error instead.",
    )
    return parser


def main(argv=None):
    """CLI entry point: `python3 panchangam_utils.py WEEKDAY [WEEKDAY ...] NAKSHATRAM CITY MONTH_YEAR PERSON [options]`.

    Wires argparse straight onto fetch_favorable_month_days's parameters,
    prints a per-month summary of favorable days to stdout, and reports
    which file each month's results were also saved to. Returns a process
    exit code (0 on success, 1 on a recognized error) rather than raising,
    so `sys.exit(main())` at the bottom of this file gives a clean CLI
    error message instead of a raw traceback for expected failure modes
    (bad input, an unresolvable/ambiguous city, or drikpanchang rate-limiting).
    """
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
        )
    except (ValueError, DrikPanchangBlockedError) as exc:
        # ValueError also covers AmbiguousCityError, a subclass.
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    for month_result in results:
        print(f"{month_result['month']} {month_result['year']}:")
        if month_result["fav_days_with_ts"]:
            for entry in month_result["fav_days_with_ts"]:
                print(f"  {entry}")
        else:
            print("  No favorable days found.")
        print(f"  (saved to {month_result['output_file']})")

    print(f"Consolidated summary saved to {results[0]['consolidated_output_file']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

