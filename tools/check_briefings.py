#!/usr/bin/env python3
"""Check data/briefings.json before publishing.

Catches the problems that make a country panel unclear, for example a
"reason" that is really a demand ("Resignation of PM X") or a country on
watch with no reasons at all.

Usage:  python3 tools/check_briefings.py [path/to/briefings.json]
Exit code 1 when there is at least one error, so it can block a daily update.
"""
import json
import re
import sys
from datetime import date

THEMES = {"cost", "wages", "housing", "education", "austerity", "services",
          "governance", "war", "media", "rights"}
TIERS = {"watch", "screen"}
# Words that usually start a demand ("what they want") rather than a cause ("why").
DEMAND_WORDS = re.compile(
    r"^\s*(resign|resignation|repeal|scrap|stop|release|withdraw|abolish|"
    r"raise|freeze|ban|reinstate|keep|no more|end )", re.I)
NUM_FIELDS = ("off", "orgc", "arrests", "deaths", "policeInj", "protInj")
# Two capitalised words (a likely full name) in the same sentence as an arrest or injury word.
ARREST_WORD = re.compile(r"\b(held|arrest|detain|charged|injur|custody)\w*", re.I)
NAME_PAIR = re.compile(r"(?<![\w'])([A-Z][a-zà-ÿ]+) ([A-Z][a-zà-ÿ]+)\b")
# Titles before a name mean a public official, who may be named.
TITLES = {"minister", "president", "mayor", "premier", "chancellor", "commissioner", "prefect",
          "senator", "mp", "deputy", "governor", "leader", "spokesman", "spokeswoman", "spokesperson"}
# Words that make a capitalised pair an institution, a place or a sentence opener, not a person.
NOT_NAMES = {"state", "police", "national", "interior", "justice", "education", "health", "defence",
             "ministry", "minister", "government", "prefecture", "court", "office", "council", "city",
             "guard", "union", "unions", "party", "news", "euronews", "agency", "press", "radio", "tv",
             "boulevard", "street", "square", "avenue", "place", "road", "bridge", "station", "hall",
             "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
             "the", "a", "an", "on", "in", "at", "by", "after", "about", "nearly", "some", "most",
             "all", "several", "many", "police", "officers", "riot", "mossos", "carabinieri", "guardia"}


def likely_person(txt):
    for sent in re.split(r"[.;:]", txt):
        if not ARREST_WORD.search(sent):
            continue
        for m in NAME_PAIR.finditer(sent):
            a, b = m.group(1).lower(), m.group(2).lower()
            if a in NOT_NAMES or b in NOT_NAMES:
                continue
            before = sent[:m.start()].split()
            if before and before[-1].strip(",(").lower() in TITLES:
                continue
            return m.group(0)
    return None


def is_date(s):
    try:
        date.fromisoformat(s)
        return True
    except (TypeError, ValueError):
        return False


def check(data):
    errors, warnings = [], []
    for code, x in sorted(data.items()):
        name = x.get("country", code)
        where = f"{code} {name}"
        err = lambda m: errors.append(f"{where}: {m}")
        warn = lambda m: warnings.append(f"{where}: {m}")

        if x.get("tier") not in TIERS:
            err(f"tier is {x.get('tier')!r}, expected one of {sorted(TIERS)}")
        for t in x.get("themes") or []:
            if t not in THEMES:
                err(f"unknown theme {t!r} (no filter or label exists for it)")
        if not x.get("checkedAt"):
            err("has no checkedAt: the panel can't say when it was last checked")
        if x.get("nextDate") and not is_date(x["nextDate"]):
            err(f"nextDate {x['nextDate']!r} is not YYYY-MM-DD")
        for e in x.get("events") or []:
            if not is_date(e.get("date")):
                err(f"event {e.get('title')!r} has no valid date")
            if not e.get("title"):
                err(f"event on {e.get('date')} has no title")
            for f in NUM_FIELDS:
                v = e.get(f)
                if v is not None and not isinstance(v, (int, float)):
                    err(f"event {e.get('date')} field {f} should be a number, got {v!r}")
            if not e.get("src"):
                warn(f"event {e.get('date')} has no source")
            for f in ("arrestsNote", "protInjNote", "extra"):
                txt = e.get(f) or ""
                who = likely_person(txt)
                if who:
                    warn(f"event {e.get('date')} {f} may name an arrested or injured person ({who}): "
                         "keep counts, name only public officials")

        if x.get("tier") != "watch":
            continue
        # Panels for countries on watch
        if not (x.get("summary") or "").strip():
            err("on watch but has no summary")
        reasons = x.get("reasons") or []
        if not reasons:
            warn("on watch but has no reasons: the panel will say "
                 "'no clear demands reported so far'")
        demands = {i.strip().lower() for g in x.get("groups") or [] for i in g.get("items") or []}
        for r in reasons:
            if DEMAND_WORDS.search(r):
                err(f"reason {r!r} reads like a demand; reasons must say WHY "
                    "(the cause), demands belong in groups[].items")
            elif r.strip().lower() in demands:
                warn(f"reason {r!r} is also listed as a demand in groups; "
                     "fine if it is both a grievance and a demand")
        if not x.get("themes"):
            warn("on watch but has no themes: it is listed under the 'No stated cause' filter")
    return errors, warnings


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "data/briefings.json"
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    errors, warnings = check(data)
    for m in errors:
        print("ERROR  ", m)
    for m in warnings:
        print("warning", m)
    watched = sum(1 for x in data.values() if x.get("tier") == "watch")
    print(f"\n{len(data)} countries, {watched} on watch: "
          f"{len(errors)} error(s), {len(warnings)} warning(s)")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
