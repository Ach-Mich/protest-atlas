#!/usr/bin/env python3
"""Protest Atlas research coverage check.

Checks the run's research log (research/YYYY-MM-DD.json) against data/briefings.json and
tools/sources.json: did every watch country get real research today, in its own languages?

  python3 tools/coverage.py                       # today's log (Europe/Paris date)
  python3 tools/coverage.py --log research/2026-11-11.json -o /tmp/coverage.md

Exit code 1 if any watch country fails. The routine must then research the failing countries
and run the check again before publishing.

Research log format (one file per day; a second run the same day adds to it):
{
  "date": "YYYY-MM-DD",
  "countries": {
    "FR": {
      "searches": [{"q": "grève 10 novembre bilan", "lang": "fr"}, ...],
      "opened":   [{"url": "https://...", "ok": true}, {"url": "https://...", "ok": false, "error": "HTTP 403"}],
      "found":    "one line: what is new, or 'nothing new since <checkedAt>'",
      "answers":  {"what": "ok", "size": "ok", "who": "ok", "demands": "ok", "why": "ok", "next": "ok", "response": "ok"},
      "gaps":     ["no official count for 10 Nov: ministry page refused (403)"]
    }
  }
}
answers values: "ok", "gap" (could not answer; explain in gaps) or "n/a" (does not apply, e.g. response for a Quiet country).
"""
import argparse, datetime as dt, json, os, sys
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

QUESTIONS = ["what", "size", "who", "demands", "why", "next", "response"]
MIN_SEARCHES = 3
FOLLOW_UP_DAYS = 5   # runs are Tuesday and Friday: a day of action since the previous run needs at least one full article or official page opened


def dom(url):
    h = (urlparse(url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def main():
    today = dt.datetime.now(ZoneInfo("Europe/Paris")).date()
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=f"research/{today.isoformat()}.json")
    ap.add_argument("--data", default="data/briefings.json")
    ap.add_argument("--sources", default="tools/sources.json")
    ap.add_argument("-o", "--out")
    a = ap.parse_args()

    data = json.load(open(a.data, encoding="utf-8"))
    src = json.load(open(a.sources, encoding="utf-8"))
    log = json.load(open(a.log, encoding="utf-8")) if os.path.exists(a.log) else {"countries": {}}
    lc = log.get("countries", {})

    fails, warns, ok = [], [], []
    watch = sorted(c for c, d in data.items() if d.get("tier") == "watch")
    for c in watch:
        d, p, r = data[c], src.get(c, {}), lc.get(c)
        name = f"{d.get('country', c)} ({c})"
        if not r:
            fails.append(f"- **{name}**: no research logged today.")
            continue
        probs, soft = [], []
        searches = r.get("searches", [])
        langs = p.get("languages", ["en"])
        if len(searches) < MIN_SEARCHES:
            probs.append(f"{len(searches)} searches (minimum {MIN_SEARCHES})")
        used = {s.get("lang") for s in searches}
        need = [l for l in langs[:2] if l != "en"] or ["en"]
        missing = [l for l in need if l not in used]
        if missing:
            probs.append(f"no search in {', '.join(missing)}")
        opened = r.get("opened", [])
        if not opened:
            probs.append("no page opened (search snippets only)")
        elif not any(o.get("ok") for o in opened):
            soft.append("every page it tried to open failed")
        if not (r.get("found") or "").strip():
            probs.append("no 'found' line")
        ans = r.get("answers", {})
        unanswered = [q for q in QUESTIONS if ans.get(q) not in ("ok", "gap", "n/a")]
        if unanswered:
            probs.append("questions not assessed: " + ", ".join(unanswered))
        gaps = [q for q in QUESTIONS if ans.get(q) == "gap"]
        if gaps and not r.get("gaps"):
            probs.append("answers marked 'gap' but no gaps[] explanation")

        # A day of action in the last few days needs a follow-up beyond snippets.
        recent = [e["date"] for e in d.get("events", []) if e.get("date")
                  and 0 <= (today - dt.date.fromisoformat(e["date"])).days <= FOLLOW_UP_DAYS]
        nd = d.get("nextDate")
        if nd:
            delta = (today - dt.date.fromisoformat(nd)).days
            if 0 <= delta <= FOLLOW_UP_DAYS:
                recent.append(nd)
            if delta > 0:
                soft.append(f"nextDate {nd} has passed: record what happened and remove or move nextDate")
        if recent:
            good = set(p.get("official", []) + p.get("wire", []) + p.get("press", []) + src.get("_default", {}).get("wire", []))
            hit = [o for o in opened if any(dom(o.get("url", "")) == g or dom(o.get("url", "")).endswith("." + g) for g in good)]
            if not hit:
                probs.append(f"day of action on {', '.join(sorted(set(recent)))} but no official, wire or press page from the profile was opened")

        if probs:
            fails.append(f"- **{name}**: " + "; ".join(probs) + ".")
        else:
            ok.append(c)
        for s_ in soft:
            warns.append(f"- **{name}**: {s_}.")

    out = [f"# Research coverage · {today.isoformat()}", "",
           f"{len(ok)} of {len(watch)} watch countries fully researched.", ""]
    out += [f"## Not researched enough ({len(fails)})", ""] + (fails or ["None."]) + [""]
    out += [f"## Warnings ({len(warns)})", ""] + (warns or ["None."]) + [""]
    txt = "\n".join(out)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(txt)
    print(txt)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
