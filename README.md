# Protest Atlas

Where people are taking to the streets, and why: a protest watch for Europe, going worldwide.

- `index.html` – the whole site (Home, Report, world map with country briefings).
- `i18n.js` – interface translations (English, French, German) and the language switcher. Briefing texts written by the daily update are still English only.
- `data/briefings.json` – one entry per tracked country, updated daily.
- `data/history/YYYY-MM-DD.json` – one snapshot per day, used for trends.

The page loads `data/briefings.json` when it opens; if that file is missing it shows the snapshot built into the page.

## Sources and credits
- Protest figures: news agencies, public broadcasters and official statements, linked in each briefing.
- Borders: Natural Earth (public domain), via world-atlas 2.0.2.
- Inflation and unemployment: Eurostat.
- Political stability: World Bank Worldwide Governance Indicators (CC BY 4.0).

Levels and "pressure on government" are Protest Atlas assessments built with fixed rules, not official measures.

## Checking the data
`python3 tools/validate.py` prints a Markdown checklist of what to verify by hand, highest risk first: structure errors, large crowd, arrest, injury and death figures, weak or single sources, and housekeeping. Useful options: `--since HEAD~1` lists events added or revised since a git ref (the daily review list), `--links` checks that every source URL still opens, `-o review.md` writes the report to a file. It never changes data and exits with code 1 if it finds a blocking problem. Source quality lists (`STRONG`, `WEAK`) are at the top of the script.
