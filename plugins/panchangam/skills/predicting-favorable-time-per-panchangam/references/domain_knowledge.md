# Introduction
This domain_knowledge.md file will highlight the overall domain knowledge of Hindu Astrology that is needed for this good day/time prediction. Mainly, there are three major concepts to be aware of to understand how to predict good days, and time within those days. They are 'Nakshatram', 'Tamil Yogam' and 'Favorable days of the week' per one's birth horoscope. All those three are explained in detail in the sections below.

# Nakshatram
As per Hindu Astrology there are 27 Nakshatrams. They are numbered from 1 to 27. Their English, Sanskrit, Tamil and Malayalam names along with the order of the Nakshatrams (1 to 27) are provided in https://www.drikpanchang.com/tutorials/nakshatra/nakshatra.html. For the purpose of this predictor, it is sufficient to focus on the English, Sanskrit and Tamil Names of the Nakshatrams. The predictor script uses a external website - www.drikpanchang.com to fetch details of the day as per Hindu Tamil Calendar. For example, https://www.drikpanchang.com/tamil/tamil-month-panchangam.html?geoname-id=5400075&date=22/09/2026 will list out the Nakshatram of the day in Sunnyvale, CA, USA city (geoname-id=5400075) for September 22, 2026. It can be observed from the web crawl that the Nakshatram mentioned for September 22, 2026 is 'Thiruvonam' which lasts upto 08:39 PM. This can be construed as "primary" Nakshatram for that day. This also means, the next Nakshatram or "secondary Nakshatram (Avittam Nakshatram based on the 1-27 Naskhatram order) will begin from 08.40 PM and will last till rest of the day (or sometimes can span across to the next day(s) as well.). When mentioning the Nakshtram, the website generally lists the Nakshtram and until when it is alive during that day. If required to figure out the birth (or beggining) time of the same Nakshatram either that day or previous day, one can refer to the end time of the "previous" Nakshatram (previous in 1-27 order).

# Tamil Yogams
As per Hindu astrology, specifically Tamil astrology, there are three Tamil Yogams: **Siddha**, **Amrutha** (Amirtha) and **Marana**. Siddha and Amrutha are auspicious; Marana is inauspicious. Tamil Yogam is *not* the same as the 27 "nithya" yogams (Vishkambha, Dhrithi, Soola, ...) that panchangams also list as "Yogam"; those come from the Sun and Moon longitudes and are not used here.

## How Tamil Yogam is computed
Tamil Yogam is a pure lookup: it depends only on the **Vedic weekday** and the **nakshatram** in force. Each of the 7 × 27 combinations is fixed to exactly one of the three yogams. The table is printed on the first page of every Vakya (Pambu) Panchangam, and is reproduced in https://www.mahastro.com/how-to-use-vakya-panchangam-or-pambu-panchangam/ under "Yogam – Column 1" (அ = Amirtha, சி = Siddha, ம = Marana).

Two rules for using it:
- **Vedic weekday.** The weekday runs from sunrise to the next sunrise, not midnight to midnight. So 3 AM on a Thursday still belongs to Wednesday, and Wednesday's row applies.
- **When the yogam changes.** It changes whenever the nakshatram changes, and at sunrise (when the weekday changes). A day with 3 nakshatrams can have 3 different yogams. The mahastro article's example is Feb 21, 2019 (Thursday): Pooram gives Siddha, Uthiram gives Marana, and Hastham gives Siddha.

The chart below uses S = Siddha, A = Amrutha and M = Marana. It is transcribed cell by cell from the article's image and re-verified against a zoomed copy; `TAMIL_YOGAM_CHART` in `panchangam_utils.py` holds the same data.

| Nakshatram | Sun | Mon | Tue | Wed | Thu | Fri | Sat |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1. Aswini | S | S | S | M | A | A | S |
| 2. Bharani | S | S | S | S | S | S | S |
| 3. Karthigai | S | M | S | A | M | S | A |
| 4. Rohini | S | A | A | S | M | M | A |
| 5. Mrigasheersham | S | A | S | S | M | S | S |
| 6. Thiruvaathirai | S | S | M | S | M | S | S |
| 7. Punarpoosam | S | A | S | S | A | S | S |
| 8. Poosam | S | S | S | S | A | M | S |
| 9. Aayilyam | S | S | S | S | S | M | M |
| 10. Makam | M | M | S | S | A | M | A |
| 11. Pooram | S | S | S | A | S | S | M |
| 12. Uthiram | A | S | A | A | M | S | M |
| 13. Hastham | A | S | S | M | S | A | M |
| 14. Chithirai | S | S | S | S | S | S | M |
| 15. Swaathi | S | A | S | S | A | S | A |
| 16. Visaakam | M | M | M | S | S | S | S |
| 17. Anusham | M | S | S | S | S | S | S |
| 18. Kettai | M | S | S | S | S | M | S |
| 19. Moolam | A | S | A | M | S | A | S |
| 20. Pooraadam | S | S | S | A | S | S | S |
| 21. Uthiradam | A | M | S | A | S | S | S |
| 22. Thiruvonam | A | A | S | S | S | M | S |
| 23. Avittam | M | S | S | M | S | S | S |
| 24. Sadayam | S | S | M | S | M | S | A |
| 25. Poorattathi | S | M | M | A | S | S | M |
| 26. Uthirattathi | A | S | A | M | S | S | S |
| 27. Ravathi | A | S | S | S | S | A | M |

## Methods and sources that do *not* reproduce this chart
- **The "anchor star + count mod 7" formula** (count from a weekday's anchor star, e.g. Thursday → Rohini, then take the remainder mod 7) is sometimes offered as an equivalent method. It isn't:
  - It yields 7 outcomes (Amrita, Siddha, Marana plus Iruthai, Nasa, Shubha and Parigha), which belong to a different yoga system.
  - Taken literally, it matches only 32 of the 189 chart cells.
  - No mapping of its remainders onto the three Tamil Yogams beats answering "Siddha" for every cell, which matches 115 of 189.
- **The sites' published Tamil Yogam comes from other tables:**
  - **drikpanchang.com** matches this chart only about half the time (153 of 330 days checked), although its own table is internally consistent.
  - **prokerala.com** matches only 8 of 21 checked days.
  - **mypanchang.com** matches on 176 of 182 days. Its table differs from the chart in only 3 cells: Thursday + Kettai, Friday + Pooraadam and Monday + Chithirai, where it says Marana and the chart says Siddha.

For these reasons the predictor computes Tamil Yogam from the chart. It uses the sites only for things they all agree on: nakshatram timings and sunrise. Each site's published Tamil Yogam is kept only as a reference.

# Favorable days of the week
This again is a Hindu Astrology concept. For a given Birth Horoscope, there are certain days of the week which are favorable, while the others are not. This means, a good day/time has to fall within one of those favorable days of the week, but its not necessary that all the times within those favorable days are the final candidate for good day/time prediction. More on how the calculation is done is in the next section.

# Good day/time prediction logic
Good day/time is chosen where it is one of the favorable days of the week (a Vedic day, sunrise to the next sunrise) AND that day should have one of the favorable Nakshatrams (primary or secondary) AND as well favorable 'Tamil Yogam' (looked up from the chart above for that weekday and nakshatram) combination. IOW, for example, if Wednesday (September 23, 2026) is one of the favorable days and that day has "Avittam" Nakshatram that lasts until 8.39 PM that day, while 'Avittam' Nakshatram is one of the favorable Nakshatrams AND there is 'Siddha Yogam' that lasts until, let say 08.10 PM, then Wednesday until 08.10 PM is a good day/time (where all three intersect - 1. Favorable day of the week, 2. Favorable Nakshatram is "alive" and not ended, 3. Favorable Yogam (Siddha or Amrutha Yogam) is "alive" and not ended).

# Gotchas during webscraping
## Captachas during repeated webscraping
As mentioned above, the predictor tool relies on www.drikpanchang.com. Drikpanchang rate-limits/reCAPTCHA-blocks aggressive scraping (empirically triggered around ~100-120 rapid sequential requests during development). A blocked response is detected by the predictor tool (`_is_blocked_response`) and raises `DrikPanchangBlockedError` instead of being cached or mis-parsed. Predictor tool has a default throttle for live requests ()`_DEFAULT_REQUEST_DELAY_SECONDS` (2s)). This means, a full 12-month forward looking prediction run can still be 100+ requests, so one can expect it to take minutes on a cold cache.

## Alternate source: prokerala.com
When drikpanchang.com blocks requests, the predictor falls back to www.prokerala.com, which publishes the same per-day details for a geoname-id, e.g. https://www.prokerala.com/astrology/tamil-panchangam/2026-september-23.html?loc=5400075 (Sunnyvale, CA). Things to know when reading it:
- Its **Nakshatram** block lists each nakshatram with full dated start and end times (e.g. "Avittam - Sep 22 08:39 PM – Sep 23 10:05 PM"). The nakshatram is identified by its link slug (e.g. `satabhisha-nakshatra.htm`), because prokerala's Tamil spellings differ from drikpanchang's ("Sadhayam", "Tiruvonam", "Mrigashirsham").
- Its **Tamil Yogam** block ("Amrutha Yogam Upto - 10:05 PM", then "Amrutha Yogam") is the Siddha/Amrutha/Marana parameter this predictor uses. The separate **Yogam** block (Dhrithi, Soola, ...) is the unrelated 27-yogam (nithya yogam) parameter and must be ignored.
- Tamil Yogam cutoffs carry no date. prokerala's panchang day runs from sunrise to sunrise, so a cutoff earlier than that day's sunrise falls on the next calendar day.
- Nakshatram timings match drikpanchang.com to within a minute. Sunrise can differ by a few minutes between the sites. prokerala's published Tamil Yogam differs from both drikpanchang's and the Pambu chart, but the predictor doesn't use any site's Tamil Yogam; it computes it from the chart.

## City name to genomeid resolution
The predictor tool uses 'geonamescache' library/package to convert the user provided location (City) to respective `geoname-id`, as it is needed to query the calendar @ www.drikpanchang.com. However, if there is more than one city that's available in the geonamescache, then the ambiguity needs to be resolved. Typically, this clarification needs to be asked to user, as a subsequent input to disambiguate. The predictor's current behavior is not to silently resolve to a city when there are more candidates. For example, "Springfield" matches 8+ US states — picking the most populous match maybe one way to go forward but that could be a wrong call for this feature (a user could easily mean the small/less-populous place). Instead: `city_name` can carry a `", state"` and/or `", country"` qualifier (by name or code, e.g. `"Springfield, IL"` or `"Springfield, Illinois, USA"`); if that doesn't fully resolve it, an explicit `chooser` callable (given the candidate list, returns the chosen one — for scripted/programmatic and test use) takes precedence in the  Predictor script , then interactive `input()` prompting if stdin is a real terminal, then `AmbiguousCityError` (a `ValueError` subclass, carries `.candidates`) as the final fallback. This is how ambiguity in city name is handled by the predictor script.

