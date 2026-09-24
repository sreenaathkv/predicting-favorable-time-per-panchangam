import unittest
from datetime import date
from pathlib import Path

import panchangam_utils as pu
from panchangam_utils import (
    NAKSHATRAS,
    NUM_NAKSHATRAS,
    AmbiguousCityError,
    DrikPanchangBlockedError,
    favorable_nakshatram_indices,
    favorable_nakshatrams,
    fetch_favorable_month_days,
    next_27_nakshatras,
    resolve_geoname_id,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "tests_fixtures"


def load_fixture(name):
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def expected_order(start_index):
    """Build the expected 27-item order by rotating NAKSHATRAS from start_index."""
    return [
        NAKSHATRAS[(start_index + offset) % NUM_NAKSHATRAS]
        for offset in range(NUM_NAKSHATRAS)
    ]


class TestNext27Nakshatras(unittest.TestCase):
    def test_returns_27_items(self):
        result = next_27_nakshatras("Aswini")
        self.assertEqual(len(result), NUM_NAKSHATRAS)

    def test_start_index_0_no_wraparound(self):
        # Aswini is index 0 -> no wraparound needed.
        result = next_27_nakshatras("Aswini")
        self.assertEqual(result, expected_order(0))
        self.assertEqual(result[0]["Tamil"], "Aswini")
        self.assertEqual(result[-1]["Tamil"], "Ravathi")

    def test_start_index_10_no_wraparound(self):
        # Pooram is index 10.
        result = next_27_nakshatras("Pooram")
        self.assertEqual(result, expected_order(10))
        self.assertEqual(result[0]["Tamil"], "Pooram")
        self.assertEqual(result[17]["Tamil"], "Aswini")

    def test_start_index_20_wraps_around(self):
        # Uthiradam is index 20 -> wraps around after 7 items.
        result = next_27_nakshatras("Uthiradam")
        self.assertEqual(result, expected_order(20))
        expected_tamil_order = [
            "Uthiradam", "Thiruvonam", "Avittam", "Sadayam", "Poorattathi",
            "Uthirattathi", "Ravathi", "Aswini", "Bharani", "Karthigai",
            "Rohini", "Mrigasheersham", "Thiruvaathirai", "Punarpoosam",
            "Poosam", "Aayilyam", "Makam", "Pooram", "Uthiram", "Hastham",
            "Chithirai", "Swaathi", "Visaakam", "Anusham", "Kettai",
            "Moolam", "Pooraadam",
        ]
        self.assertEqual([n["Tamil"] for n in result], expected_tamil_order)

    def test_sample_input_alternate_spelling(self):
        # The alternate spelling "Uthiraadam" (double a) from the prompt's
        # sample input should resolve to the same result as "Uthiradam".
        result = next_27_nakshatras("Uthiraadam")
        self.assertEqual(result, next_27_nakshatras("Uthiradam"))

    def test_start_index_26_last_item_wraps_fully(self):
        # Ravathi is index 26 (the last nakshatra) -> wraps almost immediately.
        result = next_27_nakshatras("Ravathi")
        self.assertEqual(result, expected_order(26))
        self.assertEqual(result[0]["Tamil"], "Ravathi")
        self.assertEqual(result[1]["Tamil"], "Aswini")
        self.assertEqual(result[-1]["Tamil"], "Uthirattathi")

    def test_lookup_is_case_insensitive(self):
        self.assertEqual(
            next_27_nakshatras("aswini"), next_27_nakshatras("ASWINI")
        )

    def test_lookup_strips_whitespace(self):
        self.assertEqual(
            next_27_nakshatras("  Aswini  "), next_27_nakshatras("Aswini")
        )

    def test_lookup_by_sanskrit_name(self):
        result = next_27_nakshatras("Ashwini")
        self.assertEqual(result[0]["Tamil"], "Aswini")

    def test_lookup_by_devanagiri_sanskrit_script(self):
        result = next_27_nakshatras("अश्विनी")
        self.assertEqual(result[0]["Tamil"], "Aswini")

    def test_returned_dicts_have_expected_keys(self):
        result = next_27_nakshatras("Aswini")
        for item in result:
            self.assertEqual(set(item.keys()), {"Tamil", "Sanskrit", "English"})

    def test_result_does_not_mutate_source_list(self):
        next_27_nakshatras("Uthiradam")
        self.assertEqual(NAKSHATRAS[0]["Tamil"], "Aswini")
        self.assertEqual(len(NAKSHATRAS), 27)

    def test_unknown_nakshatra_raises_value_error(self):
        with self.assertRaises(ValueError):
            next_27_nakshatras("NotARealNakshatra")

    def test_empty_string_raises_value_error(self):
        with self.assertRaises(ValueError):
            next_27_nakshatras("")

    def test_whitespace_only_raises_value_error(self):
        with self.assertRaises(ValueError):
            next_27_nakshatras("   ")

    def test_non_string_raises_value_error(self):
        with self.assertRaises(ValueError):
            next_27_nakshatras(None)
        with self.assertRaises(ValueError):
            next_27_nakshatras(5)


class TestFavorableNakshatrams(unittest.TestCase):
    def test_sample_input_uthiradam(self):
        # Values from the prompt's sample (canonicalized spelling).
        result = favorable_nakshatrams("Uthiradam")
        expected_favorable = [
            "Thiruvonam", "Sadayam", "Uthirattathi", "Aswini", "Bharani",
            "Rohini", "Thiruvaathirai", "Poosam", "Makam", "Pooram",
            "Hastham", "Swaathi", "Anusham", "Moolam", "Pooraadam",
        ]
        self.assertEqual(result["favorable"], expected_favorable)

    def test_not_favorable_uthiradam(self):
        result = favorable_nakshatrams("Uthiradam")
        expected_not_favorable = [
            "Uthiradam", "Avittam", "Poorattathi", "Ravathi", "Karthigai",
            "Mrigasheersham", "Punarpoosam", "Aayilyam", "Uthiram",
            "Chithirai", "Visaakam", "Kettai",
        ]
        self.assertEqual(result["not_favorable"], expected_not_favorable)

    def test_returns_expected_keys_only(self):
        result = favorable_nakshatrams("Uthiradam")
        self.assertEqual(set(result.keys()), {"favorable", "not_favorable"})

    def test_favorable_and_not_favorable_counts(self):
        result = favorable_nakshatrams("Uthiradam")
        self.assertEqual(len(result["favorable"]), 15)
        self.assertEqual(len(result["not_favorable"]), 12)
        self.assertEqual(
            len(result["favorable"]) + len(result["not_favorable"]),
            NUM_NAKSHATRAS,
        )

    def test_lists_partition_all_27_with_no_overlap_or_duplicates(self):
        result = favorable_nakshatrams("Uthiradam")
        combined = result["favorable"] + result["not_favorable"]
        self.assertEqual(len(combined), len(set(combined)))
        all_tamil_names = {n["Tamil"] for n in NAKSHATRAS}
        self.assertEqual(set(combined), all_tamil_names)

    def test_argument_nakshatram_itself_is_not_favorable(self):
        # Position 1 (the given nakshatra, Janma tara) is always not_favorable.
        result = favorable_nakshatrams("Uthiradam")
        self.assertEqual(result["not_favorable"][0], "Uthiradam")
        self.assertNotIn("Uthiradam", result["favorable"])

    def test_start_index_0_boundary(self):
        # Aswini is index 0.
        result = favorable_nakshatrams("Aswini")
        ordered = [n["Tamil"] for n in next_27_nakshatras("Aswini")]
        favorable_positions = {2, 4, 6, 8, 9, 11, 13, 15, 17, 18, 20, 22, 24, 26, 27}
        expected_favorable = [
            name for i, name in enumerate(ordered, start=1)
            if i in favorable_positions
        ]
        expected_not_favorable = [
            name for i, name in enumerate(ordered, start=1)
            if i not in favorable_positions
        ]
        self.assertEqual(result["favorable"], expected_favorable)
        self.assertEqual(result["not_favorable"], expected_not_favorable)

    def test_start_index_10_boundary(self):
        # Pooram is index 10.
        result = favorable_nakshatrams("Pooram")
        self.assertEqual(len(result["favorable"]), 15)
        self.assertEqual(len(result["not_favorable"]), 12)
        self.assertEqual(result["not_favorable"][0], "Pooram")

    def test_start_index_26_boundary_wraps_around(self):
        # Ravathi is index 26 (last nakshatra) -> heavy wraparound.
        result = favorable_nakshatrams("Ravathi")
        self.assertEqual(len(result["favorable"]), 15)
        self.assertEqual(len(result["not_favorable"]), 12)
        self.assertEqual(result["not_favorable"][0], "Ravathi")
        # position 2 (favorable) wraps around to Aswini.
        self.assertEqual(result["favorable"][0], "Aswini")

    def test_lookup_by_english_name(self):
        result = favorable_nakshatrams("Uttara Ashadha")
        self.assertEqual(result, favorable_nakshatrams("Uthiradam"))

    def test_lookup_by_sanskrit_devanagiri(self):
        result = favorable_nakshatrams("उत्तराषाढा")
        self.assertEqual(result, favorable_nakshatrams("Uthiradam"))

    def test_lookup_is_case_insensitive(self):
        self.assertEqual(
            favorable_nakshatrams("uthiradam"),
            favorable_nakshatrams("UTHIRADAM"),
        )

    def test_alternate_spelling_alias(self):
        self.assertEqual(
            favorable_nakshatrams("Uthiraadam"),
            favorable_nakshatrams("Uthiradam"),
        )

    def test_unknown_nakshatram_raises_value_error(self):
        with self.assertRaises(ValueError):
            favorable_nakshatrams("NotARealNakshatra")

    def test_empty_string_raises_value_error(self):
        with self.assertRaises(ValueError):
            favorable_nakshatrams("")

    def test_non_string_raises_value_error(self):
        with self.assertRaises(ValueError):
            favorable_nakshatrams(None)


class TestFavorableNakshatramIndices(unittest.TestCase):
    def test_matches_favorable_nakshatrams_tamil_names(self):
        names_via_dict = set(favorable_nakshatrams("Uthiradam")["favorable"])
        names_via_indices = {
            NAKSHATRAS[i]["Tamil"] for i in favorable_nakshatram_indices("Uthiradam")
        }
        self.assertEqual(names_via_dict, names_via_indices)

    def test_returns_15_indices(self):
        self.assertEqual(len(favorable_nakshatram_indices("Aswini")), 15)

    def test_argument_nakshatram_index_excluded(self):
        self.assertNotIn(20, favorable_nakshatram_indices("Uthiradam"))

    def test_unknown_nakshatram_raises_value_error(self):
        with self.assertRaises(ValueError):
            favorable_nakshatram_indices("NotARealNakshatra")


class TestResolveGeonameId(unittest.TestCase):
    def test_chennai_matches_documented_example(self):
        # This is the exact geoname-id used in drikpanchang.com URLs for Chennai.
        self.assertEqual(resolve_geoname_id("Chennai"), 1264527)

    def test_case_insensitive(self):
        self.assertEqual(resolve_geoname_id("chennai"), resolve_geoname_id("CHENNAI"))

    def test_alternate_name_resolves(self):
        self.assertEqual(resolve_geoname_id("Madras"), 1264527)

    def test_unknown_city_raises_value_error(self):
        with self.assertRaises(ValueError):
            resolve_geoname_id("Zzzznotarealcityanywhere")

    def test_empty_string_raises_value_error(self):
        with self.assertRaises(ValueError):
            resolve_geoname_id("")

    def test_non_string_raises_value_error(self):
        with self.assertRaises(ValueError):
            resolve_geoname_id(None)


class TestAmbiguousCityDisambiguation(unittest.TestCase):
    """"London" exists in the UK (pop ~9M) and Ontario, Canada (pop ~420K);
    "Springfield" exists across 8+ US states. Ambiguous city names must no
    longer be silently resolved by picking the most populous match -- the
    caller must disambiguate, one way or another.
    """

    def test_ambiguous_city_raises_by_default_when_not_interactive(self):
        with self.assertRaises(AmbiguousCityError):
            resolve_geoname_id("London", interactive=False)

    def test_ambiguous_city_error_lists_all_candidates(self):
        with self.assertRaises(AmbiguousCityError) as ctx:
            resolve_geoname_id("London", interactive=False)
        candidate_countries = {c["countrycode"] for c in ctx.exception.candidates}
        self.assertEqual(candidate_countries, {"GB", "CA"})

    def test_qualifier_by_country_code_disambiguates(self):
        self.assertEqual(resolve_geoname_id("London, GB", interactive=False), 2643743)
        self.assertEqual(resolve_geoname_id("London, CA", interactive=False), 6058560)

    def test_qualifier_by_country_name_disambiguates(self):
        self.assertEqual(resolve_geoname_id("London, Canada", interactive=False), 6058560)
        self.assertEqual(
            resolve_geoname_id("London, United Kingdom", interactive=False), 2643743
        )

    def test_qualifier_by_us_state_code_disambiguates(self):
        # Sunnyvale, CA vs Sunnyvale, TX from the user's original report:
        # geonamescache's dataset only includes the CA one (TX's population
        # is below its inclusion threshold), so this exercises the same
        # qualifier mechanism against a city that genuinely has 8+ matches.
        self.assertEqual(resolve_geoname_id("Springfield, IL", interactive=False), 4250542)
        self.assertEqual(resolve_geoname_id("Springfield, MO", interactive=False), 4409896)

    def test_qualifier_by_us_state_name_disambiguates(self):
        self.assertEqual(
            resolve_geoname_id("Springfield, Illinois", interactive=False),
            resolve_geoname_id("Springfield, IL", interactive=False),
        )

    def test_qualifier_with_state_and_country_disambiguates(self):
        self.assertEqual(
            resolve_geoname_id("Springfield, IL, USA", interactive=False),
            resolve_geoname_id("Springfield, IL", interactive=False),
        )

    def test_unmatched_qualifier_falls_back_to_full_candidate_list(self):
        # "Springfield, Nowhereland" matches no candidate, so all candidates
        # for "Springfield" are still considered ambiguous rather than
        # silently returning zero results.
        with self.assertRaises(AmbiguousCityError) as ctx:
            resolve_geoname_id("Springfield, Nowhereland", interactive=False)
        self.assertGreater(len(ctx.exception.candidates), 1)

    def test_chooser_callable_disambiguates_programmatically(self):
        chosen = resolve_geoname_id(
            "Springfield",
            chooser=lambda candidates: next(c for c in candidates if c["admin1code"] == "MO"),
        )
        self.assertEqual(chosen, 4409896)

    def test_chooser_takes_precedence_over_interactive(self):
        # Even with interactive=True, a chooser should be used without
        # attempting to read from stdin (which would hang/fail in tests).
        chosen = resolve_geoname_id(
            "Springfield",
            interactive=True,
            chooser=lambda candidates: next(c for c in candidates if c["admin1code"] == "OH"),
        )
        self.assertEqual(chosen, 4525353)

    def test_unmatched_qualifier_with_single_candidate_warns_not_silently_wrong(self):
        # Sunnyvale, TX is the user's own original example, but geonamescache's
        # offline dataset only includes Sunnyvale, CA (TX's population is below
        # its inclusion threshold). Falling back to the CA match without any
        # signal would be exactly the silent-wrong-guess this feature exists
        # to prevent, so this must raise a warning even though it still
        # returns the only available match.
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = resolve_geoname_id("Sunnyvale, TX", interactive=False)
        self.assertEqual(result, 5400075)
        self.assertTrue(any("Sunnyvale" in str(w.message) and "TX" in str(w.message) for w in caught))

    def test_unambiguous_city_ignores_interactive_and_chooser(self):
        # Chennai has exactly one match, so neither prompting nor a chooser
        # should ever be invoked.
        def failing_chooser(candidates):
            raise AssertionError("chooser should not have been called")

        self.assertEqual(
            resolve_geoname_id("Chennai", interactive=True, chooser=failing_chooser), 1264527
        )


class TestMonthYearParsing(unittest.TestCase):
    def test_full_month_name(self):
        self.assertEqual(pu._parse_month_year("September 2026"), (2026, 9))

    def test_abbreviated_month_name(self):
        self.assertEqual(pu._parse_month_year("Sep 2026"), (2026, 9))

    def test_numeric_slash_format(self):
        self.assertEqual(pu._parse_month_year("09/2026"), (2026, 9))

    def test_iso_style_format(self):
        self.assertEqual(pu._parse_month_year("2026-09"), (2026, 9))

    def test_unparseable_format_raises_value_error(self):
        with self.assertRaises(ValueError):
            pu._parse_month_year("not a date")

    def test_empty_string_raises_value_error(self):
        with self.assertRaises(ValueError):
            pu._parse_month_year("")


class TestWeekdayAndMonthSequenceHelpers(unittest.TestCase):
    def test_normalize_weekday_name_case_insensitive(self):
        self.assertEqual(pu._normalize_weekday_name("monday"), "Monday")
        self.assertEqual(pu._normalize_weekday_name("MONDAY"), "Monday")

    def test_normalize_unknown_weekday_raises_value_error(self):
        with self.assertRaises(ValueError):
            pu._normalize_weekday_name("Someday")

    def test_dates_in_month_for_weekdays_matches_calendar(self):
        # January 2026: every Saturday.
        saturdays = pu._dates_in_month_for_weekdays(2026, 1, ["Saturday"])
        self.assertEqual(saturdays, [date(2026, 1, 3), date(2026, 1, 10), date(2026, 1, 17), date(2026, 1, 24), date(2026, 1, 31)])

    def test_dates_in_month_for_weekdays_multiple_days(self):
        # January 2026 has 5 Saturdays (3,10,17,24,31) and 4 Sundays (4,11,18,25).
        dates = pu._dates_in_month_for_weekdays(2026, 1, ["Saturday", "Sunday"])
        self.assertEqual(len(dates), 9)
        self.assertTrue(all(d.weekday() in (5, 6) for d in dates))

    def test_forward_looking_months_within_year(self):
        self.assertEqual(
            pu._forward_looking_months(2026, 9, 3),
            [(2026, 9), (2026, 10), (2026, 11)],
        )

    def test_forward_looking_months_rolls_over_new_year(self):
        self.assertEqual(
            pu._forward_looking_months(2026, 11, 4),
            [(2026, 11), (2026, 12), (2027, 1), (2027, 2)],
        )

    def test_forward_looking_months_default_count_of_12(self):
        months = pu._forward_looking_months(2026, 1, 12)
        self.assertEqual(len(months), 12)
        self.assertEqual(months[0], (2026, 1))
        self.assertEqual(months[-1], (2026, 12))


class TestParseDayPanchangFixtures(unittest.TestCase):
    """Parsing/favorability tests against real (or, for one case, hand-crafted) drikpanchang HTML."""

    def test_no_favorable_window_either_input(self):
        html = load_fixture("chennai_2026-01-01_none.html")
        result = pu._parse_day_panchang(html, date(2026, 1, 1))
        self.assertIsNone(pu._build_favorable_entry(result, favorable_nakshatram_indices("Uthiradam")))
        self.assertIsNone(pu._build_favorable_entry(result, favorable_nakshatram_indices("Bharani")))

    def test_entire_day_from_two_consecutive_favorable_nakshatras(self):
        # Nakshatram splits mid-day (Makam until 11:56 AM, then Pooram), and
        # Tamil Yogam splits at the very same moment (Siddha -> Amrutha).
        # Both nakshatras are favorable for "Uthiradam" and both yogams are
        # favorable too, so the two windows merge into "Entire day".
        html = load_fixture("chennai_2026-01-07_entire_day.html")
        result = pu._parse_day_panchang(html, date(2026, 1, 7))
        self.assertEqual(result["primary_nakshatram_for_the_day"], "Makam")
        self.assertEqual(result["secondary_nakshatram_of_the_day"], "Pooram")
        entry = pu._build_favorable_entry(result, favorable_nakshatram_indices("Uthiradam"))
        self.assertEqual(entry, "January 7, 2026 - Entire day")

    def test_split_nakshatram_gives_different_results_per_input(self):
        # Nakshatram splits mid-day (Mrigasheersham until 8:04 PM, then
        # Thiruvaathirai); Tamil Yogam splits at the same moment (Amrutha ->
        # Siddha). Mrigasheersham is favorable for "Bharani" but not
        # "Uthiradam", while Thiruvaathirai is the other way around, so the
        # same day's data yields a different partial-day result per input
        # nakshatram: this is the exact bug pattern a user reported, where
        # treating the day's nakshatram as a single all-day value (instead of
        # splitting it the same way Tamil Yogam splits) silently produced a
        # favorable-looking answer for a day/nakshatram pairing that should
        # not have been favorable at all.
        html = load_fixture("chennai_2026-01-02_split_nakshatram_and_yogam.html")
        result = pu._parse_day_panchang(html, date(2026, 1, 2))
        self.assertEqual(result["primary_nakshatram_for_the_day"], "Mrigasheersham")
        self.assertEqual(result["secondary_nakshatram_of_the_day"], "Thiruvaathirai")
        self.assertEqual(
            pu._build_favorable_entry(result, favorable_nakshatram_indices("Bharani")),
            "January 2, 2026 - until 08:04 PM",
        )
        self.assertEqual(
            pu._build_favorable_entry(result, favorable_nakshatram_indices("Uthiradam")),
            "January 2, 2026 - from 08:04 PM onwards",
        )

    def test_from_onwards_case(self):
        html = load_fixture("chennai_2026-01-03_from_onwards.html")
        result = pu._parse_day_panchang(html, date(2026, 1, 3))
        # Thiruvaathirai (until 5:27 PM, Marana yogam) is not favorable for
        # "Uthiradam" here since the yogam fails; Punarpoosam (after 5:27 PM)
        # isn't a favorable nakshatra for "Uthiradam" either, so the day is
        # not favorable at all for that input...
        self.assertIsNone(pu._build_favorable_entry(result, favorable_nakshatram_indices("Uthiradam")))
        # ...but Thiruvaathirai *is* favorable for "Bharani", and it has
        # Marana (not favorable) until 5:27 PM, Siddha (favorable) after.
        entry = pu._build_favorable_entry(result, favorable_nakshatram_indices("Bharani"))
        self.assertEqual(entry, "January 3, 2026 - from 05:27 PM onwards")

    def test_until_case(self):
        html = load_fixture("chennai_2026-01-06_until.html")
        result = pu._parse_day_panchang(html, date(2026, 1, 6))
        entry = pu._build_favorable_entry(result, favorable_nakshatram_indices("Bharani"))
        self.assertEqual(entry, "January 6, 2026 - until 12:17 PM")

    def test_two_nakshatram_segments_in_one_day(self):
        # Real drikpanchang data can show 2 same-day Nakshathram transitions.
        html = load_fixture("chennai_2026-01-29_two_nakshatram_segments.html")
        result = pu._parse_day_panchang(html, date(2026, 1, 29))
        self.assertEqual(result["primary_nakshatram_for_the_day"], "Rohini")
        self.assertEqual(result["secondary_nakshatram_of_the_day"], "Mrigasheersham")
        self.assertEqual(len(result["_nakshatram_segments"]), 2)

    def test_three_tamil_yogam_segments_in_one_day(self):
        # Real drikpanchang data can show 3 same-day Tamil Yoga transitions
        # (Amrutha until 1:28 PM, Marana until 9:29 PM, Marana after) with
        # cutoff times completely independent of Nakshathram's own single
        # same-day transition (Uthiradam until 7:48 PM, then Thiruvonam) --
        # neither the segment count nor the cutoff times need to match
        # between the two. For "Bharani", Uthiradam is favorable but
        # Thiruvonam is not, and Amrutha is favorable but Marana is not, so
        # the binding cutoff here ends up being Tamil Yogam's (1:28 PM), not
        # Nakshathram's (7:48 PM).
        html = load_fixture("chennai_2026-02-15_three_yogam_segments.html")
        result = pu._parse_day_panchang(html, date(2026, 2, 15))
        self.assertEqual(result["secondary_nakshatram_of_the_day"], "Thiruvonam")
        self.assertEqual(len(result["_tam_yogam_segments"]), 3)
        entry = pu._build_favorable_entry(result, favorable_nakshatram_indices("Bharani"))
        self.assertEqual(entry, "February 15, 2026 - until 01:28 PM")

    def test_multi_window_disjoint_favorable_ranges(self):
        # Hand-crafted fixture: nakshatram is favorable and constant all day,
        # but Tamil Yogam goes favorable -> unfavorable -> favorable, which
        # must produce two separate ranges joined in one string. The
        # nakshatram's own "upto" also crosses into the next day (Jan 2, 3:00
        # AM), so the trailing range additionally reports that continuation.
        html = load_fixture("synthetic_multi_window.html")
        result = pu._parse_day_panchang(html, date(2026, 1, 1))
        entry = pu._build_favorable_entry(result, favorable_nakshatram_indices("Uthiradam"))
        self.assertEqual(
            entry,
            "January 1, 2026 - until 10:00 AM; "
            "from 06:00 PM onwards (favorable until January 2, 2026 03:00 AM)",
        )

    def test_entire_day_crossing_into_next_day_reports_continuation(self):
        # Regression test for a real user-reported bug: for Sunnyvale, CA on
        # Oct 17, 2026, Pooradam (favorable for "Uthiradam") and Amrutha
        # yogam both hold "upto 12:19 AM, Oct 18" -- i.e. the entire calendar
        # day of Oct 17 is favorable, continuing into the small hours of Oct
        # 18. This used to be reported as "October 17, 2026 - until 12:19 AM"
        # (implying an ordinary same-day cutoff at 12:19 AM *that morning*)
        # because _parse_tamil_yoga_segments never checked whether a
        # segment's own cutoff crossed into the next calendar day (unlike
        # the nakshatram parser, which already did) -- so it wrongly treated
        # the *next day's* Tamil Yogam value ("Marana") as if it applied to
        # the rest of Oct 17. The correct answer is "Entire day", and since
        # we know exactly how far into Oct 18 it actually continues, that's
        # surfaced too instead of silently dropping the information.
        html = load_fixture("sunnyvale_2026-10-17_entire_day_crosses_next_day.html")
        result = pu._parse_day_panchang(html, date(2026, 10, 17))
        self.assertEqual(result["primary_nakshatram_for_the_day"], "Pooraadam")
        self.assertIsNone(result["secondary_nakshatram_of_the_day"])
        self.assertEqual(result["primary_tam_yogam_for_the_day"], "Amrutha")
        self.assertIsNone(result["secondary_tam_yogam_of_the_day"])
        entry = pu._build_favorable_entry(result, favorable_nakshatram_indices("Uthiradam"))
        self.assertEqual(entry, "October 17, 2026 - Entire day (favorable until October 18, 2026 12:19 AM)")

    def test_captcha_blocked_page_raises_specific_error(self):
        html = load_fixture("captcha_blocked.html")
        with self.assertRaises(DrikPanchangBlockedError):
            pu._parse_day_panchang(html, date(2026, 1, 1))


class _FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


class _FixtureSession:
    """Fake `requests`-like session serving pre-loaded HTML keyed by the 'date' query param."""

    def __init__(self, html_by_date, default_html=None):
        self.html_by_date = html_by_date
        self.default_html = default_html
        self.requested_dates = []

    def get(self, url, params=None, headers=None, timeout=None):
        date_str = params["date"]
        self.requested_dates.append(date_str)
        if date_str in self.html_by_date:
            return _FakeResponse(self.html_by_date[date_str])
        if self.default_html is not None:
            return _FakeResponse(self.default_html)
        raise AssertionError(f"No fixture registered for requested date {date_str!r}")


class _FailingSession:
    """Fake session that fails any request, to prove a code path never hits the network."""

    def get(self, *args, **kwargs):
        raise AssertionError("No network request should have been made")


class TestFetchFavorableMonthDaysIntegration(unittest.TestCase):
    def _january_2026_saturday_session(self):
        # Saturdays in January 2026: 3, 10, 17, 24, 31. Only the 3rd and 17th
        # have specific fixtures registered; the rest fall back to a fixture
        # that's not favorable for "Uthiradam" (or any nakshatram, since its
        # Tamil Yogam is Marana all day) so they don't contribute an entry.
        none_html = load_fixture("chennai_2026-01-01_none.html")
        return _FixtureSession(
            html_by_date={
                "03/01/2026": load_fixture("chennai_2026-01-03_from_onwards.html"),
                "17/01/2026": load_fixture("chennai_2026-01-17_from_onwards_both.html"),
            },
            default_html=none_html,
        )

    def test_aggregates_favorable_days_for_one_month(self):
        import tempfile

        session = self._january_2026_saturday_session()
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = fetch_favorable_month_days(
                ["Saturday"],
                "Uthiradam",
                "Chennai",
                "January 2026",
                forward_looking_months=1,
                person="TestPerson",
                output_dir=tmp_dir,
                use_cache=False,
                request_delay_seconds=0,
                session=session,
            )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["month"], "January")
        self.assertEqual(result[0]["year"], 2026)
        # January 3's data is favorable for "Bharani" but not "Uthiradam"
        # (see test_from_onwards_case), so only the 17th contributes here.
        self.assertEqual(
            result[0]["fav_days_with_ts"],
            [
                "January 17, 2026 - from 08:12 AM onwards",
            ],
        )
        # 5 Saturdays in January 2026: 3, 10, 17, 24, 31.
        self.assertEqual(len(session.requested_dates), 5)

    def test_forward_looking_months_count_matches_request(self):
        import tempfile

        none_html = load_fixture("chennai_2026-01-01_none.html")
        session = _FixtureSession(html_by_date={}, default_html=none_html)
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = fetch_favorable_month_days(
                ["Monday"],
                "Uthiradam",
                "Chennai",
                "November 2026",
                forward_looking_months=4,
                person="TestPerson",
                output_dir=tmp_dir,
                use_cache=False,
                request_delay_seconds=0,
                session=session,
            )
        self.assertEqual(len(result), 4)
        self.assertEqual(
            [(m["month"], m["year"]) for m in result],
            [("November", 2026), ("December", 2026), ("January", 2027), ("February", 2027)],
        )
        # A month with nothing favorable should still contribute an (empty) entry.
        self.assertEqual(result[0]["fav_days_with_ts"], [])

    def test_default_forward_looking_months_is_12(self):
        import tempfile

        none_html = load_fixture("chennai_2026-01-01_none.html")
        session = _FixtureSession(html_by_date={}, default_html=none_html)
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = fetch_favorable_month_days(
                ["Monday"],
                "Uthiradam",
                "Chennai",
                "January 2026",
                person="TestPerson",
                output_dir=tmp_dir,
                use_cache=False,
                request_delay_seconds=0,
                session=session,
            )
        self.assertEqual(len(result), 12)

    def test_disk_cache_avoids_repeat_network_calls(self):
        import tempfile

        with tempfile.TemporaryDirectory() as cache_tmp_dir, tempfile.TemporaryDirectory() as output_tmp_dir:
            session = self._january_2026_saturday_session()
            first = fetch_favorable_month_days(
                ["Saturday"],
                "Uthiradam",
                "Chennai",
                "January 2026",
                forward_looking_months=1,
                person="TestPerson",
                output_dir=output_tmp_dir,
                use_cache=True,
                cache_dir=cache_tmp_dir,
                request_delay_seconds=0,
                session=session,
            )
            cached_files = list(Path(cache_tmp_dir).glob("*.html"))
            self.assertEqual(len(cached_files), 5)

            second = fetch_favorable_month_days(
                ["Saturday"],
                "Uthiradam",
                "Chennai",
                "January 2026",
                forward_looking_months=1,
                person="TestPerson",
                output_dir=output_tmp_dir,
                use_cache=True,
                cache_dir=cache_tmp_dir,
                request_delay_seconds=0,
                session=_FailingSession(),
            )
            self.assertEqual(first, second)

    def test_empty_fav_days_of_week_raises_value_error(self):
        with self.assertRaises(ValueError):
            fetch_favorable_month_days(
                [], "Uthiradam", "Chennai", "January 2026", person="Test", session=_FailingSession()
            )

    def test_unknown_weekday_raises_value_error(self):
        with self.assertRaises(ValueError):
            fetch_favorable_month_days(
                ["Someday"], "Uthiradam", "Chennai", "January 2026", person="Test", session=_FailingSession()
            )

    def test_unknown_nakshatram_raises_value_error(self):
        with self.assertRaises(ValueError):
            fetch_favorable_month_days(
                ["Monday"], "NotARealNakshatra", "Chennai", "January 2026", person="Test", session=_FailingSession()
            )

    def test_unknown_city_raises_value_error(self):
        with self.assertRaises(ValueError):
            fetch_favorable_month_days(
                ["Monday"], "Uthiradam", "Zzzznotarealcity", "January 2026", person="Test", session=_FailingSession()
            )

    def test_bad_month_year_format_raises_value_error(self):
        with self.assertRaises(ValueError):
            fetch_favorable_month_days(
                ["Monday"], "Uthiradam", "Chennai", "not a month", person="Test", session=_FailingSession()
            )

    def test_missing_person_raises_type_error(self):
        # person is a mandatory keyword-only argument.
        with self.assertRaises(TypeError):
            fetch_favorable_month_days(
                ["Monday"], "Uthiradam", "Chennai", "January 2026", session=_FailingSession()
            )

    def test_ambiguous_city_raises_before_any_network_request(self):
        # "Springfield" (no state given) is ambiguous; this must fail during
        # input validation, never reaching the fetch loop.
        with self.assertRaises(AmbiguousCityError):
            fetch_favorable_month_days(
                ["Monday"],
                "Uthiradam",
                "Springfield",
                "January 2026",
                person="Test",
                interactive=False,
                session=_FailingSession(),
            )

    def test_ambiguous_city_resolved_via_qualifier(self):
        import tempfile

        none_html = load_fixture("chennai_2026-01-01_none.html")
        session = _FixtureSession(html_by_date={}, default_html=none_html)
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = fetch_favorable_month_days(
                ["Monday"],
                "Uthiradam",
                "Springfield, IL",
                "January 2026",
                forward_looking_months=1,
                person="TestPerson",
                output_dir=tmp_dir,
                use_cache=False,
                request_delay_seconds=0,
                session=session,
            )
        self.assertEqual(len(result), 1)

    def test_ambiguous_city_resolved_via_chooser(self):
        import tempfile

        none_html = load_fixture("chennai_2026-01-01_none.html")
        session = _FixtureSession(html_by_date={}, default_html=none_html)
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = fetch_favorable_month_days(
                ["Monday"],
                "Uthiradam",
                "Springfield",
                "January 2026",
                forward_looking_months=1,
                person="TestPerson",
                output_dir=tmp_dir,
                use_cache=False,
                request_delay_seconds=0,
                session=session,
                city_chooser=lambda candidates: next(c for c in candidates if c["admin1code"] == "MO"),
            )
        self.assertEqual(len(result), 1)


class TestSlugifyPersonName(unittest.TestCase):
    def test_spaces_become_underscores(self):
        self.assertEqual(pu._slugify_person_name("Sree Naath"), "Sree_Naath")

    def test_strips_leading_trailing_whitespace(self):
        self.assertEqual(pu._slugify_person_name("  Sree  "), "Sree")

    def test_collapses_internal_whitespace_runs(self):
        self.assertEqual(pu._slugify_person_name("Sree   Naath"), "Sree_Naath")

    def test_removes_path_separators_and_special_characters(self):
        self.assertEqual(pu._slugify_person_name("Sree/Naath"), "SreeNaath")
        self.assertEqual(pu._slugify_person_name("Sree.Naath!"), "SreeNaath")

    def test_path_traversal_attempt_cannot_escape_output_dir(self):
        slug = pu._slugify_person_name("../../etc/passwd")
        self.assertNotIn("/", slug)
        self.assertNotIn("..", slug)

    def test_keeps_hyphens_and_underscores(self):
        self.assertEqual(pu._slugify_person_name("Sree-Naath_Jr"), "Sree-Naath_Jr")

    def test_empty_string_raises_value_error(self):
        with self.assertRaises(ValueError):
            pu._slugify_person_name("")

    def test_whitespace_only_raises_value_error(self):
        with self.assertRaises(ValueError):
            pu._slugify_person_name("   ")

    def test_non_string_raises_value_error(self):
        with self.assertRaises(ValueError):
            pu._slugify_person_name(None)

    def test_all_special_characters_raises_value_error(self):
        # Sanitizes down to an empty string -- nothing usable as a folder name.
        with self.assertRaises(ValueError):
            pu._slugify_person_name("!!!///...")


class TestSlugifyCityName(unittest.TestCase):
    def test_plain_city_name_is_unchanged(self):
        self.assertEqual(pu._slugify_city_name("Sunnyvale"), "Sunnyvale")

    def test_state_and_country_qualifiers_are_kept_but_sanitized(self):
        self.assertEqual(pu._slugify_city_name("Springfield, IL"), "Springfield_IL")
        self.assertEqual(
            pu._slugify_city_name("Springfield, Illinois, USA"), "Springfield_Illinois_USA"
        )

    def test_multi_word_city_name(self):
        self.assertEqual(pu._slugify_city_name("New York"), "New_York")

    def test_path_traversal_attempt_cannot_escape_person_dir(self):
        slug = pu._slugify_city_name("../../etc")
        self.assertNotIn("/", slug)
        self.assertNotIn("..", slug)

    def test_empty_or_unsanitizable_city_raises_value_error(self):
        for bad in ("", "   ", None, "///..."):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                pu._slugify_city_name(bad)


class TestFetchFavorableMonthDaysOutputFiles(unittest.TestCase):
    def _empty_month_session(self):
        return _FixtureSession(
            html_by_date={}, default_html=load_fixture("chennai_2026-01-01_none.html")
        )

    def test_params_after_forward_looking_months_are_keyword_only(self):
        # Regression test for a real user-reported bug: calling
        # fetch_favorable_month_days(..., 1, "sreenaath", "output_results")
        # positionally silently bound "sreenaath" to use_cache and
        # "output_results" to cache_dir instead of person/output_dir --
        # no error, just quietly wrong behavior (drikpanchang HTML pages
        # cached into what the user thought was their output folder, and
        # no person-named folder or .txt files ever created). Every
        # parameter after forward_looking_months must stay keyword-only so
        # this fails loudly instead.
        with self.assertRaises(TypeError):
            fetch_favorable_month_days(
                ["Monday"], "Uthiradam", "Chennai", "January 2026", 1, "sreenaath", "output_results"
            )

    def test_person_must_be_a_non_empty_string(self):
        with self.assertRaises(ValueError):
            fetch_favorable_month_days(
                ["Monday"],
                "Uthiradam",
                "Chennai",
                "January 2026",
                forward_looking_months=1,
                person="   ",
                use_cache=False,
                request_delay_seconds=0,
                session=self._empty_month_session(),
            )

    def test_missing_person_raises_type_error(self):
        # person has no default -- omitting it entirely must fail loudly,
        # rather than e.g. silently defaulting to None and blowing up later
        # (or worse, succeeding with a nonsensical folder name).
        with self.assertRaises(TypeError):
            fetch_favorable_month_days(
                ["Monday"],
                "Uthiradam",
                "Chennai",
                "January 2026",
                forward_looking_months=1,
                use_cache=False,
                request_delay_seconds=0,
                session=self._empty_month_session(),
            )

    def test_omitting_output_dir_defaults_to_person_plus_output_dir_suffix(self):
        # Regression/feature test: when output_dir isn't given, it must
        # default to f"{person}_output_dir", a path relative to the current
        # working directory -- not silently skip writing (the old behavior)
        # and not require output_dir to be given explicitly.
        import os
        import tempfile

        original_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)
            try:
                result = fetch_favorable_month_days(
                    ["Monday"],
                    "Uthiradam",
                    "Chennai",
                    "January 2026",
                    forward_looking_months=1,
                    person="sreenaath",
                    use_cache=False,
                    request_delay_seconds=0,
                    session=self._empty_month_session(),
                )
            finally:
                os.chdir(original_cwd)

            expected_dir = Path(tmp_dir) / "sreenaath_output_dir" / "sreenaath" / "Chennai"
            self.assertTrue(expected_dir.is_dir())
            expected_file = expected_dir / "January_2026.txt"
            self.assertTrue(expected_file.exists())
            # output_file is recorded as given to Path() -- since the default
            # output_dir is a relative string, the recorded path stays
            # relative (to whatever the cwd was at call time) too.
            self.assertEqual(
                result[0]["output_file"],
                str(Path("sreenaath_output_dir") / "sreenaath" / "Chennai" / "January_2026.txt"),
            )

    def test_default_output_dir_is_relative_not_absolute(self):
        import os
        import tempfile

        original_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)
            try:
                fetch_favorable_month_days(
                    ["Monday"],
                    "Uthiradam",
                    "Chennai",
                    "January 2026",
                    forward_looking_months=1,
                    person="sreenaath",
                    use_cache=False,
                    request_delay_seconds=0,
                    session=self._empty_month_session(),
                )
            finally:
                os.chdir(original_cwd)

            # Nothing should have leaked outside the current directory at
            # the time of the call.
            self.assertFalse((Path(tmp_dir).parent / "sreenaath_output_dir").exists())

    def test_explicit_output_dir_still_takes_precedence_over_default(self):
        import os
        import tempfile

        # Run from an empty working directory so a real (gitignored)
        # "Sreenaath_output_dir" left in scripts/ by a genuine run can't make
        # this pass or fail (macOS file systems are case-insensitive).
        cwd_dir = tempfile.TemporaryDirectory()
        self.addCleanup(cwd_dir.cleanup)
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(cwd_dir.name)

        with tempfile.TemporaryDirectory() as tmp_dir:
            result = fetch_favorable_month_days(
                ["Monday"],
                "Uthiradam",
                "Chennai",
                "January 2026",
                forward_looking_months=1,
                person="sreenaath",
                output_dir=tmp_dir,
                use_cache=False,
                request_delay_seconds=0,
                session=self._empty_month_session(),
            )
            self.assertEqual(
                result[0]["output_file"], str(Path(tmp_dir) / "sreenaath" / "Chennai" / "January_2026.txt")
            )
            self.assertFalse((Path.cwd() / "sreenaath_output_dir").exists())

    def test_writes_one_file_per_forward_looking_month(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            result = fetch_favorable_month_days(
                ["Monday"],
                "Uthiradam",
                "Chennai",
                "January 2026",
                forward_looking_months=3,
                use_cache=False,
                request_delay_seconds=0,
                session=self._empty_month_session(),
                person="Sreenaath",
                output_dir=tmp_dir,
            )
            person_dir = Path(tmp_dir) / "Sreenaath" / "Chennai"
            written_files = sorted(p.name for p in person_dir.glob("*.txt"))
            self.assertEqual(
                written_files, ["February_2026.txt", "January_2026.txt", "March_2026.txt"]
            )
            for month_entry in result:
                self.assertEqual(
                    month_entry["output_file"],
                    str(person_dir / f"{month_entry['month']}_{month_entry['year']}.txt"),
                )

    def test_file_contents_include_person_nakshatram_city_and_favorable_days(self):
        import tempfile

        session = _FixtureSession(
            html_by_date={"03/01/2026": load_fixture("chennai_2026-01-03_from_onwards.html")},
            default_html=load_fixture("chennai_2026-01-01_none.html"),
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            fetch_favorable_month_days(
                ["Saturday"],
                "Bharani",
                "Chennai",
                "January 2026",
                forward_looking_months=1,
                use_cache=False,
                request_delay_seconds=0,
                session=session,
                person="Sreenaath",
                output_dir=tmp_dir,
            )
            contents = (Path(tmp_dir) / "Sreenaath" / "Chennai" / "January_2026.txt").read_text()
        self.assertIn("Favorable days for Sreenaath", contents)
        self.assertIn("Nakshatram: Bharani", contents)
        self.assertIn("City: Chennai", contents)
        self.assertIn("Month: January 2026", contents)
        self.assertIn("January 3, 2026 - from 05:27 PM onwards", contents)

    def test_empty_month_file_says_no_favorable_days_found(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            fetch_favorable_month_days(
                ["Monday"],
                "Uthiradam",
                "Chennai",
                "January 2026",
                forward_looking_months=1,
                use_cache=False,
                request_delay_seconds=0,
                session=self._empty_month_session(),
                person="Sreenaath",
                output_dir=tmp_dir,
            )
            contents = (Path(tmp_dir) / "Sreenaath" / "Chennai" / "January_2026.txt").read_text()
        self.assertIn("No favorable days found.", contents)

    def test_person_name_with_spaces_is_sanitized_into_folder_name(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            fetch_favorable_month_days(
                ["Monday"],
                "Uthiradam",
                "Chennai",
                "January 2026",
                forward_looking_months=1,
                use_cache=False,
                request_delay_seconds=0,
                session=self._empty_month_session(),
                person="Sree Naath",
                output_dir=tmp_dir,
            )
            self.assertTrue((Path(tmp_dir) / "Sree_Naath" / "Chennai" / "January_2026.txt").exists())

    def test_output_files_are_overwritten_on_repeat_calls(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            for _ in range(2):
                fetch_favorable_month_days(
                    ["Monday"],
                    "Uthiradam",
                    "Chennai",
                    "January 2026",
                    forward_looking_months=1,
                    use_cache=False,
                    request_delay_seconds=0,
                    session=self._empty_month_session(),
                    person="Sreenaath",
                    output_dir=tmp_dir,
                )
            person_dir = Path(tmp_dir) / "Sreenaath" / "Chennai"
            self.assertEqual(len(list(person_dir.glob("*.txt"))), 1)

    def test_same_person_different_cities_do_not_overwrite_each_other(self):
        # Regression test: results used to live directly under
        # {output_dir}/{person}/, and neither the .txt nor the .json file name
        # carries the city, so running the same person/month for a second
        # city silently overwrote the first city's results.
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            for city in ("Chennai", "Sunnyvale"):
                fetch_favorable_month_days(
                    ["Monday"],
                    "Uthiradam",
                    city,
                    "January 2026",
                    forward_looking_months=1,
                    use_cache=False,
                    request_delay_seconds=0,
                    session=self._empty_month_session(),
                    person="Sreenaath",
                    output_dir=tmp_dir,
                )
            person_dir = Path(tmp_dir) / "Sreenaath"
            self.assertEqual(sorted(p.name for p in person_dir.iterdir()), ["Chennai", "Sunnyvale"])
            for city in ("Chennai", "Sunnyvale"):
                with self.subTest(city=city):
                    txt = person_dir / city / "January_2026.txt"
                    self.assertIn(f"City: {city}", txt.read_text())
                    self.assertTrue((person_dir / city / "Sreenaath_January_2026_1.json").exists())

    def test_qualified_city_name_is_sanitized_into_folder_name(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            result = fetch_favorable_month_days(
                ["Monday"],
                "Uthiradam",
                "Sunnyvale, CA",
                "January 2026",
                forward_looking_months=1,
                use_cache=False,
                request_delay_seconds=0,
                session=self._empty_month_session(),
                person="Sreenaath",
                output_dir=tmp_dir,
            )
            expected_dir = Path(tmp_dir) / "Sreenaath" / "Sunnyvale_CA"
            self.assertEqual(result[0]["output_file"], str(expected_dir / "January_2026.txt"))
            self.assertEqual(
                result[0]["consolidated_output_file"],
                str(expected_dir / "Sreenaath_January_2026_1.json"),
            )


class TestSplitFavorableEntryIntoRow(unittest.TestCase):
    """Unit tests for _split_favorable_entry_into_row, the tabular-row helper
    collate_and_save_predictions uses to turn display strings into columns.
    """

    def test_entire_day_entry(self):
        row = pu._split_favorable_entry_into_row("January 7, 2026 - Entire day")
        self.assertEqual(row, {"date": "January 7, 2026", "prediction": "Entire day"})

    def test_until_entry(self):
        row = pu._split_favorable_entry_into_row("January 6, 2026 - until 12:17 PM")
        self.assertEqual(row, {"date": "January 6, 2026", "prediction": "until 12:17 PM"})

    def test_from_onwards_entry(self):
        row = pu._split_favorable_entry_into_row("January 3, 2026 - from 05:27 PM onwards")
        self.assertEqual(row, {"date": "January 3, 2026", "prediction": "from 05:27 PM onwards"})

    def test_entire_day_with_continuation_entry(self):
        row = pu._split_favorable_entry_into_row(
            "October 17, 2026 - Entire day (favorable until October 18, 2026 12:19 AM)"
        )
        self.assertEqual(
            row,
            {
                "date": "October 17, 2026",
                "prediction": "Entire day (favorable until October 18, 2026 12:19 AM)",
            },
        )

    def test_multi_window_entry_keeps_full_remainder_as_one_prediction(self):
        # A semicolon-joined multi-window entry isn't split any further --
        # the whole "until X; from Y onwards" remainder is one column value.
        row = pu._split_favorable_entry_into_row(
            "January 1, 2026 - until 10:00 AM; from 06:00 PM onwards"
        )
        self.assertEqual(
            row,
            {"date": "January 1, 2026", "prediction": "until 10:00 AM; from 06:00 PM onwards"},
        )


class TestCollateAndSavePredictions(unittest.TestCase):
    """Unit tests for the collate_and_save_predictions() utility itself, independent
    of fetch_favorable_month_days.
    """

    def _sample_favorable_days_with_ts(self):
        return [
            {
                "month": "September",
                "year": 2026,
                "fav_days_with_ts": [
                    "September 4, 2026 - until 10:34 AM",
                    "September 7, 2026 - Entire day",
                ],
                "output_file": "irrelevant.txt",
            },
            {
                "month": "October",
                "year": 2026,
                "fav_days_with_ts": [],
                "output_file": "irrelevant2.txt",
            },
        ]

    def test_writes_json_file_with_expected_name(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = pu.collate_and_save_predictions(
                "Sreenaath",
                "Uthiradam",
                "Sunnyvale",
                "September 2026",
                2,
                tmp_dir,
                self._sample_favorable_days_with_ts(),
            )
            self.assertEqual(
                file_path,
                Path(tmp_dir) / "Sreenaath" / "Sunnyvale" / "Sreenaath_September_2026_2.json",
            )
            self.assertTrue(file_path.exists())

    def test_json_content_structure_and_metadata(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = pu.collate_and_save_predictions(
                "Sreenaath",
                "Uthiradam",
                "Sunnyvale",
                "September 2026",
                2,
                tmp_dir,
                self._sample_favorable_days_with_ts(),
            )
            data = json.loads(file_path.read_text(encoding="utf-8"))

        self.assertEqual(data["person"], "Sreenaath")
        self.assertEqual(data["input_nakshatram"], "Uthiradam")
        self.assertEqual(data["input_city_name"], "Sunnyvale")
        self.assertEqual(data["starting_month_year"], "September 2026")
        self.assertEqual(data["forward_looking_months"], 2)
        self.assertEqual(len(data["months"]), 2)

    def test_tabular_rows_per_month(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = pu.collate_and_save_predictions(
                "Sreenaath",
                "Uthiradam",
                "Sunnyvale",
                "September 2026",
                2,
                tmp_dir,
                self._sample_favorable_days_with_ts(),
            )
            data = json.loads(file_path.read_text(encoding="utf-8"))

        september = data["months"][0]
        self.assertEqual(september["month"], "September")
        self.assertEqual(september["year"], 2026)
        self.assertEqual(
            september["favorable_days"],
            [
                {"date": "September 4, 2026", "prediction": "until 10:34 AM"},
                {"date": "September 7, 2026", "prediction": "Entire day"},
            ],
        )

    def test_month_with_no_favorable_days_gets_empty_row_list(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = pu.collate_and_save_predictions(
                "Sreenaath",
                "Uthiradam",
                "Sunnyvale",
                "September 2026",
                2,
                tmp_dir,
                self._sample_favorable_days_with_ts(),
            )
            data = json.loads(file_path.read_text(encoding="utf-8"))

        october = data["months"][1]
        self.assertEqual(october["month"], "October")
        self.assertEqual(october["favorable_days"], [])

    def test_filename_sanitizes_person_and_month_year_but_content_keeps_originals(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = pu.collate_and_save_predictions(
                "Sree Naath",
                "Uthiradam",
                "Sunnyvale",
                "September 2026",
                1,
                tmp_dir,
                [{"month": "September", "year": 2026, "fav_days_with_ts": [], "output_file": "x"}],
            )
            self.assertEqual(file_path.name, "Sree_Naath_September_2026_1.json")
            self.assertEqual(file_path.parent.name, "Sunnyvale")
            self.assertEqual(file_path.parent.parent.name, "Sree_Naath")
            data = json.loads(file_path.read_text(encoding="utf-8"))
        # The raw (unsanitized) person name is preserved in the file's content.
        self.assertEqual(data["person"], "Sree Naath")

    def test_lives_in_same_person_city_subfolder_as_monthly_txt_files(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            month_result = {
                "month": "September",
                "year": 2026,
                "fav_days_with_ts": ["September 4, 2026 - until 10:34 AM"],
            }
            txt_path = pu._write_month_file("Sreenaath", "Uthiradam", "Sunnyvale", tmp_dir, month_result)
            json_path = pu.collate_and_save_predictions(
                "Sreenaath", "Uthiradam", "Sunnyvale", "September 2026", 1, tmp_dir, [month_result]
            )
            self.assertEqual(txt_path.parent, json_path.parent)

    def test_returns_pathlib_path_pointing_to_written_file(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = pu.collate_and_save_predictions(
                "Sreenaath",
                "Uthiradam",
                "Sunnyvale",
                "September 2026",
                1,
                tmp_dir,
                [{"month": "September", "year": 2026, "fav_days_with_ts": [], "output_file": "x"}],
            )
            self.assertIsInstance(file_path, Path)
            self.assertTrue(file_path.is_file())


class TestFetchFavorableMonthDaysCollation(unittest.TestCase):
    """Confirms fetch_favorable_month_days wires collate_and_save_predictions into
    its main workflow automatically, after all per-month files are saved.
    """

    def _empty_month_session(self):
        return _FixtureSession(
            html_by_date={}, default_html=load_fixture("chennai_2026-01-01_none.html")
        )

    def test_consolidated_file_created_alongside_monthly_files(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            result = fetch_favorable_month_days(
                ["Monday"],
                "Uthiradam",
                "Chennai",
                "January 2026",
                forward_looking_months=2,
                person="Sreenaath",
                output_dir=tmp_dir,
                use_cache=False,
                request_delay_seconds=0,
                session=self._empty_month_session(),
            )
            person_dir = Path(tmp_dir) / "Sreenaath" / "Chennai"
            consolidated_path = person_dir / "Sreenaath_January_2026_2.json"
            self.assertTrue(consolidated_path.exists())
            # The monthly .txt files are still there too, side by side.
            self.assertTrue((person_dir / "January_2026.txt").exists())
            self.assertTrue((person_dir / "February_2026.txt").exists())

            data = json.loads(consolidated_path.read_text(encoding="utf-8"))
            self.assertEqual(len(data["months"]), 2)

        for month_result in result:
            self.assertEqual(month_result["consolidated_output_file"], str(consolidated_path))

    def test_consolidated_file_reflects_actual_favorable_days(self):
        import json
        import tempfile

        session = _FixtureSession(
            html_by_date={"03/01/2026": load_fixture("chennai_2026-01-03_from_onwards.html")},
            default_html=load_fixture("chennai_2026-01-01_none.html"),
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            fetch_favorable_month_days(
                ["Saturday"],
                "Bharani",
                "Chennai",
                "January 2026",
                forward_looking_months=1,
                person="Sreenaath",
                output_dir=tmp_dir,
                use_cache=False,
                request_delay_seconds=0,
                session=session,
            )
            consolidated_path = Path(tmp_dir) / "Sreenaath" / "Chennai" / "Sreenaath_January_2026_1.json"
            data = json.loads(consolidated_path.read_text(encoding="utf-8"))

        self.assertEqual(
            data["months"][0]["favorable_days"],
            [{"date": "January 3, 2026", "prediction": "from 05:27 PM onwards"}],
        )


SUNNYVALE_SEPTEMBER_2026_FIXTURES_DIR = FIXTURES_DIR / "sunnyvale_2026_09"


class TestSunnyvaleSeptember2026Regression(unittest.TestCase):
    """Regression test for a real user-reported bug.

    fetch_favorable_month_days(["Wednesday", "Friday", "Saturday", "Monday"],
    "Uthiradam", "Sunnyvale", "September 2026", 1) originally returned wrong
    results because Nakshathram was (incorrectly) treated as a single
    all-day value whenever drikpanchang rendered only one <p> for it, even
    when its own "upto"/"next" data indicated a same-day transition -- the
    (buggy) code just reused the day's only known nakshatra past its actual
    cutoff instead of switching to the next one. Concretely:

      - Sep 2, 2026 was reported as "from 01:13 PM onwards" (favorable),
        but Bharani (favorable, until 1:13 PM) has Marana yogam until then,
        and the nakshatra after 1:13 PM is Karthigai (not favorable) even
        though its Amrutha yogam is favorable -- so the day is not
        favorable at all.
      - Sep 4, 2026 was reported as "Entire day", but Rohini (favorable,
        Amrutha yogam) only lasts until 10:34 AM; Mrigasheersham (not
        favorable) takes over for the rest of the day despite its Amrutha
        yogam being favorable -- so only "until 10:34 AM" should qualify.
      - Sep 26, 2026 was reported as "from 10:38 PM onwards", but
        Uthirattathi (favorable, until 10:38 PM) has Marana yogam until
        then, and Ravathi (not favorable) takes over after 10:38 PM despite
        Siddha yogam being favorable then -- so the day is not favorable at
        all.

    This fetches real drikpanchang.com data captured for Sunnyvale, CA
    (geoname-id 5400075) covering every Wednesday/Friday/Saturday/Monday in
    September 2026, served through a fake session so the test is offline
    and deterministic.
    """

    def setUp(self):
        import tempfile

        self._output_tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._output_tmp_dir.cleanup)

    def _session(self):
        html_by_date = {}
        for path in SUNNYVALE_SEPTEMBER_2026_FIXTURES_DIR.glob("*.html"):
            day, month, year = path.stem.split("-")
            html_by_date[f"{day}/{month}/{year}"] = path.read_text(encoding="utf-8")
        return _FixtureSession(html_by_date)

    def test_reported_bug_scenario_now_produces_correct_results(self):
        result = fetch_favorable_month_days(
            ["Wednesday", "Friday", "Saturday", "Monday"],
            "Uthiradam",
            "Sunnyvale",
            "September 2026",
            1,
            person="TestPerson",
            output_dir=self._output_tmp_dir.name,
            use_cache=False,
            request_delay_seconds=0,
            session=self._session(),
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["month"], "September")
        self.assertEqual(result[0]["year"], 2026)
        self.assertEqual(
            result[0]["fav_days_with_ts"],
            [
                "September 4, 2026 - until 10:34 AM",
                "September 7, 2026 - Entire day (favorable until September 8, 2026 04:09 AM)",
                "September 9, 2026 - Entire day (favorable until September 10, 2026 01:34 AM)",
                "September 14, 2026 - Entire day (favorable until September 15, 2026 02:51 AM)",
                "September 16, 2026 - Entire day",
                "September 18, 2026 - from 10:14 AM onwards",
                "September 19, 2026 - from 01:13 PM onwards",
                "September 21, 2026 - from 08:22 PM onwards",
                "September 23, 2026 - from 10:05 PM onwards",
                "September 25, 2026 - from 11:02 PM onwards",
                "September 28, 2026 - from 08:33 PM onwards",
                "September 30, 2026 - from 05:32 PM onwards",
            ],
        )

    def test_september_2_is_not_favorable(self):
        # Previously wrongly reported as "from 01:13 PM onwards".
        result = fetch_favorable_month_days(
            ["Wednesday"],
            "Uthiradam",
            "Sunnyvale",
            "September 2026",
            1,
            person="TestPerson",
            output_dir=self._output_tmp_dir.name,
            use_cache=False,
            request_delay_seconds=0,
            session=self._session(),
        )
        self.assertNotIn(
            "September 2, 2026 - from 01:13 PM onwards", result[0]["fav_days_with_ts"]
        )
        self.assertFalse(any(entry.startswith("September 2,") for entry in result[0]["fav_days_with_ts"]))

    def test_september_4_is_only_favorable_until_1034_am(self):
        # Previously wrongly reported as "Entire day".
        result = fetch_favorable_month_days(
            ["Friday"],
            "Uthiradam",
            "Sunnyvale",
            "September 2026",
            1,
            person="TestPerson",
            output_dir=self._output_tmp_dir.name,
            use_cache=False,
            request_delay_seconds=0,
            session=self._session(),
        )
        self.assertIn("September 4, 2026 - until 10:34 AM", result[0]["fav_days_with_ts"])

    def test_september_26_is_not_favorable(self):
        # Previously wrongly reported as "from 10:38 PM onwards".
        result = fetch_favorable_month_days(
            ["Saturday"],
            "Uthiradam",
            "Sunnyvale",
            "September 2026",
            1,
            person="TestPerson",
            output_dir=self._output_tmp_dir.name,
            use_cache=False,
            request_delay_seconds=0,
            session=self._session(),
        )
        self.assertFalse(any(entry.startswith("September 26,") for entry in result[0]["fav_days_with_ts"]))


class TestFetchFavorableMonthDaysLiveSmoke(unittest.TestCase):
    """A few genuine live requests against drikpanchang.com, kept intentionally small.

    Uses the real on-disk cache so a first successful run makes the only live
    requests; later runs (and CI re-runs) replay from cache. Skips itself
    (rather than failing) on network errors or drikpanchang's rate-limit page,
    since this test depends on a third-party site being reachable.
    """

    def test_single_month_single_weekday_against_live_site(self):
        import tempfile

        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                result = fetch_favorable_month_days(
                    ["Sunday"],
                    "Uthiradam",
                    "Chennai",
                    "December 2030",
                    forward_looking_months=1,
                    person="TestPerson",
                    output_dir=tmp_dir,
                    request_delay_seconds=2.5,
                )
        except DrikPanchangBlockedError as exc:
            self.skipTest(f"drikpanchang.com rate-limited this run: {exc}")
        except Exception as exc:  # network errors, DNS failures, etc.
            self.skipTest(f"Could not reach drikpanchang.com: {exc}")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["month"], "December")
        self.assertEqual(result[0]["year"], 2030)
        self.assertIsInstance(result[0]["fav_days_with_ts"], list)
        for entry in result[0]["fav_days_with_ts"]:
            self.assertTrue(
                entry.startswith("December") and ("Entire day" in entry or "until" in entry or "onwards" in entry)
            )


class TestArgParser(unittest.TestCase):
    """Pure argparse wiring tests -- no network, no filesystem."""

    def test_parses_required_positional_arguments(self):
        args = pu._build_arg_parser().parse_args(
            ["Monday", "Uthiradam", "Chennai", "January 2026", "Sreenaath"]
        )
        self.assertEqual(args.fav_days_of_week, ["Monday"])
        self.assertEqual(args.input_nakshatram, "Uthiradam")
        self.assertEqual(args.input_city_name, "Chennai")
        self.assertEqual(args.starting_month_year, "January 2026")
        self.assertEqual(args.person, "Sreenaath")

    def test_multiple_weekdays_consumed_before_fixed_positionals(self):
        args = pu._build_arg_parser().parse_args(
            ["Monday", "Wednesday", "Friday", "Uthiradam", "Chennai", "January 2026", "Sreenaath"]
        )
        self.assertEqual(args.fav_days_of_week, ["Monday", "Wednesday", "Friday"])
        self.assertEqual(args.input_nakshatram, "Uthiradam")
        self.assertEqual(args.person, "Sreenaath")

    def test_defaults_match_function_defaults(self):
        args = pu._build_arg_parser().parse_args(
            ["Monday", "Uthiradam", "Chennai", "January 2026", "Sreenaath"]
        )
        self.assertEqual(args.forward_looking_months, 12)
        self.assertIsNone(args.output_dir)
        self.assertIsNone(args.cache_dir)
        self.assertTrue(args.use_cache)
        self.assertEqual(args.request_delay_seconds, pu._DEFAULT_REQUEST_DELAY_SECONDS)
        self.assertTrue(args.interactive)

    def test_optional_flags_override_defaults(self):
        args = pu._build_arg_parser().parse_args(
            [
                "Monday", "Uthiradam", "Chennai", "January 2026", "Sreenaath",
                "--forward-looking-months", "3",
                "--output-dir", "/tmp/somewhere",
                "--cache-dir", "/tmp/cache",
                "--no-cache",
                "--request-delay-seconds", "0",
                "--non-interactive",
            ]
        )
        self.assertEqual(args.forward_looking_months, 3)
        self.assertEqual(args.output_dir, "/tmp/somewhere")
        self.assertEqual(args.cache_dir, "/tmp/cache")
        self.assertFalse(args.use_cache)
        self.assertEqual(args.request_delay_seconds, 0)
        self.assertFalse(args.interactive)

    def test_missing_required_argument_exits_nonzero(self):
        import contextlib
        import io

        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                # Missing person (and everything else).
                pu._build_arg_parser().parse_args(["Monday", "Uthiradam", "Chennai"])
        self.assertNotEqual(ctx.exception.code, 0)


class TestMainFunction(unittest.TestCase):
    """Tests for the `main(argv)` CLI entry point, called in-process (not via subprocess).

    Uses the project's real on-disk drikpanchang cache (`panchang_cache/`,
    which already has January 2026 fully cached for Chennai from earlier
    development/testing) so these run offline and fast, without needing a
    fake session (main() has no way to inject one, unlike
    fetch_favorable_month_days itself).
    """

    def _run_main(self, argv):
        import contextlib
        import io

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = pu.main(argv)
        return exit_code, stdout.getvalue()

    def test_successful_run_prints_favorable_days_and_exits_zero(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code, output = self._run_main(
                [
                    "Monday", "Uthiradam", "Chennai", "January 2026", "TestCliPerson",
                    "--forward-looking-months", "1",
                    "--output-dir", tmp_dir,
                    "--request-delay-seconds", "0",
                ]
            )
            self.assertEqual(exit_code, 0)
            self.assertIn("January 2026:", output)
            self.assertIn("saved to", output)
            written_file = Path(tmp_dir) / "TestCliPerson" / "Chennai" / "January_2026.txt"
            self.assertTrue(written_file.exists())

    def test_prints_and_writes_consolidated_summary(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code, output = self._run_main(
                [
                    "Monday", "Uthiradam", "Chennai", "January 2026", "TestCliPerson",
                    "--forward-looking-months", "1",
                    "--output-dir", tmp_dir,
                    "--request-delay-seconds", "0",
                ]
            )
            self.assertEqual(exit_code, 0)
            self.assertIn("Consolidated summary saved to", output)
            consolidated_file = Path(tmp_dir) / "TestCliPerson" / "Chennai" / "TestCliPerson_January_2026_1.json"
            self.assertTrue(consolidated_file.exists())
            self.assertIn(str(consolidated_file), output)

    def test_unknown_nakshatram_prints_error_and_exits_nonzero(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code, output = self._run_main(
                [
                    "Monday", "NotARealNakshatra", "Chennai", "January 2026", "TestCliPerson",
                    "--forward-looking-months", "1",
                    "--output-dir", tmp_dir,
                    "--request-delay-seconds", "0",
                ]
            )
            self.assertEqual(exit_code, 1)

    def test_ambiguous_city_non_interactive_exits_nonzero(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code, output = self._run_main(
                [
                    "Monday", "Uthiradam", "Springfield", "January 2026", "TestCliPerson",
                    "--forward-looking-months", "1",
                    "--output-dir", tmp_dir,
                    "--request-delay-seconds", "0",
                    "--non-interactive",
                ]
            )
            self.assertEqual(exit_code, 1)

    def test_output_dir_defaults_when_omitted(self):
        import os
        import tempfile

        original_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp_dir:
            os.chdir(tmp_dir)
            try:
                exit_code, output = self._run_main(
                    [
                        "Monday", "Uthiradam", "Chennai", "January 2026", "TestCliPerson",
                        "--forward-looking-months", "1",
                        "--request-delay-seconds", "0",
                    ]
                )
            finally:
                os.chdir(original_cwd)
            self.assertEqual(exit_code, 0)
            expected_file = Path(tmp_dir) / "TestCliPerson_output_dir" / "TestCliPerson" / "Chennai" / "January_2026.txt"
            self.assertTrue(expected_file.exists())


class TestFetchFavorableMonthDaysDirectInvocation(unittest.TestCase):
    """Confirms fetch_favorable_month_days() works when imported and called directly
    from another Python script/module (as opposed to via the CLI), using the same
    real on-disk cache as TestMainFunction.
    """

    def test_direct_call_from_importing_module(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            result = fetch_favorable_month_days(
                ["Monday"],
                "Uthiradam",
                "Chennai",
                "January 2026",
                forward_looking_months=1,
                person="TestScriptPerson",
                output_dir=tmp_dir,
                request_delay_seconds=0,
            )
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["month"], "January")
            written_file = Path(tmp_dir) / "TestScriptPerson" / "Chennai" / "January_2026.txt"
            self.assertTrue(written_file.exists())
            self.assertEqual(result[0]["output_file"], str(written_file))


class TestCliSubprocess(unittest.TestCase):
    """Genuine end-to-end test: runs `python3 panchangam_utils.py ...` as a real
    subprocess, exactly as a user would from a shell. Uses the project's real
    on-disk drikpanchang cache so it doesn't hit the network.
    """

    def test_cli_invocation_writes_output_file_and_prints_summary(self):
        import subprocess
        import sys
        import tempfile

        script_path = Path(pu.__file__).resolve()
        with tempfile.TemporaryDirectory() as tmp_dir:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(script_path),
                    "Monday",
                    "Uthiradam",
                    "Chennai",
                    "January 2026",
                    "SubprocessPerson",
                    "--forward-looking-months", "1",
                    "--output-dir", tmp_dir,
                    "--request-delay-seconds", "0",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            self.assertIn("January 2026:", completed.stdout)
            written_file = Path(tmp_dir) / "SubprocessPerson" / "Chennai" / "January_2026.txt"
            self.assertTrue(written_file.exists())

    def test_cli_invocation_with_bad_input_exits_nonzero_with_error_message(self):
        import subprocess
        import sys
        import tempfile

        script_path = Path(pu.__file__).resolve()
        with tempfile.TemporaryDirectory() as tmp_dir:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(script_path),
                    "Monday",
                    "NotARealNakshatra",
                    "Chennai",
                    "January 2026",
                    "SubprocessPerson",
                    "--forward-looking-months", "1",
                    "--output-dir", tmp_dir,
                    "--request-delay-seconds", "0",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("Unknown nakshatra", completed.stderr)

    def test_cli_help_exits_zero(self):
        import subprocess
        import sys

        script_path = Path(pu.__file__).resolve()
        completed = subprocess.run(
            [sys.executable, str(script_path), "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertIn("usage:", completed.stdout)


class TestGroupIntervalHelpers(unittest.TestCase):
    """Pure helpers behind find_common_favorable_times."""

    def test_merge_intervals_sorts_and_joins_touching_and_overlapping(self):
        self.assertEqual(pu._merge_intervals([(5, 8), (0, 2), (2, 3), (7, 10)]), [(0, 3), (5, 10)])

    def test_intersect_intervals(self):
        a = [(0, 10), (20, 30), (40, 50)]
        b = [(5, 25), (45, 60)]
        self.assertEqual(pu._intersect_intervals(a, b), [(5, 10), (20, 25), (45, 50)])

    def test_intersect_intervals_ignores_mere_touching(self):
        self.assertEqual(pu._intersect_intervals([(0, 10)], [(10, 20)]), [])

    def test_local_minutes_to_utc_handles_pacific_daylight_and_standard_time(self):
        from zoneinfo import ZoneInfo

        la = ZoneInfo("America/Los_Angeles")
        # 10:05 PM PDT (UTC-7) on Sep 23, 2026
        self.assertEqual(pu._local_minutes_to_utc(date(2026, 9, 23), 22 * 60 + 5, la).isoformat(), "2026-09-24T05:05:00+00:00")
        # 7:30 PM PST (UTC-8) on Nov 30, 2026, after DST ends on Nov 1
        self.assertEqual(pu._local_minutes_to_utc(date(2026, 11, 30), 19 * 60 + 30, la).isoformat(), "2026-12-01T03:30:00+00:00")

    def test_local_minutes_to_utc_accepts_minutes_past_midnight_into_next_day(self):
        from zoneinfo import ZoneInfo

        kolkata = ZoneInfo("Asia/Kolkata")
        # 24h + 1:43 AM IST past Oct 13 == Oct 14 01:43 IST == Oct 13 20:13 UTC
        self.assertEqual(
            pu._local_minutes_to_utc(date(2026, 10, 13), 24 * 60 + 103, kolkata).isoformat(), "2026-10-13T20:13:00+00:00"
        )

    def test_same_instant_in_chennai_and_sunnyvale(self):
        from zoneinfo import ZoneInfo

        sunnyvale = pu._local_minutes_to_utc(date(2026, 9, 23), 22 * 60 + 5, ZoneInfo("America/Los_Angeles"))
        chennai = pu._local_minutes_to_utc(date(2026, 9, 24), 10 * 60 + 35, ZoneInfo("Asia/Kolkata"))
        self.assertEqual(sunnyvale, chennai)

    def test_city_timezone(self):
        self.assertEqual(pu._city_timezone(resolve_geoname_id("Sunnyvale")).key, "America/Los_Angeles")
        self.assertEqual(pu._city_timezone(resolve_geoname_id("Chennai")).key, "Asia/Kolkata")

    def test_favorable_intervals_extends_entire_day_into_next_day_continuation(self):
        html = load_fixture("sunnyvale_2026-10-17_entire_day_crosses_next_day.html")
        day_result = pu._parse_day_panchang(html, date(2026, 10, 17))
        indices = favorable_nakshatram_indices("Uthiradam")
        # Rendered as "Entire day (favorable until October 18, 2026 12:19 AM)"
        self.assertEqual(
            pu._build_favorable_entry(day_result, indices),
            "October 17, 2026 - Entire day (favorable until October 18, 2026 12:19 AM)",
        )
        self.assertEqual(pu._favorable_intervals(day_result, indices), [(0, 24 * 60 + 19)])

    def test_parse_group_member_spec(self):
        self.assertEqual(
            pu._parse_group_member_spec("Jai; Uthiradam; Sunnyvale, CA; Monday, Wednesday Friday"),
            {
                "person": "Jai",
                "input_nakshatram": "Uthiradam",
                "input_city_name": "Sunnyvale, CA",
                "fav_days_of_week": ["Monday", "Wednesday", "Friday"],
            },
        )

    def test_parse_group_member_spec_rejects_wrong_field_count(self):
        import argparse

        with self.assertRaises(argparse.ArgumentTypeError):
            pu._parse_group_member_spec("Jai;Uthiradam;Chennai")


class TestFindCommonFavorableTimes(unittest.TestCase):
    """End-to-end over the captured Sunnyvale September 2026 fixtures (offline)."""

    def setUp(self):
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _session(self):
        html_by_date = {}
        for path in SUNNYVALE_SEPTEMBER_2026_FIXTURES_DIR.glob("*.html"):
            day, month, year = path.stem.split("-")
            html_by_date[f"{day}/{month}/{year}"] = path.read_text(encoding="utf-8")
        # Days just outside September (scanned as a cross-time-zone buffer) get an
        # all-day-Marana page, so they contribute nothing.
        return _FixtureSession(html_by_date, default_html=load_fixture("chennai_2026-01-01_none.html"))

    def _run(self, people):
        return pu.find_common_favorable_times(
            people,
            "September 2026",
            1,
            output_dir=self._tmp.name,
            use_cache=False,
            request_delay_seconds=0,
            session=self._session(),
        )

    def test_requires_at_least_two_people(self):
        with self.assertRaises(ValueError):
            pu.find_common_favorable_times(
                [{"person": "A", "input_nakshatram": "Uthiradam", "input_city_name": "Sunnyvale", "fav_days_of_week": ["Monday"]}],
                "September 2026",
                1,
                output_dir=self._tmp.name,
                session=_FailingSession(),
            )

    def test_common_weekdays_restrict_the_result(self):
        # Same nakshatram and city; B only has Wednesday, so the group result is
        # exactly the individual's Wednesday windows (see the Sunnyvale regression
        # test for the individual results).
        result = self._run(
            [
                {"person": "A", "input_nakshatram": "Uthiradam", "input_city_name": "Sunnyvale",
                 "fav_days_of_week": ["Monday", "Wednesday", "Friday", "Saturday"]},
                {"person": "B", "input_nakshatram": "Uthiradam", "input_city_name": "Sunnyvale",
                 "fav_days_of_week": ["Wednesday"]},
            ]
        )
        windows = result["months"][0]["common_windows"]
        spans = [(w["local_times"][0]["start"], w["local_times"][0]["end"]) for w in windows]
        self.assertEqual(
            spans,
            [
                ("Wednesday, September 9, 2026 12:00 AM", "Thursday, September 10, 2026 01:34 AM"),
                ("Wednesday, September 16, 2026 12:00 AM", "Thursday, September 17, 2026 12:00 AM"),
                ("Wednesday, September 23, 2026 10:05 PM", "Thursday, September 24, 2026 12:00 AM"),
                ("Wednesday, September 30, 2026 05:32 PM", "Thursday, October 1, 2026 12:00 AM"),
            ],
        )
        self.assertEqual(windows[2]["duration_minutes"], 115)
        self.assertEqual(result["participants"][0]["timezone"], "America/Los_Angeles")

    def test_common_favorable_nakshatrams_is_the_intersection(self):
        result = self._run(
            [
                {"person": "A", "input_nakshatram": "Uthiradam", "input_city_name": "Sunnyvale", "fav_days_of_week": ["Wednesday"]},
                {"person": "B", "input_nakshatram": "Poosam", "input_city_name": "Sunnyvale", "fav_days_of_week": ["Wednesday"]},
            ]
        )
        expected = sorted(
            set(favorable_nakshatram_indices("Uthiradam")) & set(favorable_nakshatram_indices("Poosam"))
        )
        self.assertEqual(result["common_favorable_nakshatrams"], [NAKSHATRAS[i]["Tamil"] for i in expected])

    def test_writes_json_and_txt_under_group_folder(self):
        import json
        from pathlib import Path

        result = self._run(
            [
                {"person": "A", "input_nakshatram": "Uthiradam", "input_city_name": "Sunnyvale", "fav_days_of_week": ["Wednesday"]},
                {"person": "B", "input_nakshatram": "Uthiradam", "input_city_name": "Sunnyvale", "fav_days_of_week": ["Wednesday"]},
            ]
        )
        json_path = Path(result["output_file"])
        self.assertEqual(json_path, Path(self._tmp.name) / "A_B" / "A_B_September_2026_1.json")
        self.assertEqual(json.loads(json_path.read_text())["group"], "A & B")
        self.assertTrue(json_path.with_suffix(".txt").exists())


class TestGroupCli(unittest.TestCase):
    def test_group_subcommand_dispatches(self):
        import contextlib
        import io
        from unittest import mock

        with mock.patch.object(pu, "find_common_favorable_times") as fake:
            fake.return_value = {"common_favorable_nakshatrams": ["Rohini"], "months": [], "output_file": "x.json"}
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = pu.main([
                    "group",
                    "--person", "A;Uthiradam;Sunnyvale, CA;Monday,Wednesday",
                    "--person", "B;Poosam;Chennai, India;Wednesday",
                    "September 2026",
                    "--forward-looking-months", "2",
                ])
        self.assertEqual(code, 0)
        people, month_year, months = fake.call_args.args
        self.assertEqual([p["person"] for p in people], ["A", "B"])
        self.assertEqual(people[0]["input_city_name"], "Sunnyvale, CA")
        self.assertEqual((month_year, months), ("September 2026", 2))
        self.assertIn("x.json", out.getvalue())


if __name__ == "__main__":
    unittest.main()
