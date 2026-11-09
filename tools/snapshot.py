#!/usr/bin/env python3
"""Compute the daily history snapshot from data/briefings.json.

  python3 tools/snapshot.py                      # print today's snapshot (Europe/Paris date)
  python3 tools/snapshot.py --date 2026-11-09 -o snapshot.json
  python3 tools/snapshot.py --check data/history/2026-11-08.json --date 2026-11-08 --data old_briefings.json

The snapshot has the same shape as the files in data/history/. Computing it with a script, not by hand, keeps every day identical in method.
"""
import argparse, json, datetime as dt, sys
try:
    from zoneinfo import ZoneInfo
    TODAY = dt.datetime.now(ZoneInfo("Europe/Paris")).date()
except Exception:
    TODAY = dt.date.today()

def snap(D, today):
    out = {}
    for c, P in sorted(D.items()):
        ev = P.get("events") or []
        recent = [e for e in ev if 0 <= (today - dt.date.fromisoformat(e["date"])).days <= 30]
        nat = [e for e in recent if not e.get("minor")]
        mino = [e for e in recent if e.get("minor")]
        last_nat = max((e["date"] for e in ev if not e.get("minor") and dt.date.fromisoformat(e["date"]) <= today), default=None)
        nums = lambda k, L: [e[k] for e in L if e.get(k) is not None]
        arr = nums("arrests", recent)
        pr = P.get("pressure")
        nd = P.get("nextDate")
        if nd and dt.date.fromisoformat(nd) < today: nd = None
        out[c] = {
            "tier": P.get("tier"), "nat30": len(nat), "minor30": len(mino), "lastNational": last_nat,
            "peakOff": max(nums("off", nat), default=None), "peakOrgc": max(nums("orgc", nat), default=None),
            "arrests30": sum(arr) if arr else None, "deaths30": sum(e.get("deaths") or 0 for e in recent),
            "strike30": any(e.get("strike") for e in nat), "nextDate": nd, "nextStrike": bool(P.get("nextStrike")) if nd else False,
            "themes": P.get("themes") or [], "groupTypes": sorted({g["type"] for g in P.get("groups") or [] if g.get("type")}),
            "pressure": ({**{"demand": pr.get("demand"), "opposition": bool(pr.get("opposition")), "crackdown": bool(pr.get("crackdown")),
                          "response": pr.get("response")}, **({"fragility": pr["fragility"]} if pr.get("fragility") else {})} if pr else None)}
    return {"date": today.isoformat(), "countries": out}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/briefings.json"); ap.add_argument("--date"); ap.add_argument("-o", "--out"); ap.add_argument("--check")
    a = ap.parse_args()
    today = dt.date.fromisoformat(a.date) if a.date else TODAY
    s = snap(json.load(open(a.data, encoding="utf-8")), today)
    if a.check:
        ref = json.load(open(a.check, encoding="utf-8")); bad = 0
        for c, v in s["countries"].items():
            for k, x in v.items():
                y = ref["countries"].get(c, {}).get(k, "MISSING")
                if k == "groupTypes": x, y = sorted(x), sorted(y) if isinstance(y, list) else y
                if x != y: bad += 1; print(f"{c}.{k}: script={x!r} reference={y!r}")
        print("identical" if not bad else f"{bad} differences"); sys.exit(1 if bad else 0)
    text = json.dumps(s, indent=2, ensure_ascii=False)
    if a.out: open(a.out, "w", encoding="utf-8").write(text + "\n")
    else: print(text)
if __name__ == "__main__": main()
