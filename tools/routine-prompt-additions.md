# Additions for the daily routine prompt

Paste these blocks into the scheduled prompt (see the step-by-step in the chat). Keep the existing prompt; add or replace only what is named.

## A. New optional field (add to "Document fields")
- lastProtest (screen countries with no events): {date "YYYY-MM-DD" or "YYYY-MM", title, warn (optional, e.g. "Single source"), src [[label, url]]}. The most recent protest we know of, from a news source. Update it when a quiet country has a new protest. Never use Wikipedia lists, GDELT or photo-agency captions as the only source; if that is all there is, add a "warn".

## B. Rules to add under "Document fields" or "Writing"
- Deaths: record a death only with two independent sources (agency, public broadcaster or official statement) and only if caused by or during the protest. If only one source exists, put it in "extra" with a "warn" and mention it at the top of the final summary.
- Start of a movement: when a country's movement is new, search from its first day, not only since checkedAt, and add one event per national day and per significant smaller action (the France autumn movement was missed for four weeks).
- Pre-event notices (articles published before the day) do not confirm turnout: add "warn": "Source is a pre-event notice; turnout not found".
- Crowd figures: official (police or ministry) figure in "off", organisers' in "orgc", never mix them. If a figure comes from a press summary and not from the ministry or organisers themselves, add a "warn".

## C. New validation step, BEFORE the commit and push
Split the old step 5 into three: 5 prepare the website data, 6 validate, 7 commit and push. The validation must run before anything is pushed, so that a problem can be fixed first.
6. In the cloned repository, after data/briefings.json and the history file have been written but before committing, run `python3 tools/validate.py --since HEAD -o /tmp/review.md` (HEAD is the last commit, so this lists what this run added or changed). Read /tmp/review.md.
   - If section 0 (blocking problems) is not empty, fix the data and re-run; if you cannot, do not push, say so at the top of the final summary and send a notification.
   - Put the items of section 1 (high-stakes figures) and section 3 (events added or revised) in the final summary under "To check by hand", with the source links.
   - The review file is written outside the repository, so it is never committed.

## D. Notification rules (add to the end)
Send a notification (PushNotification, inside <routine_summary>) when: a death or serious-injury figure was added or revised; a new national strike date was announced; a country changed tier or moved to Major; the validator found a blocking problem; or any step failed (access denied, push failed). Stay silent when nothing changed.

## E. Weekly ACLED check (optional, once the ingest tool exists)
If a file `review/acled_latest.md` was updated in the last 8 days, read it, research the countries it flags (steps 1 and 2 of the prompt), and list what you found.

## F. Translation (only after the phase 2 decision)
For each briefing, also write "i18n": {"fr": {summary, reasons, next, groups[].name/short/items, events[].title/cause/org/extra}, "de": {...}} with the same structure, translated faithfully; keep source titles and numbers unchanged.

## G. Update (quiet validation and scripted snapshot)
The merged prompt in routine-prompt-full.md now (a) computes the daily snapshot with `python3 tools/snapshot.py` and rewrites today's history document if data changed after an earlier run, and (b) validates with `--only-changed`, so only new or revised items appear under "To check by hand". After you have checked the current list by hand, run `python3 tools/validate.py --mark-reviewed` and commit `tools/reviewed.json`: those items stop being listed until they change.

## H. Timestamps
Use the real current time from `TZ=Europe/Paris date -Iseconds` for checkedAt, updatedAt and screenedAt, never a time you made up, and never move a stored timestamp backwards.
