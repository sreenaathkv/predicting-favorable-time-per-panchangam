---
name: predicting-favorable-time-per-panchangam
description: A comprehensive way to generate and predict favorable days and times for a given person. Use this when users want to find out a good day, time for any possible activity or even to find it out of curiosity.
---

# Predict Favorable Time per Panchangam
Comprehensive way to predict good days/time for a user, given their details like birth nakshatram (star), favorable days of the week, etc.

# Input Format
## When inputs are provided, per the requirement
User should be asked to provide the following mandatory details for this skill to be used.
- **Person Name** -- To help associate the computed calculations and predictions to a person.
- **Birth Nakshtram or Janma Nakshatram** -- This determines the favorable set of Nakshatrams (stars) from the overall pool of 27 Nakshatrams (stars)
- **Favorable days of the week** -- This is required to intersect the favorable Nakshatrams on these days to predict/find suitable day/time for the person.
- **City, State, Country** -- This is the location (City) (State, Country maybe required for disambiguation if there is identical city names), where the favorable day/time prediction is to be cast on.
- **Starting Month Year** -- This is the Month, Year from which the user expects the prediction to be projected from.
- **Prediction Months** -- This could also be referred as Forward_Looking_Months. This basically is number of months for which the user requires the favorable day/times to be predicted. It could be any number of months from 1+.

## Lack of inputs or how to proceed when there is ambiguity
When a user asks something like "is there an auspicious date to start X" or "muhurtham for Y" or "Find me a good day and time to buy a car", explicitly prompt the user to input the required arguments for executing the Predictor script (panchangam_utils.py) under scripts/ folder. For list of required arguments from user, refer to the above section ('When inputs are provided, per the requirement').

# Workflow
**Step 1: Sanitization** - First confirm if all the details from the user required for this skill, as mentioned in the Input Format section are available. If not, prompt and get additional details.

**Step 2: Tool call** - Execute the function fetch_favorable_month_days() in scripts/panchangam_utils.py by passing on the Input parameters. 
Following is an example invocation

```bash
cd scripts && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && python3 panchangam_utils.py Monday Wednesday Friday Saturday Uthiradam Chennai "September 2026" Jai --forward-looking-months 6
```

**Step 3 : Report to user** - 
a) The above step (Step 2) runs through complex calculation by finding intersection of favorable days of the week AND favorable nakshatrams relative to birth nakshatram AND favorable yogam (Siddha or Amrutha Tamil yogam). When combination of all three of them exists for a given day, that narrow window of time becomes a favorable time for that person. The above step should produce the results for the person in either user provided 'output_dir' argument or '{person}_output_dir' directory relative to the current directory of execution.

b) Once, for each month, the prediction .txt files are created, the script automatically collates them across months and will create a JSON file with consolidated view in the same "output_dir" specific to the person with the following naming convention {person}_{starting_month_year}_{forward_looking_months}.json.

c) Once the consolidated view is generated in {person}_{starting_month_year}_{forward_looking_months}.json file, please display the same to  user in a nice tabular form, across months, for all the projected months and years (refer to assets/output_template.md).

# Output Files
--{person}_{output_dir}/{person}
   |
   |- {starting_month_year}.txt
   |
   |....
   |
   |-{person}_{starting_month_year}_{forward_looking_months}.json

## References
For domain knowledge on Nakshatram, Tamil Yogam, how auspicious days/times are calculated, please refer the following reference file.
Also it contains in depth detail of the architecture/inner working of the 'panchangam_utils.py ' script referenced in the 'Workflow' section above along with dependency and inner working of external panchang website (www.drikpanchang.com) that the script depends on as well its limitations and workarounds.
 -- references/domain_knowledge.md

## Output Format Guidelines
For output format, refer to the 'assets' folder, in particular the 'output_template.md' markdown files for the template outlay to be used for printing the collating output to the user.

## Dependencies

`geonamescache`, `lxml`, `bs4`, `requests`


