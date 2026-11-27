#!/usr/bin/env python3
"""Build the files that make Protest Atlas shareable and followable.

From data/briefings.json it writes:
  c/<code>/index.html   one readable page per country (full briefing in plain HTML),
                        with its own title, description and preview picture: search
                        engines can index it, and a link pasted into WhatsApp, X,
                        Signal or Slack shows a proper card.
  c/<code>/card.png     the 1200x630 preview picture for that country
  card.png              the preview picture for the home page
  feed.xml              RSS feed: latest protest day and announced date per country
  robots.txt, sitemap.xml  for search engines (the sitemap needs --site)

Usage (from the site folder):
  python3 tools/build_pages.py --site https://your-address.example
Link previews need the full public address of the site (--site). Without it the
pages are still built, with relative links, and previews won't show until you
rebuild with --site. Pictures need Google Chrome; without it they are skipped.
"""
import argparse
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

def find_chrome():
    """Google Chrome on a Mac, or Chrome/Chromium on Linux (e.g. GitHub Actions). $CHROME wins."""
    import shutil
    for c in (os.environ.get("CHROME"), "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"):
        if c and os.path.exists(c):
            return c
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        if shutil.which(name):
            return shutil.which(name)
    return ""


CHROME = find_chrome()
THEMES = {"cost": "Cost of living", "wages": "Wages & jobs", "housing": "Housing", "education": "Education",
          "austerity": "Pensions & austerity", "services": "Public services & health",
          "governance": "Corruption & governance", "war": "War, conscription & foreign policy",
          "media": "Media freedom", "rights": "Rights & equality"}
E = html.escape


def long_date(iso):
    d = datetime.fromisoformat(iso[:10])
    return f"{d.strftime('%A')} {d.day} {d.strftime('%B')}"


def latest_event(x):
    ev = sorted(x.get("events") or [], key=lambda e: e["date"])
    return ev[-1] if ev else None


def turnout(e):
    if not e:
        return ""
    if e.get("orgc"):
        s = f"{e['orgc']:,} according to organisers"
        if e.get("off"):
            s += f", {e['off']:,} official"
        return s
    if e.get("off"):
        return f"{e['off']:,} official count"
    return "Turnout not reported"


def reasons(x):
    return x.get("reasons") or [THEMES.get(t, t) for t in x.get("themes") or []]


def description(x):
    s = (x.get("summary") or "").strip()
    if len(s) > 200:
        s = s[:197].rsplit(" ", 1)[0] + "…"
    return s or "Checked daily by Protest Atlas."


def card_html(title, kicker, lines, next_line):
    rows = "".join(f"<p>{E(l)}</p>" for l in lines if l)
    nxt = f'<p class="next">{E(next_line)}</p>' if next_line else ""
    return f"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Jost:wght@400;700&display=block" rel="stylesheet"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:1200px;height:630px;background:#FCFAF6;color:#1F2A33;font-family:Futura,"Jost","Avenir Next",sans-serif;padding:64px 72px;position:relative;overflow:hidden}}
.brand{{font-size:26px;font-weight:700;text-transform:uppercase;letter-spacing:.02em}}
.kick{{margin-top:54px;font-size:28px;color:#5B6770}}
h1{{font-size:{110 if len(title) < 12 else 84}px;line-height:.95;font-weight:700;text-transform:uppercase;letter-spacing:-.01em;margin-top:10px}}
.lines{{margin-top:26px;font-size:30px;line-height:1.35;color:#3A4650;max-width:1000px}}
.lines p{{overflow:hidden;white-space:nowrap;text-overflow:ellipsis}}
.next{{color:#E85D24;font-weight:700}}
.bar{{position:absolute;left:0;right:0;bottom:0;height:18px;background:#1F2A33}}
</style></head><body><div class="brand">Protest Atlas</div><div class="kick">{E(kicker)}</div>
<h1>{E(title)}</h1><div class="lines">{rows}{nxt}</div><div class="bar"></div></body></html>"""


def shoot(html_text, out_png):
    """Render 1200x630 HTML to PNG with headless Chrome. Returns True on success."""
    if not CHROME:
        return False
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "card.html")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write(html_text)
        r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                            "--window-size=1200,630", "--virtual-time-budget=5000", "--no-sandbox",
                            f"--screenshot={out_png}", "file://" + src],
                           capture_output=True, text=True, timeout=60)
        return r.returncode == 0 and os.path.exists(out_png)


DEMAND = {"policy": "Policy change", "programme": "Change of programme", "resignation": "Resignation"}
RESP = {"none": "No response yet", "talks": "Talks offered", "crisis": "Government crisis"}
PAGE_CSS = """*{box-sizing:border-box;margin:0;padding:0}
body{background:#FCFAF6;color:#1F2A33;font:400 17px/1.6 Jost,Futura,"Avenir Next",sans-serif}
a{color:inherit;text-underline-offset:3px}
.wrap{max-width:780px;margin:0 auto;padding:0 20px}
header{border-bottom:1px solid #DDD7CB}header .wrap{display:flex;justify-content:space-between;align-items:center;height:60px;max-width:1240px}
.logo{font-weight:800;text-transform:uppercase;text-decoration:none}
h1{font:800 clamp(48px,9vw,84px)/.9 Jost,Futura,sans-serif;text-transform:uppercase;margin:40px 0 10px}
.checked{font-size:14px;color:#5B6770;margin-bottom:16px}
.lede{font-size:19px;color:#3A4650;margin-bottom:12px}
p{margin-bottom:10px;color:#3A4650}
h2{font:700 22px/1.2 Jost,Futura,sans-serif;text-transform:uppercase;border-top:3px solid #1F2A33;padding-top:12px;margin:34px 0 12px}
.next b{color:#18695F}
.day{border-bottom:1px solid #DDD7CB;padding:12px 0}.day:last-child{border:0}
.day h3{font-size:17px;font-weight:600}
.meta{font-size:14px;color:#5B6770}
.srcs{font-size:13px;color:#5B6770}
dl{display:grid;grid-template-columns:120px 1fr;gap:6px 14px}dt{color:#5B6770}
.cta{display:inline-block;margin:28px 0 8px;font-weight:700;border-bottom:3px solid #1F2A33;text-decoration:none}
footer{border-top:1px solid #DDD7CB;margin-top:50px;padding:18px 0 40px;font-size:14px;color:#5B6770}"""


def src_line(src):
    if not src:
        return ""
    return '<p class="srcs">Sources: ' + ", ".join(f'<a href="{E(u)}" rel="noopener">{E(t)}</a>' for t, u in src) + "</p>"


# French names and the right preposition ("en France", "au Portugal", "aux Pays-Bas", "à Chypre")
FR_IN = {"AL": "en Albanie", "AT": "en Autriche", "BA": "en Bosnie-Herzégovine", "BE": "en Belgique", "BG": "en Bulgarie",
         "CH": "en Suisse", "CY": "à Chypre", "CZ": "en Tchéquie", "DE": "en Allemagne", "DK": "au Danemark",
         "EE": "en Estonie", "ES": "en Espagne", "FI": "en Finlande", "FR": "en France", "GB": "au Royaume-Uni",
         "GR": "en Grèce", "HR": "en Croatie", "HU": "en Hongrie", "IE": "en Irlande", "IS": "en Islande",
         "IT": "en Italie", "LT": "en Lituanie", "LV": "en Lettonie", "MD": "en Moldavie", "ME": "au Monténégro",
         "MK": "en Macédoine du Nord", "NL": "aux Pays-Bas", "NO": "en Norvège", "PL": "en Pologne", "PT": "au Portugal",
         "RO": "en Roumanie", "RS": "en Serbie", "SE": "en Suède", "SI": "en Slovénie", "SK": "en Slovaquie",
         "TR": "en Turquie", "UA": "en Ukraine", "XK": "au Kosovo"}
FR_NAME = {"AL": "Albanie", "AT": "Autriche", "BA": "Bosnie-Herzégovine", "BE": "Belgique", "BG": "Bulgarie", "CH": "Suisse",
           "CY": "Chypre", "CZ": "Tchéquie", "DE": "Allemagne", "DK": "Danemark", "EE": "Estonie", "ES": "Espagne",
           "FI": "Finlande", "FR": "France", "GB": "Royaume-Uni", "GR": "Grèce", "HR": "Croatie", "HU": "Hongrie",
           "IE": "Irlande", "IS": "Islande", "IT": "Italie", "LT": "Lituanie", "LV": "Lettonie", "MD": "Moldavie",
           "ME": "Monténégro", "MK": "Macédoine du Nord", "NL": "Pays-Bas", "NO": "Norvège", "PL": "Pologne",
           "PT": "Portugal", "RO": "Roumanie", "RS": "Serbie", "SE": "Suède", "SI": "Slovénie", "SK": "Slovaquie",
           "TR": "Turquie", "UA": "Ukraine", "XK": "Kosovo"}
EN_THE = {"GB", "NL"}                          # "in the United Kingdom", "in the Netherlands"
FR_DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
FR_MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
DEMAND_FR = {"policy": "Changement de politique", "programme": "Changement de programme", "resignation": "Démission"}
RESP_FR = {"none": "Pas encore de réponse", "talks": "Dialogue proposé", "crisis": "Crise gouvernementale"}
FRAG_FR = {"stable": "Stable", "strained": "Sous tension", "fragile": "Fragile"}


def long_date_fr(iso):
    d = datetime.fromisoformat(iso[:10])
    return f"{FR_DAYS[d.weekday()]} {d.day} {FR_MONTHS[d.month - 1]}"


def nfr(n):                                    # 500 000 (French thousands separator)
    return f"{n:,}".replace(",", " ")


def page_urls(code, base):
    en = f"{base}/c/{code.lower()}/" if base else f"c/{code.lower()}/"
    fr = f"{base}/fr/c/{code.lower()}/" if base else f"fr/c/{code.lower()}/"
    return en, fr


def share_page(code, x, site, lang="en"):
    """A full, readable page per country, in English (/c/xx/) or French (/fr/c/xx/), linked to each other."""
    fr = lang == "fr"
    base = site.rstrip("/") if site else ""
    en_url, fr_url = page_urls(code, base)
    url = fr_url if fr else en_url
    root = "../../../" if fr else "../../"
    img = f"{base}/c/{code.lower()}/card.png" if base else "card.png"
    name = FR_NAME.get(code, x["country"]) if fr else x["country"]
    where = FR_IN.get(code, "en " + name) if fr else ("in the " if code in EN_THE else "in ") + x["country"]
    D = long_date_fr if fr else long_date
    N = nfr if fr else (lambda n: f"{n:,}")
    ev = sorted(x.get("events") or [], key=lambda e: e["date"], reverse=True)
    last = ev[0] if ev else None
    if fr:
        title = f"Manifestations {where} : qui manifeste et pourquoi | Protest Atlas"
        crowd = ""
        if last:
            n = max(last.get("orgc") or 0, last.get("off") or 0)
            crowd = f", {nfr(n)} personnes" if n else ""
        desc = (f"Manifestations et grèves {where}, mises à jour chaque jour : "
                + (f"dernière mobilisation le {long_date_fr(last['date'])}{crowd}. " if last else "aucune mobilisation nationale récente. ")
                + "Qui manifeste, pourquoi, et les prochaines dates.")
        T = dict(kicker="Manifestations", checked="Dernière vérification le {d} à {h}.", none="Aucune mobilisation nationale trouvée dans nos sources sur les 30 derniers jours.",
                 why="Pourquoi ils manifestent :", nowhy="pas de revendication claire signalée pour l'instant.", next="Prochaine mobilisation, {d}.",
                 who="Qui manifeste, et ce qu'ils demandent", pressure="Pression sur le gouvernement", days="Journées de mobilisation",
                 demand="Revendication", response="Réponse", gov="Gouvernement", police="Maintien de l'ordre", heavy="Dur",
                 off="officiel", org="organisateurs", arr="interpellations", noturn="Participation non communiquée", src="Sources :",
                 cta=f"Voir {name} sur l'atlas", all="Tous les pays", other="English", foot="Protest Atlas est un projet indépendant.",
                 about="À propos", corr="Signaler une erreur", note="Les résumés et titres viennent de nos sources et restent en anglais pour l'instant.")
    else:
        title = f"Protests {where}: who is marching and why | Protest Atlas"
        desc = description(x)
        T = dict(kicker="Protests in", checked="Last checked {d} at {h}.", none="No national protest found in our sources for the last 30 days.",
                 why="Why they protest:", nowhy="no clear demands reported so far.", next="Next protest, {d}.",
                 who="Who is protesting, and what they want", pressure="Pressure on government", days="Protest days",
                 demand="Demand", response="Response", gov="Government", police="Policing", heavy="Heavy",
                 off="official", org="organisers", arr="arrests", noturn="Turnout not reported", src="Sources:",
                 cta=f"See {x['country']} on the live atlas", all="All countries", other="Français", foot="Protest Atlas is an independent project.",
                 about="About", corr="Send a correction", note="")
    src = lambda s_: ('<p class="srcs">' + T["src"] + " " + ", ".join(f'<a href="{E(u)}" rel="noopener">{E(t)}</a>' for t, u in s_) + "</p>") if s_ else ""
    body = []
    if x.get("checkedAt"):
        body.append(f'<p class="checked">{E(T["checked"].format(d=D(x["checkedAt"]), h=x["checkedAt"][11:16]))}</p>')
    body.append(f'<p class="lede">{E(x.get("summary") or T["none"])}</p>')
    if T["note"] and x.get("summary"):
        body.append(f'<p class="checked">{E(T["note"])}</p>')
    if x.get("tier") == "watch":
        r = reasons(x)
        body.append(f'<p><b>{T["why"]}</b> {E("; ".join(r)) + "." if r else T["nowhy"]}</p>')
    if x.get("nextDate") and x.get("next"):
        body.append(f'<p class="next"><b>{E(T["next"].format(d=D(x["nextDate"])))}</b> {E(x["next"])}</p>')
    groups = x.get("groups") or []
    if groups:
        body.append(f"<h2>{T['who']}</h2>")
        for g in groups:
            body.append(f'<p><b>{E(g.get("name",""))}</b> <span class="meta">{E(g.get("since",""))}</span><br>{E(" · ".join(g.get("items") or []))}</p>')
    p = x.get("pressure")
    if p:
        dm, rs = (DEMAND_FR, RESP_FR) if fr else (DEMAND, RESP)
        rows = [(T["demand"], dm.get(p.get("demand"), ""), p.get("demandNote")),
                (T["response"], rs.get(p.get("response"), ""), p.get("responseNote"))]
        if p.get("fragility"):
            rows.append((T["gov"], FRAG_FR.get(p["fragility"], p["fragility"]) if fr else p["fragility"].capitalize(), p.get("fragilityNote")))
        if p.get("crackdown"):
            rows.append((T["police"], T["heavy"], p.get("crackdownNote")))
        body.append(f"<h2>{T['pressure']}</h2><dl>" + "".join(
            f"<dt>{k}</dt><dd><b>{E(v)}</b>{'. ' + E(n[0].upper() + n[1:]) if n else ''}</dd>" for k, v, n in rows if v) + "</dl>" + src(p.get("src")))
    if ev:
        body.append(f"<h2>{T['days']}</h2>")
        for e in ev:
            figs = [f"{N(n)} {l}" for n, l in ((e.get("off"), T["off"]), (e.get("orgc"), T["org"]), (e.get("arrests"), T["arr"])) if n is not None]
            body.append(f'<div class="day"><h3>{E(e["title"])}</h3><p class="meta">{E(D(e["date"]))}. {E(" · ".join(figs) if figs else T["noturn"])}</p>'
                        + (f'<p>{E(e["extra"])}</p>' if e.get("extra") else "") + src(e.get("src")) + "</div>")
    live = f"{root}{'?lang=fr' if fr else ''}#{code}"
    body.append(f'<p><a class="cta" href="{live}">{E(T["cta"])}</a></p>')
    home = (base or "") + "/"
    ld = json.dumps({"@context": "https://schema.org", "@type": "WebPage", "url": url, "name": title, "description": desc,
                     "inLanguage": lang, "dateModified": (x.get("checkedAt") or "")[:10] or None,
                     "isPartOf": {"@type": "WebSite", "name": "Protest Atlas", "url": home},
                     "about": {"@type": "Country", "name": name},
                     "breadcrumb": {"@type": "BreadcrumbList", "itemListElement": [
                         {"@type": "ListItem", "position": 1, "name": "Protest Atlas", "item": home + ("?lang=fr" if fr else "")},
                         {"@type": "ListItem", "position": 2, "name": name, "item": url}]}},
                    ensure_ascii=False).replace("</", "<\\/")
    other = en_url if fr else fr_url
    kicker = "Manifestations " + where if fr else "Protests " + where
    return f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(desc)}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Protest Atlas">
<meta property="og:locale" content="{'fr_FR' if fr else 'en_GB'}">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="{E(url)}">
<meta property="og:image" content="{E(img)}">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="canonical" href="{E(url)}">
<link rel="alternate" hreflang="en" href="{E(en_url)}">
<link rel="alternate" hreflang="fr" href="{E(fr_url)}">
<link rel="alternate" hreflang="x-default" href="{E(en_url)}">
<meta name="robots" content="index,follow,max-image-preview:large">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="/icons/icon-32.png">
<link rel="apple-touch-icon" href="/icons/apple-touch-icon.png">
<script type="application/ld+json">{ld}</script>
<link rel="stylesheet" href="{root}fonts/fonts.css">
<script data-goatcounter="https://protestatlas.goatcounter.com/count" async src="https://gc.zgo.at/count.js"></script>
<style>{PAGE_CSS}
h1 small{{display:block;font:600 18px/1.2 Jost,Futura,sans-serif;text-transform:none;color:#5B6770;margin-bottom:10px}}
header nav{{display:flex;gap:18px;font-size:15px}}</style>
</head><body>
<header><div class="wrap"><a class="logo" href="{root}{'?lang=fr' if fr else ''}">Protest Atlas</a><nav><a href="{root}{'?lang=fr' if fr else ''}#countries">{T['all']}</a><a href="{E(other)}" hreflang="{'en' if fr else 'fr'}" lang="{'en' if fr else 'fr'}">{T['other']}</a></nav></div></header>
<main class="wrap"><h1><small>{E(kicker)}</small>{E(name)}</h1>
{chr(10).join(body)}
</main>
<footer><div class="wrap">{T['foot']} <a href="{root}about.html{'?lang=fr' if fr else ''}">{T['about']}</a> · <a href="{root}about.html{'?lang=fr' if fr else ''}#corrections{'-fr' if fr else ''}">{T['corr']}</a></div></footer>
</body></html>
"""


def feed(data, site):
    base = site.rstrip("/") if site else ""
    items = []
    for code, x in data.items():
        if x.get("tier") != "watch":
            continue
        link = f"{base}/c/{code.lower()}/" if base else f"c/{code.lower()}/"
        e = latest_event(x)
        if e:
            items.append((e["date"], f"{code}-{e['date']}-protest",
                          f"{x['country']}: {e['title']}",
                          f"{long_date(e['date'])}. {turnout(e)}. Why: {', '.join(reasons(x)) or 'no clear demands reported'}.",
                          link))
        if x.get("nextDate"):
            # Dated when we learned of it (last update), never in the future: email services
            # hold back or skip future-dated items.
            known = (x.get("updatedAt") or x.get("checkedAt") or x["nextDate"])[:10]
            items.append((min(known, x["nextDate"]), f"{code}-{x['nextDate']}-next",
                          f"{x['country']}: next protest {long_date(x['nextDate'])}",
                          x.get("next") or "", link))
    items.sort(key=lambda i: i[0], reverse=True)
    now = format_datetime(datetime.now(timezone.utc))
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<rss version="2.0"><channel>',
           "<title>Protest Atlas</title>", f"<link>{E(base or '.')}/</link>",
           "<description>National protests and strikes across Europe, checked daily.</description>",
           f"<lastBuildDate>{now}</lastBuildDate>"]
    for d, guid, title, desc, link in items[:60]:
        pub = format_datetime(datetime.fromisoformat(d + "T09:00:00+00:00"))
        out.append(f"<item><title>{E(title)}</title><link>{E(link)}</link><guid isPermaLink=\"false\">{E(guid)}</guid>"
                   f"<pubDate>{pub}</pubDate><description>{E(desc)}</description></item>")
    out.append("</channel></rss>")
    return "\n".join(out) + "\n"


def home_static(data, path="index.html"):
    """Write plain-text, linked content into the home page (between <!--static:...--> markers), so search engines
    can read the countries and figures without running JavaScript. The live page replaces it as soon as it loads."""
    if not os.path.exists(path):
        return
    ref = max((x.get("checkedAt") or "")[:10] for x in data.values())
    R = datetime.fromisoformat(ref)
    age = lambda d: (R - datetime.fromisoformat(d[:10])).days
    size = lambda e: max(e.get("orgc") or 0, e.get("off") or 0)
    watch = [c for c, x in data.items() if x.get("tier") == "watch"]
    recent = {c: [e for e in data[c].get("events") or [] if 0 <= age(e["date"]) < 30] for c in watch}
    watch.sort(key=lambda c: max([e["date"] for e in data[c].get("events") or []] or [""]), reverse=True)   # most recent first...
    watch.sort(key=lambda c: -len(recent[c]))                                                             # ...then most active first
    week = [data[c]["country"] for c in watch if any(0 <= age(e["date"]) < 7 for e in recent[c])]
    peak = max(((size(e), c, e) for c in watch for e in recent[c] if size(e)), default=None, key=lambda t: t[0])
    start = R - timedelta(days=6)
    line = f"<b>This week ({start.day} {start.strftime('%b')} to {R.day} {R.strftime('%b')}):</b> "
    line += ("protest days in " + ", ".join(E(n) for n in week) + "." if week else "no national protest day.")
    if peak:
        n, c, e = peak
        line += f" Largest crowd in the last 30 days: {E(data[c]['country'])}, {n:,} people ({E(long_date(e['date']))})."
    tiles = []
    for c in watch:
        x = data[c]; ev = sorted(x.get("events") or [], key=lambda e: e["date"], reverse=True)
        k = len(recent[c]); last = ev[0] if ev else None
        tiles.append(f'<article class="cty" data-c="{c}"><span class="r"><h3><a href="c/{c.lower()}/">Protests in {"the " if c in EN_THE else ""}{E(x["country"])}</a></h3></span>'
                     f'<p class="lastline"><b>{k} protest day{"s" if k != 1 else ""} in 30 days.</b>'
                     + (f' Latest, {E(long_date(last["date"]))}: {E(last["title"])}.' if last else "")
                     + (f' Why: {E(", ".join(reasons(x)[:3]))}.' if reasons(x) else "") + "</p></article>")
    quiet = sorted(c for c, x in data.items() if x.get("tier") != "watch")
    quiet_html = '<small class="k">Screened, no national protest</small><div>' + " ".join(
        f'<a href="c/{c.lower()}/">{E(data[c]["country"])}</a>' for c in quiet) + "</div>"
    with open(path, encoding="utf-8") as fh:
        s = fh.read()
    import re as _re
    for key, val in (("week", line), ("tiles", "".join(tiles)), ("quiet", quiet_html)):
        s = _re.sub(rf"<!--static:{key}-->.*?<!--/static:{key}-->", lambda m: f"<!--static:{key}-->{val}<!--/static:{key}-->", s, flags=_re.S)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default=os.environ.get("PROTEST_ATLAS_SITE", ""),
                    help="public address of the site, e.g. https://example.github.io/protest-atlas")
    ap.add_argument("--data", default="data/briefings.json")
    ap.add_argument("--no-images", action="store_true")
    a = ap.parse_args()
    with open(a.data, encoding="utf-8") as fh:
        data = json.load(fh)

    # remove pages of countries no longer in the data, keep the others (and their pictures)
    if os.path.isdir("c"):
        for d in os.listdir("c"):
            if d.upper() not in data and os.path.isdir(os.path.join("c", d)):
                shutil.rmtree(os.path.join("c", d))
    if os.path.isdir(os.path.join("fr", "c")):
        for d in os.listdir(os.path.join("fr", "c")):
            if d.upper() not in data and os.path.isdir(os.path.join("fr", "c", d)):
                shutil.rmtree(os.path.join("fr", "c", d))
    images = not a.no_images and bool(CHROME)
    made = 0
    for code, x in data.items():
        folder = os.path.join("c", code.lower())
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "index.html"), "w", encoding="utf-8") as fh:
            fh.write(share_page(code, x, a.site))
        frf = os.path.join("fr", "c", code.lower())
        os.makedirs(frf, exist_ok=True)
        with open(os.path.join(frf, "index.html"), "w", encoding="utf-8") as fh:
            fh.write(share_page(code, x, a.site, "fr"))
        if images:
            e = latest_event(x)
            if x.get("tier") == "watch":
                kicker = f"Latest protest, {long_date(e['date'])}" if e else "On watch"
                lines = [e["title"] if e else "", turnout(e) if e else "",
                         ("Why: " + ", ".join(reasons(x))) if reasons(x) else ""]
            else:
                kicker, lines = "Checked daily", ["No national protest reported recently."]
            nxt = f"Next protest: {long_date(x['nextDate'])}" if x.get("nextDate") else ""
            made += shoot(card_html(x["country"], kicker, lines, nxt), os.path.join(folder, "card.png"))
    if images:
        watched = sum(1 for x in data.values() if x.get("tier") == "watch")
        shoot(card_html("Who's on the street", "Europe, checked every morning",
                        [f"{watched} countries on watch", "Who is marching, why, how many, and what comes next."], ""),
              "card.png")
    with open("feed.xml", "w", encoding="utf-8") as fh:
        fh.write(feed(data, a.site))
    home_static(data)
    base = a.site.rstrip("/")
    with open("robots.txt", "w", encoding="utf-8") as fh:
        fh.write("User-agent: *\nAllow: /\n" + (f"Sitemap: {base}/sitemap.xml\n" if base else ""))
    if base:
        today = datetime.now(timezone.utc).date().isoformat()
        latest = max((x.get("checkedAt") or "")[:10] for x in data.values()) or today
        rows = []
        for path in ("/", "/about.html", "/rss.html"):          # main pages, each with its French version
            en, fr = f"{base}{path}", f"{base}{path}?lang=fr"
            alt = (f'<xhtml:link rel="alternate" hreflang="en" href="{E(en)}"/>'
                   f'<xhtml:link rel="alternate" hreflang="fr" href="{E(fr)}"/>'
                   f'<xhtml:link rel="alternate" hreflang="x-default" href="{E(en)}"/>')
            for u in (en, fr):
                rows.append(f"<url><loc>{E(u)}</loc>{alt}<lastmod>{latest}</lastmod></url>")
        for c in sorted(data):                                   # country pages in both languages, dated by their last check
            d = (data[c].get("checkedAt") or "")[:10] or latest
            en, fr = page_urls(c, base)
            alt = (f'<xhtml:link rel="alternate" hreflang="en" href="{E(en)}"/>'
                   f'<xhtml:link rel="alternate" hreflang="fr" href="{E(fr)}"/>'
                   f'<xhtml:link rel="alternate" hreflang="x-default" href="{E(en)}"/>')
            for u in (en, fr):
                rows.append(f"<url><loc>{E(u)}</loc>{alt}<lastmod>{d}</lastmod></url>")
        with open("sitemap.xml", "w", encoding="utf-8") as fh:
            fh.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
                     'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n' + "\n".join(rows) + "\n</urlset>\n")

    print(f"Built {len(data)} country pages in c/, feed.xml"
          + (f", {made} preview pictures" if images else ", no pictures (Chrome not found or --no-images)"))
    if not a.site:
        print("Note: no --site given. Link previews need the site's full public address; "
              "rebuild with --site https://... once the site is online.", file=sys.stderr)


if __name__ == "__main__":
    main()
