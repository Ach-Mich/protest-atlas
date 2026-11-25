# Rules for the daily data update

Whatever writes `data/briefings.json` (a script, a Claude routine or a person) should follow these rules. The site reads the file as it is, so mistakes here show up on the page.

## After every update
Run both commands from the site folder, in this order:

```
python3 tools/check_briefings.py && python3 tools/make_fallback.py && python3 tools/build_pages.py --site https://YOUR-ADDRESS
```

The third rebuilds the share pages (`c/<code>/`), their preview pictures and `feed.xml`. Replace YOUR-ADDRESS with the site's public address once it is online.

The first stops with an error if a rule below is broken. Fix the file and run it again. The second refreshes the saved copy the page shows when the live data can't load.

## Per country

| Field | Rule |
|---|---|
| `tier` | `watch` when a national protest or strike has been reported recently, otherwise `screen`. |
| `checkedAt` | When this country was last checked, ISO time with offset, e.g. `2026-11-24T06:40:00+01:00`. Update it every day, even when nothing changed: it is shown in the panel as "Last checked". |
| `summary` | 2 or 3 plain sentences: who, why, what happened last, what comes next. Mention how the movement started and any major government response. |
| `reasons` | **Why** people protest: the causes, in their terms (`Corruption`, `Rail safety after the Urda crash`). Never a demand. `Resignation of PM X`, `Repeal the law`, `Release detainees` are demands and belong in `groups[].items`. Leave the list empty if no cause is stated; the panel then says "no clear demands reported so far". |
| `themes` | Only these codes: `cost`, `wages`, `housing`, `education`, `austerity`, `services`, `governance`, `war`, `media`, `rights`. Leave empty if none fits; the country then appears under the "No stated cause" filter. |
| `groups[]` | Who is protesting (`name`, `type`, `since`) and what they want (`items` = demands). |
| `pressure` | `demand` (`policy` / `programme` / `resignation`), `response` (`none` / `talks` / `crisis`), optional `fragility`, `crackdown`, `opposition`, each with a short note and sources. |
| `nextDate`, `next` | Only for a date already called by organisers or unions. `YYYY-MM-DD`. |
| `story` | Optional. The home page no longer shows it; only the old map view (`map.html`) does. Drop it to save work if you don't need the map view. |

## Per protest day (`events[]`)

| Field | Rule |
|---|---|
| `date`, `title`, `cause`, `src` | Always. At least one source per day. |
| `off`, `orgc` | Official/police count and organisers' count, as numbers. Use `null` when not reported. Never estimate or copy one into the other. |
| `arrests`, `deaths`, `policeInj`, `protInj` | Numbers or `null`. |
| `arrestsNote`, `extra`, `warn` | Short context. **Never name people who were arrested or injured**, unless they are public officials. Write "two coordinators were held", not their names. |

## Paste-ready instruction for a Claude routine
If the update is done by a Claude routine, add this to its prompt:

> When writing data/briefings.json, follow /Users/achard/Downloads/protest-atlas-site/DATA-RULES.md. In particular: `reasons` are causes, never demands; the `story` field is optional; use `null` for unreported turnout; never name arrested or injured private people; update every country's `checkedAt`. When done, run `cd /Users/achard/Downloads/protest-atlas-site && python3 tools/check_briefings.py && python3 tools/make_fallback.py && python3 tools/build_pages.py --site https://YOUR-ADDRESS`. If the check reports errors, fix the file and run it again until it passes.
