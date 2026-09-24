# Prompts

## Prompt 1: next_27_nakshatras

Create a utility function that returns the stars count with modulo operator.

Here we are dealing with Hindu Nakshatras(stars). There are 27 of them in total, the list of which (both Tamil nakshatra and snaskrit nakshatra names is provided below)

### Goal
The goal is to create a utility function in python called 'next_27_nakshatras' in tools.py where the argument is a nakshatra from where the next 27 nakshatras are ordered and returned back.
The argument provided as nakshatra is the 0th nakshatra (current nakshatra, for assumption) and the function should return a list of dicts [{"Tamil": "" ,"Sanskrit":"", "English":"" },] that are ordered from the current nakshatra with modulo operator (27 modulo for 27 nakshatras).

### Reference
The table of the 27 nakshatras in order (starting from Ashwini nakshatra) is given here - https://www.drikpanchang.com/tutorials/nakshatra/nakshatra.html

From the above table, interpret the "Devanagiri" column as "Sanskrit" name and ingore the "Malayalam" column.

### Sample input and output
Sample input (argument) to the function 'next_27_nakshatras' : "Uthiraadam"
Return values should be in the list of dictionaries across "Tamil", "Sanskrit" and "English" names in the following order. Here only the tamil names are provided as example.

1st star : Uthiradam
2 : Thiruvonam
3: Avittam
4: Sadayam
5: Poorattathi
6: Uthirattathi
7: Ravathi
8: Aswini
9: Bharani
10: Karthigai
11: Rohini
12: Mrigasheersham
13: Thiruvaathirai
14: Punarpoosam
15: Poosam
16: Aayilyam
17: Makam
18: Pooram
19: Uthiram
20: Hastham
21: Chithirai
22: Swaathi
23: Visaakam
24: Anusham
25: Kettai
26: Moolam
27: Pooraadam

Observe that the indices for the return value in the above example start at 1 (as oppose to index 0). For the consumer of the function it is perfectly fine to assume that the consumer indexes the first start with index 0 of the return list.

### Testing
Please create unit tests with atleast 3-4 examples with varifying start indices of the nakshatram list. Say index 0, index 10, index 20 and index 26. Also generate boundary conditions for the utility function and make sure all the tests pass.
Can you try now ?

---

## Prompt 2: favorable_nakshatrams

Build another utility function "favorable_nakshatrams()" in panchang_utils.py which returns dict containing two lists given a nakshatram as input

### Input
Nakshatram : It could be in Tamil or Englist or Sanskrit

### Output
Dict of lists like below where the contents of the lists are nakshatram names for both "favorable" and "not_favorable" dict key values
{"favorable":[ ]. "not_favorable":[ ]}

### Details
1. Given the input Nakshtram, use "next_27_nakshatras()" function in panchang_utils.py to get list of nakshatram starting with the argument nakshatram as index.
2. For a given argument nakshtram (index = 1), "favorable" nakshtram lists are with indices 2, 4,6,8,9,11,13,15,17,18,20,22,24,26,27. Rest of the nakshatrams (in the order of indices) are in the "not_favorable" lists.
3. So gover the ordered lists from teh argument nakshtram as first index and construct {"favorable":[ ]. "not_favorable":[ ]}, dicts of lists.
4. Return the dicts of lists.
5. Generate unit tests along with boundary conditions and test them

### Sample Input, output
For example, for argument nakshatram "Uthiradam", the "favorable" list contains nakshatams Thiruvonam, Sadhayam, Uthirattadhi, Aswini, Bharani, Rohini, Thiruvadhirai, Poosam, Magham, Pooradam, Hastham, Swathi, Anusham, Moolam, Pooradam

---

## Prompt 3: fetch_favorable_month_days

This one is a bit involved.

### Goal
Goal is to find good days in a month for the forward looking 12 months for a given input of favorable days of the week for
a given person (input), given nakshatram(input), given location ("city name") and starting_month_year (input).
Create this in a function
"fetch_favorable_month_days (fav_days_of_week=[], str input_nakshatram, str input_city_name, str starting_month_year, int forward_looking_months=12)"

Good days are defined as follows
1.  For each week in a month, the possible favorable days are given as input to the function -
    i.e "fav_days_of_week" (for a week) in the forward looking 12 month period (from starting_month_year input)
2. For a given location - input_city_name, fetch the corresponding geonameid from https://www.geonames.org/.
   There is a python library at https://github.com/symerio/pgeocode. Use that to fetch the geonameid for the given location
   ("city name").
3. Once the geonameid is fetched,
    a) Use that to query www.drikpanchang.com to get the "nakshatram" and "tamil yogam" for each day in "fav_days_of_{month}".
       For example, to fetch for city "chennai" for Sept 19, 2026, the corresponding URL is "https://www.drikpanchang.com/tamil/tamil-month-panchangam.html?geoname-id=1264527&date=19/09/2026"
    b) In the html fetched under <body> -> <div class="dpPageWrapper"> -> <div class="dpPanchangWrapper"> -> <div class="dpDayPanchangWrapper"> fetch the test for "Nakshtram" and "Tamil Yogam". They will be wrapped under <p><class "dpElement"> <span class="dpElementKey"><span class="dpElementValue"></span></span></p><div class=""></div>
    c) Sometimes, there will be additional tags with datetime stamp like <span class="dpTimeStamp"></span>
        where the time in AM/PM for that location until when the Nakshatram is in existence or the "Tamil Yogam" is
        in existence.
    d) So when it says, for example "Nakshatram" is "Moolam" upto "1.35 PM", that means for that day, it is "Moolam"
       nakshtram until 1:35 PM and after that it is the next nakshtram (which is Pooradam). Store the first nakshatram in "primary_nakshatram_for_the_day" and the subsequent one (if it exists)
       in "secondary_nakshatram_of_the_day".
    e) Sometimes, there will be only one nakshtram in a given day (lasting full 24 hrs) and sometimes it will extend to
       next day too, which will be indicated as "up to {next day, time}". So factor that accordingly and
       fill the nakshatram variables.
    f) Similarly for "Tamil Yogam", when it says, for example "Tamil Yogam" is "Siddha" upto "1.35 PM" that means it is Siddha Yogam
       until that time. To see what "Tamil Yogam" is after that time for that day, look for
       another <span class="dpElement"> <span class="dpElementKey"> with value "Tamil Yoga" and
       find the corresponding "dpElementValue" for that. That value is the "Tamil Yogam" for the rest of the day. Store the tamil
       yogam values in "primary_tam_yogam_for_the_day" and the subsequent one (if it exists)
       in "secondary_tam_yogam_of_the_day".
4. Once the nakshatrams and yogams (primary, secondary) are computed for each of the fav_days_of_week (given as input)
   for each of the forward looking 12 months ({month_year}) , then compute the "{month}_{year}_fav_day_with_ts_until" as follows
    a) For the favorable days given as input, if the "primary_nakshatram_for_the_day" or "secondary_nakshatram_of_the_day"
       is in the list of favorable_nakshatrams returned by function "favorable_nakshatrams" in panchang_utils.py AND
        if "primary_tam_yogam_for_the_day" is one of "Siddha" yogam or "Amrutha" yogam (IOW, NOT Marana yogam),
       then that day, with the appropriate favorable  "primary_nakshatram_for_the_day" with appropriate "primary_tam_yogam_for_the_day"
       with corresponding time "upto" in AM/PM in the given city (geocodeid) is a
       favorable day (until "upto" time period in the day). Append this in per month_year list like "{month}_{year}_fav_day_with_ts_until"
       If the favorable nakshtram lasts the entire day of the favorable day, then the appended value in "{month_year}_fav_day_with_ts_until"
       can be, for example, "September 19, 2026 - Entire day". For example, if its till 2.30 PM then the value
       in the "{month}_{year}_fav_day_with_ts_until" can be for example "September 19, 2026 - until 2.30 PM"
    b) Similar to above logic exists for "secondary_nakshatram_of_the_day" (if it exists) and "secondary_tam_yogam_of_the_day".
       In my reasearch, if there is a secondary nakshtram for a day, there will be a secondary tamil yogam as well.
       Flag this if this does not exist, based on the unit test cases.
    c) Once the entire set of favorable days for a given month in the forward looking 12 month (from starting_month_year
       given as input), then store the complete set of days for that month in "{month}_{year}_fav_day_with_ts_until".
    d) Append the list "{month}_{year}_fav_day_with_ts_until" to "favorable_days_with_ts" list. "favorable_days_with_ts" list
       contains the list of favorable days for all the forward looking months (12 by default).
    e) Finally, "favorable_days_with_ts" should have 12 entries (by default or user specified # of months) (of lists)
       for each of the forward looking month.
4. Create set of unit test cases, by crawling through a different year, set of months, for the given user input of favorable days of the week for
a given person (input), given nakshatram(input), given location ("city name") and starting_month_year (input)

5. If the function works fine and all tests in unit tests are passing, append this prompt in prompt.md file

---

## Prompt 4: Bug report — fetch_favorable_month_days wrong results for Sunnyvale/September 2026

I ran a single month test for Sept 2026 for "Uthiraadam" nakshatram for favorable days "Wednesday", "Friday", "Saturday" and "Monday". Couple of responses from the function are wrong. Pasting below the response and what's wrong with some of them. Please  learn from the below errors and fix the bug accordingly. Also include the below test in your unit test and make sure it passes.

```
>>> import test_panchang_utils as pu
>>> pu.fetch_favorable_month_days(["Wednesday", "Friday", "Saturday", "Monday"], "Uthiradam", "Sunnyvale", "September 2026", 1)
[{'month': 'September', 'year': 2026, 'fav_days_with_ts':
['September 2, 2026 - from 01:13 PM onwards',
'September 4, 2026 - Entire day',
'September 7, 2026 - Entire day',
'September 9, 2026 - Entire day',
'September 14, 2026 - Entire day',
'September 16, 2026 - Entire day',
'September 19, 2026 - from 01:13 PM onwards',
'September 26, 2026 - from 10:38 PM onwards',
'September 28, 2026 - from 08:33 PM onwards']}]
```

Wrong answers --
1. 'September 2, 2026 - from 01:13 PM onwards' -- Bharani Nakshatram (favorable for "Uthiradam" nakshatram) is there till 01.13 PM, but Mrana Yogam till 01.13 PM. Though there is "Amrutha" yoga for rest of thday (after 01.13 PM), Bharani nakshatram ends at 01.13 PM after which it is "Karthigai"
    nakshatram which is not a favorable nakshatram for "Uthiradam"
2.  'September 4, 2026 - Entire day' - Until 10.34 AM there is Rohini Nakshatram which is favorable and also has Amrutha yogam till 10.34 AM. However, after 10.34 AM, Mrigasheersham nakshatram is born (next after Rohini) which is not favorable, though there is Amrutha yogam entire day. Thus the favorable time for that day is only until 10.34 AM (Rohini Nakshatram and Amrutha yogam).
3. 'September 26, 2026 - from 10:38 PM onwards' -- That day there is "Uthiratathi" until 10.38 PM, but has Marana yogam till 10.38 PM. Hence until 10.38 PM it is not favorable. However, after 10.38 PM there is Siddha yogam, but next nakshatram Ravathi is born whcih is not favorable nakshatram. So entire day becomes not favorable.

---

## Prompt 5: Handle ambiguous city names (e.g. Sunnyvale, CA vs Sunnyvale, TX)

Can you also handle scenario where a city name appears in more than one state/country ? Ask the user for clarification and then use that city, state/country combo for correct geonameid mapping.

For example, Sunnyvale city cna be Sunnyvale, CA, USA or Sunnyvale, TX, USA.

---

## Prompt 6: Bug report — October 17, 2026 shown as "until 12:19 AM" instead of "Entire day" continuing into next day

I ran the test for "Uthiradam" nakshatram, "Sunnyvale" city and start motnh of "October 2026" and for 1 month (forward looking. There is a cosmetic bug whcih you need to address. For October 17, 2026, the entire day until next day (October 18, 2026) 12.19 AM both Pooradam (favorable Nakshatram) and Amrutha yogam is there.

However, the output comes as "October 17, 2026 - until 12.19 AM", without saying it is 12.19 AM of next day (OCtober 18). Please fix such scenarios where it lasts the entire day (Nakshatram + Ypgam combination) and until the next day

---

## Prompt 7: Add person/output_dir to fetch_favorable_month_days

Can you expand the 'fetch_favorable_month_days' script to
1. Take in the name of the individual whose nakshatram, preferred days details are passed on -- via an argument  (say str person)
2. Create ability in the script to not just print the output in stdout, but also as a folder specific to the 'person' and within that a file for each month, year for which the preferable day/nakshatram/yogam matches are calculated ?
3. Take as argument in the script for output dir (say str output_dir) and store the results within that dir ?
4. Test the scripts and make necessary changes to test cases as well as additional test cases for the above and make sure they pass

---

## Prompt 8: Bug report — person/output_dir silently ignored, HTML cache files appear in output_dir instead

If I pass the output_dir and person name as given below, I still dont find a txt file per month under a directory 'sreenaath'. Infact I dont find 'sreenaath' directory under "output_results" directory in the below exmaples. All I see is bunch of html files (likely from crawling drikpanchang website) placed "output_dir"

Find below the direcotry contents --
```
(.venv) sreenaath@sreenaaths-MacBook-Pro tools % ls output_results
5400075_20260902.html   5400075_20260909.html   5400075_20260916.html   5400075_20260923.html   5400075_20260930.html
5400075_20260904.html   5400075_20260911.html   5400075_20260918.html   5400075_20260925.html
5400075_20260905.html   5400075_20260912.html   5400075_20260919.html   5400075_20260926.html
5400075_20260907.html   5400075_20260914.html   5400075_20260921.html   5400075_20260928.html
```

This is the test comand used --
```
>>> import panchangam_utils as pu
>>> pu.fetch_favorable_month_days(["Wednesday", "Friday", "Saturday", "Monday"], "Uthiradam", "Sunnyvale", "September 2026", 1, "sreenaath", "output_results")
```

---

## Prompt 9: Move person right after forward_looking_months (mandatory), default output_dir from person

1. Can you move the two arguments "person" right after the "forward_looking_months" argument in the fetch_favorable_month_days() function ? Make it mandatory argument and make the corresponding changes in the test file too and test them out.
2. If "output_dir" argument is not provided, make the necessary code change to assume "output_dir" value by appending "output_dir" string to the "person" argument string to make the "output_dir" value relative to the current directory. Make the test changes and additional test case to make this change and verify

---

## Prompt 10: Add a CLI (main) to run fetch_favorable_month_days from the command line

generate the code necessary to execute from main..iow, execute the python function 'fetch_favorable_month_days()' directory by executing the file panchangam_utils like 'python3 fetch_favorable_month_days.py ' with all mandatory fields from the command line.

Make the code changes necessary in main function in python, by usign appriiate classes like ArgumentParser and marking optional parameters, where needed.

Also generate, alter test cases to invoke both from the cli and the function fetch_favorable_month_days() directly from another python script.

---

## Prompt 11: Fix default output_dir prefix to {person}_ instead of {person}

Please fix the output dir generation to {person}_ as prefix and not just {person} prefix.

For example, for this run 'python3 panchangam_utils.py Monday Wednesday Uthiradam Chennai "September 2026" Sreenaath --forward-looking-months 1'
I want the output dir as 'Sreenaath_output_dir' and not 'Sreenaathoutput_dir'

---

## Prompt 12: Consolidated per-month tabular JSON summary

1. After all per month .txt files predictions (day/times) are generated, the ask is to collate through all the predictions for the person in the output_dir, for each month and create a json or text file of consolidated tabular view, per month, across all the projected months to the user.  Do this in the main workflow, after per month results are generated and saved. Store the consoldiated view in the same "output_dir" specific to the person with the following naming convention {person}_{starting_month_year}_{forward_looking_months}.json.
2. Create a utility function for this collation and saving logic and use this in the top level function 'fetch_favorable_month_days' or in the main function after calling 'fetch_favorable_month_days'.
3. generate additional test cases to test this collation and saving logic
