#!/usr/bin/env python3
"""Protest Atlas data review.

Reads data/briefings.json and prints a Markdown checklist of what a person should verify by hand,
highest risk first. It never changes data.

  python3 tools/validate.py                      # full review
  python3 tools/validate.py --since HEAD~1       # also list events added or changed since a git ref
  python3 tools/validate.py --links              # also check that every source URL still opens (needs internet)
  python3 tools/validate.py -o review.md         # write to a file
  python3 tools/validate.py --since HEAD --only-changed   # daily mode: only events added or revised since the ref
  python3 tools/validate.py --mark-reviewed      # after you checked the current list by hand: stop listing those items until they change

Exit code 1 if any "blocking" problem is found (bad structure, missing source, impossible numbers).
"""
import argparse, json, os, re, subprocess, sys, datetime as dt
from urllib.parse import urlparse

TODAY = dt.date.today()

# Source quality. Extend freely.
STRONG = {"reuters.com","apnews.com","afp.com","france24.com","bbc.com","bbc.co.uk","euronews.com","lemonde.fr","lefigaro.fr","liberation.fr",
  "francetvinfo.fr","rfi.fr","publicsenat.fr","politis.fr","ansa.it","corriere.it","repubblica.it","ilsole24ore.com","elpais.com","rtve.es","efe.com","europapress.es",
  "zeit.de","spiegel.de","tagesschau.de","dw.com","faz.net","sueddeutsche.de","rte.ie","irishtimes.com","thejournal.ie","brusselstimes.com","rtbf.be","vrt.be","belga.be",
  "nos.nl","nu.nl","dr.dk","svt.se","sverigesradio.se","nrk.no","yle.fi","err.ee","lrt.lt","lsm.lv","polskieradio.pl","pap.pl","tvn24.pl","ceskatelevize.cz","irozhlas.cz",
  "orf.at","derstandard.at","srf.ch","swissinfo.ch","rts.ch","bta.bg","ertnews.gr","ekathimerini.com","kathimerini.gr","rtp.pt","publico.pt","lusa.pt","tanjug.rs","rferl.org",
  "balkaninsight.com","europeanwesternbalkans.com","ukrinform.net","kyivindependent.com","aljazeera.com","theguardian.com","ft.com","cbsnews.com","nbcnews.com","wtop.com",
  "washingtontimes.com","thestar.com.my","dawn.com","n1info.ba","exit.al","english.sta.si","sta.si","hrt.hr","index.hr","mia.mk","kiprinform.com","cyprus-mail.com",
  "gazetatema.net","bfmtv.com","acteurspublics.fr","leparisien.fr","ouest-france.fr","lexpress.fr","lepoint.fr","20minutes.fr","la-croix.com","latribune.fr","lesechos.fr","courrierinternational.com","tf1info.fr","europe1.fr","rtl.fr","ledevoir.com","tagesschau.de","zdf.de","n-tv.de","tvn24.pl","abcnews.com","abcnews.go.com","lalibre.be","lavenir.net","lesoir.be","hln.be","standaard.be","franceinfo.fr","parismatch.be","itv.com","nltimes.nl","thelocal.es","thelocal.com","thelocal.de","thelocal.fr","thelocal.it","aa.com.tr","vienna.at","vol.at","sofiaglobe.com","nytimes.com","washingtonpost.com","cnn.com","politico.eu","globalfreedomofexpression.columbia.edu","cyprus-faq.com","europa.eu","eurostat.ec.europa.eu","gov.uk","interieur.gouv.fr","police.be","politiet.no","cgil.it","ccoo.es","ugt.es","cgtp.pt","fgtb.be","csc-en-ligne.be"}
WEAK = {"gdeltcloud.com","wikipedia.org","ground.news","groundnews.lakegeneva.lib.wi.us","reddit.com","x.com","twitter.com","facebook.com","youtube.com","tiktok.com",
  "sopaimages.com","anadoluimages.com","imago-images.com","imago-images.de","europeanconservative.com","rtonews7.blogspot.com","blogspot.com","substack.com","medium.com",
  "wsws.org","socialistworld.net","visitworld.today","pixidia.com","newstimes.com.ng"}

def dom(url):
    h = (urlparse(url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h
def tier(url):
    d = dom(url)
    def match(s): return any(d == x or d.endswith("." + x) for x in s)
    return "strong" if match(STRONG) else "weak" if match(WEAK) else "unknown"

def parse_date(s):
    try:
        return dt.date.fromisoformat(s)
    except Exception:
        return None

def load(path_or_ref):
    return json.load(open(path_or_ref, encoding="utf-8"))

def load_ref(ref):
    out = subprocess.check_output(["git", "show", f"{ref}:data/briefings.json"])
    return json.loads(out)

REVIEWED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reviewed.json")
def fp_event(c, e):
    keys = ("date", "title", "off", "orgc", "arrests", "policeInj", "protInj", "deaths")
    return c + "|" + "|".join(str(e.get(k)) for k in keys) + "|" + ",".join(sorted(s[1] for s in e.get("src") or []))
def fp_last(c, lp):
    return c + "|lastProtest|" + "|".join(str(lp.get(k)) for k in ("date", "title")) + "|" + ",".join(sorted(s[1] for s in lp.get("src") or []))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/briefings.json")
    ap.add_argument("--since")
    ap.add_argument("--links", action="store_true")
    ap.add_argument("-o", "--out")
    ap.add_argument("--only-changed", action="store_true")
    ap.add_argument("--mark-reviewed", action="store_true")
    a = ap.parse_args()
    D = load(a.data)
    block, p1, p2, p3 = [], [], [], []   # blocking, serious figures, source quality, hygiene
    def add(lst, c, msg): lst.append(f"- **{c}** {msg}")
    REVIEWED = set(json.load(open(REVIEWED_FILE)) if os.path.exists(REVIEWED_FILE) else [])
    changed = None
    if a.only_changed:
        if not a.since: sys.exit("--only-changed needs --since <git ref>")
        old = load_ref(a.since)
        oldfp = {fp_event(c, e) for c, P in old.items() for e in P.get("events", [])} | {fp_last(c, P["lastProtest"]) for c, P in old.items() if P.get("lastProtest")}
        changed = {fp_event(c, e) for c, P in D.items() for e in P.get("events", [])} | {fp_last(c, P["lastProtest"]) for c, P in D.items() if P.get("lastProtest")}
        changed -= oldfp
    flagged = set(); cur = [None]
    def addp(lst, c, msg):
        fp = cur[0]
        if fp in REVIEWED: return
        if changed is not None and fp not in changed: return
        flagged.add(fp); add(lst, c, msg)

    for c, P in sorted(D.items()):
        name = P.get("country", c)
        tag = f"{name} ({c})"
        if P.get("tier") not in ("watch", "screen"): add(block, tag, "tier must be `watch` or `screen`.")
        for f in ("country", "events", "summary", "next"):
            if f not in P: add(block, tag, f"missing field `{f}`.")
        ev = P.get("events", [])
        seen = set()
        for e in ev:
            d = parse_date(e.get("date", ""))
            ref = f"{tag}, {e.get('date')} “{e.get('title','')[:70]}”"
            cur[0] = fp_event(c, e)
            if not d: add(block, ref, "date is not YYYY-MM-DD."); continue
            if d > TODAY + dt.timedelta(days=1): add(block, ref, "event date is in the future.")
            key = (e.get("date"), e.get("title"))
            if key in seen: add(p3, ref, "duplicate event.")
            seen.add(key)
            src = e.get("src") or []
            if not src or not all(len(s) == 2 and str(s[1]).startswith("http") for s in src): add(block, ref, "missing or malformed source link.")
            off, orgc = e.get("off"), e.get("orgc")
            for k in ("off", "orgc", "arrests", "policeInj", "protInj", "deaths"):
                v = e.get(k)
                if v is not None and (not isinstance(v, (int, float)) or v < 0): add(block, ref, f"`{k}` must be a non-negative number or null.")
            if off and orgc and orgc < off: add(block, ref, f"organisers' count ({orgc:,}) is lower than the official count ({off:,}); check which is which.")
            if off and orgc and orgc / off > 4: addp(p1, ref, f"organisers/official ratio is {orgc/off:.1f}× (usual 1.5–3×): {off:,} vs {orgc:,}.")
            big = max(off or 0, orgc or 0)
            if big >= 100000: addp(p1, ref, f"large crowd figure ({big:,}); confirm against two sources.")
            if e.get("deaths"): addp(p1, ref, f"**{e['deaths']} death(s)** recorded. Needs two independent sources and a check that the death is caused by or during the protest.")
            if (e.get("policeInj") or 0) + (e.get("protInj") or 0) >= 50: addp(p1, ref, "injury figure ≥ 50; confirm the source and whether it is cumulative.")
            if (e.get("arrests") or 0) >= 500: addp(p1, ref, f"{e['arrests']:,} arrests; confirm (cumulative across cities, or police figure?).")
            tiers = [tier(s[1]) for s in src] if src else []
            if tiers and all(t == "weak" for t in tiers): addp(p2, ref, "all sources are weak (" + ", ".join(sorted({dom(s[1]) for s in src})) + ").")
            elif tiers and "strong" not in tiers and not e.get("warn"): addp(p2, ref, "no recognised news source (" + ", ".join(sorted({dom(s[1]) for s in src})) + ") and no `warn` flag.")
            if len(src) == 1 and not e.get("warn") and (e.get("deaths") or big >= 50000): addp(p2, ref, "single source for a high-stakes figure; add a second source or a `warn`.")
        # country level
        if P.get("tier") == "watch":
            ck = P.get("checkedAt")
            try:
                age = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(ck)).total_seconds() / 86400
                if age > 2: add(p3, tag, f"watch country not checked for {age:.1f} days.")
            except Exception: add(p3, tag, "missing or invalid `checkedAt`.")
        nd = parse_date(P.get("nextDate", "")) if P.get("nextDate") else None
        if P.get("nextDate") and not nd: add(block, tag, "`nextDate` is not YYYY-MM-DD.")
        if nd and nd < TODAY - dt.timedelta(days=1): add(p3, tag, f"`nextDate` {nd} has passed; remove it or add the event.")
        if P.get("nextStrike") and not P.get("nextDate"): add(p3, tag, "`nextStrike` is set but there is no `nextDate`.")
        recent = [e for e in ev if (d := parse_date(e.get("date", ""))) and (TODAY - d).days <= 30 and not e.get("minor")]
        if recent and P.get("reasons") and not P.get("pressure"): add(p3, tag, "national protest in the last 30 days but no `pressure` block.")
        if recent and P.get("reasons") and not P.get("themes"): add(p3, tag, "national protest in the last 30 days with reasons but no `themes`.")
        lp = P.get("lastProtest")
        if lp:
            cur[0] = fp_last(c, lp)
            lt = [tier(s[1]) for s in lp.get("src", [])]
            if not lt or "strong" not in lt: addp(p2, tag, f"`lastProtest` ({lp.get('date')}) rests on weak or unknown sources ({', '.join(dom(s[1]) for s in lp.get('src', []))}).")

    changes = []
    if a.since:
        try:
            old = load_ref(a.since)
            for c, P in sorted(D.items()):
                O = {(e["date"], e["title"]): e for e in old.get(c, {}).get("events", [])}
                for e in P.get("events", []):
                    k = (e["date"], e["title"])
                    if k not in O: changes.append(f"- **{P['country']}** NEW {e['date']} “{e['title']}” (off {e.get('off')}, orgs {e.get('orgc')}, arrests {e.get('arrests')}, deaths {e.get('deaths')}) · {', '.join(s[1] for s in e['src'])}")
                    elif any(O[k].get(f) != e.get(f) for f in ("off", "orgc", "arrests", "deaths", "policeInj", "protInj")):
                        diff = ", ".join(f"{f}: {O[k].get(f)} → {e.get(f)}" for f in ("off", "orgc", "arrests", "deaths", "policeInj", "protInj") if O[k].get(f) != e.get(f))
                        changes.append(f"- **{P['country']}** REVISED {e['date']} “{e['title']}”: {diff}")
        except Exception as ex:
            changes.append(f"- could not read `{a.since}`: {ex}")

    dead = []
    if a.links:
        import urllib.request
        urls = {}
        for c, P in D.items():
            for e in P.get("events", []):
                for s in e.get("src", []): urls.setdefault(s[1], f"{P['country']} {e['date']}")
        for u, w in sorted(urls.items()):
            try:
                r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 ProtestAtlasReview"}), timeout=15)
                if r.status >= 400: dead.append(f"- {w}: HTTP {r.status} {u}")
            except Exception as ex:
                dead.append(f"- {w}: {type(ex).__name__} {u}")

    n_ev = sum(len(P.get("events", [])) for P in D.values())
    if a.mark_reviewed:
        cur_rev = REVIEWED | flagged
        json.dump(sorted(cur_rev), open(REVIEWED_FILE, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        print(f"Marked {len(flagged)} items as reviewed ({len(cur_rev)} in total) in {REVIEWED_FILE}.")
        return
    out = [f"# Protest Atlas data review · {TODAY}", "",
           f"{len(D)} countries, {n_ev} events. Work top to bottom; the first sections are the ones that would hurt most if wrong.", ""]
    def sec(title, lst, empty="Nothing to check."):
        out.extend([f"## {title} ({len(lst)})", ""] + (lst if lst else [empty]) + [""])
    sec("0. Blocking problems (fix before publishing)", block)
    sec("1. High-stakes figures to confirm by hand", p1)
    sec("2. Source quality", p2)
    if a.since: sec(f"3. Added or revised since `{a.since}`", changes, "No event changes.")
    if a.links: sec("4. Source links that no longer open", dead)
    sec("5. Housekeeping", p3)
    out.extend(["## How to verify an item", "",
        "1. Open the source link and check the number, date and place match what we show.",
        "2. For deaths, injuries, arrests and crowds over 100,000: find a second independent source (agency, public broadcaster, official statement).",
        "3. If only one source exists, keep the figure but add a `warn` (\"Single source so far\").",
        "4. Compare with ACLED once a week (see README) for events we missed.", ""])
    text = "\n".join(out)
    if a.out: open(a.out, "w", encoding="utf-8").write(text)
    else: print(text)
    sys.exit(1 if block else 0)

if __name__ == "__main__":
    main()
