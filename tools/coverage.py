#!/usr/bin/env python3
"""Protest Atlas research coverage check (event-first routine).

Checks the run's research log (research/YYYY-MM-DD.json) against data/briefings.json and
tools/sources.json before anything is published:

  1. Detection: a Europe-wide sweep in several languages, the strike calendars, and one quick
     search per tracked country in its own language.
  2. Every protest day or announced date found is a candidate, tagged national or local, and was
     researched in proportion: national candidates need 2+ searches and a full page from an official,
     wire, public-broadcaster or press source; local ones need one opened page.
  3. Follow-up: every country with an event in the last 5 days, or a nextDate that has passed, has
     a candidate (so the outcome of a day of action is always looked up).

  python3 tools/coverage.py                       # today's log (Europe/Paris date)
  python3 tools/coverage.py --log research/2026-11-13.json -o /tmp/coverage.md

Exit code 1 if anything under "Not covered" is listed. The routine then does the missing work
and runs the check again before publishing.

Research log format (one file per day; a second run the same day adds to it):
{
  "date": "YYYY-MM-DD",
  "sweep":     [{"q": "general strike Europe", "lang": "en"}, {"q": "grève générale", "lang": "fr"}, ...],
  "calendars": [{"country": "IT", "url": "https://...", "ok": true}],
  "quick":     {"FR": {"q": "grève manifestation", "lang": "fr", "found": "one line"}, ... every tracked country},
  "candidates": [{
      "country": "FR", "date": "2026-11-17", "title": "Public-sector strike",
      "kind": "held" | "announced",
      "reach": "national" | "local",
      "rule": "strike nationwide" | "3+ cities, common call" | "capital, national organisers, 1 per 10,000" | "local",
      "searches": [{"q": "...", "lang": "fr"}],
      "opened":   [{"url": "https://...", "ok": true}],
      "outcome":  "added event" | "updated event" | "set nextDate" | "dropped: <why>",
      "answers":  {"what": "ok", "size": "gap", "who": "ok", "demands": "ok", "why": "ok", "next": "ok", "response": "ok"},
      "gaps":     ["no official count yet"]
  }]
}
answers (national candidates only): "ok", "gap" (explain in gaps) or "n/a".
"""
import argparse, datetime as dt, json, os, sys
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

QUESTIONS = ["what", "size", "who", "demands", "why", "next", "response"]
MIN_SWEEP, MIN_SWEEP_LANGS = 8, 4
FOLLOW_UP_DAYS = 5


def dom(url):
    h = (urlparse(url or "").hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def in_list(url, doms):
    d = dom(url)
    return any(d == g or d.endswith("." + g) for g in doms)


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
    log = json.load(open(a.log, encoding="utf-8")) if os.path.exists(a.log) else {}
    wire_default = src.get("_default", {}).get("wire", [])
    fails, warns = [], []

    # 1. Detection
    sweep = log.get("sweep", [])
    langs = {s.get("lang") for s in sweep}
    if len(sweep) < MIN_SWEEP or len(langs) < MIN_SWEEP_LANGS:
        fails.append(f"- **Sweep**: {len(sweep)} searches in {len(langs)} languages (minimum {MIN_SWEEP} in {MIN_SWEEP_LANGS}).")
    cal_done = {c.get("country") for c in log.get("calendars", [])}
    for c, p in src.items():
        if not c.startswith("_") and p.get("calendars") and c not in cal_done:
            fails.append(f"- **{c} strike calendar**: not checked ({', '.join(p['calendars'])}).")
    quick = log.get("quick", {})
    missing = []
    for c in sorted(data):
        first = (src.get(c, {}).get("languages") or ["en"])[0]
        q = quick.get(c)
        if not q or not (q.get("q") or "").strip():
            missing.append(c)
        elif q.get("lang") != first:
            fails.append(f"- **{c} quick check**: searched in {q.get('lang')}, not in {first}.")
    if missing:
        fails.append(f"- **Quick check missing** for {len(missing)} countries: {', '.join(missing)}.")

    # 2. Candidates researched in proportion
    cands = log.get("candidates", [])
    for k in cands:
        c = k.get("country", "?")
        name = f"{c} {k.get('date', '?')} “{(k.get('title') or '')[:60]}”"
        probs = []
        if k.get("reach") not in ("national", "local"):
            probs.append("reach not set to national or local")
        if not k.get("rule"):
            probs.append("no rule given for the reach")
        if not (k.get("outcome") or "").strip():
            probs.append("no outcome")
        opened = k.get("opened", [])
        p = src.get(c, {})
        good = p.get("official", []) + p.get("wire", []) + p.get("press", []) + p.get("organisers", []) + wire_default
        if k.get("reach") == "national":
            if len(k.get("searches", [])) < 2:
                probs.append(f"{len(k.get('searches', []))} searches (national candidates need 2)")
            if not any(in_list(o.get("url"), good) for o in opened):
                probs.append("no official, wire, broadcaster, press or organiser page from the profile opened")
            elif not any(o.get("ok") and in_list(o.get("url"), good) for o in opened):
                warns.append(f"- **{name}**: every profile page it tried failed; figures rest on other sources.")
            ans = k.get("answers", {})
            if not k.get("outcome", "").startswith("dropped"):
                un = [q for q in QUESTIONS if ans.get(q) not in ("ok", "gap", "n/a")]
                if un:
                    probs.append("questions not assessed: " + ", ".join(un))
                if any(ans.get(q) == "gap" for q in QUESTIONS) and not k.get("gaps"):
                    probs.append("answers marked 'gap' but no gaps[] explanation")
        elif k.get("reach") == "local" and not opened:
            probs.append("no page opened")
        if probs:
            fails.append(f"- **{name}**: " + "; ".join(probs) + ".")

    # 3. Follow-up on recent and passed days of action
    have = {}
    for k in cands:
        have.setdefault(k.get("country"), set()).add(k.get("date"))
    for c, d in sorted(data.items()):
        due = [e["date"] for e in d.get("events", []) if e.get("date") and 0 <= (today - dt.date.fromisoformat(e["date"])).days <= FOLLOW_UP_DAYS]
        nd = d.get("nextDate")
        if nd and 0 <= (today - dt.date.fromisoformat(nd)).days:
            due.append(nd)
            if (today - dt.date.fromisoformat(nd)).days > 0:
                warns.append(f"- **{d.get('country', c)} ({c})**: nextDate {nd} has passed; record the outcome and move or remove nextDate.")
        for day in sorted(set(due)):
            if day not in have.get(c, set()):
                fails.append(f"- **{d.get('country', c)} ({c})**: day of action on {day} has no candidate (outcome not looked up).")

    nat = sum(1 for k in cands if k.get("reach") == "national")
    out = [f"# Research coverage · {today.isoformat()}", "",
           f"Sweep {len(sweep)} searches in {len(langs)} languages · quick check {len(data) - len(missing)} of {len(data)} countries · "
           f"{len(cands)} candidates ({nat} national, {len(cands) - nat} local).", ""]
    out += [f"## Not covered ({len(fails)})", ""] + (fails or ["None."]) + [""]
    out += [f"## Warnings ({len(warns)})", ""] + (warns or ["None."]) + [""]
    txt = "\n".join(out)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(txt)
    print(txt)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
