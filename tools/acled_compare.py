#!/usr/bin/env python3
"""Compare Protest Atlas with an ACLED weekly aggregated export (Europe).

  python3 tools/acled_compare.py path/to/ACLED_export.csv [-o acled_review.md] [--weeks 4]

ACLED rows are weekly counts per country and region (columns: week, country, admin1, event_type, events, fatalities...).
This is a recall check, not a figure check: it shows where ACLED sees protest activity that our data does not,
and the reverse, plus protest-related deaths. It never changes data.
"""
import argparse, csv, json, statistics, datetime as dt, collections, sys

NAME = {"Bosnia and Herzegovina": "Bosnia & Herzegovina", "Turkey": "Türkiye", "Czech Republic": "Czechia", "Macedonia": "North Macedonia",
        "Republic of Moldova": "Moldova", "Russian Federation": "Russia"}
DEMO = ("Protests", "Riots")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv"); ap.add_argument("--data", default="data/briefings.json")
    ap.add_argument("--weeks", type=int, default=4); ap.add_argument("-o", "--out")
    a = ap.parse_args()
    D = json.load(open(a.data, encoding="utf-8"))
    by_name = {P["country"]: (c, P) for c, P in D.items()}
    rows = list(csv.DictReader(open(a.csv, encoding="utf-8-sig")))
    wk = collections.defaultdict(lambda: collections.defaultdict(int))     # country -> week -> events (protests+riots)
    fat = collections.defaultdict(lambda: collections.defaultdict(int))
    sub = collections.defaultdict(lambda: collections.defaultdict(int))
    for r in rows:
        if r["event_type"] not in DEMO: continue
        c = NAME.get(r["country"], r["country"])
        n = int(r["events"] or 0); f = int(r["fatalities"] or 0)
        wk[c][r["week"]] += n; fat[c][r["week"]] += f
    weeks = sorted({r["week"] for r in rows})
    last = weeks[-a.weeks:]; base_weeks = weeks[:-a.weeks]
    w0 = dt.date.fromisoformat(last[0]); w1 = dt.date.fromisoformat(last[-1]) + dt.timedelta(days=6)
    out = [f"# ACLED comparison · {dt.date.today()}", "",
           f"ACLED weekly data {weeks[0]} to {weeks[-1]} (last week starts {last[-1]}). Comparing the last {a.weeks} weeks ({w0} to {w1}) with a baseline of the {len(base_weeks)} weeks before.",
           "ACLED counts protests and riots (all sizes, including very small ones). We track national days and larger or sector actions, so ACLED will always show more events. What matters is a *change* or a country where we see nothing.", ""]
    table = []
    for c in sorted(wk):
        if c not in by_name: continue
        code, P = by_name[c]
        ours = [e for e in P.get("events", []) if w0 <= dt.date.fromisoformat(e["date"]) <= w1]
        ours30 = [e for e in P.get("events", []) if (dt.date.today() - dt.date.fromisoformat(e["date"])).days <= 30]
        recent = [wk[c].get(w, 0) for w in last]; base = [wk[c].get(w, 0) for w in base_weeks]
        bmed = statistics.median(base) if base else 0
        rmean = sum(recent) / len(recent)
        dead = sum(fat[c].get(w, 0) for w in weeks[-8:])
        table.append((c, code, P.get("tier"), len(ours), len(ours30), sum(recent), bmed, rmean, dead, sum(e.get("deaths") or 0 for e in P.get("events", []) if (dt.date.today() - dt.date.fromisoformat(e["date"])).days <= 60)))
    miss = [t for t in table if t[4] == 0 and t[5] >= 8]
    spike = [t for t in table if t[7] >= 1.5 * max(t[6], 1) and t[7] >= 5 and t[4] == 0]
    over = [t for t in table if t[3] >= 2 and t[5] <= 3]
    deaths = [t for t in table if t[8] > 0 and t[9] == 0]
    def line(t): return f"- **{t[0]}** ({t[2]}): ACLED {t[5]} events in the window (baseline median {t[6]:.0f}/week, now {t[7]:.1f}/week); we record {t[3]} event(s) in the window."
    def sec(title, hint, ts, fmt=line):
        out.extend([f"## {title} ({len(ts)})", "", hint, ""] + ([fmt(t) for t in ts] or ["None."]) + [""])
    sec("1. Protest-related deaths in ACLED that we do not show", "ACLED records fatalities in protests or riots in the last 8 weeks, and we have no death recorded for the last 60 days. Check each; many are riots or police actions that may not belong in our data.", deaths,
        lambda t: f"- **{t[0]}** ({t[2]}): {t[8]} fatalit{'y' if t[8]==1 else 'ies'} in protests/riots (ACLED, last 8 weeks); we record {t[9]}.")
    sec("2. Possible misses: ACLED sees steady activity, we record nothing in 30 days", "At least 8 ACLED events in the window and no event of ours in the last 30 days. Search the news for these countries and add events if a national, sector or large regional action took place.", sorted(miss, key=lambda t: -t[5]))
    sec("3. Rising activity in ACLED with nothing in ours", "A rise of 1.5× over the baseline and at least 5 events a week.", sorted(spike, key=lambda t: -t[7]))
    sec("4. We show activity, ACLED shows very little", "Possible overstatement or a mismatch in what counts as a protest; low priority.", over)
    out.extend(["## All countries", "", "| Country | Our tier | ACLED events (window) | ACLED baseline/week | ACLED now/week | Our events (window) | Our events (30 d) |", "|---|---|---|---|---|---|---|"])
    for t in sorted(table, key=lambda t: -t[5]):
        out.append(f"| {t[0]} | {t[2]} | {t[5]} | {t[6]:.0f} | {t[7]:.1f} | {t[3]} | {t[4]} |")
    text = "\n".join(out) + "\n"
    if a.out: open(a.out, "w", encoding="utf-8").write(text)
    else: print(text)
if __name__ == "__main__": main()
